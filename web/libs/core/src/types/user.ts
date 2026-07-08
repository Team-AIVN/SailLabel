import type { Ability } from "../providers/AuthProvider";

export type APIUser = {
  id: number;
  first_name: string;
  last_name: string;
  username: string;
  email: string;
  last_activity: string;
  avatar: string | null;
  initials: string;
  phone: string;
  active_organization: number;
  active_organization_meta: {
    title: string;
    email: string;
  };
  allow_newsletters: boolean;
  date_joined: string;
  permissions?: Ability[];
  /** RBAC (from whoami): true when the user is a super admin / organization owner. */
  is_super_admin?: boolean;
  /** RBAC (from whoami): true when the user can access at least one workspace. */
  has_workspace_access?: boolean;
  /** RBAC (from whoami): true when the user can access at least one project. */
  has_project_access?: boolean;
};
