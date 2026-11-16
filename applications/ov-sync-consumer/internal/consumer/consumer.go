// Package consumer reads filer events from JetStream and makes OpenViking
// match the bucket.
//
// The webhook delivers out of order, so an event only says "look at this
// file now": the consumer reads the object's current state and writes or
// deletes the file to match, whatever the event type was.
package consumer

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"github.com/minio/minio-go/v7"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
	"golang.org/x/time/rate"

	"github.com/JasperHG90/localstack/applications/ov-sync-consumer/internal/stream"
)

const (
	durable     = "ov-sync-consumer"
	errorHeader = "Ov-Sync-Error"
)

type Consumer struct {
	S3     *minio.Client
	Bucket string
	OV     *OpenViking
	Map    Mapping
	// Pool is how many events are handled at once. OV.MaxInFlight, set to
	// the same number, bounds OpenViking requests in flight.
	Pool int
	// Limit paces events. Each OpenViking write regenerates folder summaries
	// with a VLM call, so this is what bounds that cost.
	Limit *rate.Limiter
	// MaxTries is how many deliveries an event gets before it moves to the
	// dead-letter subject.
	MaxTries int
	Backoff  func(delivered uint64) time.Duration
	AckWait  time.Duration
	Log      *slog.Logger

	// A recursive folder delete takes the lock alone, so no write can land
	// in a folder between the check that it is empty and its deletion.
	tree sync.RWMutex
	// keys orders work on one OpenViking file, so a worker that read the
	// object earlier cannot write after one that read it later. A key is
	// always taken before tree and never while holding it, and nobody holds
	// two keys, so a folder delete cannot wait on a key held by a worker that
	// is waiting on the folder delete.
	keys keyLocks
}

// keyLocks is a mutex per key. An entry lives only while someone holds or
// waits on it, so the map stays as small as the work in flight.
type keyLocks struct {
	mu sync.Mutex
	m  map[string]*keyLock
}

type keyLock struct {
	mu    sync.Mutex
	users int
}

func (k *keyLocks) lock(key string) (unlock func()) {
	k.mu.Lock()
	if k.m == nil {
		k.m = map[string]*keyLock{}
	}
	l := k.m[key]
	if l == nil {
		l = &keyLock{}
		k.m[key] = l
	}
	l.users++
	k.mu.Unlock()

	l.mu.Lock()
	return func() {
		l.mu.Unlock()
		k.mu.Lock()
		if l.users--; l.users == 0 {
			delete(k.m, key)
		}
		k.mu.Unlock()
	}
}

// Backoff doubles from base per delivery, up to max.
func Backoff(base, max time.Duration) func(uint64) time.Duration {
	return func(delivered uint64) time.Duration {
		d := base
		for i := uint64(1); i < delivered && d < max; i++ {
			d *= 2
		}
		return min(d, max)
	}
}

// Run handles events until ctx ends, Pool at a time.
func (c *Consumer) Run(ctx context.Context, js jetstream.JetStream) error {
	s, err := stream.Ensure(ctx, js)
	if err != nil {
		return fmt.Errorf("stream: %w", err)
	}
	cons, err := s.CreateOrUpdateConsumer(ctx, jetstream.ConsumerConfig{
		Durable:       durable,
		FilterSubject: stream.EventsSubject,
		AckPolicy:     jetstream.AckExplicitPolicy,
		AckWait:       c.AckWait,
		MaxDeliver:    c.MaxTries,
		MaxAckPending: c.Pool * 4,
	})
	if err != nil {
		return fmt.Errorf("consumer: %w", err)
	}
	var wg sync.WaitGroup
	for range c.Pool {
		wg.Go(func() { c.work(ctx, js, cons) })
	}
	wg.Wait()
	return nil
}

func (c *Consumer) work(ctx context.Context, js jetstream.JetStream, cons jetstream.Consumer) {
	for ctx.Err() == nil {
		wait, cancel := context.WithTimeout(ctx, 5*time.Second)
		batch, err := cons.Fetch(1, jetstream.FetchContext(wait))
		if err != nil {
			cancel()
			if ctx.Err() == nil {
				c.Log.Warn("fetch failed", "err", err)
				time.Sleep(time.Second)
			}
			continue
		}
		for m := range batch.Messages() {
			c.handle(ctx, js, m)
		}
		cancel()
	}
}

func (c *Consumer) handle(ctx context.Context, js jetstream.JetStream, m jetstream.Msg) {
	err := c.HandleEvent(ctx, m.Data())
	if err == nil {
		if err := m.DoubleAck(ctx); err != nil {
			c.Log.Warn("ack failed", "err", err)
		}
		return
	}
	var delivered uint64
	if md, mdErr := m.Metadata(); mdErr == nil {
		delivered = md.NumDelivered
	}
	if errors.Is(err, errBadEvent) || delivered >= uint64(c.MaxTries) {
		c.Log.Error("dead-lettering event", "delivered", delivered, "err", err)
		c.deadLetter(ctx, js, m, err)
		_ = m.Term()
		return
	}
	if errors.Is(err, errLockBusy) {
		c.Log.Info("folder busy, retrying later", "delivered", delivered, "err", err)
	} else {
		c.Log.Warn("event failed, retrying", "delivered", delivered, "err", err)
	}
	_ = m.NakWithDelay(c.Backoff(delivered))
}

// deadLetter copies the event to the dead-letter subject. It does not copy
// the Msg-Id: the stream would drop the copy as a duplicate of the original.
func (c *Consumer) deadLetter(ctx context.Context, js jetstream.JetStream, m jetstream.Msg, cause error) {
	msg := nats.NewMsg(stream.DeadSubject)
	msg.Data = m.Data()
	msg.Header.Set(errorHeader, cause.Error())
	if _, err := js.PublishMsg(ctx, msg); err != nil {
		// The catch-up pass still repairs the file; only the record is lost.
		c.Log.Error("dead-letter publish failed", "err", err)
	}
}

var errBadEvent = errors.New("bad event")

type event struct {
	Key     string `json:"key"`
	Message struct {
		NewEntry *struct {
			IsDirectory bool `json:"is_directory"`
		} `json:"new_entry"`
		OldEntry *struct {
			IsDirectory bool `json:"is_directory"`
		} `json:"old_entry"`
	} `json:"message"`
}

// HandleEvent applies one filer webhook event. Folder events are skipped: a
// folder in OpenViking follows from the files in it.
func (c *Consumer) HandleEvent(ctx context.Context, data []byte) error {
	var ev event
	if err := json.Unmarshal(data, &ev); err != nil {
		return fmt.Errorf("%w: %v", errBadEvent, err)
	}
	key, ok := strings.CutPrefix(ev.Key, "/buckets/"+c.Bucket+"/")
	if !ok {
		return nil
	}
	if (ev.Message.NewEntry != nil && ev.Message.NewEntry.IsDirectory) ||
		(ev.Message.OldEntry != nil && ev.Message.OldEntry.IsDirectory) {
		return nil
	}
	return c.Apply(ctx, key)
}

// Apply makes OpenViking match the object's current state: an object that
// exists is written, a missing one is deleted. It holds the file's key from
// before the read until OpenViking has the result. An image is uploaded, and
// any other object that is not valid UTF-8 is skipped, since a JSON write
// would damage it.
func (c *Consumer) Apply(ctx context.Context, key string) error {
	uri, root, ok := c.Map.Resolve(key)
	if !ok {
		return nil
	}
	defer c.keys.lock(uri)()
	if err := c.Limit.Wait(ctx); err != nil {
		return err
	}
	body, err := c.read(ctx, key)
	if isNoSuchKey(err) {
		return c.remove(ctx, uri, root)
	}
	if err != nil {
		return fmt.Errorf("read %s: %w", key, err)
	}
	if !isImage(key) && !utf8.Valid(body) {
		c.Log.Info("binary file skipped", "key", key)
		return nil
	}
	c.tree.RLock()
	defer c.tree.RUnlock()
	if isImage(key) {
		return c.upload(ctx, uri, body)
	}
	if err := c.OV.Write(ctx, uri, string(body)); err != nil {
		return fmt.Errorf("write %s: %w", uri, err)
	}
	return nil
}

// upload stores an image at uri, D/name/name, by adding it as a resource
// into D/name. A plain file at D/name, the damaged copy an earlier text write
// left, goes first. Only a plain file: a non-recursive delete of an image
// folder is refused with 412 (spike:ov-sync-consumer-binary-upload/8).
func (c *Consumer) upload(ctx context.Context, uri string, body []byte) error {
	folder := parent(uri)
	siblings, _, err := c.OV.List(ctx, parent(folder))
	if err != nil {
		return err
	}
	for _, e := range siblings {
		if e.URI == folder && !e.IsDir {
			if err := c.OV.Delete(ctx, folder, false); err != nil {
				return fmt.Errorf("delete old copy %s: %w", folder, err)
			}
		}
	}
	if err := c.OV.Upload(ctx, folder, base(uri), body); err != nil {
		return fmt.Errorf("upload %s: %w", uri, err)
	}
	return nil
}

func (c *Consumer) read(ctx context.Context, key string) ([]byte, error) {
	obj, err := c.S3.GetObject(ctx, c.Bucket, key, minio.GetObjectOptions{})
	if err != nil {
		return nil, err
	}
	defer func() { _ = obj.Close() }()
	return io.ReadAll(obj)
}

func isNoSuchKey(err error) bool {
	return err != nil && minio.ToErrorResponse(err).Code == minio.NoSuchKey
}

// remove deletes the file at uri, then every folder above it, up to the
// mapped root, that the delete left holding only OpenViking's own summaries.
func (c *Consumer) remove(ctx context.Context, uri, root string) error {
	c.tree.RLock()
	err := c.OV.Delete(ctx, uri, false)
	c.tree.RUnlock()
	if err != nil {
		return fmt.Errorf("delete %s: %w", uri, err)
	}
	c.tree.Lock()
	defer c.tree.Unlock()
	top := strings.TrimSuffix(root, "/")
	for dir := parent(uri); strings.HasPrefix(dir, top+"/"); dir = parent(dir) {
		removed, err := c.removeIfEmpty(ctx, dir, dir == parent(uri) && isImageHome(uri))
		if err != nil {
			return fmt.Errorf("%w: %w", errFolderLeft, err)
		}
		if !removed {
			return nil
		}
	}
	return nil
}

// parent is the folder above uri. Not path.Dir, which would fold the `//`
// in `viking://`.
func parent(uri string) string {
	return uri[:max(strings.LastIndex(uri, "/"), 0)]
}

func base(uri string) string {
	return uri[strings.LastIndex(uri, "/")+1:]
}

func isSummary(dir, uri string) bool {
	return uri == dir+"/.abstract.md" || uri == dir+"/.overview.md"
}

// removeIfEmpty deletes dir with recursive=true only when ls shows nothing in
// it but `.abstract.md` and `.overview.md`, and checks the result by listing
// the parent. removed is true when dir is gone.
//
// An image's folder stays listed in its parent for good once deleted, as an
// empty folder (spike:ov-sync-consumer-binary-upload/6), so for image it
// counts as gone when its own ls is empty.
func (c *Consumer) removeIfEmpty(ctx context.Context, dir string, image bool) (removed bool, err error) {
	entries, found, err := c.OV.List(ctx, dir)
	if err != nil || !found {
		return !found, err
	}
	for _, e := range entries {
		if !isSummary(dir, e.URI) {
			return false, nil
		}
	}
	if err := c.OV.Delete(ctx, dir, true); err != nil {
		return false, fmt.Errorf("delete folder %s: %w", dir, err)
	}
	if image {
		left, _, err := c.OV.List(ctx, dir)
		if err != nil {
			return false, err
		}
		if len(left) > 0 {
			return false, fmt.Errorf("image folder %s not empty after its delete", dir)
		}
		return true, nil
	}
	siblings, _, err := c.OV.List(ctx, parent(dir))
	if err != nil {
		return false, err
	}
	for _, e := range siblings {
		if e.URI == dir {
			return false, fmt.Errorf("folder %s still listed after its delete", dir)
		}
	}
	return true, nil
}
