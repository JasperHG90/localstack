# EDP Compatibility Processor - Reference Implementation

This repository contains reference implementations for the **EDP Compatibility Processor**. As a core component of the EDP Sys Layer architecture, the **Compatibility Processor** is responsible for receiving events from source systems, applying source-dependent ingestion logic, validating events against data contracts, and publishing validated events to the compatibility layer output topic.

## Release cycle

For the release cycle, please check the individual repositories in '/patterns'

## About

> [!IMPORTANT]
> **This is a reference implementation repository** designed to demonstrate how VSTs should implement their own Compatibility Processors. VSTs should fork or copy this repository and customize it for their specific source systems and data contracts.

> [!WARNING]
> As this is a reference implementation, VSTs should carefully scrutinize any code they copy to ensure it is applicable to their own use case.

This reference implementation serves as a guide and example for VSTs on how to integrate their source systems with the system layer, demonstrating technical interoperability and providing a clear path for onboarding data sources.

![](./assets/currently_implemented.png)

## Table of Contents
* [Architectural Context](#architectural-context)
* [Core Concepts](#core-concepts)
* [Patterns Implemented](#patterns-implemented)
* [Event Flows](#event-flows)
  * [Standard Event Flow](#standard-event-flow)
  * [Failed Event Flow (DLQ)](#failed-event-flow-dlq)
  * [Batch Event Flow](#batch-event-flow)
* [Getting Started Guide for VSTs](#getting-started-guide-for-vst-teams)
* [API Description](#api-description)
* [Configuration](#configuration)
* [Development and Testing](#development-and-testing)
* [Deployment](#deployment)
* [Related Repositories](#related-repositories)
* [Project Structure](#project-structure)
* [Recipes](#recipes)
* [Support and Contribution](#support-and-contribution)

## Architectural Context

The Compatibility Processor sits at the entry point of the EDP Sys Layer, serving as the bridge between external source systems and the standardized data platform. This repository focuses on demonstrating how VSTs can implement their own compatibility processors to integrate with the system layer. The Sys Layer is a source-aligned layer, meaning that it is designed to ingest data from a single source system and enforce data contracts for that source.

This repository is intended to implement multiple commonly-used patterns for compatibility processors.

## Core Concepts

Regardless of the specific pattern, a Compatibility Processor has a set of core responsibilities:

* **Source System Integration:** Provides a starting point for integrating with various source systems.
* **Source-Dependent Ingestion Logic:** Includes customizable modules for data extraction and transformation.
* **Contract Validation:** Integrates with the data contract registry for event validation.
* **Event Publishing:** Publishes validated events to the compatibility layer output topic.
* **DLQ Handling:** Sends failed events to a Dead Letter Queue for investigation and reprocessing.
* **Batch Processing:** Supports either single or batch event processing.
* **Monitoring & Health Checks:** Includes health and readiness endpoints for operational monitoring.

## Patterns Implemented

This repository contains implementations of various patterns for compatibility processors. Each pattern is located in its own directory under `patterns/`.

*   **[EventArc-Triggered Pub/Sub Processor](./patterns/compatibility_processor_eventarc_pubsub/README.md)**: A pattern for processing files from GCS, triggered by EventArc and Pub/Sub. ![Release Cycle](https://img.shields.io/badge/Release%20Cycle-BETA%20RELEASE-orange.svg)

## Configuration

The Compatibility Processor is configured via environment variables. The following table lists the environment variables that are automatically injected by the EDP Sys Layer Terraform pattern.

> [!NOTE]
> These environment variables are provisioned by the [Sys Layer Terraform pattern](https://github.com/rituals-data/edp-tf-patterns/blob/main/projects/rit-edp-sys-layer/cloud_run.tf#L53-L75).

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `CLP_NAME_PREFIX` | An uppercase prefix for naming conventions. | `TEST` |
| `CLP_ACTIVE_VERSIONS` | A comma-separated list of active, supported versions. | `V1,V2,V3` |
| `CLP_DATACONTRACT_MODELS` | A comma-separated list of uppercase data contract models. | `DOMAIN_CONTRACT_MODEL_V1` |
| `CLP_LATEST_VERSION` | The version tag to be considered the "latest". | `V3` |
| `LOG_LEVEL` | The logging level for the application. | `DEBUG` |
| `CONTRACT_REGISTRY_PATH` | The GCS path to the data contract registry. | `gs://rit-edp-data-contracts-test-68eff307/datacontracts` |
| `CLP_OUTPUT_TOPIC` | The output topic for validated events. | `projects/test-project/topics/comp-layer-output` |
| `CLP_DLQ_TOPIC` | The Dead Letter Queue topic for invalid events. | `projects/test-project/topics/comp-layer-dlq` |
| `GCP_PROJECT_ID` | The Google Cloud Project ID. | `rit-edp-sys-layer-test` |
| `ENVIRONMENT` | The deployment environment. | `test` |
| `LOCATION` | The GCP region where the service is deployed. | `europe-west4` |
| `SERVICE_NAME` | The name of the Cloud Run service. | `compatibility_processor` |

## Development and Testing

### Prerequisites
- Python 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker (for integration tests)
- Google Cloud SDK (for authentication)

### Setup
```bash
# Install dependencies
make setup

# Run unit tests
make unit_test

# Run integration tests (requires Docker)
make integration_test

# Build Docker image
make docker_build
```


## CI/CD and Testing

### CI/CD Pipeline

The CI/CD pipeline is defined in `.github/workflows/CI.yaml` and consists of the following stages:

1.  **Pre-commit Checks**: Ensures code quality and style consistency.
2.  **Unit Tests**: Runs unit tests across multiple Python versions.
3.  **Integration Tests**: Verifies the interaction between components in a local, emulated environment.
4.  **Build and Push**: Builds a Docker image and pushes it to the Google Artifact Registry.
5.  **Deploy**: Deploys the Docker image to a Cloud Run service in the development environment.
6.  **End-to-End Tests**: Runs end-to-end tests against the deployed service to validate the entire workflow.

The pipeline uses reusable GitHub Actions and Workload Identity Federation for secure authentication with Google Cloud.

### Testing Strategy

The project employs a multi-layered testing strategy to ensure code quality and reliability:

*   **Unit Tests**: Focus on individual functions and classes in isolation to verify their correctness.
*   **Integration Tests**: Test the interaction between different components of the service in a controlled, local environment using emulators for services like Pub/Sub and GCS. These tests ensure that the components work together as expected.
*   **End-to-End Tests**: Verify the entire event flow in a deployed environment. These tests simulate real-world scenarios by uploading a file to GCS and verifying that it is processed correctly by the entire sys layer, with data landing in the expected BigQuery tables and Pub/Sub topics. The end-to-end tests cover both successful processing and error handling, such as bad data being routed to the Dead Letter Queue (DLQ).

> [!NOTE]
> The end-to-end tests require specific IAM permissions (`principalSets`) to be configured for the test environment. These permissions are provisioned in the `rit-edp-sys-layer` pattern in repository `https://github.com/rituals-data/edp-tf-patterns`.

## Deployment

This repository provides an example of how a compatibility processor can be deployed. VSTs should adapt this process to fit their own deployment strategies.

The example deployment process is automated via the `.github/workflows/release.yaml` GitHub Actions workflow. When a new release is published on GitHub, the workflow automatically builds and pushes a versioned Docker image to the Google Artifact Registry.

## Project Structure

This repository is structured as a monorepo that contains multiple Python packages within a single repository. This is also referred to as a "workspace" in the `uv` documentation. See the official `uv` [documentation](https://docs.astral.sh/uv/concepts/projects/workspaces/) for more information. This approach allows for shared libraries and a centralized location for managing different compatibility processor patterns.

The main components are:
-   `patterns/`: Contains the different compatibility processor patterns. Each pattern is a self-contained Python package.
-   `patterns/shared/`: A shared library that contains common code used by the different patterns.
-   `recipes/`: Contains useful code snippets and examples that can be used by VSTs but are not part of a specific pattern.
-   `Dockerfile`: A multi-stage Dockerfile is used to build the container image for a specific pattern. The `PACKAGE_NAME` build argument is used to select which pattern to install and run.

## Recipes

The `recipes/` directory contains a collection of useful patterns and code snippets that can be helpful for VSTs when implementing their own compatibility processors. These recipes are not fully implemented patterns but rather examples of how to solve common problems.

## Related Repositories

- **[edp-datacontracts-runtime](https://github.com/rituals-data/edp-datacontracts-runtime)**: Python package for contract registry interaction and validation.
- **[edp-cloudevent-publisher](https://github.com/rituals-data/edp-cloudevent-publisher)**: Library for publishing CloudEvents.

## Support and Contribution

For technical support and questions, please use the designated Slack channel. We welcome contributions to this repository. Please review our contributing guidelines before submitting a pull request.
