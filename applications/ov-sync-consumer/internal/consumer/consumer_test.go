package consumer

import (
	"context"
	"errors"
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

func TestLockConflictLogsBusy(t *testing.T) {
	const key = "JasperHG90/localstack/docs/busy.md"
	_, s3 := newFakeS3(t, map[string]string{key: "x"})
	ov, client := newFakeOV(t)
	ov.failWrites[projRoot+"/docs/busy.md"] = 2
	ov.failStatus, ov.failMessage = http.StatusConflict, lockTimeout
	js, _ := setupStream(t)
	c := newConsumer(s3, client)
	c.Backoff = Backoff(200*time.Millisecond, time.Second)
	logs := captureLog(c)
	runConsumer(t, c, js)

	start := time.Now()
	publish(t, js, eventJSON("create", key))
	waitFor(t, "busy.md to land", 10*time.Second, func() bool { return ov.has(projRoot + "/docs/busy.md") })

	// Two busy tries wait Backoff(1) and Backoff(2), 200 and 400 ms. An
	// immediate redelivery would land in a few milliseconds.
	if elapsed := time.Since(start); elapsed < 550*time.Millisecond {
		t.Fatalf("landed after %s, so the busy tries skipped the backoff", elapsed)
	}
	if n := ov.writesTo(projRoot + "/docs/busy.md"); n != 3 {
		t.Fatalf("%d write attempts, want 3 (two busy, then success)", n)
	}
	busy := logs.lines("folder busy")
	if len(busy) != 2 {
		t.Fatalf("want 2 folder busy lines, got %q", busy)
	}
	for _, line := range busy {
		if !strings.Contains(line, "level=INFO") || !strings.Contains(line, projRoot+"/docs/busy.md") {
			t.Fatalf("folder busy line is not INFO with the uri: %s", line)
		}
	}
	if warn := logs.lines("level=WARN"); len(warn) != 0 {
		t.Fatalf("a lock conflict logged at WARN: %q", warn)
	}
}

func TestOtherConflictFails(t *testing.T) {
	t.Run("other 409 warns", func(t *testing.T) {
		const key = "JasperHG90/localstack/docs/other.md"
		_, s3 := newFakeS3(t, map[string]string{key: "x"})
		ov, client := newFakeOV(t)
		ov.failWrites[projRoot+"/docs/other.md"] = 1
		ov.failStatus, ov.failMessage = http.StatusConflict, "resource already exists"
		js, _ := setupStream(t)
		c := newConsumer(s3, client)
		logs := captureLog(c)
		runConsumer(t, c, js)

		publish(t, js, eventJSON("create", key))
		waitFor(t, "other.md to land", 10*time.Second, func() bool { return ov.has(projRoot + "/docs/other.md") })
		if len(logs.lines("event failed")) != 1 || len(logs.lines("folder busy")) != 0 {
			t.Fatalf("want one event failed line and no folder busy line, got %q", logs.lines("msg="))
		}
	})
	t.Run("lock 409 on the last try dead-letters", func(t *testing.T) {
		const key = "JasperHG90/localstack/docs/stuck.md"
		_, s3 := newFakeS3(t, map[string]string{key: "x"})
		ov, client := newFakeOV(t)
		ov.failWrites[projRoot+"/docs/stuck.md"] = -1
		ov.failStatus, ov.failMessage = http.StatusConflict, lockTimeout
		js, s := setupStream(t)
		c := newConsumer(s3, client)
		c.MaxTries = 3
		runConsumer(t, c, js)

		publish(t, js, eventJSON("create", key))
		waitFor(t, "a dead letter", 10*time.Second, func() bool {
			_, err := s.GetLastMsgForSubject(context.Background(), stream.DeadSubject)
			return err == nil
		})
		if n := ov.writesTo(projRoot + "/docs/stuck.md"); n != c.MaxTries {
			t.Fatalf("%d write attempts, want exactly %d", n, c.MaxTries)
		}
	})
}

func TestCatchUpLockConflictIsBusy(t *testing.T) {
	_, s3 := newFakeS3(t, map[string]string{})
	ov, client := newFakeOV(t)
	gone := projRoot + "/docs/gone.md"
	ov.seed(gone)
	ov.busyDeletes[gone] = true
	c := newConsumer(s3, client)
	logs := captureLog(c)

	err := c.CatchUp(context.Background())
	if err != nil && strings.Contains(err.Error(), "lock acquire timed out") {
		t.Fatalf("catch-up failed the pass on a lock conflict: %v", err)
	}
	busy := logs.lines("folder busy")
	if len(busy) != 1 || !strings.Contains(busy[0], "level=INFO") || !strings.Contains(busy[0], gone) {
		t.Fatalf("want one INFO folder busy line naming %s, got %q", gone, busy)
	}
	if !ov.has(gone) {
		t.Fatal("the busy file was deleted anyway")
	}

	t.Run("busy folder cleanup still fails the pass", func(t *testing.T) {
		_, s3 := newFakeS3(t, map[string]string{})
		ov, client := newFakeOV(t)
		lone := projRoot + "/docs/lone/gone.md"
		ov.seed(lone)
		ov.busyDeletes[projRoot+"/docs/lone"] = true
		c := newConsumer(s3, client)

		err := c.CatchUp(context.Background())
		if err == nil || !strings.Contains(err.Error(), "lock acquire timed out") {
			t.Fatalf("a busy folder cleanup was dropped, so the folder stays behind: %v", err)
		}
		if ov.has(lone) {
			t.Fatal("the file itself was not deleted")
		}
	})
}

// A PNG header is not valid UTF-8, which is what a JSON content/write damages.
const (
	pngV1 = "\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\xff\xd8v1"
	pngV2 = "\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x02\x00\xfe\xc0v2"
)

// requestOrder names each request by its path, in the order they arrived.
func requestOrder(ov *fakeOV) []string {
	ov.mu.Lock()
	defer ov.mu.Unlock()
	var out []string
	for _, r := range ov.requests {
		out = append(out, r.Method+" "+r.Path)
	}
	return out
}

func TestImageUploaded(t *testing.T) {
	ctx := context.Background()
	const key = "JasperHG90/localstack/docs/ref/diagram.png"
	d := projRoot + "/docs/ref"
	_, s3 := newFakeS3(t, map[string]string{key: pngV1, "JasperHG90/localstack/docs/ref/Photo.JPG": pngV2})
	ov, client := newFakeOV(t)
	ov.seed(d + "/notes.md")
	ov.seedImage(d+"/other.png/other.png", pngV2)
	before := map[string]string{}
	for _, u := range ov.under(d) {
		before[u] = ov.content(u)
	}
	c := newConsumer(s3, client)

	if err := c.HandleEvent(ctx, eventJSON("create", key)); err != nil {
		t.Fatal(err)
	}
	if n := len(ov.calls(http.MethodPost, "/api/v1/content/write")); n != 0 {
		t.Fatalf("an image went through content/write %d times", n)
	}
	uploads := ov.calls(http.MethodPost, "/api/v1/resources/temp_upload")
	adds := ov.calls(http.MethodPost, "/api/v1/resources")
	if len(uploads) != 1 || string(uploads[0].File) != pngV1 || uploads[0].FileName != "diagram.png" {
		t.Fatalf("want one temp_upload of the exact bytes as diagram.png, got %+v", uploads)
	}
	if len(adds) != 1 || adds[0].Body["to"] != d+"/diagram.png" || adds[0].Body["source_name"] != "diagram.png" ||
		adds[0].Body["wait"] != true || adds[0].Body["temp_file_id"] == nil {
		t.Fatalf("want one add resource with to=D/diagram.png, source_name=diagram.png, wait=true, got %+v", adds)
	}
	order := requestOrder(ov)
	if order[len(order)-2] != "POST /api/v1/resources/temp_upload" || order[len(order)-1] != "POST /api/v1/resources" {
		t.Fatalf("want temp_upload then add resource last, got %v", order)
	}
	if got := ov.content(d + "/diagram.png/diagram.png"); got != pngV1 {
		t.Fatalf("D/diagram.png/diagram.png holds %q, want the PNG's exact bytes", got)
	}
	for u, v := range before {
		if strings.HasSuffix(u, "/.abstract.md") || strings.HasSuffix(u, "/.overview.md") {
			continue
		}
		if !ov.has(strings.TrimSuffix(u, "/")) || ov.content(u) != v {
			t.Errorf("sibling %s changed", u)
		}
	}

	t.Run("extension is case-insensitive", func(t *testing.T) {
		if err := c.HandleEvent(ctx, eventJSON("create", "JasperHG90/localstack/docs/ref/Photo.JPG")); err != nil {
			t.Fatal(err)
		}
		if got := ov.content(d + "/Photo.JPG/Photo.JPG"); got != pngV2 {
			t.Fatalf("Photo.JPG was not uploaded as an image: %q", got)
		}
	})

	t.Run("lock 409 on the add is busy", func(t *testing.T) {
		ov.failWrites[d+"/diagram.png/diagram.png"] = 1
		ov.failStatus, ov.failMessage = http.StatusConflict, lockTimeout
		if err := c.Apply(ctx, key); !errors.Is(err, errLockBusy) {
			t.Fatalf("want errLockBusy, got %v", err)
		}
	})
}

func TestImageReplacesOldCopies(t *testing.T) {
	ctx := context.Background()
	const key = "JasperHG90/localstack/docs/ref/diagram.png"
	d := projRoot + "/docs/ref"
	bucketFake, s3 := newFakeS3(t, map[string]string{key: pngV1})
	ov, client := newFakeOV(t)
	// The damaged copy the old text write left, a plain file at D/name.
	ov.seed(d+"/diagram.png", d+"/notes.md")
	c := newConsumer(s3, client)

	if err := c.Apply(ctx, key); err != nil {
		t.Fatal(err)
	}
	if ov.isFile(d + "/diagram.png") {
		t.Fatal("the plain file at D/diagram.png is still there")
	}
	dels := ov.calls(http.MethodDelete, "/api/v1/fs")
	if len(dels) != 1 || dels[0].Query.Get("uri") != d+"/diagram.png" || dels[0].Query.Get("recursive") == "true" {
		t.Fatalf("want one non-recursive delete of D/diagram.png, got %+v", dels)
	}
	if got := ov.content(d + "/diagram.png/diagram.png"); got != pngV1 {
		t.Fatalf("D/diagram.png/diagram.png holds %q", got)
	}

	bucketFake.set(key, pngV2)
	if err := c.Apply(ctx, key); err != nil {
		t.Fatal(err)
	}
	if got := ov.content(d + "/diagram.png/diagram.png"); got != pngV2 {
		t.Fatalf("D/diagram.png/diagram.png holds %q, want the changed PNG", got)
	}
	if n := len(ov.calls(http.MethodDelete, "/api/v1/fs")); n != 1 {
		t.Fatalf("the re-upload sent %d more deletes; the image folder must not be deleted", n-1)
	}
	want := []string{d + "/diagram.png/", d + "/diagram.png/.abstract.md", d + "/diagram.png/.overview.md", d + "/diagram.png/diagram.png"}
	var got []string
	for _, u := range ov.under(d) {
		if strings.HasPrefix(u, d+"/diagram.png") {
			got = append(got, u)
		}
	}
	if fmt.Sprint(got) != fmt.Sprint(want) {
		t.Fatalf("D holds %v for diagram.png, want %v", got, want)
	}
}

func TestOtherBinarySkipped(t *testing.T) {
	ctx := context.Background()
	const key = "JasperHG90/localstack/docs/manual.pdf"
	_, s3 := newFakeS3(t, map[string]string{key: "%PDF-1.7\n\xff\xfe\x00\x01 binary"})
	ov, client := newFakeOV(t)
	c := newConsumer(s3, client)
	logs := captureLog(c)

	if err := c.HandleEvent(ctx, eventJSON("create", key)); err != nil {
		t.Fatal(err)
	}
	if reqs := requestOrder(ov); len(reqs) != 0 {
		t.Fatalf("a skipped binary reached OpenViking: %v", reqs)
	}
	lines := logs.lines("binary file skipped")
	if len(lines) != 1 || !strings.Contains(lines[0], "level=INFO") || !strings.Contains(lines[0], key) {
		t.Fatalf("want one INFO binary file skipped line naming %s, got %q", key, lines)
	}
}

func TestUTF8ObjectWrittenExactly(t *testing.T) {
	ctx := context.Background()
	const key = "JasperHG90/localstack/docs/naïve.md"
	const body = "# Café — 日本語 🚀\n\tß ∑ €\n"
	_, s3 := newFakeS3(t, map[string]string{key: body})
	ov, client := newFakeOV(t)
	c := newConsumer(s3, client)

	if err := c.HandleEvent(ctx, eventJSON("create", key)); err != nil {
		t.Fatal(err)
	}
	if n := len(ov.calls(http.MethodPost, "/api/v1/resources/temp_upload")) + len(ov.calls(http.MethodPost, "/api/v1/resources")); n != 0 {
		t.Fatalf("a text file was uploaded as a resource %d times", n)
	}
	writes := ov.calls(http.MethodPost, "/api/v1/content/write")
	if len(writes) != 1 || writes[0].Body["content"] != body {
		t.Fatalf("want one content/write of the exact text, got %+v", writes)
	}
	if got := ov.content(projRoot + "/docs/naïve.md"); got != body {
		t.Fatalf("OpenViking holds %q, want %q", got, body)
	}
}

func TestCatchUpImages(t *testing.T) {
	ctx := context.Background()
	img := "JasperHG90/localstack/docs/img/"
	d := projRoot + "/docs/img"
	_, s3 := newFakeS3(t, map[string]string{
		img + "present.png": pngV1,
		img + "missing.png": pngV2,
		img + "migrate.png": pngV1,
		img + "keep.md":     "keep",
	})
	ov, client := newFakeOV(t)
	ov.seed(d + "/keep.md")
	ov.seedImage(d+"/present.png/present.png", pngV1)
	ov.seedImage(d+"/gone.png/gone.png", pngV2)
	// The old plain copy, while its image is wanted but not uploaded yet.
	ov.seed(d + "/migrate.png")
	c := newConsumer(s3, client)

	if err := c.CatchUp(ctx); err != nil {
		t.Fatalf("catch-up failed: %v", err)
	}
	for _, a := range ov.calls(http.MethodPost, "/api/v1/resources") {
		if a.Body["to"] == d+"/present.png" {
			t.Fatal("catch-up re-uploaded an image OpenViking already holds")
		}
	}
	if got := ov.content(d + "/missing.png/missing.png"); got != pngV2 {
		t.Fatalf("the missing image was not uploaded: %q", got)
	}
	if got := ov.content(d + "/migrate.png/migrate.png"); got != pngV1 {
		t.Fatalf("migrate.png's image was removed or never uploaded: %q", got)
	}
	if ov.isFile(d + "/migrate.png") {
		t.Fatal("the old plain copy of migrate.png is still there")
	}
	for _, del := range ov.calls(http.MethodDelete, "/api/v1/fs") {
		if u := del.Query.Get("uri"); strings.HasPrefix(u, d+"/migrate.png") && del.Query.Get("recursive") == "true" ||
			strings.HasPrefix(u, d+"/present.png") || strings.HasPrefix(u, d+"/missing.png") {
			t.Errorf("catch-up deleted %s (recursive=%s)", u, del.Query.Get("recursive"))
		}
	}
	if ov.has(d + "/gone.png/gone.png") {
		t.Fatal("the image whose object is gone is still there")
	}
	// The emptied folder stays listed in D, as on the real server, so D
	// stays too. Neither fails the pass.
	if !ov.has(d) || !ov.has(d+"/keep.md") {
		t.Fatal("D or keep.md was removed")
	}
	if len(ov.violations) != 0 {
		t.Fatalf("recursive delete of a folder with other entries: %v", ov.violations)
	}

	writes := len(ov.calls(http.MethodPost, "/api/v1/content/write"))
	adds := len(ov.calls(http.MethodPost, "/api/v1/resources"))
	dels := len(ov.calls(http.MethodDelete, "/api/v1/fs"))
	if err := c.CatchUp(ctx); err != nil {
		t.Fatalf("second pass failed: %v", err)
	}
	if n := len(ov.calls(http.MethodPost, "/api/v1/content/write")) - writes; n != 0 {
		t.Errorf("second pass wrote %d files", n)
	}
	if n := len(ov.calls(http.MethodPost, "/api/v1/resources")) - adds; n != 0 {
		t.Errorf("second pass uploaded %d images", n)
	}
	if n := len(ov.calls(http.MethodDelete, "/api/v1/fs")) - dels; n != 0 {
		t.Errorf("second pass sent %d deletes", n)
	}
}
