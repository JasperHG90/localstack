package consumer

import (
	"context"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/nats-io/nats.go/jetstream"
	"golang.org/x/time/rate"
)

const (
	bucket    = "ov-sync"
	ovToken   = "ov-test-token"
	resources = "viking://user/jasper/resources"
	projRoot  = resources + "/projects/localstack"
)

var testMapping = Mapping{"JasperHG90/localstack/": projRoot + "/"}

// fakeS3 serves the three S3 calls the consumer makes: GET object, HEAD
// object and ListObjectsV2, path-style.
type fakeS3 struct {
	mu      sync.Mutex
	objects map[string]string
}

func newFakeS3(t *testing.T, objects map[string]string) (*fakeS3, *minio.Client) {
	t.Helper()
	f := &fakeS3{objects: map[string]string{}}
	for k, v := range objects {
		f.objects[k] = v
	}
	srv := httptest.NewServer(f)
	t.Cleanup(srv.Close)
	u, _ := url.Parse(srv.URL)
	client, err := minio.New(u.Host, &minio.Options{
		Creds:  credentials.NewStaticV4("key", "secret", ""),
		Region: "us-east-1",
	})
	if err != nil {
		t.Fatal(err)
	}
	return f, client
}

func (f *fakeS3) set(key, body string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.objects[key] = body
}

func (f *fakeS3) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	b, key, _ := strings.Cut(strings.TrimPrefix(r.URL.Path, "/"), "/")
	if b != bucket {
		s3Error(w, http.StatusNotFound, "NoSuchBucket")
		return
	}
	if key == "" && r.URL.Query().Get("list-type") == "2" {
		f.list(w, r.URL.Query().Get("prefix"))
		return
	}
	body, ok := f.objects[key]
	if !ok {
		s3Error(w, http.StatusNotFound, "NoSuchKey")
		return
	}
	w.Header().Set("Content-Length", fmt.Sprint(len(body)))
	w.Header().Set("Content-Type", "text/markdown")
	w.Header().Set("ETag", `"0123456789abcdef0123456789abcdef"`)
	w.Header().Set("Last-Modified", time.Unix(1794772528, 0).UTC().Format(http.TimeFormat))
	if r.Method == http.MethodHead {
		return
	}
	_, _ = io.WriteString(w, body)
}

func (f *fakeS3) list(w http.ResponseWriter, prefix string) {
	type content struct {
		Key          string
		LastModified string
		ETag         string
		Size         int
		StorageClass string
	}
	type result struct {
		XMLName     xml.Name `xml:"http://s3.amazonaws.com/doc/2006-03-01/ ListBucketResult"`
		Name        string
		Prefix      string
		KeyCount    int
		MaxKeys     int
		IsTruncated bool
		Contents    []content
	}
	res := result{Name: bucket, Prefix: prefix, MaxKeys: 1000}
	keys := make([]string, 0, len(f.objects))
	for k := range f.objects {
		if strings.HasPrefix(k, prefix) {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)
	for _, k := range keys {
		res.Contents = append(res.Contents, content{
			Key: k, LastModified: "2026-11-15T19:55:28.000Z", ETag: `"0123456789abcdef0123456789abcdef"`,
			Size: len(f.objects[k]), StorageClass: "STANDARD",
		})
	}
	res.KeyCount = len(res.Contents)
	w.Header().Set("Content-Type", "application/xml")
	_ = xml.NewEncoder(w).Encode(res)
}

func s3Error(w http.ResponseWriter, status int, code string) {
	w.Header().Set("Content-Type", "application/xml")
	w.WriteHeader(status)
	_, _ = fmt.Fprintf(w, "<Error><Code>%s</Code><Message>%s</Message></Error>", code, code)
}

type ovRequest struct {
	Method string
	Path   string
	Query  url.Values
	Body   map[string]any
}

// fakeOV keeps a tree the way OpenViking does: every folder holds its own
// `.abstract.md` and `.overview.md`, a folder delete without recursive=true
// is refused with 412, and fs/stat answers 200 even for a removed folder.
type fakeOV struct {
	mu       sync.Mutex
	files    map[string]string
	dirs     map[string]bool
	requests []ovRequest

	// failWrites makes the next n writes to a uri fail; -1 fails them all.
	failWrites map[string]int
	writeDelay time.Duration
	// keepFolders answers a recursive folder delete with 200 but keeps the
	// folder.
	keepFolders bool
	// violations records each recursive delete of a folder that held more
	// than its two summaries.
	violations []string

	inFlight, maxInFlight int
}

func newFakeOV(t *testing.T) (*fakeOV, *OpenViking) {
	t.Helper()
	f := &fakeOV{files: map[string]string{}, dirs: map[string]bool{}, failWrites: map[string]int{}}
	srv := httptest.NewServer(f)
	t.Cleanup(srv.Close)
	tokenFile := filepath.Join(t.TempDir(), "ov_token")
	if err := os.WriteFile(tokenFile, []byte(ovToken+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	return f, &OpenViking{URL: srv.URL, TokenFile: tokenFile, HTTP: &http.Client{Timeout: 10 * time.Second}}
}

// put stores a file and the summaries OpenViking writes into every folder
// above it.
func (f *fakeOV) put(uri, content string) {
	f.files[uri] = content
	for d := parent(uri); len(d) > len(resources); d = parent(d) {
		f.dirs[d] = true
		f.files[d+"/.abstract.md"] = "abstract"
		f.files[d+"/.overview.md"] = "overview"
	}
}

func (f *fakeOV) seed(uris ...string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	for _, u := range uris {
		f.put(u, "seeded "+u)
	}
}

func (f *fakeOV) has(uri string) bool {
	f.mu.Lock()
	defer f.mu.Unlock()
	_, file := f.files[uri]
	return file || f.dirs[uri]
}

func (f *fakeOV) content(uri string) string {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.files[uri]
}

func (f *fakeOV) calls(method, path string) []ovRequest {
	f.mu.Lock()
	defer f.mu.Unlock()
	var out []ovRequest
	for _, r := range f.requests {
		if r.Method == method && r.Path == path {
			out = append(out, r)
		}
	}
	return out
}

func (f *fakeOV) writesTo(uri string) int {
	n := 0
	for _, r := range f.calls(http.MethodPost, "/api/v1/content/write") {
		if r.Body["uri"] == uri {
			n++
		}
	}
	return n
}

func (f *fakeOV) peak() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.maxInFlight
}

func ovReply(w http.ResponseWriter, status int, result any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	body := map[string]any{"status": "ok", "result": result}
	if status != http.StatusOK {
		body = map[string]any{"status": "error", "result": nil, "error": map[string]any{"code": http.StatusText(status), "message": fmt.Sprint(result)}}
	}
	_ = json.NewEncoder(w).Encode(body)
}

func (f *fakeOV) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	f.inFlight++
	f.maxInFlight = max(f.maxInFlight, f.inFlight)
	f.mu.Unlock()
	defer func() {
		f.mu.Lock()
		f.inFlight--
		f.mu.Unlock()
	}()

	req := ovRequest{Method: r.Method, Path: r.URL.Path, Query: r.URL.Query()}
	if r.Body != nil {
		_ = json.NewDecoder(r.Body).Decode(&req.Body)
	}
	f.mu.Lock()
	f.requests = append(f.requests, req)
	f.mu.Unlock()

	if r.Header.Get("Authorization") != "Bearer "+ovToken {
		ovReply(w, http.StatusUnauthorized, "bad token")
		return
	}
	q := req.Query
	switch {
	case r.Method == http.MethodPost && r.URL.Path == "/api/v1/content/write":
		f.write(w, req)
	case r.Method == http.MethodDelete && r.URL.Path == "/api/v1/fs":
		f.delete(w, q.Get("uri"), q.Get("recursive") == "true")
	case r.Method == http.MethodGet && r.URL.Path == "/api/v1/fs/ls":
		f.ls(w, q)
	case r.Method == http.MethodGet && r.URL.Path == "/api/v1/fs/stat":
		ovReply(w, http.StatusOK, map[string]any{"isDir": true})
	default:
		ovReply(w, http.StatusNotFound, "no route "+r.URL.Path)
	}
}

func (f *fakeOV) write(w http.ResponseWriter, req ovRequest) {
	uri, _ := req.Body["uri"].(string)
	content, _ := req.Body["content"].(string)
	f.mu.Lock()
	n := f.failWrites[uri]
	if n > 0 {
		f.failWrites[uri] = n - 1
	}
	delay := f.writeDelay
	f.mu.Unlock()
	if n != 0 {
		ovReply(w, http.StatusInternalServerError, "write refused")
		return
	}
	time.Sleep(delay)
	f.mu.Lock()
	f.put(uri, content)
	f.mu.Unlock()
	ovReply(w, http.StatusOK, map[string]any{"uri": uri})
}

func (f *fakeOV) delete(w http.ResponseWriter, uri string, recursive bool) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, ok := f.files[uri]; ok {
		delete(f.files, uri)
		ovReply(w, http.StatusOK, map[string]any{"uri": uri})
		return
	}
	if !f.dirs[uri] {
		ovReply(w, http.StatusNotFound, "not found "+uri)
		return
	}
	if !recursive {
		ovReply(w, http.StatusPreconditionFailed, "Cannot remove directory without --recursive")
		return
	}
	for k := range f.files {
		if strings.HasPrefix(k, uri+"/") && !isSummary(uri, k) {
			f.violations = append(f.violations, fmt.Sprintf("recursive delete of %s holding %s", uri, k))
		}
	}
	if f.keepFolders {
		ovReply(w, http.StatusOK, map[string]any{"uri": uri})
		return
	}
	delete(f.dirs, uri)
	for k := range f.files {
		if strings.HasPrefix(k, uri+"/") {
			delete(f.files, k)
		}
	}
	for k := range f.dirs {
		if strings.HasPrefix(k, uri+"/") {
			delete(f.dirs, k)
		}
	}
	ovReply(w, http.StatusOK, map[string]any{"uri": uri})
}

// ls pages like OpenViking's: at most node_limit entries (default 1000) from
// offset, with has_more beside the result. recursive=true stops three levels
// down, as the server's level_limit does.
func (f *fakeOV) ls(w http.ResponseWriter, q url.Values) {
	uri := q.Get("uri")
	hidden := q.Get("show_all_hidden") == "true"
	recursive := q.Get("recursive") == "true"
	limit, offset := 1000, 0
	if v := q.Get("node_limit"); v != "" {
		limit, _ = strconv.Atoi(v)
	}
	if v := q.Get("offset"); v != "" {
		offset, _ = strconv.Atoi(v)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if !f.dirs[uri] {
		ovReply(w, http.StatusNotFound, "not found "+uri)
		return
	}
	within := func(k string) bool {
		rest, ok := strings.CutPrefix(k, uri+"/")
		if !ok {
			return false
		}
		if recursive {
			return strings.Count(rest, "/") < 3
		}
		return !strings.Contains(rest, "/")
	}
	entries := []map[string]any{}
	for d := range f.dirs {
		if within(d) {
			entries = append(entries, map[string]any{"uri": d, "isDir": true})
		}
	}
	for k := range f.files {
		base := k[strings.LastIndex(k, "/")+1:]
		if within(k) && (hidden || !strings.HasPrefix(base, ".")) {
			entries = append(entries, map[string]any{"uri": k, "isDir": false})
		}
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i]["uri"].(string) < entries[j]["uri"].(string) })
	entries = entries[min(offset, len(entries)):]
	more := len(entries) > limit
	entries = entries[:min(limit, len(entries))]
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]any{"status": "ok", "result": entries, "has_more": more})
}

func newConsumer(s3 *minio.Client, ov *OpenViking) *Consumer {
	ov.MaxInFlight = 4
	return &Consumer{
		S3:       s3,
		Bucket:   bucket,
		OV:       ov,
		Map:      testMapping,
		Pool:     4,
		Limit:    rate.NewLimiter(rate.Inf, 1),
		MaxTries: 5,
		Backoff:  Backoff(20*time.Millisecond, 100*time.Millisecond),
		AckWait:  30 * time.Second,
		Log:      slog.New(slog.NewTextHandler(io.Discard, nil)),
	}
}

func runConsumer(t *testing.T, c *Consumer, js jetstream.JetStream) {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- c.Run(ctx, js) }()
	t.Cleanup(func() {
		cancel()
		if err := <-done; err != nil {
			t.Errorf("Run: %v", err)
		}
	})
}

func eventJSON(eventType, key string) []byte {
	entry := map[string]any{"name": key[strings.LastIndex(key, "/")+1:]}
	msg := map[string]any{"new_entry": entry}
	if eventType == "delete" {
		msg = map[string]any{"old_entry": entry}
	}
	raw, _ := json.Marshal(map[string]any{"event_type": eventType, "key": "/buckets/" + bucket + "/" + key, "message": msg})
	return raw
}

func waitFor(t *testing.T, what string, timeout time.Duration, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for !cond() {
		if time.Now().After(deadline) {
			t.Fatalf("timed out waiting for %s", what)
		}
		time.Sleep(20 * time.Millisecond)
	}
}
