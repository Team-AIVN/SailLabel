"""Role constants for the LabelSea RBAC model.

Roles are grouped in two scopes:
- Organization scope: ``OrganizationRole`` — applies to ``OrganizationMember.role``.
  ``SUPER_ADMIN`` is the org-level escalation; everyone else is a plain ``MEMBER``.
- Project scope: ``ProjectRole`` — applies to ``ProjectMember.role``.
  ``MEMBER`` is a project member with no work role yet (assigned to the project but
  not labeling or reviewing — the "Worker" bucket in the assignment UI, i.e. the
  PMb role in the permission spec). ``WORKER_ROLES`` is a logical group (annotator ∪
  reviewer) used in permission predicates and excludes ``MEMBER``.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class OrganizationRole(models.TextChoices):
    SUPER_ADMIN = 'super_admin', _('Super Admin')
    MEMBER = 'member', _('Member')


class ProjectRole(models.TextChoices):
    PROJECT_MANAGER = 'project_manager', _('Project Manager')
    ANNOTATOR = 'annotator', _('Annotator')
    REVIEWER = 'reviewer', _('Reviewer')
    MEMBER = 'member', _('Member')  # assigned to the project, no work role (PMb)


# Logical role group: a Worker is any user contributing labels or review.
# MEMBER (no work role) is intentionally excluded.
WORKER_ROLES = frozenset({ProjectRole.ANNOTATOR.value, ProjectRole.REVIEWER.value})
