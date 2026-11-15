package receiver

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/nats-io/nats.go/jetstream"

	"github.com/JasperHG90/localstack/applications/ov-sync-consumer/internal/natstest"
	"github.com/JasperHG90/localstack/applications/ov-sync-consumer/internal/stream"
)

const token = "test-token"

const eventA = `{"event_type":"create","key":"/buckets/ov-sync/o/r/docs/a.md","message":{"new_entry":{"name":"a.md","attributes":{"inode":7484667733272911122,"mtime":1794772528}}}}`

// The same event as eventA, serialized with other key order and spacing.
const eventAReordered = `{ "message": {"new_entry": {"attributes": {"mtime": 1794772528, "inode": 7484667733272911122}, "name": "a.md"}},
  "key": "/buckets/ov-sync/o/r/docs/a.md", "event_type": "create" }`

// Differs from eventA only in the low digits of the inode, which a float64
// decode would lose.
const eventB = `{"event_type":"create","key":"/buckets/ov-sync/o/r/docs/a.md","message":{"new_entry":{"name":"a.md","attributes":{"inode":7484667733272911123,"mtime":1794772528}}}}`

type running struct {
	url  string
	done chan error
}

func start(t *testing.T, natsURL string) running {
	t.Helper()
	tokenFile := filepath.Join(t.TempDir(), "token")
	if err := os.WriteFile(tokenFile, []byte(token+"\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- Serve(ctx, ln, Config{
			NATSURL:        natsURL,
			TokenFile:      tokenFile,
			PublishTimeout: 2 * time.Second,
			Log:            slog.New(slog.NewTextHandler(io.Discard, nil)),
		})
	}()
	t.Cleanup(func() {
		cancel()
		<-done
	})
	return running{url: "http://" + ln.Addr().String() + "/events", done: done}
}

func (r running) assertUp(t *testing.T) {
	t.Helper()
	select {
	case err := <-r.done:
		t.Fatalf("receiver exited: %v", err)
	default:
	}
}

func post(t *testing.T, url, auth, body string) (int, time.Duration) {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, url, strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	if auth != "" {
		req.Header.Set("Authorization", auth)
	}
	began := time.Now()
	resp, err := (&http.Client{Timeout: 10 * time.Second}).Do(req)
	if err != nil {
		t.Fatalf("receiver did not answer: %v", err)
	}
	_ = resp.Body.Close()
	return resp.StatusCode, time.Since(began)
}

func freePort(t *testing.T) int {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	port := ln.Addr().(*net.TCPAddr).Port
	_ = ln.Close()
	return port
}

func is2xx(code int) bool { return code >= 200 && code < 300 }

func streamMsgs(t *testing.T, js jetstream.JetStream) uint64 {
	t.Helper()
	s, err := js.Stream(context.Background(), stream.Name)
	if err != nil {
		t.Fatal(err)
	}
	info, err := s.Info(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	return info.State.Msgs
}

func TestReceiverStartsWithoutNATS(t *testing.T) {
	port := freePort(t)
	r := start(t, fmt.Sprintf("nats://127.0.0.1:%d", port))

	for i := 0; i < 3; i++ {
		code, _ := post(t, r.url, "Bearer "+token, eventA)
		if is2xx(code) {
			t.Fatalf("answered %d with NATS unreachable", code)
		}
		time.Sleep(time.Second)
		r.assertUp(t)
	}

	// NATS comes up later on the same address: the receiver reconnects
	// without a restart.
	srv := natstest.RunOnPort(t, port)
	_, js := natstest.Connect(t, srv)
	if _, err := stream.Ensure(context.Background(), js); err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(15 * time.Second)
	for {
		code, _ := post(t, r.url, "Bearer "+token, eventA)
		if is2xx(code) {
			break
		}
		if time.Now().After(deadline) {
			t.Fatalf("still %d after NATS came up", code)
		}
		time.Sleep(500 * time.Millisecond)
	}
	r.assertUp(t)
}

func TestReceiverPublishFailureReturnsNon2xx(t *testing.T) {
	// A server with no stream: every publish fails.
	srv := natstest.Run(t)
	r := start(t, srv.ClientURL())
	time.Sleep(200 * time.Millisecond)

	check := func(why string) {
		t.Helper()
		code, took := post(t, r.url, "Bearer "+token, eventA)
		if is2xx(code) {
			t.Fatalf("%s: answered %d", why, code)
		}
		if took >= 10*time.Second {
			t.Fatalf("%s: took %s, past the webhook's 10 s timeout", why, took)
		}
		r.assertUp(t)
	}
	check("no stream")
	srv.Shutdown()
	check("server gone")
	check("server still gone")
}

func TestReceiverRejectsBadToken(t *testing.T) {
	srv := natstest.Run(t)
	_, js := natstest.Connect(t, srv)
	if _, err := stream.Ensure(context.Background(), js); err != nil {
		t.Fatal(err)
	}
	r := start(t, srv.ClientURL())

	for _, auth := range []string{"", "Bearer wrong", "Bearer " + token + "x", token, "Basic " + token} {
		code, _ := post(t, r.url, auth, eventA)
		if is2xx(code) {
			t.Fatalf("auth %q answered %d", auth, code)
		}
	}
	if n := streamMsgs(t, js); n != 0 {
		t.Fatalf("%d messages reached JetStream from refused requests", n)
	}

	// The same setup does publish with the right token.
	if code, _ := post(t, r.url, "Bearer "+token, eventA); !is2xx(code) {
		t.Fatalf("good token answered %d", code)
	}
	if n := streamMsgs(t, js); n != 1 {
		t.Fatalf("want 1 message after a good request, got %d", n)
	}
}

func TestReceiverPublishesWithMsgID(t *testing.T) {
	srv := natstest.Run(t)
	_, js := natstest.Connect(t, srv)
	s, err := stream.Ensure(context.Background(), js)
	if err != nil {
		t.Fatal(err)
	}
	r := start(t, srv.ClientURL())

	for _, body := range []string{eventA, eventA, eventAReordered} {
		if code, _ := post(t, r.url, "Bearer "+token, body); !is2xx(code) {
			t.Fatalf("answered %d", code)
		}
	}
	if n := streamMsgs(t, js); n != 1 {
		t.Fatalf("one event delivered three times: want 1 message, got %d", n)
	}
	first, err := s.GetMsg(context.Background(), 1)
	if err != nil {
		t.Fatal(err)
	}
	idA := first.Header.Get("Nats-Msg-Id")
	if idA == "" {
		t.Fatal("published without a Msg-Id")
	}

	if code, _ := post(t, r.url, "Bearer "+token, eventB); !is2xx(code) {
		t.Fatalf("answered %d", code)
	}
	if n := streamMsgs(t, js); n != 2 {
		t.Fatalf("a different event: want 2 messages, got %d", n)
	}
	second, err := s.GetMsg(context.Background(), 2)
	if err != nil {
		t.Fatal(err)
	}
	idB := second.Header.Get("Nats-Msg-Id")
	if idB == "" || idB == idA {
		t.Fatalf("event B got id %q, event A %q", idB, idA)
	}
}
