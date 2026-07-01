# Attribution and License Compliance

## Summary

**LabelSea** is an open-source data-labeling platform that is a **derivative
work based on [Label Studio](https://github.com/HumanSignal/label-studio)**, an
open-source project created and maintained by **HumanSignal, Inc.** (formerly
Heartex, Inc.).

Both Label Studio and LabelSea are distributed under the **Apache License,
Version 2.0**. LabelSea retains that same license. This document records the
attribution and the steps taken to comply with the Apache License so that the
use of Label Studio raises no licensing or legal issue.

## Upstream project

| | |
|---|---|
| **Upstream project** | Label Studio |
| **Upstream author / copyright holder** | HumanSignal, Inc. (formerly Heartex, Inc.) |
| **Upstream source** | https://github.com/HumanSignal/label-studio |
| **Upstream copyright** | Copyright (c) 2019–2021 Heartex, Inc. All Rights Reserved. |
| **Upstream license** | Apache License, Version 2.0 |

## LabelSea

| | |
|---|---|
| **Project** | LabelSea |
| **Copyright** | Copyright (c) 2025–2026 LabelSea contributors. |
| **License** | Apache License, Version 2.0 (same as upstream) — see [`LICENSE`](LICENSE) |
| **Relationship** | Derivative work based on Label Studio |

## How LabelSea complies with the Apache License, Version 2.0

The Apache License permits derivative works provided the conditions in
Section 4 are met. LabelSea satisfies them as follows:

1. **Section 4(a) — Provide a copy of the License.**
   The full, unmodified Apache License, Version 2.0 is included in
   [`LICENSE`](LICENSE). A short LabelSea attribution preamble precedes the
   license text; the license text itself is unchanged.

2. **Section 4(b) — Mark changed files.**
   Files that the LabelSea project modified, and the new files it added, are
   tracked in the project's version-control history. New source files carry
   the standard Apache 2.0 license header, and the changes are summarized in
   the "Summary of LabelSea changes" section below.

3. **Section 4(c) — Retain notices.**
   The copyright, patent, trademark, and attribution notices from Label Studio
   are retained. The per-file Apache 2.0 license headers throughout the
   repository are preserved unchanged.

4. **Section 4(d) — Preserve the NOTICE file.**
   The upstream NOTICE text is preserved verbatim inside the [`NOTICE`](NOTICE)
   file, alongside LabelSea's own attribution. No upstream notices were
   removed.

LabelSea adds no additional restrictions to the rights granted by the Apache
License. All LabelSea modifications and additions are themselves licensed
under the Apache License, Version 2.0.

## Summary of LabelSea changes

LabelSea builds on Label Studio and adds, among other things:

- An Organization → **Workspace** → Project multi-tenancy layer with
  workspace-scoped roles, dashboards, and dataset management.
- **Work Pools**: curated sets of dataset items bound to projects.
- An in-project **annotation review workflow** (reviewer assignment,
  accept / reject / fix-and-accept, review history and progress) plus a
  reviewer task view and a review page.
- A **Compensation** module (per-project pricing, derived earnings, payment
  tracking).
- **Worker assignment** (annotators / reviewers) in project creation and
  project settings.
- Various Data Manager, project-card, and import/pairing enhancements.
- Re-branding of the user-facing application name to "LabelSea".

This list is a non-exhaustive summary; the authoritative record of changes is
the repository's commit history.

## Trademarks and endorsement

"Label Studio" and the Label Studio logo are trademarks of HumanSignal, Inc.
LabelSea is an **independent project** and is **not affiliated with, sponsored
by, or endorsed by HumanSignal, Inc.** References to "Label Studio" in this
repository (for example in this file, in `NOTICE`, in `LICENSE`, in source-code
comments, and in upstream documentation strings) are used solely to identify
the upstream project from which LabelSea is derived — a nominative,
descriptive use. The Apache License grants a copyright and patent license but
does **not** grant any right to use the upstream project's trademarks except as
required for reasonable and customary use in describing the origin of the work.
Accordingly, the LabelSea product is branded as "LabelSea", not "Label
Studio".

## Third-party components

Label Studio and LabelSea depend on additional third-party open-source
components, each governed by its own license. Those licenses continue to apply
to their respective components and are unaffected by this attribution.

## If you redistribute LabelSea

When redistributing LabelSea or a derivative of it, retain this
`ATTRIBUTION.md` file, the [`LICENSE`](LICENSE) file, and the [`NOTICE`](NOTICE)
file, and keep the per-file license headers intact, in order to remain
compliant with the Apache License, Version 2.0.
