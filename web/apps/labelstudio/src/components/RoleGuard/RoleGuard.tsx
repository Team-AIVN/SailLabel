/**
 * Route guards for role-based access control (RBAC).
 *
 * These redirect users away from pages their role may not access, closing the
 * "direct URL" hole that the menu gating alone can't (menu hides links, but a
 * user could still type the URL). Access rules mirror
 * `docs/markdowns/permissions-by-url.md`; the backend enforces the same rules
 * on the API — these guards are the UI half.
 */
import type { ReactNode } from "react";
import { Redirect } from "react-router-dom";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useProject } from "../../providers/ProjectProvider";
import { projectPermissions, usePermissions } from "../../utils/permissions";

type ProjectPerms = ReturnType<typeof projectPermissions>;

/**
 * Guards a project-scoped page (settings, review, export, …). Redirects unless
 * the current user's project role satisfies `check`. Waits for the project to
 * load before deciding, and renders nothing meanwhile so forbidden content is
 * never flashed.
 */
export const ProjectRoleGuard = ({
  check,
  children,
  redirectTo,
}: {
  check: (perms: ProjectPerms) => boolean;
  children: ReactNode;
  redirectTo?: string;
}) => {
  const { project } = useProject();
  const projectId = (project as APIProject)?.id;
  const role = (project as APIProject)?.current_user_role;

  // Project not resolved yet → wait (don't flash content or redirect prematurely).
  if (!projectId) return null;

  if (!check(projectPermissions(role))) {
    return <Redirect to={redirectTo ?? `/projects/${projectId}/data`} />;
  }
  return <>{children}</>;
};

/** Guards a super-admin-only page (Organization, Models). */
export const SuperAdminGuard = ({
  children,
  redirectTo = "/projects",
}: {
  children: ReactNode;
  redirectTo?: string;
}) => {
  const { isLoading } = useAuth();
  const { isSuperAdmin } = usePermissions();

  // Wait for the current user to load before deciding.
  if (isLoading) return null;
  if (!isSuperAdmin) return <Redirect to={redirectTo} />;
  return <>{children}</>;
};
