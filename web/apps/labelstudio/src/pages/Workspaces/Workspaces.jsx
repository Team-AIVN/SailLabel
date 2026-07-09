import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@humansignal/ui";
import { IconPlus } from "@humansignal/icons";
import { Oneof } from "../../components/Oneof/Oneof";
import { Spinner } from "../../components/Spinner/Spinner";
import { ApiContext } from "../../providers/ApiProvider";
import { useContextProps } from "../../providers/RoutesProvider";
import { cn } from "../../utils/bem";
import { useUpdatePageTitle } from "@humansignal/core";
import { WorkspaceAccessGuard } from "../../components/RoleGuard/RoleGuard";
import { CreateWorkspace } from "./CreateWorkspace";
import { WorkspaceDetail } from "./WorkspaceDetail";
import { EmptyWorkspacesList, WorkspacesList } from "./WorkspacesList";
// Reuse the project list design system (projects-page / project-card / empty-projects-page).
import "../Projects/Projects.prefix.css";
import "./Workspaces.prefix.css";

const getCurrentPage = () => {
  const pageNumberFromURL = new URLSearchParams(location.search).get("page");
  return pageNumberFromURL ? Number.parseInt(pageNumberFromURL) : 1;
};

const WorkspacesPageInner = () => {
  const { t } = useTranslation();
  const api = React.useContext(ApiContext);
  const [workspacesList, setWorkspacesList] = React.useState([]);
  const [networkState, setNetworkState] = React.useState(null);
  const [currentPage, setCurrentPage] = useState(getCurrentPage());
  const [totalItems, setTotalItems] = useState(1);
  const setContextProps = useContextProps();
  const [modal, setModal] = React.useState(false);

  useUpdatePageTitle(t("workspaces.pageTitle"));
  const defaultPageSize = Number.parseInt(localStorage.getItem("pages:workspaces-list") ?? 30);

  const openModal = () => setModal(true);
  const closeModal = () => setModal(false);

  const fetchWorkspaces = async (page = currentPage, pageSize = defaultPageSize) => {
    setNetworkState("loading");
    const data = await api.callApi("workspaces", { params: { page, page_size: pageSize } });
    const results = Array.isArray(data) ? data : (data?.results ?? []);
    setTotalItems(data?.count ?? results.length ?? 1);
    setWorkspacesList(results);
    setNetworkState("loaded");
  };

  const loadNextPage = async (page, pageSize) => {
    setCurrentPage(page);
    await fetchWorkspaces(page, pageSize);
  };

  React.useEffect(() => {
    fetchWorkspaces();
  }, []);

  React.useEffect(() => {
    // empty state has its own Create button, so hide the header context button then
    setContextProps({ openModal, showButton: workspacesList.length > 0 });
  }, [workspacesList.length]);

  return (
    <div className={cn("projects-page").toClassName()}>
      <Oneof value={networkState}>
        <div className={cn("projects-page").elem("loading").toClassName()} case="loading">
          <Spinner size={64} />
        </div>
        <div className={cn("projects-page").elem("content").toClassName()} case="loaded">
          {workspacesList.length ? (
            <WorkspacesList
              workspaces={workspacesList}
              currentPage={currentPage}
              totalItems={totalItems}
              loadNextPage={loadNextPage}
              pageSize={defaultPageSize}
            />
          ) : (
            <EmptyWorkspacesList openModal={openModal} />
          )}
          {modal && (
            <CreateWorkspace
              opened
              onClose={closeModal}
              onCreated={() => {
                closeModal();
                fetchWorkspaces();
              }}
            />
          )}
        </div>
      </Oneof>
    </div>
  );
};

// Workspaces are for SA / workspace managers / project managers / workspace members.
// Labelers and reviewers (no workspace access) are redirected to their projects.
export const WorkspacesPage = () => (
  <WorkspaceAccessGuard>
    <WorkspacesPageInner />
  </WorkspaceAccessGuard>
);

WorkspacesPage.title = "Workspaces";
WorkspacesPage.path = "/workspaces";
WorkspacesPage.exact = true;
// Guard the detail route too — otherwise a user without workspace access could open
// /workspaces/<id> directly (a "direct-URL hole") even though the menu is hidden.
const GuardedWorkspaceDetail = (props) => (
  <WorkspaceAccessGuard>
    <WorkspaceDetail {...props} />
  </WorkspaceAccessGuard>
);

WorkspacesPage.routes = () => [
  {
    title: "Workspace",
    path: "/:id(\\d+)",
    exact: true,
    component: GuardedWorkspaceDetail,
  },
];

const CreateWorkspaceContextButton = ({ openModal }) => {
  const { t } = useTranslation();
  return (
    <Button
      onClick={openModal}
      size="small"
      leading={<IconPlus className="!h-4" />}
      aria-label={t("workspaces.createWorkspaceAriaLabel")}
    >
      {t("workspaces.createButton")}
    </Button>
  );
};

WorkspacesPage.context = ({ openModal, showButton }) => {
  if (!showButton || !openModal) return null;
  return <CreateWorkspaceContextButton openModal={openModal} />;
};
