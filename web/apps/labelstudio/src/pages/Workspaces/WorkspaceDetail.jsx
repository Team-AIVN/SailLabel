import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useHistory, useLocation, useParams } from "react-router";
import { Button, useToast } from "@humansignal/ui";
import { Spinner } from "../../components/Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./WorkspaceDetail.prefix.css";

const TABS = ["projects", "datasets", "users"];
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
  const fileInputRef = useRef();

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
  const [newProjectTitle, setNewProjectTitle] = useState("");
  const [newProjectTags, setNewProjectTags] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [inviteUser, setInviteUser] = useState("");
  const [inviteRole, setInviteRole] = useState("member");

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
  const createProject = useCallback(async () => {
    const title = newProjectTitle.trim();
    if (title.length < 1) return;
    const tags = newProjectTags
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const res = await api.callApi("createWorkspaceProject", {
      params: { pk: id },
      body: { title, tags },
    });
    if (res?.id) {
      toast.show({ message: t("workspaces.dashboard.projectCreated", "Project created") });
      setNewProjectTitle("");
      setNewProjectTags("");
      setShowNewProject(false);
      loadProjects();
      loadSummary();
    } else {
      toast.show({ message: res?.detail ?? t("workspaces.dashboard.actionFailed", "Action failed"), type: "error" });
    }
  }, [api, id, newProjectTitle, newProjectTags, toast, t, loadProjects, loadSummary]);

  const uploadDataset = useCallback(
    async (event) => {
      const selected = Array.from(event.target.files ?? []);
      if (!selected.length) return;
      const fd = new FormData();
      for (const file of selected) fd.append(file.name, file);
      const res = await api.callApi("workspaceImportFiles", { params: { pk: id }, body: fd });
      event.target.value = "";
      if (res && !res.error) {
        toast.show({ message: t("workspaces.dataset.uploaded", { count: selected.length }) });
        loadDatasets();
        loadSummary();
      } else {
        toast.show({ message: res?.detail ?? t("workspaces.dataset.uploadFailed"), type: "error" });
      }
    },
    [api, id, toast, t, loadDatasets, loadSummary],
  );

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
        fileInputRef.current?.click();
      } else if (action === "user") {
        setTab("users");
        setShowInvite(true);
        loadOrgMembers();
      }
    },
    [setTab, loadOrgMembers],
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
        <input type="file" multiple ref={fileInputRef} onChange={uploadDataset} style={{ display: "none" }} />
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
            {t(`workspaces.detail.${tab === "users" ? "members" : tab === "datasets" ? "dataset" : "projects"}`)}
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
            <Button size="small" onClick={() => setShowNewProject((v) => !v)}>
              {t("workspaces.dashboard.newProject", "New Project")}
            </Button>
          </div>

          {showNewProject && (
            <div className={root.elem("inline-form").toClassName()}>
              <input
                placeholder={t("workspaces.fields.title")}
                value={newProjectTitle}
                onChange={(e) => setNewProjectTitle(e.target.value)}
              />
              <input
                placeholder={t("workspaces.dashboard.tagsPlaceholder", "tags, comma separated")}
                value={newProjectTags}
                onChange={(e) => setNewProjectTags(e.target.value)}
              />
              <Button size="small" onClick={createProject} disabled={!newProjectTitle.trim()}>
                {t("common.create", "Create")}
              </Button>
            </div>
          )}

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
            <Button size="small" onClick={() => fileInputRef.current?.click()}>
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
    </div>
  );
};
