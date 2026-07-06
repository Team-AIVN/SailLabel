from rest_framework.permissions import SAFE_METHODS, BasePermission


class HasObjectPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.has_permission(request.user)


class MemberHasOwnerPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method not in SAFE_METHODS and not request.user.own_organization:
            return False

        return obj.has_permission(request.user)


class ProjectManagerObjectPermission(BasePermission):
    """Object-level guard for project mutations.

    Read (SAFE) methods fall through to the org-scope check the view already
    applies via ``get_queryset``. Mutations split by intent:
    - change (PATCH/PUT) requires project-manager authority (PM/WM/SA);
    - delete (DELETE) requires workspace-manager authority (WM/SA only), matching
      the policy that project create/delete is a workspace-management action and
      project managers may edit but not create or delete projects.

    Needed because the declarative ``permission_required`` (ViewClassPermission)
    on the core project views is not actually enforced — without this class any
    authenticated org member (e.g. a labeler) could modify or delete a project
    through the API even though the UI hides those controls.
    """

    message = 'You do not have permission to modify this project.'

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # Imported lazily to avoid an app-loading cycle (rules -> models -> ...).
        from users.rules import is_project_manager_of, is_super_admin, is_workspace_manager_of

        user = request.user
        if is_super_admin.test(user):
            return True
        if request.method == 'DELETE':
            # Deleting a project is a workspace-management action (WM/SA only).
            return bool(is_workspace_manager_of.test(user, obj))
        # PATCH/PUT: project managers may edit their project.
        return bool(is_project_manager_of.test(user, obj))


class ProjectManagerSubresourcePermission(BasePermission):
    """Object-level guard for project sub-resources (webhooks, ML backends, storage).

    Reads pass through; any mutation (PATCH/PUT/DELETE) requires project-manager
    authority (PM/WM/SA). Unlike ``ProjectManagerObjectPermission`` (which reserves
    delete for workspace managers on the project itself), sub-resource deletion is
    part of routine project management, so project managers may do it. Resolves the
    project via the object's ``.project`` attribute.
    """

    message = 'Only project managers, workspace managers, or super admins can manage this resource.'

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        from users.rules import is_project_manager_of, is_super_admin

        user = request.user
        return bool(is_super_admin.test(user) or is_project_manager_of.test(user, obj))


class ProjectManagerBodyPermission(BasePermission):
    """View-level guard for create endpoints whose project id is in the request body.

    Only POST is gated (list GET passes through, scoped by the view's queryset). The
    check runs in ``initial()``, before serializer validation — important for
    endpoints that validate an external connection (ML backend health check, storage
    credential check) so an unauthorized user cannot trigger that side effect. POST
    requires PM/WM/SA on the project named in ``request.data['project']``.
    """

    message = 'Only project managers, workspace managers, or super admins can manage this resource.'

    def has_permission(self, request, view):
        if request.method != 'POST':
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        from users.rules import is_project_manager_of, is_super_admin

        if is_super_admin.test(user):
            return True
        pid = request.data.get('project')
        if pid is None:
            return False
        from projects.models import Project

        project = Project.objects.filter(pk=pid).first()
        if project is None:
            return False
        return bool(is_project_manager_of.test(user, project))


class CanCreateWorkspacePermission(BasePermission):
    """View-level guard for workspace creation (POST): super admins and workspace
    managers only. Checked in ``initial()`` so a non-manager is rejected before
    serializer validation. Non-POST methods pass through."""

    message = 'Only workspace managers or super admins can create workspaces.'

    def has_permission(self, request, view):
        if request.method != 'POST':
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        from users.rules import can_create_workspace

        return bool(can_create_workspace.test(user))


class IsProjectManager(BasePermission):
    """View-level guard for project-scoped management endpoints (e.g. export).

    Resolves the project from the URL ``pk`` and requires project-manager
    authority for every method, so it protects list/create endpoints that never
    call ``get_object`` as well as object endpoints. Labelers, reviewers and
    plain members are denied — matching the export permission spec (PM/WM/SA
    only).
    """

    message = 'Only project managers, workspace managers, or super admins can access this resource.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        from users.rules import is_project_manager_of, is_super_admin

        if is_super_admin.test(user):
            return True
        project_pk = view.kwargs.get('pk')
        if project_pk is None:
            return False
        from projects.models import Project

        project = Project.objects.filter(pk=project_pk).first()
        if project is None:
            return False
        return bool(is_project_manager_of.test(user, project))
