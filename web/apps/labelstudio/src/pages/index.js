import { ProjectsPage } from "./Projects/Projects";
import { HomePage } from "./Home/HomePage";
import { OrganizationPage } from "./Organization";
import { ModelsPage } from "./Organization/Models/ModelsPage";
import { WorkspacesPage } from "./Workspaces/Workspaces";
import { MyReviewsPage } from "./MyReviews/MyReviews";
import { FF_BATCH_REVIEW, FF_HOMEPAGE, FF_WORKSPACE, isFF } from "../utils/feature-flags";
import { pages } from "@humansignal/app-common";

export const Pages = [
  isFF(FF_HOMEPAGE) && HomePage,
  ProjectsPage,
  isFF(FF_WORKSPACE) && WorkspacesPage,
  isFF(FF_BATCH_REVIEW) && MyReviewsPage,
  OrganizationPage,
  ModelsPage,
  pages.AccountSettingsPage,
].filter(Boolean);
