import { formatDistance } from "date-fns";
import { useTranslation } from "react-i18next";
import { cn } from "../../utils/bem";

export const WorkspacesList = ({ workspaces }) => {
  const { t } = useTranslation();
  const root = cn("workspaces-page");

  return (
    <div className={root.elem("list").toClassName()}>
      {workspaces.map((ws) => {
        const createdAt = ws.created_at ? new Date(ws.created_at) : null;
        return (
          <div key={ws.id} className={root.elem("card").toClassName()}>
            <h3 className={root.elem("card-title").toClassName()}>{ws.title}</h3>
            <p className={root.elem("card-description").toClassName()}>{ws.description || " "}</p>
            <div className={root.elem("card-meta").toClassName()}>
              <span>{t("workspaces.card.projectCount", { count: ws.project_count ?? 0 })}</span>
              {createdAt && <span>{formatDistance(createdAt, new Date(), { addSuffix: true })}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
};
