package consumer

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync"
)

// OpenViking is the slice of OpenViking's HTTP API the consumer uses, per
// spike:ov-sync-consumer/7: one file per `content/write` with `wait: true`
// (never `content/batch-write`, which 404s under missing folders), deletes
// through `DELETE /api/v1/fs`, and `fs/ls` with hidden files to judge what a
// folder holds. Never `fs/stat`, which still answers 200 for a removed folder.
type OpenViking struct {
	URL string
	// TokenFile holds the Vault identity token. It is read on every request
	// because the template re-renders it without restarting the task.
	TokenFile string
	HTTP      *http.Client
	// MaxInFlight bounds requests in flight across every caller, workers and
	// catch-up alike. A slot is held for one request only, never while a
	// caller waits on the consumer's tree lock, so a folder delete holding
	// that lock cannot wait on a worker that is waiting on it.
	MaxInFlight int

	slotsOnce sync.Once
	slots     chan struct{}
}

// lsPage is how many entries one fs/ls asks for; has_more says to ask again.
const lsPage = 1000

// Entry is one row of an `fs/ls` listing.
type Entry struct {
	URI   string `json:"uri"`
	IsDir bool   `json:"isDir"`
}

var errNotFound = errors.New("not found")

// errLockBusy marks OpenViking's 409 for a folder lock it gave up waiting
// for, after about 150 ms. The lock can stay held for minutes, probably by
// OpenViking's own folder summary, so the caller retries later rather than
// at once.
var errLockBusy = errors.New("openviking folder lock busy")

// errFolderLeft marks a failed cleanup of the emptied folders above a deleted
// file. An event's redelivery retries it, but catch-up cannot: it never sees a
// folder that holds only summaries.
var errFolderLeft = errors.New("emptied folder left behind")

type envelope struct {
	Status  string          `json:"status"`
	Result  json.RawMessage `json:"result"`
	HasMore bool            `json:"has_more"`
	Error   *struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	} `json:"error"`
}

func (o *OpenViking) do(ctx context.Context, method, path string, query url.Values, body any) (*envelope, error) {
	var reader io.Reader
	contentType := ""
	if body != nil {
		raw, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		reader = bytes.NewReader(raw)
		contentType = "application/json"
	}
	return o.call(ctx, method, path, query, contentType, reader)
}

func (o *OpenViking) call(ctx context.Context, method, path string, query url.Values, contentType string, body io.Reader) (*envelope, error) {
	token, err := os.ReadFile(o.TokenFile)
	if err != nil {
		return nil, fmt.Errorf("openviking token: %w", err)
	}
	u := strings.TrimSuffix(o.URL, "/") + path
	if query != nil {
		u += "?" + query.Encode()
	}
	req, err := http.NewRequestWithContext(ctx, method, u, body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+strings.TrimSpace(string(token)))
	if contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	status, raw, err := o.send(req)
	if err != nil {
		return nil, err
	}
	if status == http.StatusNotFound {
		return nil, errNotFound
	}
	var env envelope
	if err := json.Unmarshal(raw, &env); err != nil || status != http.StatusOK || env.Status != "ok" {
		msg := strings.TrimSpace(string(raw))
		if env.Error != nil {
			msg = env.Error.Code + ": " + env.Error.Message
			if status == http.StatusConflict && strings.Contains(env.Error.Message, "lock acquire timed out") {
				return nil, fmt.Errorf("%s %s: HTTP %d: %s: %w", method, path, status, msg, errLockBusy)
			}
		}
		return nil, fmt.Errorf("%s %s: HTTP %d: %s", method, path, status, msg)
	}
	return &env, nil
}

// send makes one request inside a MaxInFlight slot and reads the whole body
// before giving the slot back.
func (o *OpenViking) send(req *http.Request) (int, []byte, error) {
	if o.MaxInFlight > 0 {
		o.slotsOnce.Do(func() { o.slots = make(chan struct{}, o.MaxInFlight) })
		select {
		case o.slots <- struct{}{}:
		case <-req.Context().Done():
			return 0, nil, req.Context().Err()
		}
		defer func() { <-o.slots }()
	}
	resp, err := o.HTTP.Do(req)
	if err != nil {
		return 0, nil, err
	}
	defer func() { _ = resp.Body.Close() }()
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
	return resp.StatusCode, raw, err
}

// Write creates or replaces one file, creating its missing parent folders.
func (o *OpenViking) Write(ctx context.Context, uri, content string) error {
	_, err := o.do(ctx, http.MethodPost, "/api/v1/content/write", nil, map[string]any{
		"uri":     uri,
		"content": content,
		"wait":    true,
		"timeout": 120,
	})
	return err
}

// Upload stores body byte for byte at folder/name, the way OpenViking ingests
// a file (spike:ov-sync-consumer-binary-upload/1): temp_upload, then add
// resource with `to` set to the resource's own folder. The add creates
// missing parents and replaces whatever that folder held, and it stores the
// bytes even when the image description fails.
func (o *OpenViking) Upload(ctx context.Context, folder, name string, body []byte) error {
	var form bytes.Buffer
	mw := multipart.NewWriter(&form)
	part, err := mw.CreateFormFile("file", name)
	if err != nil {
		return err
	}
	if _, err := part.Write(body); err != nil {
		return err
	}
	if err := mw.Close(); err != nil {
		return err
	}
	env, err := o.call(ctx, http.MethodPost, "/api/v1/resources/temp_upload", nil, mw.FormDataContentType(), &form)
	if err != nil {
		return err
	}
	var temp struct {
		ID string `json:"temp_file_id"`
	}
	if err := json.Unmarshal(env.Result, &temp); err != nil || temp.ID == "" {
		return fmt.Errorf("temp_upload: no temp_file_id in %s", env.Result)
	}
	_, err = o.do(ctx, http.MethodPost, "/api/v1/resources", nil, map[string]any{
		"temp_file_id": temp.ID,
		"to":           folder,
		"source_name":  name,
		"wait":         true,
		"timeout":      120,
	})
	return err
}

// Delete removes uri. A uri that is already gone counts as removed.
func (o *OpenViking) Delete(ctx context.Context, uri string, recursive bool) error {
	q := url.Values{"uri": {uri}, "wait": {"true"}}
	if recursive {
		q.Set("recursive", "true")
	}
	_, err := o.do(ctx, http.MethodDelete, "/api/v1/fs", q, nil)
	if errors.Is(err, errNotFound) {
		return nil
	}
	return err
}

// List returns what the folder uri holds directly, hidden files included,
// following has_more until the listing is complete. found is false when the
// folder does not exist. It never asks for recursive=true, which the server
// stops at three levels and caps without a way to page on.
func (o *OpenViking) List(ctx context.Context, uri string) (entries []Entry, found bool, err error) {
	for {
		q := url.Values{
			"uri":             {uri},
			"show_all_hidden": {"true"},
			"node_limit":      {strconv.Itoa(lsPage)},
			"offset":          {strconv.Itoa(len(entries))},
		}
		env, err := o.do(ctx, http.MethodGet, "/api/v1/fs/ls", q, nil)
		if errors.Is(err, errNotFound) {
			return nil, false, nil
		}
		if err != nil {
			return nil, false, err
		}
		var page []Entry
		if err := json.Unmarshal(env.Result, &page); err != nil {
			return nil, false, fmt.Errorf("ls %s: %w", uri, err)
		}
		for i := range page {
			page[i].URI = strings.TrimSuffix(page[i].URI, "/")
		}
		entries = append(entries, page...)
		if !env.HasMore || len(page) == 0 {
			return entries, true, nil
		}
	}
}

// Walk lists the folder uri and every folder under it, one level at a time.
func (o *OpenViking) Walk(ctx context.Context, uri string) ([]Entry, error) {
	var all []Entry
	for queue := []string{uri}; len(queue) > 0; queue = queue[1:] {
		entries, _, err := o.List(ctx, queue[0])
		if err != nil {
			return nil, err
		}
		for _, e := range entries {
			if e.IsDir {
				queue = append(queue, e.URI)
			}
		}
		all = append(all, entries...)
	}
	return all, nil
}
