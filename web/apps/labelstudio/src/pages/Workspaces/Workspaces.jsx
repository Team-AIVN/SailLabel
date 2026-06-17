import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@humansignal/ui";
import { useUpdatePageTitle } from "@humansignal/core";
import { IconPlus } from "@humansignal/icons";
import { Spinner } from "../../components/Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";
import { useContextProps } from "../../providers/RoutesProvider";
import { cn } from "../../utils/bem";
import { CreateWorkspace } from "./CreateWorkspace";
import { WorkspacesList } from "./WorkspacesList";
import "./Workspaces.prefix.css";

const parseList = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

export const WorkspacesPage = () => {
  const { t } = useTranslation();
  const api = useAPI();
  const setContextProps = useContextProps();

  const [workspaces, setWorkspaces] = useState([]);
  const [networkState, setNetworkState] = useState("loading");
  const [createOpen, setCreateOpen] = useState(false);

  useUpdatePageTitle(t("workspaces.pageTitle"));

  const fetchWorkspaces = useCallback(async () => {
    setNetworkState("loading");
    const response = await api.callApi("workspaces");
    setWorkspaces(parseList(response));
    setNetworkState("loaded");
  }, [api]);

  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  const openCreate = useCallback(() => setCreateOpen(true), []);
  const closeCreate = useCallback(() => setCreateOpen(false), []);

  useEffect(() => {
    setContextProps({ openCreate, showButton: workspaces.length > 0 });
  }, [workspaces.length, openCreate, setContextProps]);

  const root = useMemo(() => cn("workspaces-page"), []);
  const isEmpty = networkState === "loaded" && workspaces.length === 0;

  return (
    <div className={root.toClassName()}>
      {networkState === "loading" ? (
        <div className={root.elem("loading").toClassName()}>
          <Spinner size={48} />
        </div>
      ) : isEmpty ? (
        <div className={root.elem("empty").toClassName()}>
          <div>
            <div className={root.elem("empty-title").toClassName()}>{t("workspaces.empty.title")}</div>
            <div className={root.elem("empty-description").toClassName()}>{t("workspaces.empty.description")}</div>
            <Button
              leading={<IconPlus className="!h-4" />}
              onClick={openCreate}
              aria-label={t("workspaces.createWorkspaceAriaLabel")}
            >
              {t("workspaces.createButton")}
            </Button>
          </div>
        </div>
      ) : (
        <WorkspacesList workspaces={workspaces} />
      )}

      <CreateWorkspace
        opened={createOpen}
        onClose={closeCreate}
        onCreated={() => {
          closeCreate();
          fetchWorkspaces();
        }}
      />
    </div>
  );
};

WorkspacesPage.title = "Workspaces";
WorkspacesPage.path = "/workspaces";
WorkspacesPage.exact = true;

const CreateWorkspaceContextButton = ({ openCreate }) => {
  const { t } = useTranslation();
  return (
    <Button
      onClick={openCreate}
      size="small"
      leading={<IconPlus className="!h-4" />}
      aria-label={t("workspaces.createWorkspaceAriaLabel")}
    >
      {t("workspaces.createButton")}
    </Button>
  );
};

WorkspacesPage.context = ({ openCreate, showButton }) => {
  if (!showButton || !openCreate) return null;
  return <CreateWorkspaceContextButton openCreate={openCreate} />;
};
