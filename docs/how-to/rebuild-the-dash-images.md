# How to rebuild and deploy the dash images

## Introduction

This builds new `dash-backend` and `dash-frontend` images, pushes them, and
deploys them. Each image builds from its own single-directory context
(`deployments/applications/services/dash/backend/` and
`deployments/applications/services/dash/frontend/`), and neither depends
on `cli/`.

## Prerequisites

- Push access to `ghcr.io/jasperhg90`. The recipes log in with
  `GITHUB_USER` and `GITHUB_WRITE_PAT` from your environment.
- Docker, which the recipes use to build `linux/arm64` images.
- A Terraform setup that can run `just apply` in `deployments/applications/`.

## Directions

### Step 1: Bump the image tags

Both tags are read out of `services.tf`, so bump them there before
rebuilding. They are `dash_backend_version` and `dash_frontend_version`.

### Step 2: Rebuild the backend image

```
cd deployments/applications
just rebuild_dash_backend
```

`rebuild_dash_backend` builds and pushes
`ghcr.io/jasperhg90/dash-backend:<dash_backend_version>`.

### Step 3: Rebuild the frontend image

```
just rebuild_dash_frontend
```

`rebuild_dash_frontend` builds and pushes
`ghcr.io/jasperhg90/dash-frontend:<dash_frontend_version>`.

### Step 4: Deploy the new images

```
just apply
```

`just apply` deploys the new images.

## Additional resources

- [dash](../reference/dash.md)
- [How to add, remove, or reorder a dash tile](change-a-dash-tile.md)
