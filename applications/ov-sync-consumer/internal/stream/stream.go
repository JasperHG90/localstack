// Package stream names the JetStream stream the receiver publishes to and the
// consumer reads from, so both subcommands agree on it.
package stream

import (
	"context"
	"time"

	"github.com/nats-io/nats.go/jetstream"
)

const (
	Name          = "OV_SYNC"
	EventsSubject = "ovsync.events"
	DeadSubject   = "ovsync.dead"
)

// Config is the stream the consumer creates. The receiver never creates it,
// so it stays small: until the consumer has run once, the receiver's
// publishes fail and the webhook answers non-2xx.
func Config() jetstream.StreamConfig {
	return jetstream.StreamConfig{
		Name:       Name,
		Subjects:   []string{EventsSubject, DeadSubject},
		Storage:    jetstream.FileStorage,
		Retention:  jetstream.LimitsPolicy,
		Discard:    jetstream.DiscardOld,
		MaxAge:     7 * 24 * time.Hour,
		MaxBytes:   64 << 20,
		Duplicates: 2 * time.Minute,
	}
}

// Ensure creates the stream, or updates it to Config.
func Ensure(ctx context.Context, js jetstream.JetStream) (jetstream.Stream, error) {
	return js.CreateOrUpdateStream(ctx, Config())
}
