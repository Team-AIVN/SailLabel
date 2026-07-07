import { SidebarMenu } from "../../components/SidebarMenu/SidebarMenu";
import { ProjectRoleGuard } from "../../components/RoleGuard/RoleGuard";
import { useProject } from "../../providers/ProjectProvider";
import { projectPermissions } from "../../utils/permissions";
import { FF_WORKSPACE, isFF } from "../../utils/feature-flags";
import { WebhookPage } from "../WebhookPage/WebhookPage";
import { DangerZone } from "./DangerZone";
import { GeneralSettings } from "./GeneralSettings";
import { WorkersSettings } from "./WorkersSettings";
import { AnnotationSettings } from "./AnnotationSettings";
import { LabelingSettings } from "./LabelingSettings";
import { MachineLearningSettings } from "./MachineLearningSettings/MachineLearningSettings";
import { PredictionsSettings } from "./PredictionsSettings/PredictionsSettings";
import "./settings.prefix.css";

export const MenuLayout = ({ children, ...routeProps }) => {
  const { project } = useProject();
  // Deleting a project is workspace-manager/super-admin only — project managers manage
  // settings but can't delete, so hide Danger Zone from them.
  const canDelete = projectPermissions(project?.current_user_role).canDelete;
  return (
    <SidebarMenu
      menuItems={[
        GeneralSettings,
        isFF(FF_WORKSPACE) && WorkersSettings,
        LabelingSettings,
        AnnotationSettings,
        MachineLearningSettings,
        PredictionsSettings,
        WebhookPage,
        canDelete && DangerZone,
      ].filter(Boolean)}
      path={routeProps.match.url}
      children={<ProjectRoleGuard check={(perms) => perms.canManage}>{children}</ProjectRoleGuard>}
    />
  );
};

const pages = {
  WorkersSettings,
  AnnotationSettings,
  LabelingSettings,
  MachineLearningSettings,
  PredictionsSettings,
  WebhookPage,
  DangerZone,
};

export const SettingsPage = {
  title: "Settings",
  path: "/settings",
  exact: true,
  layout: MenuLayout,
  component: GeneralSettings,
  pages,
};
