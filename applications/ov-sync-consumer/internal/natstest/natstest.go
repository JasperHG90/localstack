// Package natstest runs an in-process NATS server with JetStream for tests.
// Only test files import it, so nats-server never reaches the binary.
package natstest

import (
	"testing"
	"time"

	"github.com/nats-io/nats-server/v2/server"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
)

// Run starts a JetStream server on a random port and stops it when the test
// ends. Call Shutdown on the result to stop it earlier.
func Run(t *testing.T) *server.Server {
	t.Helper()
	return RunOnPort(t, -1)
}

// RunOnPort is Run on a fixed port.
func RunOnPort(t *testing.T, port int) *server.Server {
	t.Helper()
	s, err := server.NewServer(&server.Options{
		Host:      "127.0.0.1",
		Port:      port,
		JetStream: true,
		StoreDir:  t.TempDir(),
		NoLog:     true,
		NoSigs:    true,
	})
	if err != nil {
		t.Fatalf("nats server: %v", err)
	}
	go s.Start()
	if !s.ReadyForConnections(10 * time.Second) {
		t.Fatal("nats server did not start")
	}
	t.Cleanup(s.Shutdown)
	return s
}

// Connect returns a JetStream client for s, closed when the test ends.
func Connect(t *testing.T, s *server.Server) (*nats.Conn, jetstream.JetStream) {
	t.Helper()
	nc, err := nats.Connect(s.ClientURL())
	if err != nil {
		t.Fatalf("nats connect: %v", err)
	}
	t.Cleanup(nc.Close)
	js, err := jetstream.New(nc)
	if err != nil {
		t.Fatalf("jetstream: %v", err)
	}
	return nc, js
}
