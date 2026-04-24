import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Select } from "@humansignal/ui";
import { useAPI } from "../../../providers/ApiProvider";
import { cn } from "../../../utils/bem";
import "./Members.prefix.css";

const ROLES = ["project_manager", "reviewer", "annotator"];

const userLabel = (user) => user.email || user.username || `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim() || `#${user.id}`;

export const MembersPage = ({ show, assignments, setAssignments, organizationId }) => {
  const { t } = useTranslation();
  const api = useAPI();

  const [members, setMembers] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [selectedRole, setSelectedRole] = useState(ROLES[2]);
  const [selectedUserId, setSelectedUserId] = useState(null);

  useEffect(() => {
    if (!organizationId) return;
    let cancelled = false;
    (async () => {
      const resp = await api.callApi("memberships", {
        params: { pk: organizationId, contributed_to_projects: 0 },
        suppressError: true,
      });
      if (cancelled) return;
      if (!resp || resp.error) {
        setLoadError(t("createProject.members.loadError"));
        return;
      }
      const items = resp?.results || resp || [];
      const list = (Array.isArray(items) ? items : [])
        .map((m) => m.user)
        .filter(Boolean);
      setMembers(list);
      if (!selectedUserId && list.length > 0) setSelectedUserId(list[0].id);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [organizationId]);

  const rootClass = useMemo(() => cn("project-members"), []);

  const userOptions = useMemo(
    () => members.map((u) => ({ value: u.id, label: userLabel(u) })),
    [members],
  );

  const roleOptions = useMemo(
    () => ROLES.map((r) => ({ value: r, label: t(`createProject.members.roles.${r}`) })),
    [t],
  );

  const handleAdd = useCallback(() => {
    if (!selectedUserId || !selectedRole) return;
    setAssignments((prev) => {
      const exists = prev.some((a) => a.user === selectedUserId && a.role === selectedRole);
      if (exists) return prev;
      const user = members.find((u) => u.id === selectedUserId);
      return [...prev, { user: selectedUserId, role: selectedRole, label: user ? userLabel(user) : `#${selectedUserId}` }];
    });
  }, [selectedUserId, selectedRole, members, setAssignments]);

  const handleRemove = useCallback(
    (idx) => {
      setAssignments((prev) => prev.filter((_, i) => i !== idx));
    },
    [setAssignments],
  );

  if (!show) return null;

  return (
    <div className={rootClass.toClassName()}>
      <div className={rootClass.elem("note").toClassName()}>{t("createProject.members.note")}</div>

      <div className={rootClass.elem("picker").toClassName()}>
        <label className={rootClass.elem("field").toClassName()}>
          <span>{t("createProject.members.rolePicker")}</span>
          <Select value={selectedRole} options={roleOptions} onChange={setSelectedRole} />
        </label>
        <label className={rootClass.elem("field").toClassName()}>
          <span>{t("createProject.members.userPicker")}</span>
          <Select
            value={selectedUserId}
            options={userOptions}
            onChange={setSelectedUserId}
            disabled={userOptions.length === 0}
          />
        </label>
        <Button
          look="primary"
          onClick={handleAdd}
          disabled={!selectedUserId}
          aria-label={t("createProject.members.addButton")}
        >
          {t("createProject.members.addButton")}
        </Button>
      </div>

      {loadError && <div className={rootClass.elem("error").toClassName()}>{loadError}</div>}

      {assignments.length === 0 ? (
        <div className={rootClass.elem("empty").toClassName()}>{t("createProject.members.empty")}</div>
      ) : (
        <ul className={rootClass.elem("list").toClassName()}>
          {assignments.map((a, idx) => (
            <li key={`${a.user}-${a.role}`} className={rootClass.elem("row").toClassName()}>
              <span className={rootClass.elem("chip").mod({ role: a.role }).toClassName()}>
                {t(`createProject.members.roles.${a.role}`)}
              </span>
              <span className={rootClass.elem("user").toClassName()}>{a.label}</span>
              <Button
                size="small"
                look="outlined"
                variant="negative"
                onClick={() => handleRemove(idx)}
                aria-label={t("createProject.members.removeAriaLabel")}
              >
                {t("common.remove", "Remove")}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
