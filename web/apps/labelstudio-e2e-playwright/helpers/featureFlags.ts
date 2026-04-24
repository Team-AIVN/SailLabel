/**
 * Feature flags the frontend checks in `isFF(...)` at page-build time.
 *
 * The values are string keys from
 * `web/libs/core/src/lib/utils/feature-flags/flags.ts`; setting them to
 * `"true"` in localStorage toggles the feature ON for the session.
 *
 * Flags kept here:
 *   fflag_workspace                              — /workspaces page + menu
 *   fflag_batch_review                           — /reviews page + menu
 *   fflag_all_feat_dia_1777_ls_homepage_short    — Home dashboard (/)
 *   fflag_review_workflow                        — reviewer UI surface
 *   fflag_settlement                             — Settlement settings tab
 */
export const E2E_FEATURE_FLAGS = [
  'fflag_workspace',
  'fflag_batch_review',
  'fflag_all_feat_dia_1777_ls_homepage_short',
  'fflag_review_workflow',
  'fflag_settlement',
] as const;

/** Init script body — runs in the page before any app JS executes. */
export function buildFlagInitScript(flags: readonly string[] = E2E_FEATURE_FLAGS): string {
  return `(() => {
    const flags = ${JSON.stringify(flags)};
    try {
      flags.forEach((k) => window.localStorage.setItem(k, 'true'));
    } catch (e) {
      // localStorage may be unavailable on about:blank — ignore.
    }
  })();`;
}
