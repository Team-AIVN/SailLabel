// Mirrors `WorkspaceSerializer` (label_studio/workspaces/serializers.py).
declare type APIWorkspace = {
  id: number;

  /** Workspace name. */
  title: string;

  /** Workspace description */
  description?: string | null;

  organization?: number;
  created_by?: number | null;
  created_at?: string;
  updated_at?: string;

  /** Number of non-deleted projects inside the workspace */
  project_count?: number;

  /** Caller's role in this workspace, or null when they have no membership */
  current_user_role?: string | null;
};
