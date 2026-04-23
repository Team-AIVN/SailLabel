"""Settlement app — per-project pricing and batch payout reports.

Built under Phase 6 of the SailLabel roadmap (§3.4.5). Works alongside the
`fsm` audit trail: batch settlement derives payouts from `AnnotationState`
rows (transition_name ∈ {accept_annotation, reject_annotation}) so the
computation is deterministic and reproducible from raw audit data.
"""

default_app_config = 'settlement.apps.SettlementConfig'
