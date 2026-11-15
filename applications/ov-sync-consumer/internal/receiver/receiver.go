// Package receiver takes SeaweedFS filer webhook events on loopback and
// publishes each one to JetStream.
//
// The receiver owns the SeaweedFS group's network namespace, so its exit fails
// the whole alloc and takes S3 down with it. Nothing outside the process may
// make it exit: it starts with NATS unreachable, reconnects forever, and
// answers non-2xx while it cannot publish. The webhook retries, and the
// consumer's catch-up pass repairs what is dropped.
package receiver

import (
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"

	"github.com/JasperHG90/localstack/applications/ov-sync-consumer/internal/stream"
)

const maxBody = 1 << 20

type Config struct {
	NATSURL string
	// TokenFile is read on every request, so a rotated token takes effect
	// when the template re-renders it, without restarting the receiver.
	TokenFile      string
	PublishTimeout time.Duration
	Log            *slog.Logger
}

// Serve answers webhook POSTs on ln until ctx ends. It returns early only if
// the NATS URL cannot be parsed or the HTTP server fails.
func Serve(ctx context.Context, ln net.Listener, cfg Config) error {
	nc, err := nats.Connect(cfg.NATSURL,
		nats.Name("ov-sync-receiver"),
		nats.RetryOnFailedConnect(true),
		nats.MaxReconnects(-1),
		nats.ReconnectWait(2*time.Second),
		// No buffering while disconnected: a publish fails at once, so the
		// webhook gets its non-2xx inside its own timeout.
		nats.ReconnectBufSize(-1),
	)
	if err != nil {
		return fmt.Errorf("nats: %w", err)
	}
	defer nc.Close()
	js, err := jetstream.New(nc)
	if err != nil {
		return fmt.Errorf("jetstream: %w", err)
	}

	srv := &http.Server{
		Handler:           &handler{cfg: cfg, nc: nc, js: js},
		ReadHeaderTimeout: 5 * time.Second,
	}
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdown)
	}()
	if err := srv.Serve(ln); !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

type handler struct {
	cfg Config
	nc  *nats.Conn
	js  jetstream.JetStream
}

func (h *handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST only", http.StatusMethodNotAllowed)
		return
	}
	token, err := os.ReadFile(h.cfg.TokenFile)
	want := bytes.TrimSpace(token)
	if err != nil || len(want) == 0 {
		h.cfg.Log.Error("no bearer token to check against", "file", h.cfg.TokenFile, "err", err)
		http.Error(w, "receiver has no token", http.StatusInternalServerError)
		return
	}
	got, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
	if !ok || subtle.ConstantTimeCompare([]byte(got), want) != 1 {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, maxBody))
	if err != nil {
		http.Error(w, "unreadable body", http.StatusBadRequest)
		return
	}
	id, err := MsgID(body)
	if err != nil {
		http.Error(w, "body is not JSON", http.StatusBadRequest)
		return
	}
	if h.nc.Status() != nats.CONNECTED {
		http.Error(w, "nats unavailable", http.StatusServiceUnavailable)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), h.cfg.PublishTimeout)
	defer cancel()
	if _, err := h.js.Publish(ctx, stream.EventsSubject, body, jetstream.WithMsgID(id)); err != nil {
		h.cfg.Log.Warn("publish failed", "err", err)
		http.Error(w, "publish failed", http.StatusServiceUnavailable)
		return
	}
	w.WriteHeader(http.StatusOK)
}

// MsgID is the hash of the event's canonical JSON: keys sorted, numbers kept
// as written. A redelivered webhook carries the same event, so it gets the
// same id and JetStream drops the copy inside its dedupe window.
func MsgID(body []byte) (string, error) {
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return "", err
	}
	if _, ok := v.(map[string]any); !ok {
		return "", errors.New("event is not a JSON object")
	}
	canonical, err := json.Marshal(v)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(canonical)
	return hex.EncodeToString(sum[:]), nil
}
