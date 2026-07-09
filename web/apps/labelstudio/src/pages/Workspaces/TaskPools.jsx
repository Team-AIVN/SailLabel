import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./TaskPools.prefix.css";

const listOf = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const TYPE_ICON = {
  image: "🖼️",
  audio: "🎧",
  video: "🎬",
  csv: "📊",
  pair: "🖼️",
  json: "📄",
  text: "📄",
  pdf: "📄",
  html: "📄",
};

const itemPreview = (item) => {
  if (item.thumbnail) return item.thumbnail;
  if (item.data && typeof item.data === "object") {
    const v = Object.values(item.data).find((x) => typeof x === "string");
    if (v) return v;
  }
  return "";
};

/** URL 덤프 대신 사람이 읽는 라벨: 파일명 또는 짧은 텍스트. */
const itemLabel = (item) => {
  const preview = itemPreview(item);
  if (!preview) return `#${item.id}`;
  if (preview.includes("://") || preview.startsWith("/")) {
    const base = preview.split("?")[0].split("/").pop();
    try {
      return decodeURIComponent(base || preview);
    } catch {
      return base || preview;
    }
  }
  return preview.length > 80 ? `${preview.slice(0, 80)}…` : preview;
};

/** 작업집합(풀) 중심 관리 화면.
 *
 * 주 유입은 클라우드 스토리지 연결이 자동으로 처리하므로, 이 화면은
 * "풀 안에 뭐가 있나 확인 + 예외적으로 항목을 추가/제거"하는 용도다.
 */
export const TaskPools = ({ workspaceId }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("task-pools"), []);

  const [pools, setPools] = useState([]);
  const [selectedPoolId, setSelectedPoolId] = useState(null);
  const [poolDetail, setPoolDetail] = useState(null);
  const [poolSelected, setPoolSelected] = useState(() => new Set());
  const [newPoolTitle, setNewPoolTitle] = useState("");
  const [loading, setLoading] = useState(true);

  // 항목 추가 피커
  const [showPicker, setShowPicker] = useState(false);
  const [items, setItems] = useState([]);
  const [pickerSelected, setPickerSelected] = useState(() => new Set());
  const [sourceFilter, setSourceFilter] = useState("");
  const [sourceOptions, setSourceOptions] = useState([]); // [{value: 'azure:3', label: '1차'}]
  const [search, setSearch] = useState("");

  const sourceLabel = useMemo(() => {
    const map = new Map(sourceOptions.map((s) => [s.value, s.label]));
    return (src) => (src ? (map.get(src) ?? "Azure") : t("taskpools.sourceUpload", "업로드"));
  }, [sourceOptions, t]);

  const loadPools = useCallback(async () => {
    const res = await api.callApi("taskPools", { params: { pk: workspaceId } });
    const rows = listOf(res);
    setPools(rows);
    return rows;
  }, [api, workspaceId]);

  const loadPoolDetail = useCallback(
    async (poolId) => {
      if (!poolId) {
        setPoolDetail(null);
        return;
      }
      const res = await api.callApi("taskPool", { params: { pk: workspaceId, poolPk: poolId } });
      setPoolDetail(res && !res.error ? res : null);
    },
    [api, workspaceId],
  );

  const loadItems = useCallback(async () => {
    const params = { pk: workspaceId };
    if (sourceFilter) params.source = sourceFilter;
    if (search) params.search = search;
    if (selectedPoolId) params.task_pool = selectedPoolId;
    const res = await api.callApi("workspaceTaskSourceItems", { params });
    setItems(listOf(res));
  }, [api, workspaceId, sourceFilter, search, selectedPoolId]);

  const loadSourceOptions = useCallback(async () => {
    const res = await api.callApi("workspaceStorages", {
      params: { provider: "azure", workspace: workspaceId },
      errorFilter: () => true,
    });
    if (!res?.$meta?.ok) return;
    setSourceOptions(listOf(res).map((s) => ({ value: `azure:${s.id}`, label: s.title || s.container })));
  }, [api, workspaceId]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      loadSourceOptions();
      const rows = await loadPools();
      if (rows.length && selectedPoolId == null) setSelectedPoolId(rows[0].id);
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 피커가 열려 있을 때만 전체 항목 목록을 불러온다.
  useEffect(() => {
    if (showPicker) loadItems();
  }, [showPicker, loadItems]);

  useEffect(() => {
    loadPoolDetail(selectedPoolId);
    setPoolSelected(new Set());
    setPickerSelected(new Set());
  }, [selectedPoolId, loadPoolDetail]);

  const toggle = (setFn) => (id) =>
    setFn((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const togglePicker = toggle(setPickerSelected);
  const togglePoolItem = toggle(setPoolSelected);

  const selectableIds = useMemo(() => items.filter((it) => !it.included).map((it) => it.id), [items]);
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => pickerSelected.has(id));
  const toggleSelectAll = useCallback(() => {
    setPickerSelected((prev) => {
      const allChosen = selectableIds.length > 0 && selectableIds.every((id) => prev.has(id));
      if (allChosen) {
        const next = new Set(prev);
        selectableIds.forEach((id) => next.delete(id));
        return next;
      }
      return new Set([...prev, ...selectableIds]);
    });
  }, [selectableIds]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadPoolDetail(selectedPoolId), loadPools(), showPicker ? loadItems() : Promise.resolve()]);
    setPickerSelected(new Set());
    setPoolSelected(new Set());
  }, [loadPoolDetail, loadPools, loadItems, selectedPoolId, showPicker]);

  const addItems = useCallback(async () => {
    if (!selectedPoolId || pickerSelected.size === 0) return;
    const res = await api.callApi("addTaskPoolItems", {
      params: { pk: workspaceId, poolPk: selectedPoolId },
      body: { task_source_item_ids: Array.from(pickerSelected) },
    });
    if (res && !res.error) {
      toast.show({ message: t("taskpools.added", "항목을 추가했습니다") });
      setShowPicker(false);
      refreshAll();
    } else {
      toast.show({ message: res?.detail ?? t("taskpools.actionFailed", "실패했습니다"), type: "error" });
    }
  }, [api, workspaceId, selectedPoolId, pickerSelected, toast, t, refreshAll]);

  const removeItems = useCallback(async () => {
    if (!selectedPoolId || poolSelected.size === 0) return;
    const res = await api.callApi("removeTaskPoolItems", {
      params: { pk: workspaceId, poolPk: selectedPoolId },
      body: { task_source_item_ids: Array.from(poolSelected) },
    });
    if (res && !res.error) {
      toast.show({ message: t("taskpools.removed", "항목을 제거했습니다") });
      refreshAll();
    }
  }, [api, workspaceId, selectedPoolId, poolSelected, toast, t, refreshAll]);

  const createPool = useCallback(async () => {
    const title = newPoolTitle.trim();
    if (!title) return;
    const res = await api.callApi("createTaskPool", { params: { pk: workspaceId }, body: { title } });
    if (res?.id) {
      setNewPoolTitle("");
      await loadPools();
      setSelectedPoolId(res.id);
      toast.show({ message: t("taskpools.created", "작업집합을 만들었습니다") });
    } else {
      toast.show({ message: res?.detail ?? t("taskpools.actionFailed", "실패했습니다"), type: "error" });
    }
  }, [api, workspaceId, newPoolTitle, loadPools, toast, t]);

  const renamePool = useCallback(async () => {
    if (!poolDetail) return;
    const title = window.prompt(t("taskpools.renamePrompt", "새 이름"), poolDetail.title);
    if (!title || !title.trim()) return;
    const res = await api.callApi("updateTaskPool", {
      params: { pk: workspaceId, poolPk: poolDetail.id },
      body: { title: title.trim() },
    });
    if (res?.id) {
      loadPools();
      loadPoolDetail(poolDetail.id);
    }
  }, [api, workspaceId, poolDetail, t, loadPools, loadPoolDetail]);

  const deletePool = useCallback(async () => {
    if (!poolDetail) return;
    if (!window.confirm(t("taskpools.deleteConfirm", "이 작업집합을 삭제할까요? (데이터셋 항목은 유지됩니다)"))) return;
    await api.callApi("deleteTaskPool", { params: { pk: workspaceId, poolPk: poolDetail.id } });
    setSelectedPoolId(null);
    const rows = await loadPools();
    setSelectedPoolId(rows[0]?.id ?? null);
  }, [api, workspaceId, poolDetail, t, loadPools]);

  const renderItemRow = (it, { checked, onToggle, disabled = false, badge = null }) => {
    const preview = itemPreview(it);
    const isImageUrl =
      preview && /\.(png|jpe?g|gif|webp|svg)(\?|$)/i.test(preview) && !preview.startsWith("azure-blob");
    return (
      <li key={it.id} className={root.elem("item").mod({ included: disabled, selected: checked }).toClassName()}>
        <input type="checkbox" disabled={disabled} checked={checked} onChange={onToggle} />
        <span className={root.elem("thumb").toClassName()}>
          {isImageUrl ? (
            <img src={preview} alt="" />
          ) : (
            <span style={{ fontSize: 16 }}>{TYPE_ICON[it.data_type] ?? "📄"}</span>
          )}
        </span>
        <span className={root.elem("item-meta").toClassName()}>
          <span className={root.elem("item-text").toClassName()}>{itemLabel(it)}</span>
          <span className={root.elem("item-id").toClassName()}>
            #{it.id} · {sourceLabel(it.source)}
          </span>
        </span>
        {badge}
      </li>
    );
  };

  if (loading) return <div className={root.elem("loading").toClassName()}>…</div>;

  return (
    <div className={root.toClassName()}>
      {/* 작업집합 관리 (메인) */}
      <section className={root.elem("panel").toClassName()}>
        <header className={root.elem("panel-head").toClassName()}>
          <div className={root.elem("panel-title").toClassName()}>
            <select
              value={selectedPoolId ?? ""}
              onChange={(e) => setSelectedPoolId(e.target.value ? Number(e.target.value) : null)}
              style={{ minWidth: 220 }}
            >
              <option value="">{t("taskpools.selectPool", "작업집합 선택")}</option>
              {pools.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} ({p.item_count})
                </option>
              ))}
            </select>
            {poolDetail && (
              <div className={root.elem("pool-actions").toClassName()}>
                <Button size="smaller" look="string" onClick={renamePool}>
                  {t("taskpools.rename", "이름 변경")}
                </Button>
                <Button size="smaller" look="string" variant="negative" onClick={deletePool}>
                  {t("common.delete", "삭제")}
                </Button>
              </div>
            )}
            <div style={{ flex: 1 }} />
            <input
              placeholder={t("taskpools.newPoolTitle", "새 작업집합 이름")}
              value={newPoolTitle}
              onChange={(e) => setNewPoolTitle(e.target.value)}
              style={{ width: 180 }}
            />
            <Button size="small" onClick={createPool} disabled={!newPoolTitle.trim()}>
              {t("taskpools.create", "만들기")}
            </Button>
          </div>
        </header>

        {poolDetail ? (
          <>
            <div className={root.elem("toolbar").toClassName()}>
              <span className={root.elem("count").toClassName()}>
                {t("taskpools.itemCount", "{{count}}개 항목", {
                  count: poolDetail.item_count ?? (poolDetail.items ?? []).length,
                })}
                {poolSelected.size > 0 && ` · ${poolSelected.size}개 선택`}
              </span>
              <div style={{ flex: 1 }} />
              {poolSelected.size > 0 && (
                <Button size="smaller" look="outlined" variant="negative" onClick={removeItems}>
                  {t("taskpools.removeSelected", "선택 항목 제거")}
                </Button>
              )}
              <Button
                size="smaller"
                look={showPicker ? "string" : "outlined"}
                onClick={() => setShowPicker(!showPicker)}
              >
                {showPicker ? t("common.close", "닫기") : t("taskpools.addItems", "+ 항목 추가")}
              </Button>
            </div>
            <ul className={root.elem("items").toClassName()}>
              {(poolDetail.items ?? []).map((it) =>
                renderItemRow(it, { checked: poolSelected.has(it.id), onToggle: () => togglePoolItem(it.id) }),
              )}
              {(poolDetail.items ?? []).length === 0 && (
                <li className={root.elem("muted").toClassName()}>
                  {t(
                    "taskpools.empty",
                    "비어 있습니다 — 클라우드 스토리지 탭에서 폴더를 연결하거나 [+ 항목 추가]로 담으세요.",
                  )}
                </li>
              )}
            </ul>
          </>
        ) : (
          <p className={root.elem("muted").toClassName()}>
            {t(
              "taskpools.noPool",
              "작업집합이 없습니다. 클라우드 스토리지 탭에서 폴더를 연결하면 자동으로 만들어집니다.",
            )}
          </p>
        )}
      </section>

      {/* 항목 추가 피커 (필요할 때만) */}
      {showPicker && poolDetail && (
        <section className={root.elem("panel").mod({ picker: true }).toClassName()}>
          <header className={root.elem("panel-head").toClassName()}>
            <div className={root.elem("panel-title").toClassName()}>
              <strong>
                {t("taskpools.pickerTitle", "추가할 항목 선택")}
                {pickerSelected.size > 0 && (
                  <span className={root.elem("selected-count").toClassName()}> ({pickerSelected.size})</span>
                )}
              </strong>
              <Button size="smaller" look="string" onClick={toggleSelectAll} disabled={selectableIds.length === 0}>
                {allSelected ? t("taskpools.deselectAll", "전체 해제") : t("taskpools.selectAll", "전체 선택")}
              </Button>
            </div>
            <div className={root.elem("filters").toClassName()}>
              <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} aria-label="source filter">
                <option value="">{t("taskpools.allSources", "모든 소스")}</option>
                <option value="upload">{t("taskpools.sourceUpload", "직접 업로드")}</option>
                {sourceOptions.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label} (Azure)
                  </option>
                ))}
              </select>
              <input
                placeholder={t("taskpools.search", "검색")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </header>
          <ul className={root.elem("items").toClassName()}>
            {items.map((it) =>
              renderItemRow(it, {
                checked: pickerSelected.has(it.id),
                onToggle: () => togglePicker(it.id),
                disabled: it.included,
                badge: it.included ? (
                  <span className={root.elem("badge").toClassName()}>{t("taskpools.included", "이미 담김")}</span>
                ) : null,
              }),
            )}
            {items.length === 0 && (
              <li className={root.elem("muted").toClassName()}>{t("taskpools.noItems", "항목이 없습니다")}</li>
            )}
          </ul>
          <footer className={root.elem("picker-foot").toClassName()}>
            <Button size="small" look="outlined" onClick={() => setShowPicker(false)}>
              {t("common.cancel", "취소")}
            </Button>
            <Button size="small" onClick={addItems} disabled={pickerSelected.size === 0}>
              {t("taskpools.addSelected", "선택 {{count}}개 추가", { count: pickerSelected.size })}
            </Button>
          </footer>
        </section>
      )}
    </div>
  );
};
