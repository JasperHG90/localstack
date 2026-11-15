package consumer

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

// Mapping maps a bucket prefix `<owner>/<repo>/` to the OpenViking folder its
// files land in, `viking://user/jasper/resources/projects/<repo>/`. A key under
// no mapped prefix is skipped.
type Mapping map[string]string

// LoadMapping reads a JSON object of prefix to folder URI.
func LoadMapping(path string) (Mapping, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var in map[string]string
	if err := json.Unmarshal(raw, &in); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	m := Mapping{}
	for prefix, root := range in {
		parts := strings.Split(strings.TrimSuffix(prefix, "/"), "/")
		if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
			return nil, fmt.Errorf("prefix %q is not <owner>/<repo>/", prefix)
		}
		if !strings.HasPrefix(root, "viking://") {
			return nil, fmt.Errorf("folder %q for %q is not a viking:// URI", root, prefix)
		}
		m[parts[0]+"/"+parts[1]+"/"] = strings.TrimSuffix(root, "/") + "/"
	}
	if len(m) == 0 {
		return nil, fmt.Errorf("%s maps no prefix", path)
	}
	return m, nil
}

// Resolve returns the OpenViking URI for an object key and the mapped folder
// it sits under. ok is false for an unmapped prefix, a folder marker, and
// anything under `<owner>/<repo>/_state/`, which CI writes for itself.
func (m Mapping) Resolve(key string) (uri, root string, ok bool) {
	parts := strings.SplitN(key, "/", 3)
	if len(parts) != 3 {
		return "", "", false
	}
	root, ok = m[parts[0]+"/"+parts[1]+"/"]
	rest := parts[2]
	if !ok || rest == "" || strings.HasSuffix(rest, "/") || rest == "_state" || strings.HasPrefix(rest, "_state/") {
		return "", "", false
	}
	return root + rest, root, true
}
