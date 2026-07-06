import { useCallback, useEffect, useMemo, useState } from "react";
import { DragDropContext, Draggable, Droppable } from "react-beautiful-dnd";
import { useTranslation } from "react-i18next";
import { useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./WorkerAssignment.prefix.css";

// At project creation we don't split labeler/reviewer: whoever is added is a
// worker (stored as annotator). Reviewers are designated later in the project's
// Workers settings tab.
const POOL = "members";
const WORKERS = "workers";
const WORKER_ROLES = new Set(["annotator", "reviewer"]);

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
 * Drag-and-drop worker assignment for project creation: workspace members on the
 * left, the project's workers on the right. Drag a member into Workers to assign
 * (stored as annotator), drag back to unassign. Changes persist immediately.
 */
export const WorkerAssignment = ({ projectId, workspaceId, show = true }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("worker-assign"), []);

  const [members, setMembers] = useState([]); // workspace members (left pool)
  const [projectMembers, setProjectMembers] = useState([]); // assigned (right)
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);

  const loadMembers = useCallback(async () => {
    const ws = await api.callApi("workspaceMembers", { params: { pk: workspaceId } });
    setMembers(listOf(ws));
  }, [api, workspaceId]);

  const loadProjectMembers = useCallback(async () => {
    const pm = await api.callApi("projectMembers", { params: { pk: projectId } });
    setProjectMembers(listOf(pm));
  }, [api, projectId]);

  // Persist the chosen workspace onto the draft project first, so workspace-manager
  // authority resolves (membership management requires it) before we load/mutate.
  useEffect(() => {
    if (!show || !projectId || !workspaceId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      await api.callApi("updateProject", { params: { pk: projectId }, body: { workspace: workspaceId } });
      if (cancelled) return;
      await Promise.all([loadMembers(), loadProjectMembers()]);
      if (cancelled) return;
      setLoading(false);
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [show, projectId, workspaceId, api, loadMembers, loadProjectMembers]);

  // Workers = project members holding a worker role (annotator/reviewer).
  const workers = useMemo(() => projectMembers.filter((m) => WORKER_ROLES.has(m.role)), [projectMembers]);
  const memberIdByUser = useMemo(() => {
    const map = new Map();
    for (const m of workers) map.set(m.user, m.id);
    return map;
  }, [workers]);
  const assignedUserIds = useMemo(() => new Set(workers.map((m) => m.user)), [workers]);

  // Left pool = workspace members not yet assigned (respecting search).
  const poolMembers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return members
      .filter((m) => !assignedUserIds.has(m.user))
      .filter((m) => !q || userLabel(m.user_detail).toLowerCase().includes(q));
  }, [members, assignedUserIds, search]);

  const refresh = useCallback(async () => {
    await loadProjectMembers();
  }, [loadProjectMembers]);

  const onDragEnd = useCallback(
    async (result) => {
      const { destination, draggableId } = result;
      if (!destination) return;
      const uid = Number(draggableId);
      const zone = destination.droppableId;

      if (zone === WORKERS) {
        if (assignedUserIds.has(uid)) return; // reordering within workers, no-op
        const res = await api.callApi("createProjectMember", {
          params: { pk: projectId },
          body: { user: uid, role: "annotator" },
        });
        if (res && res.error) {
          toast.show({ message: t("assign.actionFailed", "Could not update assignment"), type: "error" });
        } else {
          toast.show({ message: t("assign.added", "Workers assigned") });
        }
        await refresh();
      } else if (zone === POOL) {
        const memberPk = memberIdByUser.get(uid);
        if (!memberPk) return; // wasn't assigned, no-op
        await api.callApi("deleteProjectMember", { params: { pk: projectId, memberPk } });
        toast.show({ message: t("assign.removed", "Workers removed") });
        await refresh();
      }
    },
    [api, projectId, assignedUserIds, memberIdByUser, toast, t, refresh],
  );

  if (!show) return null;
  if (loading || !ready) return <div className={root.elem("loading").toClassName()}>…</div>;

  const renderCard = (uid, detail, index) => (
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
          <span className={root.elem("item-text").toClassName()}>{userLabel(detail)}</span>
        </li>
      )}
    </Draggable>
  );

  return (
    <div className={cn("project-name").toClassName()}>
      <DragDropContext onDragEnd={onDragEnd}>
        <div className={root.mod({ dnd: true }).toClassName()}>
          {/* LEFT: workspace members */}
          <section className={root.elem("panel").toClassName()}>
            <header className={root.elem("panel-head").toClassName()}>
              <strong>
                {t("assign.workspaceMembers", "Workspace members")}
                <span className={root.elem("count").toClassName()}>({poolMembers.length})</span>
              </strong>
              <input
                placeholder={t("assign.search", "Search")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </header>
            <Droppable droppableId={POOL}>
              {(provided, snapshot) => (
                <ul
                  ref={provided.innerRef}
                  {...provided.droppableProps}
                  className={root
                    .elem("items")
                    .mod({ over: snapshot.isDraggingOver })
                    .toClassName()}
                >
                  {poolMembers.map((m, i) => renderCard(m.user, m.user_detail, i))}
                  {provided.placeholder}
                  {poolMembers.length === 0 && (
                    <li className={root.elem("muted").toClassName()}>{t("assign.noMembers", "No members")}</li>
                  )}
                </ul>
              )}
            </Droppable>
          </section>

          {/* RIGHT: workers (no role split) */}
          <section className={root.elem("box").toClassName()}>
            <header className={root.elem("box-head").toClassName()}>
              <strong>
                {t("assign.workers", "Workers")}
                <span className={root.elem("count").toClassName()}>({workers.length})</span>
              </strong>
            </header>
            <Droppable droppableId={WORKERS}>
              {(provided, snapshot) => (
                <ul
                  ref={provided.innerRef}
                  {...provided.droppableProps}
                  className={root
                    .elem("items")
                    .mod({ over: snapshot.isDraggingOver })
                    .toClassName()}
                >
                  {workers.map((m, i) => renderCard(m.user, m.user_detail, i))}
                  {provided.placeholder}
                  {workers.length === 0 && (
                    <li className={root.elem("muted").toClassName()}>{t("assign.dragHere", "여기로 드래그")}</li>
                  )}
                </ul>
              )}
            </Droppable>
          </section>
        </div>
      </DragDropContext>
    </div>
  );
};
