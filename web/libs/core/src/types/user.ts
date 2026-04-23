import type { Ability } from "../providers/AuthProvider";
import type { OrganizationRole } from "../lib/utils/roles";

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
  organization_role?: OrganizationRole;
  is_super_admin?: boolean;
};
