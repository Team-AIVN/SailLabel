import { IconExternal, IconFolderAdd, IconHumanSignal, IconUserAdd, IconFolderOpen } from "@humansignal/icons";
import { Button, SimpleCard, Spinner, Tooltip, Typography } from "@humansignal/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { Link, useHistory, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useUpdatePageTitle } from "@humansignal/core";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { HeidiTips } from "../../components/HeidiTips/HeidiTips";
import { usePermissions } from "../../utils/permissions";
import { useAPI } from "../../providers/ApiProvider";
import { CreateProject } from "../CreateProject/CreateProject";
import { InviteLink } from "../Organization/PeoplePage/InviteLink";
import type { Page } from "../types/Page";
import {
  creationDialogOpen,
  invitationOpen,
  locationKeyAtom,
  PROJECTS_TO_SHOW,
  projectsDataAtom,
  sortedProjectsAtom,
  visitedIdsAtom,
} from "./atoms";

const resourceLinks = [
  { key: "documentation", url: "https://labelstud.io/guide/" },
  { key: "apiDocumentation", url: "https://api.labelstud.io/api-reference/introduction/getting-started" },
  { key: "releaseNotes", url: "https://labelstud.io/learn/categories/release-notes/" },
  { key: "blog", url: "https://labelstud.io/blog/" },
  { key: "slackCommunity", url: "https://slack.labelstud.io" },
] as const;

const actions = [
  { type: "createWorkspace", labelKey: "home.actions.createWorkspace", icon: IconFolderOpen },
  { type: "createProject", labelKey: "home.actions.createProject", icon: IconFolderAdd },
  { type: "inviteMembers", labelKey: "home.actions.inviteMembers", icon: IconUserAdd },
] as const;

type Action = (typeof actions)[number]["type"];

export const HomePage: Page = () => {
  const { t } = useTranslation();
  const api = useAPI();
  const location = useLocation();
  const history = useHistory();
  const [modalIsOpen, setModalIsOpen] = useAtom(creationDialogOpen);
  const [invitationIsOpen, setInvitationIsOpen] = useAtom(invitationOpen);
  const setLocationKey = useSetAtom(locationKeyAtom);
  const setProjectsData = useSetAtom(projectsDataAtom);
  const sortedProjects = useAtomValue(sortedProjectsAtom);
  const visitedIds = useAtomValue(visitedIdsAtom);
  const { canCreateWorkspace, isSuperAdmin } = usePermissions();

  // Only managers create workspaces/projects; only super admins invite org members.
  // Plain members see neither, and get a "wait to be assigned" empty state.
  const visibleActions = actions.filter((a) =>
    a.type === "inviteMembers" ? isSuperAdmin : canCreateWorkspace,
  );

  useUpdatePageTitle(t("home.pageTitle"));

  const versionEdition = useMemo(() => {
    const edition = (window as unknown as { APP_SETTINGS?: { version_edition?: string } })?.APP_SETTINGS
      ?.version_edition;
    return edition || "Community";
  }, []);

  // Fetch regular projects
  const { data, isFetching, isSuccess, isError } = useQuery({
    queryKey: ["projects", { page_size: PROJECTS_TO_SHOW }],
    async queryFn() {
      return api.callApi<{ results: APIProject[]; count: number }>("projects", {
        params: { page_size: PROJECTS_TO_SHOW },
      });
    },
  });

  // Fetch visited projects specifically by their IDs
  const { data: visitedProjectsData } = useQuery({
    queryKey: ["visited-projects", { ids: visitedIds }],
    async queryFn() {
      if (visitedIds.length === 0) return { results: [], count: 0 };

      return api.callApi<{ results: APIProject[]; count: number }>("projects", {
        params: {
          ids: visitedIds.join(","),
          page_size: visitedIds.length,
        },
      });
    },
    enabled: visitedIds.length > 0,
  });

  useEffect(() => {
    setLocationKey(Date.now().toString());
  }, [location.pathname, setLocationKey]);

  useEffect(() => {
    const visitedProjects = visitedProjectsData?.results ?? [];
    const regularProjects = data?.results ?? [];
    const allProjects = [...visitedProjects, ...regularProjects];
    const uniqueProjects = Array.from(new Map(allProjects.map((p) => [p.id, p])).values());

    if (uniqueProjects.length > 0) {
      setProjectsData(uniqueProjects);
    }
  }, [data?.results, visitedProjectsData?.results, setProjectsData]);

  const handleActions = (action: Action) => {
    return () => {
      switch (action) {
        case "createWorkspace":
          // Workspace is the top-level container (datasets live here); send the
          // user to the Workspaces page to create one before projects.
          history.push("/workspaces");
          break;
        case "createProject":
          setModalIsOpen(true);
          break;
        case "inviteMembers":
          setInvitationIsOpen(true);
          break;
      }
    };
  };

  return (
    <main className="p-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_450px]">
        <section className="flex flex-col gap-6">
          <div className="flex flex-col gap-1">
            <Typography variant="headline" size="small">
              {t("home.welcome")}
            </Typography>
            <Typography size="small" className="text-neutral-content-subtler">
              {t("home.getStarted")}
            </Typography>
          </div>
          <div className="flex flex-wrap justify-start gap-4">
            {visibleActions.map((action) => {
              const label = t(action.labelKey);
              return (
                <Button
                  key={action.type}
                  look="outlined"
                  align="center"
                  className="flex-grow-0 text-16/24 gap-2 text-primary-content text-left min-w-[250px] [&_svg]:w-6 [&_svg]:h-6 pl-2"
                  onClick={handleActions(action.type)}
                  leading={<action.icon />}
                >
                  {label}
                </Button>
              );
            })}
          </div>

          <SimpleCard
            title={
              data && data?.count > 0 ? (
                <>
                  {t("home.recentProjects")}{" "}
                  <a href="/projects" className="text-lg font-normal hover:underline">
                    {t("home.viewAll")}
                  </a>
                </>
              ) : null
            }
          >
            {isFetching ? (
              <div className="h-64 flex justify-center items-center">
                <Spinner />
              </div>
            ) : isError ? (
              <div className="h-64 flex justify-center items-center">{t("home.loadError")}</div>
            ) : isSuccess && data && sortedProjects.length === 0 ? (
              <div className="flex flex-col justify-center items-center border border-primary-border-subtle bg-primary-emphasis-subtle rounded-lg h-64">
                <div
                  className={
                    "rounded-full w-12 h-12 flex justify-center items-center bg-accent-grape-subtle text-primary-icon"
                  }
                >
                  <IconFolderOpen />
                </div>
                <Typography variant="headline" size="small">
                  {t(canCreateWorkspace ? "home.empty.title" : "home.empty.memberTitle")}
                </Typography>
                <Typography size="small" className="text-neutral-content-subtler">
                  {t(canCreateWorkspace ? "home.empty.description" : "home.empty.memberDescription")}
                </Typography>
                {canCreateWorkspace && (
                  <Button
                    className="mt-4"
                    onClick={() => history.push("/workspaces")}
                    aria-label={t("home.empty.createWorkspaceAriaLabel")}
                  >
                    {t("home.empty.cta")}
                  </Button>
                )}
              </div>
            ) : isSuccess && data && sortedProjects.length > 0 ? (
              <div className="flex flex-col gap-1">
                {sortedProjects.map((project) => {
                  return <ProjectSimpleCard key={project.id} project={project} />;
                })}
              </div>
            ) : null}
          </SimpleCard>
        </section>
        <section className="flex flex-col gap-6">
          <HeidiTips collection="projectSettings" />
          <SimpleCard
            title={t("home.resources.title")}
            description={t("home.resources.description")}
            data-testid="resources-card"
          >
            <ul>
              {resourceLinks.map((link) => {
                return (
                  <li key={link.key}>
                    <a
                      href={link.url}
                      className="py-2 px-1 flex justify-between items-center text-neutral-content"
                      target="_blank"
                      rel="noreferrer"
                    >
                      {t(`home.resources.${link.key}`)}
                      <IconExternal className="text-primary-icon" />
                    </a>
                  </li>
                );
              })}
            </ul>
          </SimpleCard>
          <div className="flex gap-2 items-center">
            <IconHumanSignal />
            <span className="text-neutral-content-subtle">
              {t("home.versionLabel", { edition: versionEdition })}
            </span>
          </div>
        </section>
      </div>
      {modalIsOpen && <CreateProject onClose={() => setModalIsOpen(false)} />}
      <InviteLink opened={invitationIsOpen} onClosed={() => setInvitationIsOpen(false)} />
    </main>
  );
};

HomePage.title = "Home";
HomePage.path = "/";
HomePage.exact = true;

function ProjectSimpleCard({ project }: { project: APIProject }) {
  const { t } = useTranslation();
  const finished = project.finished_task_number ?? 0;
  const total = project.task_number ?? 0;
  const progress = (total > 0 ? finished / total : 0) * 100;
  const percent = total > 0 ? Math.round((finished / total) * 100) : 0;
  const white = "#FFFFFF";
  const color = project.color && project.color !== white ? project.color : "#E1DED5";

  return (
    <Link
      to={`/projects/${project.id}`}
      className="block even:bg-neutral-surface rounded-sm overflow-hidden"
      data-external
    >
      <div
        className="grid grid-cols-[minmax(0,1fr)_150px] p-2 py-3 items-center border-l-[3px]"
        style={{ borderLeftColor: color }}
      >
        <div className="flex flex-col gap-1">
          <Tooltip title={project.title}>
            <span className="text-neutral-content truncate">{project.title}</span>
          </Tooltip>
          <div className="text-neutral-content-subtler text-sm">
            {t("home.tasksProgress", { finished, total, percent })}
          </div>
        </div>
        <div className="bg-neutral-surface rounded-full overflow-hidden w-full h-2 shadow-neutral-border-subtle shadow-border-1">
          <div className="bg-positive-surface-hover h-full" style={{ maxWidth: `${progress}%` }} />
        </div>
      </div>
    </Link>
  );
}
