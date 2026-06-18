import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useHistory, useLocation, useParams } from "react-router";
import { Button, useToast } from "@humansignal/ui";
import { Modal } from "../../components/Modal/Modal";
import { Space } from "../../components/Space/Space";
import { Spinner } from "../../components/Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import { CreateProject } from "../CreateProject/CreateProject";
import { WorkPools } from "./WorkPools";
import { WorkspaceImportPage } from "./WorkspaceImport";
import "./WorkspaceDetail.prefix.css";

const TABS = ["projects", "datasets", "workpools", "users"];
const TAB_LABEL_KEY = {
  projects: "workspaces.detail.projects",
  datasets: "workspaces.detail.dataset",
  workpools: "workspaces.detail.workpools",
  users: "workspaces.detail.members",
};
const WORKSPACE_ROLES = ["member", "workspace_manager"];

const listOf = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const userLabel = (user) => {
  if (!user) return "";
  const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  return name || user.email || user.username || `User ${user.id}`;
};

const formatDate = (value) => {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString();
  } catch {
    return "—";
  }
};

export const WorkspaceDetail = () => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const { id } = useParams();
  const history = useHistory();
  const location = useLocation();
  const root = useMemo(() => cn("workspace-detail"), []);

  const activeTab = useMemo(() => {
    const tab = new URLSearchParams(location.search).get("tab");
    return TABS.includes(tab) ? tab : "projects";
  }, [location.search]);

  const setTab = useCallback((tab) => history.push(`/workspaces/${id}?tab=${tab}`), [history, id]);

  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const [projects, setProjects] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [users, setUsers] = useState([]);
  const [orgMembers, setOrgMembers] = useState([]);

  // filters
  const [projectSearch, setProjectSearch] = useState("");
  const [labelTypeFilter, setLabelTypeFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [ordering, setOrdering] = useState("-created_at");
  const [datasetSearch, setDatasetSearch] = useState("");
  const [userSearch, setUserSearch] = useState("");

  // create affordances
  const [showNewProject, setShowNewProject] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteUser, setInviteUser] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [showImport, setShowImport] = useState(false);
  const [importUploading, setImportUploading] = useState(false);

  const loadSummary = useCallback(async () => {
    const res = await api.callApi("workspaceSummary", { params: { pk: id } });
    setSummary(res ?? null);
  }, [api, id]);

  const loadProjects = useCallback(async () => {
    const params = { pk: id, ordering };
    if (projectSearch) params.search = projectSearch;
    if (labelTypeFilter) params.label_type = labelTypeFilter;
    if (tagFilter) params.tag = tagFilter;
    const res = await api.callApi("workspaceProjects", { params });
    setProjects(listOf(res));
  }, [api, id, ordering, projectSearch, labelTypeFilter, tagFilter]);

  const loadDatasets = useCallback(async () => {
    const params = { pk: id };
    if (datasetSearch) params.search = datasetSearch;
    const res = await api.callApi("workspaceDatasets", { params });
    setDatasets(listOf(res));
  }, [api, id, datasetSearch]);

  const loadUsers = useCallback(async () => {
    const params = { pk: id };
    if (userSearch) params.search = userSearch;
    const res = await api.callApi("workspaceMembers", { params });
    setUsers(listOf(res));
  }, [api, id, userSearch]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await Promise.all([loadSummary(), loadProjects(), loadDatasets(), loadUsers()]);
      setLoading(false);
    })();
    // initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // reactive reloads when filters change
  useEffect(() => {
    loadProjects();
  }, [loadProjects]);
  useEffect(() => {
    loadDatasets();
  }, [loadDatasets]);
  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const loadOrgMembers = useCallback(async () => {
    // summary doesn't carry org id; fetch the workspace detail to resolve it
    const detail = await api.callApi("workspace", { params: { pk: id } });
    if (detail?.organization) {
      const res = await api.callApi("memberships", { params: { pk: detail.organization } });
      setOrgMembers(listOf(res));
    }
  }, [api, id]);

  const labelTypeOptions = useMemo(() => {
    const set = new Set(projects.map((p) => p.label_type).filter(Boolean));
    return Array.from(set);
  }, [projects]);

  // --- actions ---
  const closeNewProject = useCallback(() => {
    setShowNewProject(false);
    loadProjects();
    loadSummary();
  }, [loadProjects, loadSummary]);

  const openImport = useCallback(() => setShowImport(true), []);

  const closeImport = useCallback(() => {
    setShowImport(false);
    // WorkspaceImport uploads files to the pool as they are dropped, so refresh on close.
    loadDatasets();
    loadSummary();
  }, [loadDatasets, loadSummary]);

  const inviteMember = useCallback(async () => {
    if (!inviteUser) return;
    const res = await api.callApi("createWorkspaceMember", {
      params: { pk: id },
      body: { user: Number(inviteUser), role: inviteRole },
    });
    if (res?.id) {
      toast.show({ message: t("workspaces.members.added") });
      setInviteUser("");
      setInviteRole("member");
      setShowInvite(false);
      loadUsers();
      loadSummary();
    } else {
      toast.show({ message: res?.detail ?? t("workspaces.members.addFailed"), type: "error" });
    }
  }, [api, id, inviteUser, inviteRole, toast, t, loadUsers, loadSummary]);

  const changeRole = useCallback(
    async (member, role) => {
      await api.callApi("updateWorkspaceMember", { params: { pk: id, memberPk: member.id }, body: { role } });
      toast.show({ message: t("workspaces.members.roleUpdated") });
      loadUsers();
    },
    [api, id, toast, t, loadUsers],
  );

  const removeMember = useCallback(
    async (member) => {
      await api.callApi("deleteWorkspaceMember", { params: { pk: id, memberPk: member.id } });
      toast.show({ message: t("workspaces.members.removed") });
      loadUsers();
      loadSummary();
    },
    [api, id, toast, t, loadUsers, loadSummary],
  );

  const openQuickAction = useCallback(
    (action) => {
      if (action === "project") {
        setTab("projects");
        setShowNewProject(true);
      } else if (action === "dataset") {
        setTab("datasets");
        openImport();
      } else if (action === "user") {
        setTab("users");
        setShowInvite(true);
        loadOrgMembers();
      }
    },
    [setTab, loadOrgMembers, openImport],
  );

  if (loading && !summary) {
    return (
      <div className={root.elem("loading").toClassName()}>
        <Spinner size={48} />
      </div>
    );
  }

  const memberUserIds = new Set(users.map((m) => m.user));
  const addableUsers = orgMembers
    .map((m) => m.user_detail ?? m.user)
    .filter((u) => u && typeof u === "object" && !memberUserIds.has(u.id));

  return (
    <div className={root.toClassName()}>
      {/* Header */}
      <header className={root.elem("header").toClassName()}>
        <div className={root.elem("header-main").toClassName()}>
          <h1>{summary?.title}</h1>
          {summary?.description && <p>{summary.description}</p>}
        </div>
        <div className={root.elem("stats").toClassName()}>
          <div className={root.elem("stat").toClassName()}>
            <span className={root.elem("stat-value").toClassName()}>{summary?.total_users ?? 0}</span>
            <span className={root.elem("stat-label").toClassName()}>{t("workspaces.detail.members")}</span>
          </div>
          <div className={root.elem("stat").toClassName()}>
            <span className={root.elem("stat-value").toClassName()}>{summary?.total_datasets ?? 0}</span>
            <span className={root.elem("stat-label").toClassName()}>{t("workspaces.detail.dataset")}</span>
          </div>
          <div className={root.elem("stat").toClassName()}>
            <span className={root.elem("stat-value").toClassName()}>{summary?.total_projects ?? 0}</span>
            <span className={root.elem("stat-label").toClassName()}>{t("workspaces.detail.projects")}</span>
          </div>
          <div className={root.elem("stat").toClassName()}>
            <span className={root.elem("stat-value").toClassName()}>{summary?.total_work_pools ?? 0}</span>
            <span className={root.elem("stat-label").toClassName()}>{t("workspaces.detail.workpools")}</span>
          </div>
        </div>
      </header>

      {/* Quick actions */}
      <div className={root.elem("quick-actions").toClassName()}>
        <Button size="small" onClick={() => openQuickAction("project")}>
          {t("workspaces.dashboard.newProject", "New Project")}
        </Button>
        <Button size="small" look="outlined" onClick={() => openQuickAction("dataset")}>
          {t("workspaces.dashboard.newDataset", "New Dataset")}
        </Button>
        <Button size="small" look="outlined" onClick={() => openQuickAction("user")}>
          {t("workspaces.dashboard.inviteUser", "Invite User")}
        </Button>
      </div>

      {/* Tabs */}
      <nav className={root.elem("tabs").toClassName()}>
        {TABS.map((tab) => (
          <button
            type="button"
            key={tab}
            className={root
              .elem("tab")
              .mod({ active: activeTab === tab })
              .toClassName()}
            onClick={() => setTab(tab)}
          >
            {t(TAB_LABEL_KEY[tab])}
          </button>
        ))}
      </nav>

      {/* Projects tab (primary) */}
      {activeTab === "projects" && (
        <section className={root.elem("panel").toClassName()}>
          <div className={root.elem("toolbar").toClassName()}>
            <input
              className={root.elem("search").toClassName()}
              placeholder={t("workspaces.dashboard.searchProjects", "Search projects")}
              value={projectSearch}
              onChange={(e) => setProjectSearch(e.target.value)}
            />
            <select value={labelTypeFilter} onChange={(e) => setLabelTypeFilter(e.target.value)}>
              <option value="">{t("workspaces.dashboard.allTypes", "All types")}</option>
              {labelTypeOptions.map((lt) => (
                <option key={lt} value={lt}>
                  {lt}
                </option>
              ))}
            </select>
            <input
              className={root.elem("tag-filter").toClassName()}
              placeholder={t("workspaces.dashboard.filterTag", "Filter by tag")}
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
            />
            <select value={ordering} onChange={(e) => setOrdering(e.target.value)}>
              <option value="-created_at">{t("workspaces.dashboard.sortNewest", "Newest")}</option>
              <option value="due_date">{t("workspaces.dashboard.sortDueDate", "Due date")}</option>
              <option value="-progress">{t("workspaces.dashboard.sortProgress", "Progress")}</option>
              <option value="title">{t("workspaces.dashboard.sortTitle", "Title")}</option>
            </select>
            <Button size="small" onClick={() => setShowNewProject(true)}>
              {t("workspaces.dashboard.newProject", "New Project")}
            </Button>
          </div>

          {projects.length === 0 ? (
            <p className={root.elem("muted").toClassName()}>{t("workspaces.detail.noProjects")}</p>
          ) : (
            <div className={root.elem("cards").toClassName()}>
              {projects.map((p) => (
                <a key={p.id} href={`/projects/${p.id}/data`} className={root.elem("card").toClassName()}>
                  <div className={root.elem("card-head").toClassName()}>
                    <h3>{p.title}</h3>
                    {p.label_type && <span className={root.elem("badge").toClassName()}>{p.label_type}</span>}
                  </div>
                  <div className={root.elem("progress").toClassName()}>
                    <div
                      className={root.elem("progress-bar").toClassName()}
                      style={{ width: `${p.review_progress ?? 0}%` }}
                    />
                  </div>
                  <div className={root.elem("card-meta").toClassName()}>
                    <span>
                      {t("workspaces.dashboard.reviewProgress", "{{p}}% reviewed", { p: p.review_progress ?? 0 })}
                    </span>
                    <span>{formatDate(p.due_date)}</span>
                  </div>
                  {Array.isArray(p.tags) && p.tags.length > 0 && (
                    <div className={root.elem("tags").toClassName()}>
                      {p.tags.map((tag) => (
                        <span key={tag} className={root.elem("tag").toClassName()}>
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </a>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Datasets tab */}
      {activeTab === "datasets" && (
        <section className={root.elem("panel").toClassName()}>
          <div className={root.elem("toolbar").toClassName()}>
            <input
              className={root.elem("search").toClassName()}
              placeholder={t("workspaces.dashboard.searchDatasets", "Search datasets")}
              value={datasetSearch}
              onChange={(e) => setDatasetSearch(e.target.value)}
            />
            <Button size="small" onClick={openImport}>
              {t("workspaces.dashboard.newDataset", "New Dataset")}
            </Button>
          </div>
          <table className={root.elem("table").toClassName()}>
            <thead>
              <tr>
                <th>{t("workspaces.dashboard.datasetName", "Name")}</th>
                <th>{t("workspaces.dashboard.dataType", "Type")}</th>
                <th>{t("workspaces.dashboard.itemCount", "Items")}</th>
                <th>{t("workspaces.dashboard.lastUpdated", "Last updated")}</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.data_type}</td>
                  <td>{d.item_count ?? "—"}</td>
                  <td>{formatDate(d.last_updated)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* Work Pools tab */}
      {activeTab === "workpools" && (
        <section className={root.elem("panel").toClassName()}>
          <WorkPools workspaceId={Number(id)} />
        </section>
      )}

      {/* Users tab */}
      {activeTab === "users" && (
        <section className={root.elem("panel").toClassName()}>
          <div className={root.elem("toolbar").toClassName()}>
            <input
              className={root.elem("search").toClassName()}
              placeholder={t("workspaces.dashboard.searchUsers", "Search users")}
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
            />
            <Button
              size="small"
              onClick={() => {
                setShowInvite((v) => !v);
                loadOrgMembers();
              }}
            >
              {t("workspaces.dashboard.inviteUser", "Invite User")}
            </Button>
          </div>

          {showInvite && (
            <div className={root.elem("inline-form").toClassName()}>
              <select value={inviteUser} onChange={(e) => setInviteUser(e.target.value)}>
                <option value="">{t("workspaces.members.selectUser")}</option>
                {addableUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {userLabel(u)}
                  </option>
                ))}
              </select>
              <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
                {WORKSPACE_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {t(`workspaces.roles.${r}`, r)}
                  </option>
                ))}
              </select>
              <Button size="small" onClick={inviteMember} disabled={!inviteUser}>
                {t("workspaces.members.add")}
              </Button>
            </div>
          )}

          <table className={root.elem("table").toClassName()}>
            <thead>
              <tr>
                <th>{t("workspaces.members.user")}</th>
                <th>{t("workspaces.members.role")}</th>
                <th aria-label="actions" />
              </tr>
            </thead>
            <tbody>
              {users.map((m) => (
                <tr key={m.id}>
                  <td>{userLabel(m.user_detail)}</td>
                  <td>
                    <select value={m.role} onChange={(e) => changeRole(m, e.target.value)}>
                      {WORKSPACE_ROLES.map((r) => (
                        <option key={r} value={r}>
                          {t(`workspaces.roles.${r}`, r)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <Button look="outlined" size="small" variant="negative" onClick={() => removeMember(m)}>
                      {t("common.remove", "Remove")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {showImport && (
        <Modal
          title={t("workspaces.dashboard.importTitle", "Import data")}
          onHide={closeImport}
          fullscreen
          visible
          bare
        >
          <Modal.Header divided>
            <div className={cn("modal").elem("title").toClassName()}>
              {t("workspaces.dashboard.importTitle", "Import data")}
            </div>
            <Space>
              <Button
                size="small"
                onClick={closeImport}
                waiting={importUploading}
                aria-label={t("common.close", "Close")}
              >
                {t("common.close", "Close")}
              </Button>
            </Space>
          </Modal.Header>
          <WorkspaceImportPage
            workspace={summary ? { id: summary.id } : { id: Number(id) }}
            show
            onWaiting={setImportUploading}
            onFileListUpdate={() => {}}
          />
        </Modal>
      )}

      {showNewProject && <CreateProject workspaceId={Number(id)} onClose={closeNewProject} />}
    </div>
  );
};
