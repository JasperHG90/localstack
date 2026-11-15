// ov-sync-consumer turns SeaweedFS filer events on the ov-sync bucket into
// OpenViking writes and deletes through NATS JetStream. One binary, two
// subcommands: `receiver` runs beside SeaweedFS and `consumer` on radxa.
// Both are configured through the environment; see the jobspecs.
package main

import (
	"context"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"
	"golang.org/x/time/rate"

	"github.com/JasperHG90/localstack/applications/ov-sync-consumer/internal/consumer"
	"github.com/JasperHG90/localstack/applications/ov-sync-consumer/internal/receiver"
)

func main() {
	log := slog.New(slog.NewTextHandler(os.Stderr, nil))
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: ov-sync-consumer receiver|consumer")
		os.Exit(2)
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	var err error
	switch os.Args[1] {
	case "receiver":
		err = runReceiver(ctx, log)
	case "consumer":
		err = runConsumer(ctx, log)
	default:
		err = fmt.Errorf("unknown subcommand %q", os.Args[1])
	}
	if err != nil {
		log.Error("exiting", "err", err)
		os.Exit(1)
	}
}

func runReceiver(ctx context.Context, log *slog.Logger) error {
	addr := env("RECEIVER_ADDR", "127.0.0.1:20500")
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	log.Info("receiver listening", "addr", addr)
	return receiver.Serve(ctx, ln, receiver.Config{
		NATSURL:        must("NATS_URL"),
		TokenFile:      must("RECEIVER_TOKEN_FILE"),
		PublishTimeout: 3 * time.Second,
		Log:            log,
	})
}

func runConsumer(ctx context.Context, log *slog.Logger) error {
	mapping, err := consumer.LoadMapping(must("OV_SYNC_MAP_FILE"))
	if err != nil {
		return err
	}
	s3Endpoint := must("S3_ENDPOINT")
	roleARN := must("AWS_ROLE_ARN")
	// minio-go's web identity exchange: the Nomad workload JWT for an hour of
	// SeaweedFS credentials under this job's own role, the way tempo does it.
	creds, err := credentials.NewSTSWebIdentity("http://"+s3Endpoint,
		func() (*credentials.WebIdentityToken, error) { return nil, nil },
		credentials.WithWebIdentityTokenFile(must("AWS_WEB_IDENTITY_TOKEN_FILE")),
		func(i *credentials.STSWebIdentity) { i.RoleARN = roleARN },
	)
	if err != nil {
		return err
	}
	s3, err := minio.New(s3Endpoint, &minio.Options{Creds: creds, Region: "us-east-1"})
	if err != nil {
		return err
	}

	perSecond, err := strconv.ParseFloat(env("RATE_PER_SECOND", "2"), 64)
	if err != nil {
		return fmt.Errorf("RATE_PER_SECOND: %w", err)
	}
	pool := envInt("POOL_SIZE", 4)
	c := &consumer.Consumer{
		S3:     s3,
		Bucket: env("S3_BUCKET", "ov-sync"),
		OV: &consumer.OpenViking{
			URL:         must("OV_URL"),
			TokenFile:   must("OV_TOKEN_FILE"),
			HTTP:        &http.Client{Timeout: 150 * time.Second},
			MaxInFlight: pool,
		},
		Map:   mapping,
		Pool:  pool,
		Limit: rate.NewLimiter(rate.Limit(perSecond), 1),
		// 20 tries, the gap doubling from 2 s to 30 s, span about eight
		// minutes, so an OpenViking outage of five is ridden out by retries
		// and the catch-up pass is only the backstop.
		MaxTries: envInt("MAX_TRIES", 20),
		Backoff:  consumer.Backoff(2*time.Second, 30*time.Second),
		AckWait:  5 * time.Minute,
		Log:      log,
	}

	nc, err := nats.Connect(must("NATS_URL"),
		nats.Name("ov-sync-consumer"),
		nats.RetryOnFailedConnect(true),
		nats.MaxReconnects(-1),
		nats.ReconnectWait(2*time.Second),
	)
	if err != nil {
		return err
	}
	defer nc.Close()
	js, err := jetstream.New(nc)
	if err != nil {
		return err
	}

	interval, err := time.ParseDuration(env("CATCHUP_INTERVAL", "15m"))
	if err != nil {
		return fmt.Errorf("CATCHUP_INTERVAL: %w", err)
	}
	go func() {
		for {
			if err := c.CatchUp(ctx); err != nil && ctx.Err() == nil {
				log.Warn("catch-up pass failed", "err", err)
			}
			select {
			case <-ctx.Done():
				return
			case <-time.After(interval):
			}
		}
	}()

	for {
		err := c.Run(ctx, js)
		if ctx.Err() != nil {
			return nil
		}
		log.Warn("consumer stopped, starting again", "err", err)
		select {
		case <-ctx.Done():
			return nil
		case <-time.After(5 * time.Second):
		}
	}
}

func env(name, fallback string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return fallback
}

func must(name string) string {
	v := os.Getenv(name)
	if v == "" {
		fmt.Fprintf(os.Stderr, "%s is not set\n", name)
		os.Exit(2)
	}
	return v
}

func envInt(name string, fallback int) int {
	n, err := strconv.Atoi(env(name, strconv.Itoa(fallback)))
	if err != nil || n < 1 {
		fmt.Fprintf(os.Stderr, "%s must be a positive integer\n", name)
		os.Exit(2)
	}
	return n
}
