/**
 * Role constants — mirrors label_studio/users/constants.py.
 *
 * Keep the string values in sync with the backend enums; both sides rely on the
 * exact match for role comparisons. Frontend gating is advisory — server-side
 * django-rules is the enforcement point.
 */

export const OrganizationRole = {
  SUPER_ADMIN: "super_admin",
  MEMBER: "member",
} as const;
export type OrganizationRole = (typeof OrganizationRole)[keyof typeof OrganizationRole];

export const ProjectRole = {
  PROJECT_MANAGER: "project_manager",
  ANNOTATOR: "annotator",
  REVIEWER: "reviewer",
} as const;
export type ProjectRole = (typeof ProjectRole)[keyof typeof ProjectRole];

export const WorkspaceRole = {
  WORKSPACE_MANAGER: "workspace_manager",
  MEMBER: "member",
} as const;
export type WorkspaceRole = (typeof WorkspaceRole)[keyof typeof WorkspaceRole];

/**
 * Logical union role. A user is a Worker in a project if they are an annotator or reviewer.
 * Not a stored column — derive from ProjectMember.role at call site.
 */
export const WORKER_ROLES: readonly ProjectRole[] = [ProjectRole.ANNOTATOR, ProjectRole.REVIEWER];

export const isWorkerRole = (role: string | null | undefined): role is ProjectRole =>
  role === ProjectRole.ANNOTATOR || role === ProjectRole.REVIEWER;
