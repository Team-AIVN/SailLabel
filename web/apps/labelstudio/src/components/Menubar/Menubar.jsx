import { createContext, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { StaticContent } from "../../app/StaticContent/StaticContent";
import { LocaleSwitcher } from "../LocaleSwitcher/LocaleSwitcher";
import {
  IconBook,
  IconChevronDown,
  IconChevronRight,
  IconFolder,
  IconHome,
  IconHotkeys,
  IconLayers2,
  IconPeople,
  IconPersonInCircle,
  IconPin,
  IconTerminal,
  IconDoor,
  IconGithub,
  IconSlack,
} from "@humansignal/icons";
import { LSLogo } from "../../assets/images";
import { Button, Userpic, ThemeToggle } from "@humansignal/ui";
import { useConfig } from "../../providers/ConfigProvider";
import { useContextComponent, useFixedLocation } from "../../providers/RoutesProvider";
import { useAPI } from "../../providers/ApiProvider";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { cn } from "../../utils/bem";
import { absoluteURL, isDefined } from "../../utils/helpers";
import { Breadcrumbs } from "../Breadcrumbs/Breadcrumbs";
import { Dropdown } from "@humansignal/ui";
import { Hamburger } from "../Hamburger/Hamburger";
import { Menu } from "../Menu/Menu";
import { VersionNotifier, VersionProvider } from "../VersionNotifier/VersionNotifier";
import "./Menubar.prefix.css";
import "./MenuContent.prefix.css";
import "./MenuSidebar.prefix.css";
import { FF_HOMEPAGE, FF_WORKSPACE } from "../../utils/feature-flags";
import { pages } from "@humansignal/app-common";
import { isFF } from "../../utils/feature-flags";
import { ff } from "@humansignal/core";
import { openHotkeyHelp } from "@humansignal/app-common/pages/AccountSettings/sections/Hotkeys/Help";

export const MenubarContext = createContext();

const CollapsibleMenuSection = ({ icon, label, to, expanded, onToggle, children }) => {
  const rootClass = cn("main-menu").elem("item");
  const collapsibleClass = cn("menu-collapsible");
  const chevronClass = cn("menu-collapsible-chevron");
  const linkClass = cn("menu-collapsible-link");
  const classList = [rootClass.toClassName(), linkClass.toClassName()];
  const chevron = expanded ? <IconChevronDown /> : <IconChevronRight />;

  const handleToggle = (e) => {
    e.preventDefault();
    e.stopPropagation();
    onToggle();
  };

  return (
    <>
      <li className={collapsibleClass.toClassName()}>
        <button
          type="button"
          className={chevronClass.toClassName()}
          aria-expanded={expanded}
          aria-label={expanded ? `Collapse ${label}` : `Expand ${label}`}
          onClick={handleToggle}
        >
          {chevron}
        </button>
        <NavLink
          to={to}
          exact
          data-external
          className={classList.join(" ")}
          activeClassName={rootClass.mod({ active: true }).toClassName()}
        >
          {icon && <span className={rootClass.elem("item-icon").toClassName()}>{icon}</span>}
          {label}
        </NavLink>
      </li>
      {expanded && children}
    </>
  );
};

const LeftContextMenu = ({ className }) => (
  <StaticContent id="context-menu-left" className={className}>
    {(template) => <Breadcrumbs fromTemplate={template} />}
  </StaticContent>
);

const RightContextMenu = ({ className, ...props }) => {
  const { ContextComponent, contextProps } = useContextComponent();

  return ContextComponent ? (
    <div className={className}>
      <ContextComponent {...props} {...(contextProps ?? {})} />
    </div>
  ) : (
    <StaticContent id="context-menu-right" className={className} />
  );
};

export const Menubar = ({ enabled, defaultOpened, defaultPinned, children, onSidebarToggle, onSidebarPin }) => {
  const { t } = useTranslation();
  const menuDropdownRef = useRef();
  const useMenuRef = useRef();
  const { user, isLoading } = useAuth();
  const api = useAPI();
  const location = useFixedLocation();

  const config = useConfig();
  const [sidebarOpened, setSidebarOpened] = useState(defaultOpened ?? false);
  const [sidebarPinned, setSidebarPinned] = useState(defaultPinned ?? false);
  const [projectsList, setProjectsList] = useState([]);
  const [workspacesById, setWorkspacesById] = useState({});
  const [PageContext, setPageContext] = useState({
    Component: null,
    props: {},
  });
  const [workspacesExpanded, setWorkspacesExpanded] = useState(() => {
    try { return localStorage.getItem("menu:workspaces-expanded") === "1"; } catch { return false; }
  });
  const [projectsExpanded, setProjectsExpanded] = useState(() => {
    try { return localStorage.getItem("menu:projects-expanded") === "1"; } catch { return false; }
  });
  const toggleWorkspaces = useCallback(() => {
    setWorkspacesExpanded((v) => {
      try { localStorage.setItem("menu:workspaces-expanded", v ? "0" : "1"); } catch {}
      return !v;
    });
  }, []);
  const toggleProjects = useCallback(() => {
    setProjectsExpanded((v) => {
      try { localStorage.setItem("menu:projects-expanded", v ? "0" : "1"); } catch {}
      return !v;
    });
  }, []);

  // super_admin OR workspace_manager of any workspace → show the Workspaces
  // top-level menu entry. Everyone else (project_manager / reviewer /
  // annotator / plain org member) only sees Projects.
  const canSeeWorkspaces = useMemo(
    () => !!user?.is_super_admin || (user?.managed_workspace_ids?.length ?? 0) > 0,
    [user?.is_super_admin, user?.managed_workspace_ids],
  );

  useEffect(() => {
    if (!enabled || !user?.id) return;
    let cancelled = false;
    // Fetch both in parallel; workspaces is optional — we fall back to
    // ungrouped if the feature flag is off server-side.
    Promise.all([
      api.callApi("projects", {
        params: {
          page: 1,
          page_size: 100,
          include: ["id", "title", "workspace", "color"].join(","),
        },
      }),
      isFF(FF_WORKSPACE)
        ? api.callApi("workspaces", { params: { page: 1, page_size: 200 } })
        : Promise.resolve(null),
    ]).then(([projects, workspaces]) => {
      if (cancelled) return;
      setProjectsList(projects?.results ?? []);
      const map = {};
      const wsResults = workspaces?.results ?? workspaces ?? [];
      for (const ws of Array.isArray(wsResults) ? wsResults : []) {
        map[ws.id] = ws;
      }
      setWorkspacesById(map);
    });
    return () => {
      cancelled = true;
    };
  }, [api, enabled, user?.id, user?.active_organization]);

  // Group projects by their workspace FK. If projects span >1 workspace, the
  // sidebar renders a Menu.Group per workspace so users can navigate between
  // scopes. Single-workspace (or legacy unassigned) projects stay flat.
  const projectGroups = useMemo(() => {
    if (!projectsList.length) return [];
    const groups = new Map();
    for (const p of projectsList) {
      const wsId = p.workspace ?? null;
      if (!groups.has(wsId)) groups.set(wsId, []);
      groups.get(wsId).push(p);
    }
    return Array.from(groups.entries()).map(([wsId, items]) => ({
      workspaceId: wsId,
      title:
        wsId != null
          ? workspacesById[wsId]?.title ?? t("menubar.unknownWorkspace", "Workspace")
          : t("menubar.unassignedWorkspace", "Unassigned"),
      items,
    }));
  }, [projectsList, workspacesById, t]);

  const shouldGroupProjects = projectGroups.length > 1;

  const menubarClass = cn("menu-header");
  const menubarContext = menubarClass.elem("context");
  const sidebarClass = cn("sidebar");
  const contentClass = cn("content-wrapper");
  const contextItem = menubarClass.elem("context-item");
  const showNewsletterDot = !isDefined(user?.allow_newsletters);

  const sidebarPin = useCallback(
    (e) => {
      e.preventDefault();

      const newState = !sidebarPinned;

      setSidebarPinned(newState);
      onSidebarPin?.(newState);
    },
    [sidebarPinned],
  );

  const sidebarToggle = useCallback(
    (visible) => {
      const newState = visible;

      setSidebarOpened(newState);
      onSidebarToggle?.(newState);
    },
    [sidebarOpened],
  );

  const providerValue = useMemo(
    () => ({
      PageContext,

      setContext(ctx) {
        setTimeout(() => {
          setPageContext({
            ...PageContext,
            Component: ctx,
          });
        });
      },

      setProps(props) {
        setTimeout(() => {
          setPageContext({
            ...PageContext,
            props,
          });
        });
      },

      contextIsSet(ctx) {
        return PageContext.Component === ctx;
      },
    }),
    [PageContext],
  );

  useEffect(() => {
    if (!sidebarPinned) {
      menuDropdownRef?.current?.close();
    }
    useMenuRef?.current?.close();
  }, [location]);

  return (
    <div className={contentClass}>
      {enabled && (
        <div className={menubarClass}>
          <Dropdown.Trigger dropdown={menuDropdownRef} closeOnClickOutside={!sidebarPinned}>
            <div className={`${menubarClass.elem("trigger")} main-menu-trigger`}>
              <LSLogo className={`${menubarClass.elem("logo")}`} alt={t("app.logoAlt")} />
              <Hamburger opened={sidebarOpened} />
            </div>
          </Dropdown.Trigger>

          <div className={menubarContext}>
            <LeftContextMenu className={contextItem.mod({ left: true }).toClassName()} />
            <RightContextMenu className={contextItem.mod({ right: true }).toClassName()} />
          </div>

          <div className={menubarClass.elem("hotkeys").toClassName()}>
            <div className={menubarClass.elem("hotkeys-button").toClassName()}>
              <Button
                variant="neutral"
                look="outlined"
                tooltip={t("menubar.keyboardShortcuts")}
                data-testid="hotkeys-button"
                size="small"
                onClick={() => {
                  openHotkeyHelp([
                    "annotation",
                    "data_manager",
                    "regions",
                    "tools",
                    "audio",
                    "video",
                    "timeseries",
                    "image_gallery",
                  ]);
                }}
                icon={<IconHotkeys />}
              />
            </div>
          </div>

          {ff.isActive(ff.FF_THEME_TOGGLE) && <ThemeToggle />}

          <LocaleSwitcher />

          <Dropdown.Trigger
            ref={useMenuRef}
            align="right"
            content={
              <Menu>
                <Menu.Item
                  icon={<IconPersonInCircle />}
                  label={t("menubar.accountSettings")}
                  href={pages.AccountSettingsPage.path}
                />
                {/* <Menu.Item label="Dark Mode"/> */}
                <Menu.Item
                  icon={<IconDoor />}
                  label={t("menubar.logOut")}
                  href={absoluteURL("/logout")}
                  data-external
                />
                {showNewsletterDot && (
                  <>
                    <Menu.Divider />
                    <Menu.Item
                      className={cn("newsletter-menu-item").toClassName()}
                      href={pages.AccountSettingsPage.path}
                    >
                      <span>{t("menubar.newsletterNotice")}</span>
                      <span className={cn("newsletter-menu-badge").toClassName()} />
                    </Menu.Item>
                  </>
                )}
              </Menu>
            }
          >
            <div title={user?.email} className={menubarClass.elem("user").toClassName()}>
              <Userpic user={user} isInProgress={isLoading} />
              {showNewsletterDot && <div className={menubarClass.elem("userpic-badge").toClassName()} />}
            </div>
          </Dropdown.Trigger>
        </div>
      )}

      <VersionProvider>
        <div className={contentClass.elem("body").toClassName()}>
          {enabled && (
            <Dropdown
              ref={menuDropdownRef}
              onToggle={sidebarToggle}
              onVisibilityChanged={() => window.dispatchEvent(new Event("resize"))}
              visible={sidebarOpened}
              className={[sidebarClass, sidebarClass.mod({ floating: !sidebarPinned })].join(" ")}
              style={{ width: 240 }}
            >
              <Menu>
                {isFF(FF_HOMEPAGE) && (
                  <Menu.Item label={t("menubar.home")} to="/" icon={<IconHome />} data-external exact />
                )}
                {isFF(FF_WORKSPACE) && canSeeWorkspaces && (
                  <CollapsibleMenuSection
                    icon={<IconLayers2 />}
                    label={t("menubar.workspaces")}
                    to="/workspaces"
                    expanded={workspacesExpanded}
                    onToggle={toggleWorkspaces}
                  >
                    {Object.values(workspacesById).length > 0 && (
                      <Menu.Group>
                        {Object.values(workspacesById).map((ws) => (
                          <Menu.Item
                            key={`workspace-${ws.id}`}
                            to={`/workspaces/${ws.id}`}
                            data-external
                            exact
                          >
                            {ws.title}
                          </Menu.Item>
                        ))}
                      </Menu.Group>
                    )}
                  </CollapsibleMenuSection>
                )}
                <CollapsibleMenuSection
                  icon={<IconFolder />}
                  label={t("menubar.projects")}
                  to="/projects"
                  expanded={projectsExpanded}
                  onToggle={toggleProjects}
                >
                  {shouldGroupProjects
                    ? projectGroups.map((group) => (
                        <Menu.Group key={`ws-${group.workspaceId ?? "none"}`} title={group.title}>
                          {group.items.map((p) => (
                            <Menu.Item
                              key={`project-${p.id}`}
                              to={`/projects/${p.id}/data`}
                              data-external
                              exact
                            >
                              {p.title}
                            </Menu.Item>
                          ))}
                        </Menu.Group>
                      ))
                    : projectsList.length > 0 && (
                        <Menu.Group>
                          {projectsList.map((p) => (
                            <Menu.Item
                              key={`project-${p.id}`}
                              to={`/projects/${p.id}/data`}
                              data-external
                              exact
                            >
                              {p.title}
                            </Menu.Item>
                          ))}
                        </Menu.Group>
                      )}
                </CollapsibleMenuSection>
                <Menu.Item
                  label={t("menubar.organization")}
                  to="/organization"
                  icon={<IconPeople />}
                  data-external
                  exact
                />

                <Menu.Spacer />

                <VersionNotifier showNewVersion />

                <Menu.Item
                  label={t("menubar.api")}
                  href="https://api.labelstud.io/api-reference/introduction/getting-started"
                  icon={<IconTerminal />}
                  target="_blank"
                />
                <Menu.Item
                  label={t("menubar.docs")}
                  href="https://labelstud.io/guide"
                  icon={<IconBook />}
                  target="_blank"
                />
                <Menu.Item
                  label={t("menubar.github")}
                  href="https://github.com/HumanSignal/label-studio"
                  icon={<IconGithub />}
                  target="_blank"
                  rel="noreferrer"
                />
                <Menu.Item
                  label={t("menubar.slackCommunity")}
                  href="https://slack.labelstud.io/?source=product-menu"
                  icon={<IconSlack />}
                  target="_blank"
                  rel="noreferrer"
                />

                <VersionNotifier showCurrentVersion />

                <Menu.Divider />

                <Menu.Item
                  icon={<IconPin />}
                  className={sidebarClass.elem("pin").toClassName()}
                  onClick={sidebarPin}
                  active={sidebarPinned}
                >
                  {sidebarPinned ? t("menubar.unpinMenu") : t("menubar.pinMenu")}
                </Menu.Item>
              </Menu>
            </Dropdown>
          )}

          <MenubarContext.Provider value={providerValue}>
            <div
              className={contentClass
                .elem("content")
                .mod({ withSidebar: sidebarPinned && sidebarOpened })
                .toClassName()}
            >
              {children}
            </div>
          </MenubarContext.Provider>
        </div>
      </VersionProvider>
    </div>
  );
};
