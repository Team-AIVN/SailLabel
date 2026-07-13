/**
 * Central RBAC helpers for the LabelSea frontend.
 *
 * Single source of truth for "who can see / do what" in the UI. Mirrors the
 * backend role model (`label_studio/users/roles.py`) and the permission matrix
 * in `docs/markdowns/permissions-by-url.md`.
 *
 * The backend still enforces access independently via API permissions — these
 * helpers only gate the UI (menus, routes, controls) so users don't see or
 * reach things they can't use.
 *
 * Two inputs:
 * - Global flags from `whoami` (`is_super_admin`, `has_workspace_access`,
 *   `has_project_access`) → drive the top-level menu (see `usePermissions`).
 * - Per-object role from the API (`project.current_user_role`,
 *   `workspace.current_user_role`) → drive page/control gating.
 */
import { useAuth } from "@humansignal/core/providers/AuthProvider";

/** Canonical role strings — must match backend `users/roles.py`. */
export const Role = {
  SUPER_ADMIN: "super_admin",
  WORKSPACE_MANAGER: "workspace_manager",
  PROJECT_MANAGER: "project_manager",
  REVIEWER: "reviewer",
  ANNOTATOR: "annotator",
  MEMBER: "member",
} as const;

export type Role = (typeof Role)[keyof typeof Role];

/** Roles with management authority over a project (settings, export, delete). */
const PROJECT_MANAGER_ROLES: readonly string[] = [
  Role.SUPER_ADMIN,
  Role.WORKSPACE_MANAGER,
  Role.PROJECT_MANAGER,
];

/**
 * Capabilities derived from a project's `current_user_role`.
 * Pass `project.current_user_role` (may be null/undefined when no access).
 */
export function projectPermissions(role?: string | null) {
  return {
    /** Can open the project / data manager at all. */
    canView: role != null,
    /** Project settings, export, worker assignment (project managers and up). */
    canManage: PROJECT_MANAGER_ROLES.includes(role ?? ""),
    /** Delete/create projects — workspace managers / super admins only, NOT PMs. */
    canDelete: [Role.SUPER_ADMIN, Role.WORKSPACE_MANAGER].includes(role ?? ""),
    /** Add project managers (PMs) to this project — workspace managers / super admins
     * only. A PM may invite workers but not other managers (mirrors the backend). */
    canAssignManagers: [Role.SUPER_ADMIN, Role.WORKSPACE_MANAGER].includes(role ?? ""),
    /** Review page (accept / reject / fix). */
    canReview: [...PROJECT_MANAGER_ROLES, Role.REVIEWER].includes(role ?? ""),
    /** Export labeled data — super admins / workspace managers only, NOT PMs. */
    canExport: [Role.SUPER_ADMIN, Role.WORKSPACE_MANAGER].includes(role ?? ""),
    /** Perform labeling in the editor. */
    canLabel: [...PROJECT_MANAGER_ROLES, Role.ANNOTATOR].includes(role ?? ""),
  };
}

/**
 * Capabilities derived from a workspace's `current_user_role`.
 * Pass `workspace.current_user_role` (may be null/undefined when no access).
 */
export function workspacePermissions(role?: string | null) {
  return {
    /** Can open the workspace (header at minimum). */
    canView: role != null,
    /** Can see the workspace tabs (projects/datasets/taskpools/users/compensation). */
    canViewTabs: [Role.SUPER_ADMIN, Role.WORKSPACE_MANAGER, Role.PROJECT_MANAGER].includes(role ?? ""),
    /** Can create/edit/delete inside the workspace (managers only). */
    canManage: [Role.SUPER_ADMIN, Role.WORKSPACE_MANAGER].includes(role ?? ""),
  };
}

/**
 * Global, user-level permissions for top-level navigation gating.
 * Reads the whoami flags off the authenticated user.
 */
export function usePermissions() {
  const { user } = useAuth();
  return {
    isSuperAdmin: !!user?.is_super_admin,
    canSeeProjectsMenu: !!user?.has_project_access,
    canSeeWorkspacesMenu: !!user?.has_workspace_access,
    canSeeOrganization: !!user?.is_super_admin,
    // Super admins and workspace managers may create workspaces/projects.
    canCreateWorkspace: !!user?.can_create_workspace,
  };
}
