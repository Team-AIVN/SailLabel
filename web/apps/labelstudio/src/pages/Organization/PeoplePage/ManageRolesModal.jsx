import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Select } from "@humansignal/ui";
import { useAPI } from "../../../providers/ApiProvider";
import { cn } from "../../../utils/bem";
import "./ManageRolesModal.prefix.css";

// RoleKey strings must match backend enums:
//   OrganizationRole -> super_admin, member
//   WorkspaceMember.Role -> workspace_manager, member
//   ProjectRole -> project_manager, reviewer, annotator
const ROLE_TYPES = [
  { value: "super_admin", label: "Super Admin", scope: "organization" },
  { value: "workspace_manager", label: "Workspace Manager", scope: "workspace" },
  { value: "project_manager", label: "Project Manager", scope: "project" },
  { value: "reviewer", label: "Reviewer", scope: "project" },
  { value: "annotator", label: "Annotator", scope: "project" },
];

const roleLabel = (role) => ROLE_TYPES.find((r) => r.value === role)?.label || role;

export const ManageRolesModal = ({ user, onUpdated, onClose }) => {
  const api = useAPI();
  const [assignments, setAssignments] = useState([]);
  const [orgRole, setOrgRole] = useState("member");
  const [organizationId, setOrganizationId] = useState(null);
  const [workspaces, setWorkspaces] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedRole, setSelectedRole] = useState(ROLE_TYPES[0].value);
  const [selectedScopeId, setSelectedScopeId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    const resp = await api.callApi("memberships", { params: { pk: 1 } });
    if (!resp?.results) return;
    const member = resp.results.find((m) => m.user.id === user.id);
    if (!member) return;
    setOrganizationId(member.organization);
    setOrgRole(member.role || "member");
    setAssignments(member.role_assignments || []);
  }, [api, user.id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    api.callApi("workspaces").then((resp) => {
      const items = resp?.results || resp || [];
      setWorkspaces(Array.isArray(items) ? items : []);
    });
    api.callApi("projects").then((resp) => {
      const items = resp?.results || resp || [];
      setProjects(Array.isArray(items) ? items : []);
    });
  }, [api]);

  const selectedRoleMeta = useMemo(
    () => ROLE_TYPES.find((r) => r.value === selectedRole),
    [selectedRole],
  );

  const scopeOptions = useMemo(() => {
    if (selectedRoleMeta?.scope === "workspace") {
      return workspaces.map((w) => ({ value: w.id, label: w.title }));
    }
    if (selectedRoleMeta?.scope === "project") {
      return projects.map((p) => ({ value: p.id, label: p.title }));
    }
    return [];
  }, [selectedRoleMeta, workspaces, projects]);

  useEffect(() => {
    // reset scope when role scope changes
    setSelectedScopeId(scopeOptions[0]?.value ?? null);
  }, [selectedRole, scopeOptions.length]);

  const handleAdd = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (selectedRoleMeta?.scope === "organization") {
        if (selectedRole !== "super_admin") {
          setError("Only super_admin is selectable at the organization scope.");
          return;
        }
        await api.callApi("updateOrganizationMemberRole", {
          params: { pk: organizationId ?? 1, userPk: user.id },
          body: { role: "super_admin" },
        });
      } else if (selectedRoleMeta?.scope === "workspace") {
        if (!selectedScopeId) {
          setError("Pick a workspace.");
          return;
        }
        // Backend workspace-members serializer accepts `role` and `user`.
        await api.callApi("createWorkspaceMember", {
          params: { pk: selectedScopeId },
          body: { user: user.id, role: "workspace_manager" },
        });
      } else if (selectedRoleMeta?.scope === "project") {
        if (!selectedScopeId) {
          setError("Pick a project.");
          return;
        }
        await api.callApi("createProjectMember", {
          params: { pk: selectedScopeId },
          body: { user: user.id, role: selectedRole },
        });
      }
      await refresh();
      onUpdated?.();
    } catch (e) {
      setError(e?.response?.detail || e?.message || "Failed to grant role");
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async (assignment) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (assignment.scope === "workspace") {
        // Need member_pk — fetch the workspace's members and find by user.
        const resp = await api.callApi("workspaceMembers", {
          params: { pk: assignment.scope_id },
        });
        const items = resp?.results || resp || [];
        const row = (Array.isArray(items) ? items : []).find((m) => m.user === user.id);
        if (row) {
          await api.callApi("deleteWorkspaceMember", {
            params: { pk: assignment.scope_id, memberPk: row.id },
          });
        }
      } else if (assignment.scope === "project") {
        const resp = await api.callApi("projectMembers", {
          params: { pk: assignment.scope_id },
        });
        const items = resp?.results || resp || [];
        const row = (Array.isArray(items) ? items : []).find(
          (m) => m.user === user.id && m.role === assignment.role,
        );
        if (row) {
          await api.callApi("deleteProjectMember", {
            params: { pk: assignment.scope_id, memberPk: row.id },
          });
        }
      }
      await refresh();
      onUpdated?.();
    } catch (e) {
      setError(e?.response?.detail || e?.message || "Failed to revoke role");
    } finally {
      setBusy(false);
    }
  };

  const handleOrgRoleChange = async (newOrgRole) => {
    if (busy || newOrgRole === orgRole) return;
    setBusy(true);
    setError(null);
    try {
      await api.callApi("updateOrganizationMemberRole", {
        params: { pk: organizationId ?? 1, userPk: user.id },
        body: { role: newOrgRole },
      });
      await refresh();
      onUpdated?.();
    } catch (e) {
      setError(e?.response?.detail || e?.message || "Failed to change org role");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={cn("manage-roles").toClassName()}>
      <div className={cn("manage-roles").elem("subject").toClassName()}>
        <strong>{user.email}</strong>
        <span>{user.first_name} {user.last_name}</span>
      </div>

      <section className={cn("manage-roles").elem("section").toClassName()}>
        <h4>Organization role</h4>
        <div className={cn("manage-roles").elem("row").toClassName()}>
          <Select
            value={orgRole}
            options={[
              { value: "super_admin", label: "Super Admin" },
              { value: "member", label: "Member" },
            ]}
            onChange={handleOrgRoleChange}
            disabled={busy}
          />
        </div>
      </section>

      <section className={cn("manage-roles").elem("section").toClassName()}>
        <h4>Current role assignments</h4>
        {assignments.length === 0 ? (
          <div className={cn("manage-roles").elem("empty").toClassName()}>
            No workspace or project roles granted yet.
          </div>
        ) : (
          <ul className={cn("manage-roles").elem("list").toClassName()}>
            {assignments.map((a) => (
              <li key={`${a.scope}-${a.scope_id}-${a.role}`}>
                <span className={cn("manage-roles").elem("chip").toClassName()}>
                  {roleLabel(a.role)}
                </span>
                <span className={cn("manage-roles").elem("scope").toClassName()}>
                  {a.scope}: {a.scope_title || `#${a.scope_id}`}
                </span>
                <Button
                  size="small"
                  look="outlined"
                  onClick={() => handleRevoke(a)}
                  disabled={busy}
                  aria-label={`Revoke ${a.role} on ${a.scope}`}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={cn("manage-roles").elem("section").toClassName()}>
        <h4>Grant a role</h4>
        <div className={cn("manage-roles").elem("row").toClassName()}>
          <Select
            value={selectedRole}
            options={ROLE_TYPES.map((r) => ({ value: r.value, label: r.label }))}
            onChange={setSelectedRole}
            disabled={busy}
          />
          {selectedRoleMeta?.scope !== "organization" && (
            <Select
              value={selectedScopeId}
              options={scopeOptions}
              onChange={setSelectedScopeId}
              placeholder={selectedRoleMeta?.scope === "workspace" ? "Workspace…" : "Project…"}
              disabled={busy || scopeOptions.length === 0}
            />
          )}
          <Button onClick={handleAdd} disabled={busy}>
            Grant
          </Button>
        </div>
      </section>

      {error && <div className={cn("manage-roles").elem("error").toClassName()}>{error}</div>}

      <div className={cn("manage-roles").elem("footer").toClassName()}>
        <Button look="outlined" onClick={onClose}>Close</Button>
      </div>
    </div>
  );
};
