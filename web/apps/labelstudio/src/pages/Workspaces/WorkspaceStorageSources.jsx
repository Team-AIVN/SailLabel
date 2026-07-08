import { useCallback, useEffect, useState } from "react";
import { Button, useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";

const PROVIDER = "azure";

const EMPTY_FORM = {
  title: "",
  container: "",
  prefix: "",
  account_name: "",
  account_key: "",
  regex_filter: "",
  use_blob_urls: true,
};

const rootClass = cn("workspace-storage-sources");

/** Workspace-level Azure storage sources: synced blobs become task-pool source items. */
export const WorkspaceStorageSources = ({ workspaceId }) => {
  const api = useAPI();
  const toast = useToast();
  const [storages, setStorages] = useState([]);
  const [form, setForm] = useState(null); // null = closed, {...fields, id?} = open
  const [busyId, setBusyId] = useState(null);

  const refresh = useCallback(async () => {
    const res = await api.callApi("workspaceStorages", {
      params: { provider: PROVIDER, workspacePk: workspaceId },
    });
    setStorages(Array.isArray(res) ? res : (res?.results ?? []));
  }, [api, workspaceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const setField = (key) => (e) => {
    const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };

  const save = useCallback(async () => {
    const isEdit = !!form.id;
    const body = { ...form, workspace: workspaceId };
    // Don't overwrite a stored key with the blank placeholder on edit.
    if (isEdit && !body.account_key) delete body.account_key;
    const res = await api.callApi(isEdit ? "updateWorkspaceStorage" : "createWorkspaceStorage", {
      params: isEdit ? { provider: PROVIDER, pk: form.id } : { provider: PROVIDER },
      body,
      errorFilter: () => true,
    });
    if (res?.error || res?.$meta?.status >= 400) {
      toast.show({ message: res?.response?.detail ?? "스토리지 저장에 실패했습니다.", type: "error" });
      return;
    }
    setForm(null);
    toast.show({ message: isEdit ? "스토리지가 수정되었습니다." : "스토리지가 등록되었습니다." });
    refresh();
  }, [api, form, workspaceId, toast, refresh]);

  const remove = useCallback(
    async (storage) => {
      if (
        !window.confirm(
          `"${storage.title || storage.container}" 스토리지를 삭제할까요?\n(이미 가져온 데이터셋 아이템은 유지됩니다)`,
        )
      )
        return;
      await api.callApi("deleteWorkspaceStorage", { params: { provider: PROVIDER, pk: storage.id } });
      refresh();
    },
    [api, refresh],
  );

  const sync = useCallback(
    async (storage) => {
      setBusyId(storage.id);
      try {
        const res = await api.callApi("syncWorkspaceStorage", {
          params: { provider: PROVIDER, pk: storage.id },
          errorFilter: () => true,
        });
        if (res?.error || res?.$meta?.status >= 400) {
          toast.show({
            message: res?.response?.detail ?? "동기화에 실패했습니다. 연결 정보를 확인하세요.",
            type: "error",
          });
          return;
        }
        const created = res?.created_items ?? 0;
        toast.show({
          message:
            created > 0
              ? `${created}개 아이템을 데이터셋으로 가져왔습니다. 작업집합 탭에서 큐레이션하세요.`
              : "새로 가져올 아이템이 없습니다. (이미 모두 동기화됨)",
        });
        refresh();
      } finally {
        setBusyId(null);
      }
    },
    [api, toast, refresh],
  );

  return (
    <div className={rootClass.toClassName()} style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div>
          <span style={{ fontWeight: 600 }}>작업집합 데이터 소스 (Azure)</span>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--color-neutral-content-subtler)" }}>
            동기화하면 컨테이너의 파일(JSON 태스크·이미지)이 워크스페이스 데이터셋 아이템으로 들어와 작업집합에 담을 수
            있습니다. JSON에 predictions가 있으면 프로젝트 생성 시 함께 반영됩니다.
          </p>
        </div>
        <Button size="small" onClick={() => setForm({ ...EMPTY_FORM })}>
          스토리지 추가
        </Button>
      </div>

      {storages.length === 0 && !form && (
        <p style={{ fontSize: 13, color: "var(--color-neutral-content-subtler)" }}>등록된 데이터 소스가 없습니다.</p>
      )}

      {storages.map((s) => (
        <div
          key={s.id}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 12px",
            border: "1px solid var(--color-neutral-border)",
            borderRadius: 8,
            marginBottom: 8,
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600 }}>{s.title || s.container}</div>
            <div style={{ fontSize: 12, color: "var(--color-neutral-content-subtler)" }}>
              {s.container}
              {s.prefix ? `/${s.prefix}` : ""}
              {s.last_sync
                ? ` · 마지막 동기화 ${new Date(s.last_sync).toLocaleString()} (${s.last_sync_count ?? 0}개)`
                : " · 아직 동기화 안 됨"}
            </div>
          </div>
          <Button size="smaller" waiting={busyId === s.id} onClick={() => sync(s)}>
            동기화
          </Button>
          <Button size="smaller" look="outlined" onClick={() => setForm({ ...EMPTY_FORM, ...s, account_key: "" })}>
            수정
          </Button>
          <Button size="smaller" look="danger" onClick={() => remove(s)}>
            삭제
          </Button>
        </div>
      ))}

      {form && (
        <div
          style={{
            padding: 12,
            border: "1px solid var(--color-neutral-border)",
            borderRadius: 8,
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 8,
          }}
        >
          <label style={{ fontSize: 12 }}>
            이름
            <input
              value={form.title}
              onChange={setField("title")}
              style={{ width: "100%" }}
              placeholder="예: 선박 데이터"
            />
          </label>
          <label style={{ fontSize: 12 }}>
            컨테이너 *
            <input
              value={form.container}
              onChange={setField("container")}
              style={{ width: "100%" }}
              placeholder="label-images"
            />
          </label>
          <label style={{ fontSize: 12 }}>
            Prefix (하위 경로)
            <input
              value={form.prefix ?? ""}
              onChange={setField("prefix")}
              style={{ width: "100%" }}
              placeholder="images/"
            />
          </label>
          <label style={{ fontSize: 12 }}>
            파일명 필터 (정규식)
            <input
              value={form.regex_filter ?? ""}
              onChange={setField("regex_filter")}
              style={{ width: "100%" }}
              placeholder=".*json"
            />
          </label>
          <label style={{ fontSize: 12 }}>
            스토리지 계정 이름 *
            <input value={form.account_name ?? ""} onChange={setField("account_name")} style={{ width: "100%" }} />
          </label>
          <label style={{ fontSize: 12 }}>
            액세스 키 {form.id ? "(변경할 때만 입력)" : "*"}
            <input
              type="password"
              value={form.account_key ?? ""}
              onChange={setField("account_key")}
              style={{ width: "100%" }}
            />
          </label>
          <label style={{ fontSize: 12, gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={!!form.use_blob_urls} onChange={setField("use_blob_urls")} />
            모든 파일을 개별 아이템으로 취급 (끄면 JSON 파일을 태스크 목록으로 파싱)
          </label>
          <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <Button size="small" look="outlined" onClick={() => setForm(null)}>
              취소
            </Button>
            <Button size="small" onClick={save} disabled={!form.container || !form.account_name}>
              저장
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
