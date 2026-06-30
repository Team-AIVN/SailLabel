import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./WorkerAssignment.prefix.css";

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
 * Two-panel worker assignment (mirrors the Task Pool UI): workspace members on the
 * left, the project's Annotators / Reviewers on the right. Pick a right-side list to
 * activate it, then add (→) selected members or remove (←) them — exactly like pools.
 */
export const WorkerAssignment = ({ projectId, workspaceId, show = true }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("worker-assign"), []);

  const [members, setMembers] = useState([]); // workspace members (left pool)
  const [projectMembers, setProjectMembers] = useState([]); // assigned (right)
  const [activeRole, setActiveRole] = useState("annotator");
  const [leftSelected, setLeftSelected] = useState(() => new Set());
  const [rightSelected, setRightSelected] = useState(() => new Set());
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

  const annotators = useMemo(() => projectMembers.filter((m) => m.role === "annotator"), [projectMembers]);
  const reviewers = useMemo(() => projectMembers.filter((m) => m.role === "reviewer"), [projectMembers]);
  const byRole = activeRole === "annotator" ? annotators : reviewers;
  const assignedUserIds = useMemo(() => new Set(byRole.map((m) => m.user)), [byRole]);
  const roleByUser = useMemo(() => {
    const map = new Map();
    for (const m of projectMembers) map.set(m.user, m.role);
    return map;
  }, [projectMembers]);

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

  const refresh = useCallback(async () => {
    await loadProjectMembers();
    setLeftSelected(new Set());
    setRightSelected(new Set());
  }, [loadProjectMembers]);

  const selectRole = useCallback((role) => {
    setActiveRole(role);
    setLeftSelected(new Set());
    setRightSelected(new Set());
  }, []);

  const addMembers = useCallback(async () => {
    const userIds = Array.from(leftSelected).filter((uid) => !assignedUserIds.has(uid));
    if (userIds.length === 0) return;
    const results = await Promise.all(
      userIds.map((uid) =>
        api.callApi("createProjectMember", { params: { pk: projectId }, body: { user: uid, role: activeRole } }),
      ),
    );
    if (results.some((r) => r && r.error)) {
      toast.show({ message: t("assign.actionFailed", "Could not update assignment"), type: "error" });
    } else {
      toast.show({ message: t("assign.added", "Workers assigned") });
    }
    await refresh();
  }, [api, projectId, leftSelected, assignedUserIds, activeRole, toast, t, refresh]);

  const removeMembers = useCallback(async () => {
    const ids = Array.from(rightSelected);
    if (ids.length === 0) return;
    await Promise.all(
      ids.map((memberPk) => api.callApi("deleteProjectMember", { params: { pk: projectId, memberPk } })),
    );
    toast.show({ message: t("assign.removed", "Workers removed") });
    await refresh();
  }, [api, projectId, rightSelected, toast, t, refresh]);

  if (!show) return null;
  if (loading || !ready) return <div className={root.elem("loading").toClassName()}>…</div>;

  const renderRoleBox = (role, rows) => {
    const isActive = activeRole === role;
    return (
      <section className={root.elem("box").mod({ active: isActive }).toClassName()} onClick={() => selectRole(role)}>
        <header className={root.elem("box-head").toClassName()}>
          <strong>
            {role === "annotator" ? t("assign.annotators", "Annotators") : t("assign.reviewers", "Reviewers")}
            <span className={root.elem("count").toClassName()}>({rows.length})</span>
          </strong>
          {isActive && <span className={root.elem("active-tag").toClassName()}>{t("assign.active", "Active")}</span>}
        </header>
        <ul className={root.elem("items").toClassName()}>
          {rows.map((m) => (
            <li
              key={m.id}
              className={root
                .elem("item")
                .mod({ selected: rightSelected.has(m.id) })
                .toClassName()}
            >
              <input
                type="checkbox"
                disabled={!isActive}
                checked={rightSelected.has(m.id)}
                onChange={() => toggleRight(m.id)}
                onClick={(e) => e.stopPropagation()}
              />
              <span className={root.elem("item-text").toClassName()}>{userLabel(m.user_detail)}</span>
            </li>
          ))}
          {rows.length === 0 && <li className={root.elem("muted").toClassName()}>{t("assign.none", "None")}</li>}
        </ul>
      </section>
    );
  };

  return (
    <div className={cn("project-name").toClassName()}>
      <div className={root.toClassName()}>
        {/* LEFT: workspace members */}
        <section className={root.elem("panel").toClassName()}>
          <header className={root.elem("panel-head").toClassName()}>
            <strong>{t("assign.workspaceMembers", "Workspace members")}</strong>
            <input
              placeholder={t("assign.search", "Search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </header>
          <ul className={root.elem("items").toClassName()}>
            {visibleMembers.map((m) => {
              const included = assignedUserIds.has(m.user);
              const currentRole = roleByUser.get(m.user);
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
                      {currentRole === "annotator"
                        ? t("assign.annotator", "Annotator")
                        : t("assign.reviewer", "Reviewer")}
                    </span>
                  )}
                </li>
              );
            })}
            {visibleMembers.length === 0 && (
              <li className={root.elem("muted").toClassName()}>{t("assign.noMembers", "No members")}</li>
            )}
          </ul>
        </section>

        {/* CENTER: arrows */}
        <div className={root.elem("controls").toClassName()}>
          <Button
            size="small"
            onClick={addMembers}
            disabled={Array.from(leftSelected).every((uid) => assignedUserIds.has(uid))}
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
    </div>
  );
};
