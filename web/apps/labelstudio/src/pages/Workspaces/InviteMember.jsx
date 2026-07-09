import { useMemo, useState } from "react";
import { Button, useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";

// Workspace-level roles vs project-level roles. Selecting a project switches the
// role options to the project roles (PM designation happens here for WM/SA).
const WS_ROLES = [
  { value: "member", label: "멤버 (배정 대기)" },
  { value: "workspace_manager", label: "워크스페이스 관리자" },
];
export const PROJECT_ROLES = [
  { value: "project_manager", label: "PM (프로젝트 관리자)" },
  { value: "annotator", label: "라벨러" },
  { value: "reviewer", label: "검수자" },
  { value: "member", label: "Worker (미배정)" },
];

const fieldStyle = { height: 32, padding: "0 8px", border: "1px solid var(--color-neutral-border)", borderRadius: 6 };

/**
 * Email-based invite: creates a per-recipient link that, once the person signs up,
 * places them into this workspace (and optionally a project with a role).
 */
export const InviteMember = ({ workspaceId, projects = [] }) => {
  const api = useAPI();
  const toast = useToast();
  const [projectId, setProjectId] = useState("");
  const [role, setRole] = useState("member");
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);

  const roleOptions = useMemo(() => (projectId ? PROJECT_ROLES : WS_ROLES), [projectId]);

  const onProjectChange = (value) => {
    setProjectId(value);
    setRole(value ? "annotator" : "member");
    setLink("");
  };

  const generate = async () => {
    setBusy(true);
    const body = { role };
    if (projectId) body.project = Number(projectId);
    else body.workspace = Number(workspaceId);
    const res = await api.callApi("createInvitation", { body });
    setBusy(false);
    if (res?.link) {
      setLink(res.link);
      toast.show({ message: "초대 링크가 생성됐습니다" });
    } else {
      toast.show({ message: res?.detail ?? "초대 생성에 실패했습니다", type: "error" });
    }
  };

  const copy = async () => {
    // navigator.clipboard is only available in secure contexts (https/localhost); on a
    // plain-http deployment it's undefined, so fall back to execCommand and only claim
    // success when a copy actually happened.
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(link);
      } else {
        const ta = document.createElement("textarea");
        ta.value = link;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        if (!ok) throw new Error("execCommand copy failed");
      }
      toast.show({ message: "복사됐습니다" });
    } catch {
      toast.show({ message: "복사에 실패했습니다. 링크를 직접 선택해 복사하세요.", type: "error" });
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 720 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <select value={projectId} onChange={(e) => onProjectChange(e.target.value)} style={fieldStyle}>
          <option value="">프로젝트 없음 (워크스페이스만)</option>
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
        <select value={role} onChange={(e) => setRole(e.target.value)} style={fieldStyle}>
          {roleOptions.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <Button size="small" onClick={generate} waiting={busy}>
          초대 링크 생성
        </Button>
      </div>
      {link && (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input readOnly value={link} style={{ ...fieldStyle, flex: 1 }} onFocus={(e) => e.target.select()} />
          <Button size="small" look="outlined" onClick={copy}>
            링크 복사
          </Button>
        </div>
      )}
    </div>
  );
};
