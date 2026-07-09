# LabelSea

**LabelSea** is an open-source data-labeling platform for building and
managing high-quality training data — with first-class support for
**organizations, workspaces, labeler/reviewer workflows, and worker
compensation**.

LabelSea is a **derivative work based on
[Label Studio](https://github.com/HumanSignal/label-studio)** (by HumanSignal,
Inc.) and is distributed under the same **Apache License, Version 2.0**. It
inherits Label Studio's flexible labeling interface for audio, text, images,
video, time series, and more, and layers a multi-tenant collaboration and
review platform on top.

> **Attribution:** "Label Studio" is a trademark of HumanSignal, Inc. LabelSea
> is an independent project and is **not affiliated with, sponsored by, or
> endorsed by HumanSignal, Inc.** See [ATTRIBUTION.md](ATTRIBUTION.md),
> [NOTICE](NOTICE), and [LICENSE](LICENSE) for full details.

---

## What LabelSea adds on top of Label Studio

- **Workspaces** — an Organization → Workspace → Project tenancy layer with
  workspace-scoped roles, dashboards, and dataset management.
- **Datasets & Task Pools** — upload datasets at the workspace level and curate
  them into reusable Task Pools that seed project tasks (including automatic
  pairing of same-name image + CSV uploads).
- **Annotation review workflow** — assign reviewers, review tasks with
  **Accept / Reject / Fix-and-Accept**, keep full review history, and track
  annotation/review progress, with a dedicated reviewer task view and review
  page (comments rendered as code diffs for fixes).
- **Worker assignment** — assign labelers and reviewers to a project during
  creation and from project settings.
- **Compensation** — per-project pricing (currency, annotation/review unit
  prices), earnings derived from the review history, and payment tracking.
- **Richer Data Manager & project cards** — reviewer/`reviewed`/`reviews`
  columns, work-pool/labeler/reviewer counts, and progress summaries.

## Core labeling features (from Label Studio)

The underlying labeling engine, configurable label configs, import/export,
machine-learning backend integration, and storage connectors come from Label
Studio. For documentation of those core capabilities, refer to the upstream
project:

- Label Studio docs: <https://labelstud.io/guide/>
- Label Studio repository: <https://github.com/HumanSignal/label-studio>

## Running LabelSea

LabelSea uses the same stack as Label Studio (Django backend + an `nx`-based
React frontend under `web/`). After installing backend dependencies (Poetry)
and building the frontend (`yarn ls:build`), run the server and open
`http://localhost:8080`.

- [Run locally for development](#run-locally-for-development)
- [Run with Docker](#run-with-docker)
- [Run with Docker Compose (LabelSea + Nginx + PostgreSQL)](#run-with-docker-compose)
- [Run with Docker Compose + MinIO](#run-with-docker-compose--minio)
- [Deploy in a cloud instance](#deploy-in-a-cloud-instance)

### Run locally for development

```bash
# Install all package dependencies
pip install poetry
poetry install

# Activate venv
source .venv/bin/activate

# Run database migrations
python label_studio/manage.py migrate
python label_studio/manage.py collectstatic

# Start the server in development mode at http://localhost:8080
python label_studio/manage.py runserver
```

For information about building and updating the frontend, see
[`web/README.md`](web/README.md).

### Run with Docker

LabelSea is not published as a prebuilt image, so build the image locally
from the repository root and run it in a container. It will be available at
`http://localhost:8080`.

```bash
docker build -t labelsea:latest .
docker run -it -p 8080:8080 -v $(pwd)/mydata:/label-studio/data labelsea:latest
```

All generated assets — including the SQLite3 database storage
`label_studio.sqlite3` and uploaded files — are kept in the `./mydata`
directory.

You can override the default launch command by appending new arguments:

```bash
docker run -it -p 8080:8080 -v $(pwd)/mydata:/label-studio/data labelsea:latest label-studio --log-level DEBUG
```

### Run with Docker Compose

The Docker Compose script provides a production-ready stack consisting of the
following components:

- LabelSea
- [Nginx](https://www.nginx.com/) — proxy web server used to serve various
  static data, including uploaded audio, images, etc.
- [PostgreSQL](https://www.postgresql.org/) — production-ready database that
  replaces the less performant SQLite3.

The compose file builds the image from the local source (`build: .`), so it
always runs this fork's code. To start using the app from `http://localhost`,
run this command:

```bash
docker-compose up
```

### Run with Docker Compose + MinIO

You can also run LabelSea with an additional [MinIO](https://min.io/) server
for local S3 storage. This is particularly useful when you want to test
S3-storage behavior on your local system:

```bash
# Add sudo on Linux if you are not a member of the docker group
docker compose -f docker-compose.yml -f docker-compose.minio.yml up -d
```

If you do not have a static IP address, you must create an entry in your hosts
file so that both LabelSea and your browser can access the MinIO server.

### Deploy in a cloud instance

The repository ships with deployment configurations inherited from Label
Studio for the following cloud platforms:

- **Heroku** — [`heroku.yml`](heroku.yml) and
  [`Dockerfile.heroku`](Dockerfile.heroku) (with persistent PostgreSQL).
- **Microsoft Azure** — [`azuredeploy.json`](azuredeploy.json) ARM template
  and [`azuredeploy.parameters.json`](azuredeploy.parameters.json).
- **Google Cloud Run** — [`Dockerfile.cloudrun`](Dockerfile.cloudrun).

For platform-specific instructions, refer to the upstream Label Studio
deployment guide: <https://labelstud.io/guide/install>.

## License

LabelSea is licensed under the **Apache License, Version 2.0** — the same
license as the upstream Label Studio project.

- [`LICENSE`](LICENSE) — the full Apache 2.0 license, with a LabelSea
  attribution preamble.
- [`NOTICE`](NOTICE) — LabelSea attribution plus the preserved upstream Label
  Studio notice.
- [`ATTRIBUTION.md`](ATTRIBUTION.md) — detailed attribution and Apache 2.0
  compliance statement.

Copyright (c) 2025–2026 LabelSea contributors.
Portions Copyright (c) 2019–2021 Heartex, Inc. (HumanSignal, Inc.) — Label Studio.
