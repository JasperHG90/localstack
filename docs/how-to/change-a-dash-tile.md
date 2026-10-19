---
description: Add, remove or reorder the tiles and headings https://dash.lab.orangecluster.nl shows.
stale_after: 2027-01-19
sources:
  - resource: deployments/applications/services/dash/tiles.json
  - resource: deployments/applications/services/dash.hcl
  - resource: deployments/applications/services.tf
---

# How to add, remove, or reorder a dash tile

## Introduction

This changes which tiles `https://dash.lab.orangecluster.nl` shows, under
which heading, and in what order. The tiles come from one config file, and
applying it redeploys the job.

## Prerequisites

- A Terraform setup that can run `just apply` in `deployments/applications/`.
- The fields a group and a tile carry, listed in
  [dash](../reference/dash.md#tilesjson).

## Directions

### Step 1: Edit the tiles file

Edit `deployments/applications/services/dash/tiles.json`. It is an array of
groups, and array order is display order, for the headings and for the
tiles inside each one. Moving a tile up the page is moving it up the file.

Two characters are forbidden anywhere in the file: `${` and `%{`. Terraform
splices this config into a Nomad heredoc
(`deployments/applications/services/dash.hcl`), where both open a template.
An expression-shaped `${...}` fails `terraform apply`. `%{ ... }` is worse:
it parses cleanly and rewrites the text on its way to the job. A bare `$` is
fine and already ships. The backend suite
(`deployments/applications/services/dash/backend/tests/test_tiles.py`)
asserts both openers are absent.

### Step 2: Apply the change

Apply through `deployments/applications`'s normal `just apply`. The file
round-trips through Terraform's `jsondecode`/`jsonencode`, so a JSON syntax
error fails `terraform plan` rather than reaching the job.

## Additional resources

- [dash](../reference/dash.md)
- [How to rebuild and deploy the dash images](rebuild-the-dash-images.md)
