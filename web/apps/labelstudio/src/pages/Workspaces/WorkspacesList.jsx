import { format } from "date-fns";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";
import { IconEllipsis } from "@humansignal/icons";
import { Button, Dropdown, Tooltip } from "@humansignal/ui";
import { Menu, Pagination } from "../../components";
import { cn } from "../../utils/bem";
import { absoluteURL } from "../../utils/helpers";
// Reuse the project list design system (projects-page / project-card / empty-projects-page).
import "../Projects/Projects.prefix.css";

export const WorkspacesList = ({ workspaces, currentPage, totalItems, loadNextPage, pageSize }) => {
  const { t } = useTranslation();
  return (
    <>
      <div className={cn("projects-page").elem("list").toClassName()}>
        {workspaces.map((workspace) => (
          <WorkspaceCard key={workspace.id} workspace={workspace} />
        ))}
      </div>
      <div className={cn("projects-page").elem("pages").toClassName()}>
        <Pagination
          name="workspaces-list"
          label={t("workspaces.pageTitle")}
          page={currentPage}
          totalItems={totalItems}
          urlParamName="page"
          pageSize={pageSize}
          pageSizeOptions={[10, 30, 50, 100]}
          onPageLoad={(page, pageSize) => loadNextPage(page, pageSize)}
        />
      </div>
    </>
  );
};

export const EmptyWorkspacesList = ({ openModal }) => {
  const { t } = useTranslation();
  return (
    <div className={cn("empty-projects-page").toClassName()}>
      <img
        alt={t("workspaces.empty.title")}
        className={cn("empty-projects-page").elem("heidi").toClassName()}
        src={absoluteURL("/static/images/opossum_looking.png")}
      />
      <h1 className={cn("empty-projects-page").elem("header").toClassName()}>{t("workspaces.empty.title")}</h1>
      <p>{t("workspaces.empty.description")}</p>
      <Button onClick={openModal} className="my-8" aria-label={t("workspaces.createWorkspaceAriaLabel")}>
        {t("workspaces.createButton")}
      </Button>
    </div>
  );
};

const WorkspaceCard = ({ workspace }) => {
  const { t } = useTranslation();

  return (
    <NavLink
      className={cn("projects-page").elem("link").toClassName()}
      to={`/workspaces/${workspace.id}`}
      data-external
    >
      <div className={cn("project-card").toClassName()}>
        <div className={cn("project-card").elem("header").toClassName()}>
          <div className={cn("project-card").elem("title").toClassName()}>
            <div className={cn("project-card").elem("title-text-wrapper").toClassName()}>
              <Tooltip title={workspace.title}>
                <div className={cn("project-card").elem("title-text").toClassName()}>{workspace.title}</div>
              </Tooltip>
            </div>

            <div
              className={cn("project-card").elem("menu").toClassName()}
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
              }}
            >
              <Dropdown.Trigger
                content={
                  <Menu contextual>
                    <Menu.Item href={`/workspaces/${workspace.id}`}>{t("workspaces.card.open", "Open")}</Menu.Item>
                  </Menu>
                }
              >
                <Button size="smaller" look="string" aria-label={t("workspaces.createWorkspaceAriaLabel")}>
                  <IconEllipsis />
                </Button>
              </Dropdown.Trigger>
            </div>
          </div>

          <div className={cn("project-card").elem("summary").toClassName()}>
            <div className={cn("project-card").elem("annotation").toClassName()}>
              <div className={cn("project-card").elem("total").toClassName()}>
                {t("workspaces.card.projectCount", { count: workspace.project_count ?? 0 })}
              </div>
            </div>
          </div>
        </div>

        <div className={cn("project-card").elem("description").toClassName()}>{workspace.description}</div>

        <div className={cn("project-card").elem("info").toClassName()}>
          <div className={cn("project-card").elem("created-date").toClassName()}>
            {workspace.created_at ? format(new Date(workspace.created_at), "dd MMM yyyy, HH:mm") : ""}
          </div>
        </div>
      </div>
    </NavLink>
  );
};
