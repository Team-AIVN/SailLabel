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
    """Object-level guard for project mutations (PATCH/PUT/DELETE).

    Read (SAFE) methods fall through to the org-scope check the view already
    applies via ``get_queryset``; mutations require project-manager authority
    (project manager, workspace manager, or super admin).

    Needed because the declarative ``permission_required`` (ViewClassPermission)
    on the core project views is not actually enforced — without this class any
    authenticated org member (e.g. a labeler) can modify or delete a project
    through the API even though the UI hides those controls.
    """

    message = 'Only project managers, workspace managers, or super admins can modify this project.'

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # Imported lazily to avoid an app-loading cycle (rules -> models -> ...).
        from users.rules import is_project_manager_of, is_super_admin

        user = request.user
        return bool(is_super_admin.test(user) or is_project_manager_of.test(user, obj))


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
