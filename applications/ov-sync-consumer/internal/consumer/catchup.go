package consumer

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/minio/minio-go/v7"
)

// CatchUp compares each mapped prefix with its OpenViking folder and repairs
// what lost events left behind: it writes a bucket file missing from
// OpenViking and deletes an OpenViking file whose object is gone. It only
// compares which files exist; a lost update to a file both sides hold waits
// for the next event on that file. A file at U while U/base(U) is wanted is
// an image's old plain copy, which the image's upload deletes, so the pass
// leaves it alone.
func (c *Consumer) CatchUp(ctx context.Context) error {
	var errs []error
	for prefix, root := range c.Map {
		if err := c.catchUpPrefix(ctx, prefix, root); err != nil {
			errs = append(errs, fmt.Errorf("%s: %w", prefix, err))
		}
	}
	return errors.Join(errs...)
}

func (c *Consumer) catchUpPrefix(ctx context.Context, prefix, root string) error {
	want := map[string]string{}
	for obj := range c.S3.ListObjects(ctx, c.Bucket, minio.ListObjectsOptions{Prefix: prefix, Recursive: true}) {
		if obj.Err != nil {
			return fmt.Errorf("list bucket: %w", obj.Err)
		}
		if uri, _, ok := c.Map.Resolve(obj.Key); ok {
			want[uri] = obj.Key
		}
	}
	entries, err := c.OV.Walk(ctx, strings.TrimSuffix(root, "/"))
	if err != nil {
		return err
	}
	have := files(entries)

	var errs []error
	for uri, key := range want {
		if !have[uri] {
			errs = append(errs, c.skipBusy(c.Apply(ctx, key)))
		}
	}
	for uri := range have {
		if _, ok := want[uri]; ok {
			continue
		}
		if _, ok := want[uri+"/"+base(uri)]; ok {
			continue
		}
		unlock := c.keys.lock(uri)
		if err := c.Limit.Wait(ctx); err != nil {
			unlock()
			return err
		}
		errs = append(errs, c.skipBusy(c.remove(ctx, uri, root)))
		unlock()
	}
	return errors.Join(errs...)
}

// skipBusy logs a folder lock conflict on a file and drops it, since the
// next pass tries the file again. A conflict on folder cleanup stays an
// error: the next pass would not see that folder.
func (c *Consumer) skipBusy(err error) error {
	if errors.Is(err, errLockBusy) && !errors.Is(err, errFolderLeft) {
		c.Log.Info("folder busy, catch-up retries next pass", "err", err)
		return nil
	}
	return err
}

// files picks the files out of a listing, leaving out folders and
// OpenViking's own summaries. An entry counts as a folder when ls says so or
// when another entry sits under it.
func files(entries []Entry) map[string]bool {
	dirs := map[string]bool{}
	for _, e := range entries {
		if e.IsDir {
			dirs[e.URI] = true
		}
		dirs[parent(e.URI)] = true
	}
	out := map[string]bool{}
	for _, e := range entries {
		if !dirs[e.URI] && !isSummary(parent(e.URI), e.URI) {
			out[e.URI] = true
		}
	}
	return out
}
