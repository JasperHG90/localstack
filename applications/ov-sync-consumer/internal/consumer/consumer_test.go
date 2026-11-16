package consumer

import (
	"context"
	"fmt"
	"math/rand/v2"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/nats-io/nats.go/jetstream"

	"github.com/JasperHG90/localstack/applications/ov-sync-consumer/internal/natstest"
	"github.com/JasperHG90/localstack/applications/ov-sync-consumer/internal/stream"
)

func TestConsumerAppliesCurrentState(t *testing.T) {
	ctx := context.Background()
	const back = "JasperHG90/localstack/docs/back.md"
	const gone = "JasperHG90/localstack/docs/gone.md"
	_, s3 := newFakeS3(t, map[string]string{back: "# back again\n"})
	ov, client := newFakeOV(t)
	ov.seed(projRoot+"/docs/back.md", projRoot+"/docs/gone.md")
	c := newConsumer(s3, client)

	// A delete event for an object that exists again: write, never delete.
	if err := c.HandleEvent(ctx, eventJSON("delete", back)); err != nil {
		t.Fatal(err)
	}
	if n := len(ov.calls(http.MethodDelete, "/api/v1/fs")); n != 0 {
		t.Fatalf("delete event for an existing object sent %d deletes", n)
	}
	writes := ov.calls(http.MethodPost, "/api/v1/content/write")
	if len(writes) != 1 || writes[0].Body["uri"] != projRoot+"/docs/back.md" ||
		writes[0].Body["content"] != "# back again\n" || writes[0].Body["wait"] != true {
		t.Fatalf("want one content/write of back.md with wait true, got %+v", writes)
	}

	// A create event for an object that is gone: delete, never write.
	if err := c.HandleEvent(ctx, eventJSON("create", gone)); err != nil {
		t.Fatal(err)
	}
	if n := ov.writesTo(projRoot + "/docs/gone.md"); n != 0 {
		t.Fatalf("create event for a gone object sent %d writes", n)
	}
	if ov.has(projRoot + "/docs/gone.md") {
		t.Fatal("gone.md is still in OpenViking")
	}

	if n := len(ov.calls(http.MethodPost, "/api/v1/content/batch-write")); n != 0 {
		t.Fatalf("batch-write used %d times", n)
	}
}

func TestConsumerMapsPrefixes(t *testing.T) {
	ctx := context.Background()
	mapFile := filepath.Join(t.TempDir(), "map.json")
	if err := os.WriteFile(mapFile, []byte(`{"JasperHG90/localstack": "viking://user/jasper/resources/projects/localstack"}`), 0o600); err != nil {
		t.Fatal(err)
	}
	m, err := LoadMapping(mapFile)
	if err != nil {
		t.Fatal(err)
	}

	objects := map[string]string{
		"JasperHG90/localstack/docs/how-to/a.md":     "a",
		"JasperHG90/localstack/.okf/index.md":        "index",
		"JasperHG90/localstack/_state/manifest.json": "{}",
		"JasperHG90/other/docs/b.md":                 "b",
		"someone/localstack/docs/c.md":               "c",
	}
	_, s3 := newFakeS3(t, objects)
	ov, client := newFakeOV(t)
	c := newConsumer(s3, client)
	c.Map = m
	for key := range objects {
		if err := c.HandleEvent(ctx, eventJSON("create", key)); err != nil {
			t.Fatalf("%s: %v", key, err)
		}
	}

	want := map[string]bool{
		"viking://user/jasper/resources/projects/localstack/docs/how-to/a.md": true,
		"viking://user/jasper/resources/projects/localstack/.okf/index.md":    true,
	}
	got := map[string]bool{}
	for _, w := range ov.calls(http.MethodPost, "/api/v1/content/write") {
		got[fmt.Sprint(w.Body["uri"])] = true
	}
	if fmt.Sprint(got) != fmt.Sprint(want) {
		t.Fatalf("writes went to %v, want %v", got, want)
	}
	if n := len(ov.requests); n != 2 {
		t.Fatalf("want only the two writes to reach OpenViking, got %d requests: %+v", n, ov.requests)
	}
}

func setupStream(t *testing.T) (jetstream.JetStream, jetstream.Stream) {
	t.Helper()
	srv := natstest.Run(t)
	_, js := natstest.Connect(t, srv)
	s, err := stream.Ensure(context.Background(), js)
	if err != nil {
		t.Fatal(err)
	}
	return js, s
}

func publish(t *testing.T, js jetstream.JetStream, data []byte) {
	t.Helper()
	if _, err := js.Publish(context.Background(), stream.EventsSubject, data); err != nil {
		t.Fatal(err)
	}
}

func TestConsumerRetriesThenDeadLetters(t *testing.T) {
	const broken = "JasperHG90/localstack/docs/broken.md"
	const flaky = "JasperHG90/localstack/docs/flaky.md"
	_, s3 := newFakeS3(t, map[string]string{broken: "x", flaky: "y"})
	ov, client := newFakeOV(t)
	ov.failWrites[projRoot+"/docs/broken.md"] = -1
	ov.failWrites[projRoot+"/docs/flaky.md"] = 2
	js, s := setupStream(t)
	c := newConsumer(s3, client)
	c.MaxTries = 3
	runConsumer(t, c, js)

	publish(t, js, eventJSON("create", flaky))
	publish(t, js, eventJSON("create", broken))

	ctx := context.Background()
	var dead *jetstream.RawStreamMsg
	waitFor(t, "a dead letter", 10*time.Second, func() bool {
		m, err := s.GetLastMsgForSubject(ctx, stream.DeadSubject)
		dead = m
		return err == nil
	})
	if string(dead.Data) != string(eventJSON("create", broken)) {
		t.Fatalf("dead letter holds %s", dead.Data)
	}
	if dead.Header.Get(errorHeader) == "" {
		t.Fatal("dead letter carries no error")
	}

	cons, err := s.Consumer(ctx, durable)
	if err != nil {
		t.Fatal(err)
	}
	waitFor(t, "both events settled", 5*time.Second, func() bool {
		info, err := cons.Info(ctx)
		return err == nil && info.AckFloor.Stream == 2 && info.NumAckPending == 0 && info.NumPending == 0
	})
	// Long enough for several more backoffs, had the retries no bound.
	time.Sleep(500 * time.Millisecond)

	if n := ov.writesTo(projRoot + "/docs/broken.md"); n != c.MaxTries {
		t.Fatalf("broken.md: %d write attempts, want exactly %d", n, c.MaxTries)
	}
	// An ack before success would have stopped the retries at one try.
	if n := ov.writesTo(projRoot + "/docs/flaky.md"); n != 3 {
		t.Fatalf("flaky.md: %d write attempts, want 3 (two failures, then success)", n)
	}
	if !ov.has(projRoot + "/docs/flaky.md") {
		t.Fatal("flaky.md never landed")
	}
	info, err := s.Info(ctx, jetstream.WithSubjectFilter(stream.DeadSubject))
	if err != nil {
		t.Fatal(err)
	}
	if n := info.State.Subjects[stream.DeadSubject]; n != 1 {
		t.Fatalf("want only broken.md dead-lettered, got %d dead letters", n)
	}
}

func TestConsumerPoolBound(t *testing.T) {
	const burst = 200
	objects := map[string]string{}
	for i := range burst {
		objects[fmt.Sprintf("JasperHG90/localstack/docs/f%03d.md", i)] = fmt.Sprint(i)
	}
	_, s3 := newFakeS3(t, objects)
	ov, client := newFakeOV(t)
	ov.writeDelay = 10 * time.Millisecond
	// Files with no object give the catch-up pass deletes and listings to
	// send alongside its writes.
	for i := range 40 {
		ov.seed(fmt.Sprintf("%s/old/d%02d/s.md", projRoot, i))
	}
	js, _ := setupStream(t)
	for key := range objects {
		publish(t, js, eventJSON("create", key))
	}

	c := newConsumer(s3, client)
	runConsumer(t, c, js)

	// Catch-up passes run beside the workers, as main runs them.
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan struct{})
	go func() {
		defer close(done)
		for ctx.Err() == nil {
			_ = c.CatchUp(ctx)
		}
	}()
	t.Cleanup(func() { cancel(); <-done })

	waitFor(t, "every write", 30*time.Second, func() bool {
		return len(ov.calls(http.MethodPost, "/api/v1/content/write")) >= burst
	})
	waitFor(t, "catch-up deletes", 30*time.Second, func() bool {
		return !ov.has(projRoot + "/old")
	})
	if peak := ov.peak(); peak > c.Pool {
		t.Fatalf("%d OpenViking requests in flight, pool is %d", peak, c.Pool)
	}
	t.Logf("peak in flight: %d of %d", ov.peak(), c.Pool)
}

func TestConsumerFolderDeleteGuard(t *testing.T) {
	ctx := context.Background()
	_, s3 := newFakeS3(t, map[string]string{"JasperHG90/localstack/docs/c/e.md": "e"})
	ov, client := newFakeOV(t)
	docs := projRoot + "/docs"
	ov.seed(docs+"/a/b.md", docs+"/c/d.md", docs+"/c/e.md")
	c := newConsumer(s3, client)

	// docs/a holds only its summaries once b.md goes, so it is removed. docs
	// still holds c/, so it stays.
	if err := c.HandleEvent(ctx, eventJSON("delete", "JasperHG90/localstack/docs/a/b.md")); err != nil {
		t.Fatal(err)
	}
	if ov.has(docs + "/a") {
		t.Fatal("emptied folder docs/a is still there")
	}
	if !ov.has(docs) {
		t.Fatal("docs was removed while it still held c/")
	}

	// docs/c still holds e.md, so no recursive delete reaches it.
	if err := c.HandleEvent(ctx, eventJSON("delete", "JasperHG90/localstack/docs/c/d.md")); err != nil {
		t.Fatal(err)
	}
	if !ov.has(docs+"/c") || !ov.has(docs+"/c/e.md") {
		t.Fatal("docs/c or its remaining file was removed")
	}

	for _, d := range ov.calls(http.MethodDelete, "/api/v1/fs") {
		if d.Query.Get("recursive") == "true" && d.Query.Get("uri") != docs+"/a" {
			t.Errorf("recursive delete of %s", d.Query.Get("uri"))
		}
	}
	if len(ov.violations) != 0 {
		t.Fatalf("recursive delete of a folder with other entries: %v", ov.violations)
	}
	if n := len(ov.calls(http.MethodGet, "/api/v1/fs/stat")); n != 0 {
		t.Fatalf("fs/stat called %d times", n)
	}

	// A delete that answers 200 but leaves the folder is caught by ls.
	ov.seed(docs + "/x/y.md")
	ov.keepFolders = true
	if err := c.HandleEvent(ctx, eventJSON("delete", "JasperHG90/localstack/docs/x/y.md")); err == nil {
		t.Fatal("a folder still listed after its delete was reported as removed")
	}
}

func TestCatchUpRepairs(t *testing.T) {
	ctx := context.Background()
	_, s3 := newFakeS3(t, map[string]string{
		"JasperHG90/localstack/docs/new.md":          "# new\n",
		"JasperHG90/localstack/docs/kept.md":         "# kept\n",
		"JasperHG90/localstack/_state/manifest.json": "{}",
	})
	ov, client := newFakeOV(t)
	docs := projRoot + "/docs"
	ov.seed(docs+"/kept.md", docs+"/gone.md", docs+"/old/x.md")
	c := newConsumer(s3, client)

	if err := c.CatchUp(ctx); err != nil {
		t.Fatal(err)
	}
	if got := ov.content(docs + "/new.md"); got != "# new\n" {
		t.Fatalf("new.md in OpenViking holds %q", got)
	}
	for _, u := range []string{docs + "/gone.md", docs + "/old/x.md", docs + "/old"} {
		if ov.has(u) {
			t.Errorf("%s survived the catch-up pass", u)
		}
	}
	if !ov.has(docs + "/kept.md") {
		t.Fatal("kept.md was removed")
	}
	if n := ov.writesTo(docs + "/kept.md"); n != 0 {
		t.Fatalf("kept.md rewritten %d times", n)
	}
	if ov.has(projRoot + "/_state/manifest.json") {
		t.Fatal("a _state/ key reached OpenViking")
	}
}

// OpenViking caps a recursive ls at 1000 entries and three levels, so the
// pass must see every file in a wide folder and a deep one, or it rewrites
// what is already there.
func TestCatchUpListsWholeTree(t *testing.T) {
	ctx := context.Background()
	objects := map[string]string{"JasperHG90/localstack/docs/a/b/c/d/deep.md": "deep"}
	uris := []string{projRoot + "/docs/a/b/c/d/deep.md"}
	for i := range 1200 {
		objects[fmt.Sprintf("JasperHG90/localstack/docs/wide/f%04d.md", i)] = "w"
		uris = append(uris, fmt.Sprintf("%s/docs/wide/f%04d.md", projRoot, i))
	}
	_, s3 := newFakeS3(t, objects)
	ov, client := newFakeOV(t)
	ov.seed(uris...)
	c := newConsumer(s3, client)

	if err := c.CatchUp(ctx); err != nil {
		t.Fatal(err)
	}
	if n := len(ov.calls(http.MethodPost, "/api/v1/content/write")); n != 0 {
		t.Fatalf("catch-up rewrote %d files OpenViking already holds", n)
	}
	if n := len(ov.calls(http.MethodDelete, "/api/v1/fs")); n != 0 {
		t.Fatalf("catch-up sent %d deletes", n)
	}
}

func TestApplySerializesPerKey(t *testing.T) {
	ctx := context.Background()
	const key = "JasperHG90/localstack/docs/a.md"
	const uri = projRoot + "/docs/a.md"
	bucketFake, s3 := newFakeS3(t, map[string]string{key: "v1"})
	ov, client := newFakeOV(t)
	c := newConsumer(s3, client)

	// A has read v1 and its write is held back until released.
	held, release := make(chan struct{}), make(chan struct{})
	ov.beforeWrite = func(_, content string) {
		if content == "v1" {
			close(held)
			<-release
		}
	}
	aDone := make(chan error, 1)
	go func() { aDone <- c.Apply(ctx, key) }()
	<-held

	bucketFake.set(key, "v2")
	bDone := make(chan error, 1)
	go func() { bDone <- c.Apply(ctx, key) }()
	// Without per-key ordering B reads and writes v2 now. With it, B waits
	// for A, and the timeout lets A go.
	var bErr error
	bFinished := false
	select {
	case bErr = <-bDone:
		bFinished = true
	case <-time.After(300 * time.Millisecond):
	}
	close(release)
	if err := <-aDone; err != nil {
		t.Fatalf("A: %v", err)
	}
	if !bFinished {
		bErr = <-bDone
	}
	if bErr != nil {
		t.Fatalf("B: %v", bErr)
	}
	if got := ov.content(uri); got != "v2" {
		t.Fatalf("OpenViking holds %q, want the latest content v2", got)
	}
}

func TestPerKeyLockNoDeadlock(t *testing.T) {
	var keys []string
	for _, dir := range []string{"a", "a/x", "b", "c/y/z"} {
		for i := range 3 {
			keys = append(keys, fmt.Sprintf("JasperHG90/localstack/%s/f%d.md", dir, i))
		}
	}
	objects := map[string]string{}
	for _, k := range keys {
		objects[k] = "seed"
	}
	bucketFake, s3 := newFakeS3(t, objects)
	ov, client := newFakeOV(t)
	ov.writeDelay = time.Millisecond
	c := newConsumer(s3, client)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	catchUpDone := make(chan struct{})
	go func() {
		defer close(catchUpDone)
		for ctx.Err() == nil {
			_ = c.CatchUp(ctx)
		}
	}()

	var wg sync.WaitGroup
	for w := range 8 {
		wg.Go(func() {
			r := rand.New(rand.NewPCG(uint64(w), 0))
			for i := range 40 {
				k := keys[r.IntN(len(keys))]
				batch := []string{k}
				switch r.IntN(3) {
				case 0:
					bucketFake.set(k, fmt.Sprintf("w%d-%d", w, i))
				case 1:
					bucketFake.del(k)
				case 2:
					// Empty k's folder so its removal reaches the tree lock.
					dir := k[:strings.LastIndex(k, "/")+1]
					batch = nil
					for _, other := range keys {
						if strings.HasPrefix(other, dir) && !strings.Contains(other[len(dir):], "/") {
							bucketFake.del(other)
							batch = append(batch, other)
						}
					}
				}
				for _, b := range batch {
					if err := c.Apply(ctx, b); err != nil {
						t.Errorf("apply %s: %v", b, err)
					}
				}
			}
		})
	}
	burstDone := make(chan struct{})
	go func() { wg.Wait(); close(burstDone) }()
	select {
	case <-burstDone:
	case <-time.After(60 * time.Second):
		t.Fatal("burst of writes, deletes and folder removals did not finish: deadlock")
	}
	cancel()
	<-catchUpDone

	for _, k := range keys {
		if err := c.Apply(context.Background(), k); err != nil {
			t.Fatalf("apply %s: %v", k, err)
		}
	}
	for _, k := range keys {
		uri, _, _ := c.Map.Resolve(k)
		bucketFake.mu.Lock()
		want, exists := bucketFake.objects[k]
		bucketFake.mu.Unlock()
		if exists && ov.content(uri) != want {
			t.Errorf("%s: OpenViking holds %q, bucket %q", uri, ov.content(uri), want)
		}
		if !exists && ov.has(uri) {
			t.Errorf("%s is in OpenViking but not in the bucket", uri)
		}
	}
	if n := len(c.keys.m); n != 0 {
		t.Errorf("%d key locks left after every holder finished", n)
	}
	ov.mu.Lock()
	defer ov.mu.Unlock()
	if len(ov.violations) != 0 {
		t.Fatalf("recursive delete of a folder with other entries: %v", ov.violations)
	}
}
