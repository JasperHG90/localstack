"""Mirror git-tracked folders into one prefix of an S3 bucket, using a manifest.

The manifest, `<prefix>/_state/manifest.json`, maps each synced repo-relative
path to its sha256. A run uploads files whose hash differs from it and deletes
keys it lists whose file is gone, so the credential never needs to list the
bucket. After any change it writes the manifest as the bucket now stands: a
failed upload keeps its old entry and a failed delete keeps its entry, so the
next run retries exactly those. It also writes it every CHECKPOINT uploads,
so a run killed partway keeps its progress. A failed checkpoint write is
reported but does not fail the run. Any other failure exits non-zero.

Standard library only; S3 calls go through the `aws` CLI on the runner.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

MANIFEST = "_state/manifest.json"
# The first sync of a repo uploads every file, one aws process each.
WORKERS = 32
# Uploads between manifest writes, so a run the job timeout kills keeps what
# it uploaded and the next run starts from there.
CHECKPOINT = 50


class S3:
    def __init__(self, endpoint: str, bucket: str) -> None:
        self.endpoint = endpoint
        self.bucket = bucket

    def call(self, op: str, key: str, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "aws",
                "--endpoint-url",
                self.endpoint,
                "s3api",
                op,
                "--bucket",
                self.bucket,
            ]
            + ["--key", key, *extra],
            capture_output=True,
            text=True,
            check=False,
        )


def tracked_hashes(folders: list[str]) -> dict[str, str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", *folders],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    hashes = {}
    for path in filter(None, listed.split("\0")):
        file = Path(path)
        # A submodule is listed as a directory; a file deleted but not yet
        # committed is listed and absent. Neither has content to sync.
        if file.is_file():
            hashes[path] = hashlib.sha256(file.read_bytes()).hexdigest()
    return hashes


def read_manifest(s3: S3, key: str, scratch: Path) -> dict[str, str]:
    out = scratch / "manifest.json"
    result = s3.call("get-object", key, str(out))
    if result.returncode == 0:
        manifest: dict[str, str] = json.loads(out.read_text())
        return manifest
    if "NoSuchKey" in result.stderr:
        return {}
    sys.exit(f"reading {key} failed: {result.stderr.strip()}")


def write_manifest(s3: S3, key: str, state: dict[str, str], scratch: Path) -> bool:
    body = scratch / "new-manifest.json"
    body.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n")
    result = s3.call("put-object", key, "--body", str(body))
    if result.returncode != 0:
        print(f"::error::writing the manifest failed: {result.stderr.strip()}")
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", required=True, help="<owner>/<repo>")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument(
        "--folders", required=True, help="whitespace-separated, repo-relative"
    )
    args = parser.parse_args()

    prefix = args.prefix.strip("/") + "/"
    s3 = S3(args.endpoint, args.bucket)
    with tempfile.TemporaryDirectory() as tmp:
        old = read_manifest(s3, prefix + MANIFEST, Path(tmp))
        new = tracked_hashes(args.folders.split())
        uploads = sorted(p for p, digest in new.items() if old.get(p) != digest)
        deletes = sorted(p for p in old if p not in new)

        def upload(path: str) -> tuple[str, subprocess.CompletedProcess[str]]:
            return path, s3.call("put-object", prefix + path, "--body", path)

        def delete(path: str) -> tuple[str, subprocess.CompletedProcess[str]]:
            return path, s3.call("delete-object", prefix + path)

        state = dict(old)
        failed = 0
        with ThreadPoolExecutor(WORKERS) as pool:
            # In completion order, so one slow upload does not hold back the
            # checkpoints for the uploads that finished after it.
            running = [pool.submit(upload, path) for path in uploads]
            for done, future in enumerate(as_completed(running), 1):
                path, result = future.result()
                if result.returncode == 0:
                    state[path] = new[path]
                    print(f"uploaded {prefix}{path}")
                else:
                    failed += 1
                    print(f"::error::upload of {path} failed: {result.stderr.strip()}")
                if done % CHECKPOINT == 0:
                    write_manifest(s3, prefix + MANIFEST, state, Path(tmp))
            for path, result in pool.map(delete, deletes):
                if result.returncode == 0:
                    del state[path]
                    print(f"deleted {prefix}{path}")
                else:
                    failed += 1
                    print(f"::error::delete of {path} failed: {result.stderr.strip()}")

        print(f"{len(uploads)} to upload, {len(deletes)} to delete, {failed} failed")
        if state != old and not write_manifest(s3, prefix + MANIFEST, state, Path(tmp)):
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
