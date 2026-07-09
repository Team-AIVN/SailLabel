import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";

const PROVIDER = "azure";
// 폴더 하나를 연결할 때 내부적으로 쓰는 규칙: JSON 태스크만, 하위 폴더 포함.
const TASK_JSON_REGEX = ".*\\.json$";

const rootClass = cn("workspace-storage-sources");

const boxStyle = {
  padding: "8px 12px",
  border: "1px solid var(--color-neutral-border)",
  borderRadius: 8,
  marginBottom: 6,
};

const mutedStyle = { fontSize: 12, color: "var(--color-neutral-content-subtler)" };

// 흰 배경 위에서도 입력 영역이 구분되도록 테두리/배경을 명시한다.
const inputStyle = {
  border: "1px solid var(--color-neutral-border-bold, #b6b9c2)",
  borderRadius: 6,
  background: "var(--color-neutral-surface, #fff)",
  padding: "4px 8px",
  fontSize: 13,
  height: 30,
};

/** Azure 폴더 → 작업집합 연결 관리자.
 *
 * 계정/키/컨테이너는 서버 환경변수(AZURE_BLOB_ACCOUNT_NAME/KEY, AZURE_BLOB_DEFAULT_CONTAINER)로
 * 관리한다 — 화면은 트리에서 폴더를 골라 작업집합에 연결하는 것만 노출한다.
 */
export const WorkspaceStorageSources = ({ workspaceId }) => {
  const api = useAPI();
  const toast = useToast();

  const [meta, setMeta] = useState(null); // {configured, container} | {configured:false, detail}
  const [tree, setTree] = useState({}); // path -> {folders: [{name, path}], fileCount}
  const [expanded, setExpanded] = useState(() => new Set());
  const [connections, setConnections] = useState([]);
  const [pools, setPools] = useState([]);
  const [connectTarget, setConnectTarget] = useState(null); // {name, path}
  const [poolChoice, setPoolChoice] = useState("new");
  const [newPoolTitle, setNewPoolTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [busySyncId, setBusySyncId] = useState(null);

  const listOf = (res) => (Array.isArray(res) ? res : (res?.results ?? []));

  const loadConnections = useCallback(async () => {
    const res = await api.callApi("workspaceStorages", {
      params: { provider: PROVIDER, workspace: workspaceId },
      errorFilter: () => true,
    });
    if (res?.$meta?.ok) setConnections(listOf(res));
  }, [api, workspaceId]);

  const loadPools = useCallback(async () => {
    const res = await api.callApi("taskPools", { params: { pk: workspaceId }, errorFilter: () => true });
    if (res?.$meta?.ok) setPools(listOf(res));
  }, [api, workspaceId]);

  /** 한 폴더 레벨을 읽어 트리에 저장. 반환: 그 레벨 정보. */
  const fetchLevel = useCallback(
    async (path = "") => {
      const res = await api.callApi("browseWorkspaceStorage", {
        params: { workspace: workspaceId, ...(path ? { path } : {}) },
        errorFilter: () => true,
      });
      if (!res?.$meta?.ok) {
        if (!path)
          setMeta({ configured: false, detail: res?.response?.detail ?? "Azure 연결 정보를 확인할 수 없습니다." });
        return null;
      }
      if (!path) setMeta({ configured: true, container: res.container });
      setTree((t) => ({ ...t, [path]: { folders: res.folders ?? [], fileCount: res.file_count ?? 0 } }));
      return res;
    },
    [api, workspaceId],
  );

  /** 펼치기: 자기 레벨 + 자식들의 파일 개수까지 미리 읽는다(개수 인라인 표시용). */
  const expand = useCallback(
    async (path) => {
      setExpanded((prev) => new Set(prev).add(path));
      const level = await fetchLevel(path);
      await Promise.all((level?.folders ?? []).map((f) => fetchLevel(f.path)));
    },
    [fetchLevel],
  );

  const collapse = (path) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.delete(path);
      return next;
    });

  useEffect(() => {
    (async () => {
      loadConnections();
      loadPools();
      const root = await fetchLevel("");
      // 루트 폴더는 자동으로 펼쳐서 바로 하위(1차/2차...)가 보이게 한다.
      await Promise.all((root?.folders ?? []).map((f) => expand(f.path)));
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  // 한 폴더가 여러 작업집합에 연결될 수 있으므로 prefix -> [연결...] 목록으로 관리.
  const connectedByPrefix = useMemo(() => {
    const map = new Map();
    connections.forEach((c) => {
      const key = c.prefix || "";
      map.set(key, [...(map.get(key) ?? []), c]);
    });
    return map;
  }, [connections]);

  const openConnect = (folder) => {
    setConnectTarget(folder);
    setPoolChoice("new");
    setNewPoolTitle(folder.name);
  };

  /** 폴더 하나를 작업집합에 연결하고 즉시 가져온다. */
  const connectAndImport = useCallback(async () => {
    if (!connectTarget) return;
    setBusy(true);
    try {
      let poolId = poolChoice === "new" ? null : Number(poolChoice);
      let poolTitle = poolChoice === "new" ? newPoolTitle.trim() : pools.find((p) => p.id === poolId)?.title;
      if (poolChoice === "new") {
        if (!poolTitle) {
          toast.show({ message: "작업집합 이름을 입력해 주세요.", type: "error" });
          return;
        }
        const res = await api.callApi("createTaskPool", {
          params: { pk: workspaceId },
          body: { title: poolTitle },
          errorFilter: () => true,
        });
        if (!res?.$meta?.ok) {
          toast.show({ message: res?.response?.detail ?? "작업집합 생성에 실패했습니다.", type: "error" });
          return;
        }
        poolId = res.id;
        loadPools();
      }

      const createRes = await api.callApi("createWorkspaceStorage", {
        params: { provider: PROVIDER },
        body: {
          workspace: workspaceId,
          title: connectTarget.name,
          container: meta?.container,
          prefix: connectTarget.path,
          regex_filter: TASK_JSON_REGEX,
          use_blob_urls: false,
          recursive_scan: true,
          task_pool: poolId,
        },
        errorFilter: () => true,
      });
      if (!createRes?.$meta?.ok) {
        toast.show({ message: createRes?.response?.detail ?? "폴더 연결에 실패했습니다.", type: "error" });
        return;
      }

      const syncRes = await api.callApi("syncWorkspaceStorage", {
        params: { provider: PROVIDER, pk: createRes.id },
        errorFilter: () => true,
      });
      if (!syncRes?.$meta?.ok) {
        toast.show({ message: syncRes?.response?.detail ?? "가져오기에 실패했습니다.", type: "error" });
        return;
      }
      const created = syncRes.created_items ?? 0;
      const linked = syncRes.linked_items ?? 0;
      toast.show({
        message:
          created > 0
            ? `'${connectTarget.name}' 폴더에서 ${created}개를 작업집합 '${poolTitle}'(으)로 가져왔습니다.`
            : linked > 0
              ? `이미 가져온 데이터 ${linked}개를 작업집합 '${poolTitle}'에 담았습니다. (복사 없음)`
              : `'${connectTarget.name}' 폴더에 가져올 파일이 없습니다.`,
      });
      setConnectTarget(null);
      loadConnections();
    } finally {
      setBusy(false);
    }
  }, [api, workspaceId, connectTarget, poolChoice, newPoolTitle, pools, meta, toast, loadConnections, loadPools]);

  /** 연결된 폴더에서 새 파일만 다시 가져온다. */
  const syncConnection = useCallback(
    async (conn) => {
      setBusySyncId(conn.id);
      try {
        const res = await api.callApi("syncWorkspaceStorage", {
          params: { provider: PROVIDER, pk: conn.id },
          errorFilter: () => true,
        });
        if (!res?.$meta?.ok) {
          toast.show({ message: res?.response?.detail ?? "가져오기에 실패했습니다.", type: "error" });
          return;
        }
        const n = (res.created_items ?? 0) + (res.linked_items ?? 0);
        toast.show({
          message:
            n > 0
              ? `새 데이터 ${n}개를 '${conn.task_pool_title ?? "데이터셋"}'(으)로 가져왔습니다.`
              : "새로 추가된 파일이 없습니다.",
        });
        loadConnections();
      } finally {
        setBusySyncId(null);
      }
    },
    [api, toast, loadConnections],
  );

  const disconnect = useCallback(
    async (conn) => {
      if (
        !window.confirm(
          `'${conn.title || conn.prefix}' 폴더 연결을 해제할까요?\n(이미 가져온 데이터와 작업집합은 그대로 유지됩니다)`,
        )
      )
        return;
      await api.callApi("deleteWorkspaceStorage", { params: { provider: PROVIDER, pk: conn.id } });
      loadConnections();
    },
    [api, loadConnections],
  );

  /** 연결 폼 (폴더 행 아래 확장) */
  const renderConnectForm = () => (
    <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px dashed var(--color-neutral-border)" }}>
      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, marginBottom: 6 }}>
        <input type="radio" checked={poolChoice === "new"} onChange={() => setPoolChoice("new")} />새 작업집합:
        <input
          value={newPoolTitle}
          onChange={(e) => setNewPoolTitle(e.target.value)}
          disabled={poolChoice !== "new"}
          style={{ ...inputStyle, flex: 1, maxWidth: 220, opacity: poolChoice === "new" ? 1 : 0.5 }}
        />
      </label>
      {pools.length > 0 && (
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, marginBottom: 6 }}>
          <input type="radio" checked={poolChoice !== "new"} onChange={() => setPoolChoice(String(pools[0].id))} />
          기존 작업집합:
          <select
            value={poolChoice === "new" ? "" : poolChoice}
            onChange={(e) => setPoolChoice(e.target.value)}
            disabled={poolChoice === "new"}
            style={{ ...inputStyle, minWidth: 140, opacity: poolChoice === "new" ? 0.5 : 1 }}
          >
            {pools.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
      )}
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <Button size="small" look="outlined" onClick={() => setConnectTarget(null)}>
          취소
        </Button>
        <Button size="small" waiting={busy} onClick={connectAndImport}>
          가져오기 시작
        </Button>
      </div>
    </div>
  );

  /** 트리 렌더 (재귀) */
  const renderNodes = (path = "", depth = 0) => {
    const level = tree[path];
    if (!level) return null;
    return level.folders.map((f) => {
      const conns = connectedByPrefix.get(f.path) ?? [];
      const child = tree[f.path];
      const isLeaf = child && child.folders.length === 0;
      const isExpanded = expanded.has(f.path);
      const isFormOpen = connectTarget?.path === f.path;
      return (
        <div key={f.path}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "7px 10px",
              paddingLeft: 10 + depth * 24,
              borderRadius: 6,
            }}
          >
            {isLeaf ? (
              <span style={{ width: 16 }} />
            ) : (
              <button
                type="button"
                onClick={() => (isExpanded ? collapse(f.path) : expand(f.path))}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  width: 16,
                  padding: 0,
                  color: "var(--color-neutral-content-subtler)",
                }}
                aria-label={isExpanded ? "접기" : "펼치기"}
              >
                {isExpanded ? "▾" : "▸"}
              </button>
            )}
            <span style={{ fontSize: 14 }}>
              {isLeaf ? "📁" : "📂"} <b>{f.name}</b>
            </span>
            {child && <span style={mutedStyle}>파일 {child.fileCount}개</span>}
            <div style={{ flex: 1 }} />
            {conns.length > 0 && (
              <span style={mutedStyle}>
                연결됨 → <b>{conns.map((c) => c.task_pool_title ?? c.title).join(", ")}</b>
              </span>
            )}
            {isLeaf && (
              // 가져오기는 말단 폴더(=데이터셋 단위)에서만. 이미 연결된 폴더도 다른
              // 작업집합으로 더 가져올 수 있다 — 파일 단위 중복 방지가 복사를 막아준다.
              <Button
                size="smaller"
                look={conns.length > 0 ? "string" : "outlined"}
                onClick={() => (isFormOpen ? setConnectTarget(null) : openConnect(f))}
              >
                {isFormOpen ? "닫기" : conns.length > 0 ? "+ 다른 작업집합으로" : "작업집합으로 가져오기"}
              </Button>
            )}
          </div>
          {isFormOpen && <div style={{ margin: `0 10px 6px ${34 + depth * 24}px` }}>{renderConnectForm()}</div>}
          {isExpanded && renderNodes(f.path, depth + 1)}
        </div>
      );
    });
  };

  // ----- 렌더 -----

  if (meta && meta.configured === false) {
    return (
      <div className={rootClass.toClassName()} style={{ marginBottom: 24 }}>
        <div style={{ ...boxStyle, borderColor: "var(--color-warning-border, orange)" }}>
          <strong>Azure 연결이 설정되지 않았습니다</strong>
          <p style={mutedStyle}>{meta.detail}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={rootClass.toClassName()} style={{ marginBottom: 24 }}>
      {/* 연결된 폴더 (증분 가져오기 대시보드) */}
      {connections.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>연결된 폴더</div>
          {connections.map((c) => (
            <div key={c.id} style={{ ...boxStyle, display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 14 }}>
                  📁 <b>{c.title || c.prefix}</b>
                </span>
                <span style={{ ...mutedStyle, marginLeft: 8 }}>
                  → <b>{c.task_pool_title ?? "(작업집합 미지정)"}</b>
                  {c.last_sync ? ` · ${new Date(c.last_sync).toLocaleString()} (${c.last_sync_count ?? 0}개)` : ""}
                </span>
              </div>
              <Button size="smaller" waiting={busySyncId === c.id} onClick={() => syncConnection(c)}>
                새 데이터 가져오기
              </Button>
              <Button size="smaller" look="string" onClick={() => disconnect(c)}>
                연결 해제
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* 폴더 트리 */}
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 6 }}>
          <span style={{ fontWeight: 600 }}>Azure 폴더 둘러보기</span>
          {meta?.container && <span style={mutedStyle}>저장소 {meta.container}</span>}
        </div>
        <div style={{ ...boxStyle, padding: "4px 0" }}>
          {!meta && <p style={{ ...mutedStyle, padding: "6px 12px" }}>폴더 목록을 불러오는 중...</p>}
          {meta?.configured && tree[""] && tree[""].folders.length === 0 && (
            <p style={{ ...mutedStyle, padding: "6px 12px" }}>가져올 수 있는 폴더가 없습니다.</p>
          )}
          {renderNodes()}
        </div>
      </div>
    </div>
  );
};
