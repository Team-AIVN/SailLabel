import { PersonalInfo } from "./PersonalInfo";
import { EmailPreferences } from "./EmailPreferences";
import { PersonalAccessToken, PersonalAccessTokenDescription } from "./PersonalAccessToken";
import { MembershipInfo } from "./MembershipInfo";
import { HotkeysManager } from "./Hotkeys";
import type React from "react";
import { PersonalJWTToken } from "./PersonalJWTToken";
import type { AuthTokenSettings } from "../types";
import { ABILITY, type AuthPermissions } from "@humansignal/core/providers/AuthProvider";
import { ff } from "@humansignal/core";
import { Badge } from "@humansignal/ui";
import type { TFunction } from "i18next";

export type SectionType = {
  title: string | React.ReactNode;
  id: string;
  component: React.FC;
  description?: React.FC | React.ReactNode;
};

export const accountSettingsSections = (
  settings: AuthTokenSettings,
  permissions: AuthPermissions,
  t: TFunction,
): SectionType[] => {
  const canCreateTokens = permissions.can(ABILITY.can_create_tokens);

  return [
    {
      title: t("accountSettings.sections.personalInfo"),
      id: "personal-info",
      component: PersonalInfo,
    },
    {
      title: (
        <div className="flex items-center gap-tight">
          <span>{t("accountSettings.sections.hotkeys")}</span>
          <Badge variant="beta" style="solid" shape="rounded">
            Beta
          </Badge>
        </div>
      ),
      id: "hotkeys",
      component: HotkeysManager,
      description: () => <>{t("accountSettings.sections.hotkeysDescription")}</>,
    },
    {
      title: t("accountSettings.sections.emailPreferences"),
      id: "email-preferences",
      component: EmailPreferences,
    },
    {
      title: t("accountSettings.sections.membershipInfo"),
      id: "membership-info",
      component: MembershipInfo,
    },
    settings.api_tokens_enabled &&
      canCreateTokens &&
      ff.isActive(ff.FF_AUTH_TOKENS) && {
        title: t("accountSettings.sections.personalAccessToken"),
        id: "personal-access-token",
        component: PersonalJWTToken,
        description: PersonalAccessTokenDescription,
      },
    settings.legacy_api_tokens_enabled &&
      canCreateTokens && {
        title: ff.isActive(ff.FF_AUTH_TOKENS)
          ? t("accountSettings.sections.legacyToken")
          : t("accountSettings.sections.accessToken"),
        id: "legacy-token",
        component: PersonalAccessToken,
        description: PersonalAccessTokenDescription,
      },
  ].filter(Boolean) as SectionType[];
};
