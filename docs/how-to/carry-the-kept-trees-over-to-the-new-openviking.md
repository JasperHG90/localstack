---
description: "Copy clips, blogs, blog-scraper and leo from the old OpenViking store into the new one, re-index them and check the result."
stale_after: 2027-01-20
sources:
  - resource: deployments/applications/services/ov-carry-over.hcl
  - resource: scripts/ov_carry_over.py
  - resource: deployments/applications/storage.tf
  - resource: deployments/applications/services/hermes/skills/productivity/blog-scraper/SKILL.md
---

# How to carry the kept trees over to the new OpenViking

## Introduction

This copies `clips/`, `blogs/`, `leo/` and `blog-scraper/` from the old
OpenViking bucket into the new one, with `blog-scraper/` merged into
`blogs/`, then makes them searchable in the new instance. Run it once, after
the cutover to the v2 store. Each step can run again: the copy only adds
missing keys, and the script's checks can run on their own.

## Prerequisites

- The cutover is done, and you kept the `openviking.lsf` baseline from its
  step 2, see
  [the OpenViking deployment README](../../deployments/applications/services/openviking/README.md#cutover-to-the-v2-store).
- A Nomad token that can dispatch jobs and `alloc exec` into `hermes`, see
  [How to sign in to Nomad with Vault](sign-in-to-nomad-with-vault.md).
- `OV_URL` and `OV_TOKEN` set as in
  [How to call OpenViking from the CLI](call-openviking-from-the-cli.md).
- A Vault login that reads `secret/default/openviking/db`, see
  [How to log in to Vault](log-in-to-vault.md).
- `psql`, or Docker to run the `postgres:18.0` image, from
  [postgresql.org](https://www.postgresql.org/download/).

## Directions

### Step 1: Check that the daily blog scrape is paused

```console
$ nomad alloc exec -job hermes -task hermes hermes cron list
```

`daily-blog-scrape` should show as paused. If it is not, pause it with
`hermes cron pause <id>`, using the id from the list. A run before step 2
lands saves under `blog-scraper/`, which step 4 then reports.

### Step 2: Apply the applications root

```console
$ cd deployments/applications
$ just apply
```

The plan adds the `ov-carry-over` storage user, its key, its Vault secret and
the `ov-carry-over` job, and changes the `hermes` job, which ships the
blog-scraper skill that now saves under `blogs/<source>/`.

### Step 3: Dispatch the copy job

```console
$ nomad job dispatch ov-carry-over
$ nomad job status ov-carry-over
```

Wait until the dispatched child shows `dead`, then read its exit code:

```console
$ nomad alloc status <alloc id>
```

The `Terminated` line under Recent Events carries `Exit Code: N`.

`0` means every tree copied and checked. Any other code names one failure,
listed in [OpenViking](../reference/openviking.md#carry-over-from-the-old-store).
Fix the cause and dispatch again.

### Step 4: Re-index and check

From the repository root:

```console
$ export PGPASSWORD=$(vault kv get -field=password secret/default/openviking/db)
$ python3 scripts/ov_carry_over.py --old-listing openviking.lsf \
    --psql "docker run --rm -i -e PGPASSWORD postgres:18.0 psql postgresql://openviking@192.168.2.30:5432/openviking"
```

It prints `done` per re-index, then `pass` per check, and exits 0. A
`FAIL` line names what is wrong. Files saved since the cutover show as
`note` lines and do not fail it. If a name under `resources/` that you
created on purpose fails the check, pass it with `--allow <name>`. To repeat
only the checks, add `--check-only`.

### Step 5: Compare the old store with the baseline

Repeat the two `rclone` commands from step 2 of the cutover in
`deployments/applications/services/openviking/README.md` and `diff` them
against `openviking.lsf` and `openviking.md5`. There should be no
difference.

### Step 6: Resume the daily blog scrape

```console
$ nomad alloc exec -job hermes -task hermes hermes cron resume <id>
```

## Additional resources

- [OpenViking](../reference/openviking.md#carry-over-from-the-old-store)
- `.okf/decisions/0022-openviking-carry-over-copies-storage-and-re-indexes.md`
