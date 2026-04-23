import { useMemo } from "react";
import { useAuth } from "../../providers/AuthProvider";
import { OrganizationRole } from "../utils/roles";

/**
 * Read-only view of the current user's organization-scope role.
 *
 * Frontend role info is advisory — use it only to decide UI affordances.
 * Never rely on these flags for actual access control; the server enforces
 * permissions via django-rules regardless of what the client sends.
 */
export function useUserRoles() {
  const { user, isLoading } = useAuth();

  return useMemo(() => {
    const organizationRole = (user?.organization_role ?? OrganizationRole.MEMBER) as OrganizationRole;
    const isSuperAdmin = Boolean(user?.is_super_admin);
    return {
      isLoading,
      organizationRole,
      isSuperAdmin,
      /**
       * Returns true iff the user holds the given org-scope role.
       * Does NOT consider project/workspace-scope roles — those require a
       * separate membership lookup per resource.
       */
      hasOrganizationRole: (role: OrganizationRole) => organizationRole === role,
    };
  }, [user?.organization_role, user?.is_super_admin, isLoading]);
}
