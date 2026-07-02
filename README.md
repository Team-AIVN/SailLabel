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
