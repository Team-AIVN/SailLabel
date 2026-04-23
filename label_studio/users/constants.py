"""Role constants for the SailLabel RBAC model.

Roles are grouped in two scopes:
- Organization scope: ``OrganizationRole`` — applies to ``OrganizationMember.role``.
  ``SUPER_ADMIN`` is the org-level escalation; everyone else is a plain ``MEMBER``.
- Project scope: ``ProjectRole`` — applies to ``ProjectMember.role``.
  ``WORKER`` is a logical alias (annotator ∪ reviewer) and is NOT stored; use it only
  in permission predicates via ``ProjectRole.WORKER_ROLES``.
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


# Logical role group: a Worker is any user contributing labels or review.
WORKER_ROLES = frozenset({ProjectRole.ANNOTATOR.value, ProjectRole.REVIEWER.value})
