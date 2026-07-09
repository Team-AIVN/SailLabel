"""Compensation derivation.

Earnings are NEVER stored: they are computed on demand from project pricing
(:class:`ProjectCompensationPolicy`) and historical workflow data (task review
status, the annotation revision chain, and :class:`reviews.models.Review`). Qualified
counts cannot be edited by anyone — there is no field for them; they are recomputed
every read, so the dashboard is always reproducible and auditable.

Qualification rules (a "data item" is a Task):
* Annotation is compensable once per task whose final ``review_status`` is one of
  ACCEPTED / FIXED_AND_ACCEPTED / NOT_SELECTED. Credit goes to the ORIGINAL annotator
  (root of the revision chain) — reviewer fixes never transfer annotation credit, and
  rejection/rework cycles never add extra credit (still one task = one annotation).
* Review is compensable once per task whose final ``review_status`` is ACCEPTED or
  FIXED_AND_ACCEPTED. Credit goes to the reviewer of the latest terminal review.
  NOT_SELECTED tasks were never reviewed, so they earn no review compensation.
"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Min
from reviews.models import Review
from tasks.models import Annotation, Task

from .models import PaymentRecord, ProjectCompensationPolicy

# Final task states that make the (single) annotation for a data item compensable.
ANNOTATION_QUALIFIED_STATUSES = (
    Task.ReviewStatus.ACCEPTED,
    Task.ReviewStatus.FIXED_AND_ACCEPTED,
    Task.ReviewStatus.NOT_SELECTED,
)
# Final task states that make a review compensable (the item was actually reviewed).
REVIEW_QUALIFIED_STATUSES = (
    Task.ReviewStatus.ACCEPTED,
    Task.ReviewStatus.FIXED_AND_ACCEPTED,
)
TERMINAL_REVIEW_DECISIONS = (
    Review.Decision.ACCEPT,
    Review.Decision.FIX_AND_ACCEPT,
)


def qualified_counts_for_project(project):
    """Return ``{user_id: {'annotation': n, 'review': m}}`` of qualified counts.

    Each task contributes at most one annotation credit and one review credit,
    regardless of how many revision/rejection cycles it went through.
    """
    counts = defaultdict(lambda: {'annotation': 0, 'review': 0})

    # --- Qualified annotations: one per qualified task, to the original annotator. ---
    # No current_annotation filter: NONE-strategy projects never set it, yet their
    # NOT_SELECTED tasks are still compensable. The root-annotation lookup below
    # naturally excludes tasks that have no annotation at all (unworked tasks).
    ann_task_ids = list(
        Task.objects.filter(
            project=project,
            review_status__in=ANNOTATION_QUALIFIED_STATUSES,
        ).values_list('id', flat=True)
    )
    if ann_task_ids:
        # Root annotation per task = lowest-id NON-cancelled annotation = the original
        # annotator's real work. Excluding was_cancelled skips means a skipped task with
        # no real annotation earns nothing, and a skip-then-relabel credits the relabeler
        # (not whoever skipped first with a lower id).
        roots = (
            Annotation.objects.filter(task_id__in=ann_task_ids, was_cancelled=False)
            .values('task_id')
            .annotate(root_id=Min('id'))
        )
        root_ids = [r['root_id'] for r in roots]
        for completed_by_id in Annotation.objects.filter(id__in=root_ids).values_list(
            'completed_by_id', flat=True
        ):
            if completed_by_id is not None:
                counts[completed_by_id]['annotation'] += 1

    # --- Qualified reviews: one per reviewed task, to the latest terminal reviewer. ---
    rev_task_ids = list(
        Task.objects.filter(
            project=project,
            review_status__in=REVIEW_QUALIFIED_STATUSES,
        ).values_list('id', flat=True)
    )
    if rev_task_ids:
        rows = (
            Review.objects.filter(
                annotation__task_id__in=rev_task_ids,
                decision__in=TERMINAL_REVIEW_DECISIONS,
                reviewer__isnull=False,
            )
            .order_by('annotation__task_id', '-created_at', '-id')
            .values('annotation__task_id', 'reviewer_id')
        )
        seen = set()
        for row in rows:
            task_id = row['annotation__task_id']
            if task_id in seen:  # rows are newest-first per task; keep only the latest
                continue
            seen.add(task_id)
            counts[row['reviewer_id']]['review'] += 1

    return counts


def _money(d: Decimal) -> float:
    """Round a Decimal to 2 places before float() so JSON never shows binary noise
    (e.g. 0.05*3 = 0.15000000000000002)."""
    return float(Decimal(d).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _status_for(earned: Decimal, paid: Decimal) -> str:
    if paid <= 0:
        return 'UNPAID'
    if paid >= earned:
        return 'PAID'
    return 'PARTIALLY_PAID'


def _member_roles(workspace):
    from workspaces.models import WorkspaceMember

    return {
        m.user_id: m.role
        for m in WorkspaceMember.objects.filter(workspace=workspace, deleted_at__isnull=True)
    }


def _user_label(user):
    if user is None:
        return None
    name = (user.get_full_name() or '').strip() if hasattr(user, 'get_full_name') else ''
    return name or getattr(user, 'email', None) or getattr(user, 'username', None) or f'User {user.pk}'


def _policies_by_project(workspace):
    # Exclude soft-deleted projects so their earnings never resurface in settlement.
    return (
        ProjectCompensationPolicy.objects.filter(
            project__workspace=workspace, project__deleted_at__isnull=True
        ).select_related('project')
    )


def compute_workspace_compensation(workspace):
    """Build dashboard rows: one per (member, currency).

    Earnings sum across projects sharing a currency, but each project's earnings use
    that project's own unit prices before being summed into the currency bucket.
    """
    from django.contrib.auth import get_user_model

    # (user_id, currency) -> aggregated earnings + counts
    agg = defaultdict(
        lambda: {
            'annotation_count': 0,
            'review_count': 0,
            'annotation_earnings': Decimal('0'),
            'review_earnings': Decimal('0'),
        }
    )

    for policy in _policies_by_project(workspace):
        currency = policy.currency
        counts = qualified_counts_for_project(policy.project)
        for user_id, c in counts.items():
            bucket = agg[(user_id, currency)]
            bucket['annotation_count'] += c['annotation']
            bucket['review_count'] += c['review']
            bucket['annotation_earnings'] += policy.annotation_unit_price * c['annotation']
            bucket['review_earnings'] += policy.review_unit_price * c['review']

    # Payments per (user, currency).
    paid_map = defaultdict(lambda: Decimal('0'))
    for rec in PaymentRecord.objects.filter(workspace=workspace):
        paid_map[(rec.user_id, rec.currency)] += rec.amount

    roles = _member_roles(workspace)
    user_ids = {uid for (uid, _c) in agg} | {uid for (uid, _c) in paid_map}
    users = {u.pk: u for u in get_user_model().objects.filter(pk__in=user_ids)}

    rows = []
    keys = set(agg) | set(paid_map)
    for (user_id, currency) in keys:
        bucket = agg.get((user_id, currency))
        annotation_earnings = bucket['annotation_earnings'] if bucket else Decimal('0')
        review_earnings = bucket['review_earnings'] if bucket else Decimal('0')
        earned = annotation_earnings + review_earnings
        paid = paid_map.get((user_id, currency), Decimal('0'))
        rows.append(
            {
                'member_id': user_id,
                'member_name': _user_label(users.get(user_id)),
                'role': roles.get(user_id),
                'currency': currency,
                'annotation_count': bucket['annotation_count'] if bucket else 0,
                'review_count': bucket['review_count'] if bucket else 0,
                'total_earned': _money(earned),
                'total_paid': _money(paid),
                'remaining_balance': _money(earned - paid),
                'status': _status_for(earned, paid),
            }
        )

    rows.sort(key=lambda r: (str(r['member_name'] or ''), r['currency']))
    return rows


def compensation_projects(workspace, allowed_project_ids):
    """Projects (with a compensation policy) the caller may see — for the filter dropdown."""
    return [
        {'id': p.project_id, 'title': p.project.title, 'currency': p.currency}
        for p in _policies_by_project(workspace).order_by('project__title')
        if p.project_id in allowed_project_ids
    ]


def compute_project_compensation(workspace, allowed_project_ids, project_id=None):
    """Per-(project, member) settlement rows, scoped to the projects the caller may see.

    Each project settles in its own currency (the policy currency). Returns one row per
    (project, member) with qualified counts, earnings, amount paid, remaining and status.
    """
    from django.contrib.auth import get_user_model

    policies = [
        p
        for p in _policies_by_project(workspace)
        if p.project_id in allowed_project_ids and (project_id is None or p.project_id == project_id)
    ]
    project_meta = {p.project_id: (p.currency, p.project.title) for p in policies}
    project_currency = {pid: cur for pid, (cur, _) in project_meta.items()}

    # Payments per (project, user), restricted to the visible projects. Only payments in
    # the project's settlement currency count — a mismatched-currency record must never
    # be added to a different-currency balance (would corrupt paid/status). Creation is
    # also validated (see PaymentRecordListCreateAPI), so this is defense-in-depth.
    paid_map = defaultdict(lambda: Decimal('0'))
    for rec in PaymentRecord.objects.filter(workspace=workspace, project_id__in=list(project_meta)):
        if rec.currency == project_currency.get(rec.project_id):
            paid_map[(rec.project_id, rec.user_id)] += rec.amount

    # Earnings per (project, user).
    per = {}
    user_ids = set()
    for policy in policies:
        counts = qualified_counts_for_project(policy.project)
        for uid, c in counts.items():
            if c['annotation'] == 0 and c['review'] == 0:
                continue
            per[(policy.project_id, uid)] = {
                'annotation_count': c['annotation'],
                'review_count': c['review'],
                'annotation_earnings': policy.annotation_unit_price * c['annotation'],
                'review_earnings': policy.review_unit_price * c['review'],
            }
            user_ids.add(uid)
    # Include payment-only (project, user) rows so recorded payments always show.
    for (pid, uid) in paid_map:
        user_ids.add(uid)
        per.setdefault(
            (pid, uid),
            {
                'annotation_count': 0,
                'review_count': 0,
                'annotation_earnings': Decimal('0'),
                'review_earnings': Decimal('0'),
            },
        )

    roles = _member_roles(workspace)
    users = {u.pk: u for u in get_user_model().objects.filter(pk__in=user_ids)}

    rows = []
    for (pid, uid), d in per.items():
        currency, project_name = project_meta.get(pid, (None, None))
        earned = d['annotation_earnings'] + d['review_earnings']
        paid = paid_map.get((pid, uid), Decimal('0'))
        rows.append(
            {
                'project_id': pid,
                'project_name': project_name,
                'member_id': uid,
                'member_name': _user_label(users.get(uid)),
                'role': roles.get(uid),
                'currency': currency,
                'annotation_count': d['annotation_count'],
                'review_count': d['review_count'],
                'annotation_earnings': _money(d['annotation_earnings']),
                'review_earnings': _money(d['review_earnings']),
                'total_earned': _money(earned),
                'total_paid': _money(paid),
                'remaining_balance': _money(earned - paid),
                'status': _status_for(earned, paid),
            }
        )
    rows.sort(key=lambda r: (str(r['project_name'] or ''), str(r['member_name'] or '')))
    return rows


def compute_member_compensation(workspace, user, allowed_project_ids=None):
    """Per-project earnings breakdown and payment history for one worker (optionally
    scoped to the projects the caller may see)."""
    projects = []
    for policy in _policies_by_project(workspace).order_by('project__title'):
        if allowed_project_ids is not None and policy.project_id not in allowed_project_ids:
            continue
        counts = qualified_counts_for_project(policy.project).get(user.pk)
        if not counts or (counts['annotation'] == 0 and counts['review'] == 0):
            continue
        annotation_earnings = policy.annotation_unit_price * counts['annotation']
        review_earnings = policy.review_unit_price * counts['review']
        projects.append(
            {
                'project_id': policy.project_id,
                'project_name': policy.project.title,
                'currency': policy.currency,
                'qualified_annotation_count': counts['annotation'],
                'annotation_unit_price': _money(policy.annotation_unit_price),
                'annotation_earnings': _money(annotation_earnings),
                'qualified_review_count': counts['review'],
                'review_unit_price': _money(policy.review_unit_price),
                'review_earnings': _money(review_earnings),
                'total_earnings': _money(annotation_earnings + review_earnings),
            }
        )

    payments = [
        {
            'id': rec.id,
            'paid_at': rec.paid_at,
            'amount': _money(rec.amount),
            'currency': rec.currency,
            'memo': rec.memo,
        }
        for rec in PaymentRecord.objects.filter(workspace=workspace, user=user)
    ]

    return {
        'member_id': user.pk,
        'member_name': _user_label(user),
        'projects': projects,
        'payments': payments,
    }
