"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license."""

import csv
import io
from decimal import Decimal
from typing import Iterable

from .models import SettlementBatch, SettlementItem


_CSV_HEADER = (
    'user_id',
    'user_email',
    'user_full_name',
    'accepted_count',
    'review_count',
    'label_amount',
    'review_amount',
    'amount',
    'currency',
)


def _iter_item_rows(items: Iterable[SettlementItem]):
    """Yield normalized CSV row tuples for each SettlementItem.

    `select_related('user')` on the caller prevents the N+1 problem; this
    function just flattens the object into primitive columns.
    """
    for item in items:
        user = item.user
        yield (
            getattr(user, 'id', '') or '',
            getattr(user, 'email', '') or '',
            _user_name(user),
            item.accepted_count,
            item.review_count,
            _fmt_amount(item.label_amount),
            _fmt_amount(item.review_amount),
            _fmt_amount(item.amount),
            item.currency,
        )


def _user_name(user) -> str:
    if user is None:
        return ''
    full = (getattr(user, 'first_name', '') + ' ' + getattr(user, 'last_name', '')).strip()
    return full or getattr(user, 'username', '') or getattr(user, 'email', '') or ''


def _fmt_amount(value) -> str:
    if value is None:
        return ''
    if isinstance(value, Decimal):
        return format(value.normalize(), 'f') if value == value.to_integral() else str(value)
    return str(value)


def render_csv(batch: SettlementBatch) -> bytes:
    """Render a UTF-8 BOM CSV (Excel-friendly) with a metadata header + per-user lines."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator='\n')

    # Metadata preamble — ignored by most CSV tools but useful when someone
    # opens the file in a plain editor to verify the batch it came from.
    writer.writerow(['# settlement_batch_id', batch.id])
    writer.writerow(['# project_id', batch.project_id])
    writer.writerow(['# period_start', batch.period_start.isoformat() if batch.period_start else ''])
    writer.writerow(['# period_end', batch.period_end.isoformat() if batch.period_end else ''])
    writer.writerow(['# currency', batch.currency])
    writer.writerow(['# total_amount', _fmt_amount(batch.total_amount)])
    writer.writerow([])

    writer.writerow(_CSV_HEADER)
    items = batch.items.select_related('user').order_by('-amount', 'user_id')
    for row in _iter_item_rows(items):
        writer.writerow(row)

    writer.writerow([])
    writer.writerow([
        '', '', 'TOTAL',
        batch.accepted_annotation_count,
        batch.review_count,
        '', '',
        _fmt_amount(batch.total_amount),
        batch.currency,
    ])

    # Excel auto-detects UTF-8 only when the BOM is present.
    return '﻿'.encode('utf-8') + buffer.getvalue().encode('utf-8')


def render_pdf(batch: SettlementBatch) -> bytes:
    """Render a single-page-ish PDF report via reportlab.

    Uses the platypus flowable API so tables auto-paginate — no manual layout
    math. The document is intentionally plain text / default fonts to keep the
    dependency footprint minimal (no custom TTFs for CJK, etc).
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f'Settlement Batch #{batch.id}',
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f'Settlement Batch #{batch.id}', styles['Title']))
    elements.append(Spacer(1, 6))

    project_title = getattr(batch.project, 'title', None) or f'#{batch.project_id}'
    meta_rows = [
        ['Project', project_title],
        ['Period', f'{batch.period_start.isoformat() if batch.period_start else ""} → '
                   f'{batch.period_end.isoformat() if batch.period_end else ""}'],
        ['Status', batch.status],
        ['Currency', batch.currency],
        ['Accepted annotations', batch.accepted_annotation_count],
        ['Review actions', batch.review_count],
        ['Total payout', f'{_fmt_amount(batch.total_amount)} {batch.currency}'],
    ]
    meta_table = Table(meta_rows, colWidths=[45 * mm, 120 * mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (0, -1), colors.whitesmoke),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph('Per-user payouts', styles['Heading2']))

    data = [[
        'User', 'Accepted', 'Reviews',
        'Label amount', 'Review amount', 'Total',
    ]]
    items = batch.items.select_related('user').order_by('-amount', 'user_id')
    for item in items:
        data.append([
            _user_name(item.user) or f'#{item.user_id}',
            item.accepted_count,
            item.review_count,
            _fmt_amount(item.label_amount),
            _fmt_amount(item.review_amount),
            _fmt_amount(item.amount),
        ])
    data.append([
        'TOTAL',
        batch.accepted_annotation_count,
        batch.review_count,
        '', '',
        _fmt_amount(batch.total_amount),
    ])

    table = Table(
        data,
        colWidths=[60 * mm, 20 * mm, 20 * mm, 25 * mm, 25 * mm, 25 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
