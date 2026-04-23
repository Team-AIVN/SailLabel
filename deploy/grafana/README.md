# SailLabel Observability Deployment

Grafana dashboards and Prometheus rules that accompany the
`label_studio.core.observability` package.

## Layout

| File | Purpose |
|---|---|
| `grafana/saillabel-overview.json` | Operator dashboard: error rate, latency, sync health, settlement, readiness. |
| `../prometheus/scrape.yml` | Reference scrape config for the Django `/metrics/` endpoint. |
| `../prometheus/alerts.yml` | SLO alert rules (error rate, p95, sync failure, settlement, readiness). |

## Import

1. Load the Prometheus rule file via `rule_files` (see `scrape.yml`).
2. In Grafana: *Dashboards → New → Import → Upload JSON file* and pick
   `saillabel-overview.json`. Select your Prometheus datasource when prompted.
3. Confirm metrics are populated by requesting `/metrics/` on a live app pod —
   you should see `saillabel_http_request_duration_seconds_bucket`,
   `saillabel_storage_sync_total`, etc.

## SLO targets (instructions.md §4)

| SLO | Measurement | Alert threshold |
|---|---|---|
| HTTP error rate | `rate(saillabel_http_requests_total{status_class="5xx"}[5m])` | > 1% for 5 min |
| HTTP p95 latency | `histogram_quantile(0.95, …http_request_duration_seconds_bucket…)` | > 2s for 10 min |
| Storage sync failure | `saillabel_storage_sync_total{result="failure"}` ratio | > 5% for 15 min |
| Settlement batch | `saillabel_settlement_batch_total{result="failure"}` | any failure, page oncall |
| Dependency readiness | `saillabel_readiness_status` gauge | 0 for 2 min |

## Maintenance windows

Planned maintenance is excluded from the 99.5% availability target
(instructions.md §4). Record windows in your change-management system; silence
alerts via Alertmanager routes (`match_re: {service: saillabel}`) during the
window rather than disabling rules here.
