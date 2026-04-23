"""Phase 5 — `state` column registration in Data Manager.

The FSM `state` is already annotated at the queryset level (see
`data_manager.managers.annotate_state`) and ordered via a CASE expression
(`managers.py:175`). What was missing — and what this test guards — is the
frontend-facing column list: `get_all_columns()` must advertise `state` so
reviewers can pick it in the Data Manager column chooser and filter by it.
"""

import pytest  # type: ignore[import]
from data_manager.functions import get_all_columns
from fsm.state_choices import TaskStateChoices
from organizations.tests.factories import OrganizationFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db


def _find(columns, column_id):
    return next((c for c in columns if c['id'] == column_id), None)


def test_state_column_is_exposed_when_fsm_flags_enabled():
    # pytest.ini enables `fflag_feat_fit_568_finite_state_management` and
    # `fflag_feat_fit_710_fsm_state_fields` so the conditional branch is live.
    org = OrganizationFactory()
    project = ProjectFactory(organization=org, created_by=org.created_by)

    columns = get_all_columns(project)['columns']
    state = _find(columns, 'state')

    assert state is not None, 'state column must be advertised to Data Manager'
    assert state['target'] == 'tasks'
    assert state['type'] == 'String'
    assert set(state['schema']['items']) == set(TaskStateChoices.values)
