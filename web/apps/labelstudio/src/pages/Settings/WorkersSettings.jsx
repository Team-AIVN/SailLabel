import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { DragDropContext, Draggable, Droppable } from "react-beautiful-dnd";
import { Button, useToast } from "@humansignal/ui";
import { ProjectContext } from "../../providers/ProjectProvider";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "../CreateProject/WorkerAssignment.prefix.css";

// Left pool droppable id + the three role zones. "member" is the no-work-role
// bucket (labeled "Worker"). A card's zone IS its staged ProjectMember.role.
const POOL = "members";
const ROLE_ZONES = [
  { id: "member", label: "Worker" },
  { id: "annotator", label: "Labelers" },
  { id: "reviewer", label: "Reviewers" },
];
const ROLE_IDS = new Set(ROLE_ZONES.map((z) => z.id));

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
 * Project Settings → Workers: drag-and-drop worker assignment. Workspace members
 * live in the left pool; drag a member into Worker / Labelers / Reviewers to assign,
 * between boxes to switch role, or back to the pool to unassign. "Worker" is the
 * no-work-role `member` state. Changes are staged locally and applied on Save.
 */
export const WorkersSettings = () => {
  const { project } = useContext(ProjectContext);
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("worker-assign"), []);

  const projectId = project?.id;
  const orgId = project?.organization;

  const [members, setMembers] = useState([]); // org members (assignable pool)
  const [userInfo, setUserInfo] = useState({}); // user_id -> user_detail
  const [serverByUser, setServerByUser] = useState({}); // user_id -> { memberId, role } (saved state)
  const [assignments, setAssignments] = useState({}); // user_id -> role (desired/staged)
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    // Pool is every organization member: assigning one to a project role also grants
    // workspace membership on the backend, so managers add people from here directly.
    const [org, pm] = await Promise.all([
      orgId ? api.callApi("memberships", { params: { pk: orgId } }) : Promise.resolve([]),
      api.callApi("projectMembers", { params: { pk: projectId } }),
    ]);
    // Org memberships expose { user: <user object> }; normalize to the { user: id,
    // user_detail: object } shape the rest of this component expects.
    const orgMembers = listOf(org).map((m) => ({ user: m.user?.id ?? m.user, user_detail: m.user_detail ?? m.user }));
    const projMembers = listOf(pm);

    const info = {};
    for (const m of orgMembers) info[m.user] = m.user_detail;
    for (const m of projMembers) info[m.user] = m.user_detail ?? info[m.user];

    const server = {};
    const desired = {};
    for (const m of projMembers) {
      if (ROLE_IDS.has(m.role)) {
        server[m.user] = { memberId: m.id, role: m.role };
        desired[m.user] = m.role;
      }
    }

    setMembers(orgMembers);
    setUserInfo(info);
    setServerByUser(server);
    setAssignments(desired);
    setLoading(false);
  }, [api, projectId, orgId]);

  useEffect(() => {
    load();
  }, [load]);

  // Derive per-zone user lists from the staged assignments.
  const byRole = useMemo(() => {
    const map = { member: [], annotator: [], reviewer: [] };
    for (const [uid, role] of Object.entries(assignments)) map[role]?.push(Number(uid));
    return map;
  }, [assignments]);
  const assignedUserIds = useMemo(() => new Set(Object.keys(assignments).map(Number)), [assignments]);

  // Left pool = workspace members not assigned to any role (respecting search).
  const poolMembers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return members
      .filter((m) => !assignedUserIds.has(m.user))
      .filter((m) => !q || userLabel(m.user_detail).toLowerCase().includes(q));
  }, [members, assignedUserIds, search]);

  const dirty = useMemo(() => {
    const keys = new Set([...Object.keys(serverByUser), ...Object.keys(assignments)]);
    for (const k of keys) {
      if ((serverByUser[k]?.role ?? null) !== (assignments[k] ?? null)) return true;
    }
    return false;
  }, [serverByUser, assignments]);

  const onDragEnd = useCallback((result) => {
    const { destination, draggableId } = result;
    if (!destination) return;
    const uid = Number(draggableId);
    const zone = destination.droppableId;
    setAssignments((prev) => {
      const next = { ...prev };
      if (zone === POOL) delete next[uid];
      else if (ROLE_IDS.has(zone)) next[uid] = zone;
      return next;
    });
  }, []);

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
  }, [serverByUser]);

  const renderCard = (uid, index) => (
    <Draggable key={uid} draggableId={String(uid)} index={index}>
      {(provided, snapshot) => (
        <li
          ref={provided.innerRef}
          {...provided.draggableProps}
          {...provided.dragHandleProps}
          className={root
            .elem("card")
            .mod({ dragging: snapshot.isDragging })
            .toClassName()}
        >
          <span className={root.elem("grip").toClassName()} aria-hidden>
            ⠿
          </span>
          <span className={root.elem("item-text").toClassName()}>{userLabel(userInfo[uid])}</span>
        </li>
      )}
    </Draggable>
  );

  const renderZone = (zoneId, title, uids, { head } = {}) => (
    <section className={root.elem(zoneId === POOL ? "panel" : "box").toClassName()}>
      {head ?? (
        <header className={root.elem("box-head").toClassName()}>
          <strong>
            {title}
            <span className={root.elem("count").toClassName()}>({uids.length})</span>
          </strong>
        </header>
      )}
      <Droppable droppableId={zoneId}>
        {(provided, snapshot) => (
          <ul
            ref={provided.innerRef}
            {...provided.droppableProps}
            className={root
              .elem("items")
              .mod({ over: snapshot.isDraggingOver })
              .toClassName()}
          >
            {uids.map((uid, i) => renderCard(uid, i))}
            {provided.placeholder}
            {uids.length === 0 && <li className={root.elem("muted").toClassName()}>{"여기로 드래그"}</li>}
          </ul>
        )}
      </Droppable>
    </section>
  );

  const poolHead = (
    <header className={root.elem("panel-head").toClassName()}>
      <strong>
        멤버
        <span className={root.elem("count").toClassName()}>({poolMembers.length})</span>
      </strong>
      <input placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
    </header>
  );

  return (
    <div className={cn("general-settings").toClassName()}>
      <div className={cn("general-settings").elem("wrapper").toClassName()}>
        <h1>Workers</h1>
        <p className={root.elem("hint").toClassName()}>
          조직 멤버를 <b>Worker</b>, <b>Labelers</b>, <b>Reviewers</b> 중 하나로 끌어다 놓아 배치하세요.
          <br />
          <b>Worker</b>는 아직 역할이 없는 상태이고, 상자 사이로 끌면 역할이 바뀝니다.
          <br />
          왼쪽으로 끌면 배치가 해제됩니다.
        </p>
        <div className={cn("settings-wrapper").toClassName()}>
          {loading ? (
            <div className={root.elem("loading").toClassName()}>…</div>
          ) : (
            <>
              <DragDropContext onDragEnd={onDragEnd}>
                <div className={root.mod({ dnd: true, triple: true }).toClassName()}>
                  {/* LEFT: unassigned workspace members */}
                  {renderZone(POOL, "멤버", poolMembers.map((m) => m.user), { head: poolHead })}

                  {/* RIGHT: three role zones */}
                  <div className={root.elem("roles").toClassName()}>
                    {ROLE_ZONES.map((z) => (
                      <div key={z.id}>{renderZone(z.id, z.label, byRole[z.id] ?? [])}</div>
                    ))}
                  </div>
                </div>
              </DragDropContext>

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
