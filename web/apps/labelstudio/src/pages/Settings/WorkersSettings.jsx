import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Button, useToast } from "@humansignal/ui";
import { ProjectContext } from "../../providers/ProjectProvider";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "../CreateProject/WorkerAssignment.prefix.css";

const ROLES = ["annotator", "reviewer"];

const listOf = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const userLabel = (detail) => {
  if (!detail) return "—";
  const name = `${detail.first_name ?? ""} ${detail.last_name ?? ""}`.trim();
  return name || detail.username || detail.email || `User ${detail.id}`;
};

/**
 * Project Settings → Workers: the same two-panel annotator/reviewer assignment used in
 * project creation, reflecting this project's current members. Changes are staged locally
 * and only applied on Save (Cancel reverts to the saved state).
 */
export const WorkersSettings = () => {
  const { project } = useContext(ProjectContext);
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("worker-assign"), []);

  const projectId = project?.id;
  const workspaceId = project?.workspace;

  const [members, setMembers] = useState([]); // workspace members (left pool)
  const [userInfo, setUserInfo] = useState({}); // user_id -> user_detail
  const [serverByUser, setServerByUser] = useState({}); // user_id -> { memberId, role } (saved state)
  const [assignments, setAssignments] = useState({}); // user_id -> role (desired/staged)
  const [activeRole, setActiveRole] = useState("annotator");
  const [leftSelected, setLeftSelected] = useState(() => new Set());
  const [rightSelected, setRightSelected] = useState(() => new Set());
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    const [ws, pm] = await Promise.all([
      workspaceId ? api.callApi("workspaceMembers", { params: { pk: workspaceId } }) : Promise.resolve([]),
      api.callApi("projectMembers", { params: { pk: projectId } }),
    ]);
    const wsMembers = listOf(ws);
    const projMembers = listOf(pm);

    const info = {};
    for (const m of wsMembers) info[m.user] = m.user_detail;
    for (const m of projMembers) info[m.user] = m.user_detail ?? info[m.user];

    const server = {};
    const desired = {};
    for (const m of projMembers) {
      if (m.role === "annotator" || m.role === "reviewer") {
        server[m.user] = { memberId: m.id, role: m.role };
        desired[m.user] = m.role;
      }
    }

    setMembers(wsMembers);
    setUserInfo(info);
    setServerByUser(server);
    setAssignments(desired);
    setLeftSelected(new Set());
    setRightSelected(new Set());
    setLoading(false);
  }, [api, projectId, workspaceId]);

  useEffect(() => {
    load();
  }, [load]);

  const annotators = useMemo(
    () =>
      Object.keys(assignments)
        .filter((u) => assignments[u] === "annotator")
        .map(Number),
    [assignments],
  );
  const reviewers = useMemo(
    () =>
      Object.keys(assignments)
        .filter((u) => assignments[u] === "reviewer")
        .map(Number),
    [assignments],
  );
  const assignedActive = useMemo(
    () => new Set(activeRole === "annotator" ? annotators : reviewers),
    [activeRole, annotators, reviewers],
  );

  const dirty = useMemo(() => {
    const keys = new Set([...Object.keys(serverByUser), ...Object.keys(assignments)]);
    for (const k of keys) {
      if ((serverByUser[k]?.role ?? null) !== (assignments[k] ?? null)) return true;
    }
    return false;
  }, [serverByUser, assignments]);

  const visibleMembers = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return members;
    return members.filter((m) => userLabel(m.user_detail).toLowerCase().includes(q));
  }, [members, search]);

  const toggle = (setFn) => (id) =>
    setFn((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const toggleLeft = toggle(setLeftSelected);
  const toggleRight = toggle(setRightSelected);

  const selectRole = useCallback((role) => {
    setActiveRole(role);
    setLeftSelected(new Set());
    setRightSelected(new Set());
  }, []);

  const addMembers = useCallback(() => {
    setAssignments((prev) => {
      const next = { ...prev };
      for (const uid of leftSelected) next[uid] = activeRole;
      return next;
    });
    setLeftSelected(new Set());
  }, [leftSelected, activeRole]);

  const removeMembers = useCallback(() => {
    setAssignments((prev) => {
      const next = { ...prev };
      for (const uid of rightSelected) delete next[uid];
      return next;
    });
    setRightSelected(new Set());
  }, [rightSelected]);

  const onSave = useCallback(async () => {
    if (!dirty) return;
    setSaving(true);
    const ops = [];
    // Removals + role changes against the saved state.
    for (const [uidStr, srv] of Object.entries(serverByUser)) {
      const uid = Number(uidStr);
      const desiredRole = assignments[uid];
      if (!desiredRole) {
        ops.push(api.callApi("deleteProjectMember", { params: { pk: projectId, memberPk: srv.memberId } }));
      } else if (desiredRole !== srv.role) {
        // POST upserts the (user, project) row's role on the backend.
        ops.push(
          api.callApi("createProjectMember", { params: { pk: projectId }, body: { user: uid, role: desiredRole } }),
        );
      }
    }
    // Additions.
    for (const [uidStr, role] of Object.entries(assignments)) {
      const uid = Number(uidStr);
      if (!serverByUser[uid]) {
        ops.push(api.callApi("createProjectMember", { params: { pk: projectId }, body: { user: uid, role } }));
      }
    }
    const results = await Promise.all(ops);
    setSaving(false);
    if (results.some((r) => r && r.error)) {
      toast.show({ message: "Could not save some changes", type: "error" });
    } else {
      toast.show({ message: "Workers updated" });
    }
    await load();
  }, [api, projectId, dirty, serverByUser, assignments, toast, load]);

  const onCancel = useCallback(() => {
    const desired = {};
    for (const [uid, srv] of Object.entries(serverByUser)) desired[uid] = srv.role;
    setAssignments(desired);
    setLeftSelected(new Set());
    setRightSelected(new Set());
  }, [serverByUser]);

  const renderRoleBox = (role, rows) => {
    const isActive = activeRole === role;
    return (
      <section className={root.elem("box").mod({ active: isActive }).toClassName()} onClick={() => selectRole(role)}>
        <header className={root.elem("box-head").toClassName()}>
          <strong>
            {role === "annotator" ? "Annotators" : "Reviewers"}
            <span className={root.elem("count").toClassName()}>({rows.length})</span>
          </strong>
          {isActive && <span className={root.elem("active-tag").toClassName()}>Active</span>}
        </header>
        <ul className={root.elem("items").toClassName()}>
          {rows.map((uid) => (
            <li
              key={uid}
              className={root
                .elem("item")
                .mod({ selected: rightSelected.has(uid) })
                .toClassName()}
            >
              <input
                type="checkbox"
                disabled={!isActive}
                checked={rightSelected.has(uid)}
                onChange={() => toggleRight(uid)}
                onClick={(e) => e.stopPropagation()}
              />
              <span className={root.elem("item-text").toClassName()}>{userLabel(userInfo[uid])}</span>
            </li>
          ))}
          {rows.length === 0 && <li className={root.elem("muted").toClassName()}>None</li>}
        </ul>
      </section>
    );
  };

  return (
    <div className={cn("general-settings").toClassName()}>
      <div className={cn("general-settings").elem("wrapper").toClassName()}>
        <h1>Workers</h1>
        <div className={cn("settings-wrapper").toClassName()}>
          {loading ? (
            <div className={root.elem("loading").toClassName()}>…</div>
          ) : (
            <>
              <div className={root.toClassName()}>
                {/* LEFT: workspace members */}
                <section className={root.elem("panel").toClassName()}>
                  <header className={root.elem("panel-head").toClassName()}>
                    <strong>Workspace members</strong>
                    <input placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
                  </header>
                  <ul className={root.elem("items").toClassName()}>
                    {visibleMembers.map((m) => {
                      const included = assignedActive.has(m.user);
                      const currentRole = assignments[m.user];
                      return (
                        <li
                          key={m.id}
                          className={root
                            .elem("item")
                            .mod({ included, selected: leftSelected.has(m.user) })
                            .toClassName()}
                        >
                          <input
                            type="checkbox"
                            disabled={included}
                            checked={leftSelected.has(m.user)}
                            onChange={() => toggleLeft(m.user)}
                          />
                          <span className={root.elem("item-text").toClassName()}>{userLabel(m.user_detail)}</span>
                          {currentRole && (
                            <span className={root.elem("badge").mod({ role: currentRole }).toClassName()}>
                              {currentRole === "annotator" ? "Annotator" : "Reviewer"}
                            </span>
                          )}
                        </li>
                      );
                    })}
                    {visibleMembers.length === 0 && <li className={root.elem("muted").toClassName()}>No members</li>}
                  </ul>
                </section>

                {/* CENTER: arrows */}
                <div className={root.elem("controls").toClassName()}>
                  <Button
                    size="small"
                    onClick={addMembers}
                    disabled={Array.from(leftSelected).every((uid) => assignedActive.has(uid))}
                    aria-label="add"
                  >
                    →
                  </Button>
                  <Button
                    size="small"
                    look="outlined"
                    onClick={removeMembers}
                    disabled={rightSelected.size === 0}
                    aria-label="remove"
                  >
                    ←
                  </Button>
                </div>

                {/* RIGHT: annotators / reviewers */}
                <div className={root.elem("roles").toClassName()}>
                  {ROLES.map((role) => renderRoleBox(role, role === "annotator" ? annotators : reviewers))}
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
                <Button
                  look="outlined"
                  onClick={onCancel}
                  disabled={!dirty || saving}
                  aria-label="Cancel worker changes"
                >
                  Cancel
                </Button>
                <Button onClick={onSave} waiting={saving} disabled={!dirty} aria-label="Save worker changes">
                  Save
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

WorkersSettings.menuItem = "Workers";
WorkersSettings.path = "/workers";
WorkersSettings.exact = true;
