import factory
from core.utils.common import load_func
from django.conf import settings

from workspaces.models import Workspace, WorkspaceMember


class WorkspaceFactory(factory.django.DjangoModelFactory):
    title = factory.Sequence(lambda n: f'Workspace {n}')
    description = ''
    organization = factory.SubFactory(load_func(settings.ORGANIZATION_FACTORY))
    created_by = factory.SelfAttribute('organization.created_by')

    class Meta:
        model = Workspace


class WorkspaceMemberFactory(factory.django.DjangoModelFactory):
    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SelfAttribute('workspace.organization.created_by')
    role = WorkspaceMember.Role.MEMBER

    class Meta:
        model = WorkspaceMember
