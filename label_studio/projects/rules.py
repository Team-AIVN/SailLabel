"""Project-level permission wiring.

Binds the five named project permissions (create/view/change/delete/reset_cache)
to role predicates from ``users.rules``. Imported from
``projects.apps.ProjectsConfig.ready`` so the overrides apply at startup.
"""

from core.permissions import make_perm
from users.rules import (
    can_create_project,
    is_project_manager_of,
    is_super_admin,
    is_workspace_manager_of,
)

# Mutation: project managers, workspace managers, and super admins.
# Annotators/reviewers can READ (queryset-filtered) but cannot mutate.
project_mutator = is_project_manager_of | is_workspace_manager_of | is_super_admin

# Cache reset is a project-management action; same scope as mutator.
project_cache_reset = project_mutator


make_perm('projects.change', project_mutator, overwrite=True)
make_perm('projects.delete', project_mutator, overwrite=True)
make_perm('projects.reset_cache', project_cache_reset, overwrite=True)
# Creation is a management action: workspace managers (of any workspace) and super
# admins only. Whether to additionally require a target workspace and auto-assign the
# creator as PM is still an open team decision (see permissions-actions.md).
make_perm('projects.create', can_create_project, overwrite=True)
# projects.view keeps the default `is_authenticated` predicate —
# visibility is enforced in the DRF queryset filter (active_organization scope).
