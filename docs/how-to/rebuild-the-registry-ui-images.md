# How to rebuild and deploy the registry-ui images

## Introduction

This builds new `registry-ui` backend and frontend images, pushes them, and
deploys them. Each image builds from its own single-directory context
(`services/registry-ui/backend/` and `services/registry-ui/frontend/`).

## Prerequisites

- Push access to `ghcr.io/jasperhg90`. The recipes log in with
  `GITHUB_USER` and `GITHUB_WRITE_PAT` from your environment.
- Docker, which the recipes use to build `linux/arm64` images.
- A Terraform setup that can run `just apply` in `deployments/applications/`,
  and in `deployments/infrastructure/` for a first deployment.

## Directions

### Step 1: Bump the image tags

Both tags are read out of `services.tf`, so bump them there before
rebuilding. They are `registry_ui_backend_version` and
`registry_ui_frontend_version`.

### Step 2: Apply the infrastructure root on a first deployment

The `registry_ui_data` volume and the oauth2-proxy instance live in
`deployments/infrastructure`, so a first deployment applies that root too.

### Step 3: Rebuild the images

```
cd deployments/applications
just rebuild_registry_ui_backend
just rebuild_registry_ui_frontend
```

### Step 4: Deploy the new images

```
just apply
```

## Additional resources

- [registry-ui](../reference/registry-ui.md)
- [Why registry-ui stays cheap, and where it stops scaling](../explanation/registry-ui-cost.md)
