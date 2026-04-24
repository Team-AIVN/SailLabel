import { formatDistance } from "date-fns";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Userpic } from "@humansignal/ui";
import { Pagination, Spinner } from "../../../components";
import { usePage, usePageSize } from "../../../components/Pagination/Pagination";
import { useAPI } from "../../../providers/ApiProvider";
import { cn } from "../../../utils/bem";
import { isDefined } from "../../../utils/helpers";
import { modal } from "../../../components/Modal/Modal";
import "./PeopleList.prefix.css";
import { CopyableTooltip } from "../../../components/CopyableTooltip/CopyableTooltip";
import { ManageRolesModal } from "./ManageRolesModal";

const ROLE_LABELS = {
  super_admin: "Super Admin",
  workspace_manager: "Workspace Manager",
  project_manager: "Project Manager",
  reviewer: "Reviewer",
  annotator: "Annotator",
  member: "Member",
};

const RoleChips = ({ member }) => {
  const chips = [];
  const orgRole = member.role || "member";
  if (orgRole === "super_admin") {
    chips.push({ key: "org-super", label: "Super Admin", tone: "admin" });
  }
  for (const a of member.role_assignments || []) {
    chips.push({
      key: `${a.scope}-${a.scope_id}-${a.role}`,
      label: `${ROLE_LABELS[a.role] || a.role} · ${a.scope_title || a.scope}`,
      tone: a.scope === "workspace" ? "workspace" : "project",
    });
  }
  if (chips.length === 0) {
    chips.push({ key: "member", label: "Member", tone: "muted" });
  }
  return (
    <div className={cn("people-list").elem("chips").toClassName()}>
      {chips.map((c) => (
        <span
          key={c.key}
          className={cn("people-list").elem("chip").mod({ tone: c.tone }).toClassName()}
        >
          {c.label}
        </span>
      ))}
    </div>
  );
};

export const PeopleList = ({ onSelect, selectedUser, defaultSelected }) => {
  const api = useAPI();
  const [usersList, setUsersList] = useState();
  const [currentPage] = usePage("page", 1);
  const [currentPageSize] = usePageSize("page_size", 30);
  const [totalItems, setTotalItems] = useState(0);
  const [currentUser, setCurrentUser] = useState(null);
  const manageModalRef = useRef();

  const fetchUsers = useCallback(
    async (page, pageSize) => {
      const response = await api.callApi("memberships", {
        params: {
          pk: 1,
          contributed_to_projects: 1,
          page,
          page_size: pageSize,
        },
      });

      if (response.results) {
        setUsersList(response.results);
        setTotalItems(response.count);
      }
    },
    [api],
  );

  useEffect(() => {
    api.callApi("me").then((resp) => {
      if (resp) setCurrentUser(resp);
    });
  }, [api]);

  const canManageRoles = useMemo(() => !!currentUser?.is_super_admin, [currentUser]);

  const selectUser = useCallback(
    (user) => {
      if (selectedUser?.id === user.id) {
        onSelect?.(null);
      } else {
        onSelect?.(user);
      }
    },
    [selectedUser],
  );

  useEffect(() => {
    fetchUsers(currentPage, currentPageSize);
  }, [fetchUsers, currentPage, currentPageSize]);

  useEffect(() => {
    if (isDefined(defaultSelected) && usersList) {
      const selected = usersList.find(({ user }) => user.id === Number(defaultSelected));

      if (selected) selectUser(selected.user);
    }
  }, [usersList, defaultSelected]);

  const openManageModal = useCallback(
    (member) => {
      // Close any prior instance first — `modal()` returns an imperative handle
      // and modal.tsx will otherwise stack them.
      manageModalRef.current?.close?.();
      manageModalRef.current = modal({
        title: `Manage roles — ${member.user.email}`,
        style: { width: 560 },
        body: () => (
          <ManageRolesModal
            user={member.user}
            onUpdated={() => fetchUsers(currentPage, currentPageSize)}
            onClose={() => manageModalRef.current?.close?.()}
          />
        ),
      });
    },
    [fetchUsers, currentPage, currentPageSize],
  );

  return (
    <>
      <div className={cn("people-list").toClassName()}>
        <div className={cn("people-list").elem("wrapper").toClassName()}>
          {usersList ? (
            <div className={cn("people-list").elem("users").toClassName()}>
              <div className={cn("people-list").elem("header").toClassName()}>
                <div className={cn("people-list").elem("column").mix("avatar").toClassName()} />
                <div className={cn("people-list").elem("column").mix("email").toClassName()}>Email</div>
                <div className={cn("people-list").elem("column").mix("name").toClassName()}>Name</div>
                <div className={cn("people-list").elem("column").mix("roles").toClassName()}>Roles</div>
                <div className={cn("people-list").elem("column").mix("last-activity").toClassName()}>Last Activity</div>
                {canManageRoles && (
                  <div className={cn("people-list").elem("column").mix("actions").toClassName()}>Actions</div>
                )}
              </div>
              <div className={cn("people-list").elem("body").toClassName()}>
                {usersList.map((member) => {
                  const { user } = member;
                  const active = user.id === selectedUser?.id;

                  return (
                    <div
                      key={`user-${user.id}`}
                      className={cn("people-list").elem("user").mod({ active }).toClassName()}
                      onClick={() => selectUser(user)}
                    >
                      <div className={cn("people-list").elem("field").mix("avatar").toClassName()}>
                        <CopyableTooltip title={`User ID: ${user.id}`} textForCopy={user.id}>
                          <Userpic user={user} style={{ width: 28, height: 28 }} />
                        </CopyableTooltip>
                      </div>
                      <div className={cn("people-list").elem("field").mix("email").toClassName()}>{user.email}</div>
                      <div className={cn("people-list").elem("field").mix("name").toClassName()}>
                        {user.first_name} {user.last_name}
                      </div>
                      <div className={cn("people-list").elem("field").mix("roles").toClassName()}>
                        <RoleChips member={member} />
                      </div>
                      <div className={cn("people-list").elem("field").mix("last-activity").toClassName()}>
                        {user.last_activity
                          ? formatDistance(new Date(user.last_activity), new Date(), { addSuffix: true })
                          : "—"}
                      </div>
                      {canManageRoles && (
                        <div className={cn("people-list").elem("field").mix("actions").toClassName()}>
                          <Button
                            size="small"
                            look="outlined"
                            onClick={(e) => {
                              e.stopPropagation();
                              openManageModal(member);
                            }}
                            aria-label={`Manage roles for ${user.email}`}
                          >
                            Manage
                          </Button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className={cn("people-list").elem("loading").toClassName()}>
              <Spinner size={36} />
            </div>
          )}
        </div>
        <Pagination
          page={currentPage}
          urlParamName="page"
          totalItems={totalItems}
          pageSize={currentPageSize}
          pageSizeOptions={[30, 50, 100]}
          onPageLoad={fetchUsers}
          style={{ paddingTop: 16 }}
        />
      </div>
    </>
  );
};
