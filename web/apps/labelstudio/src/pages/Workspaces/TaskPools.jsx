import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./TaskPools.prefix.css";

const DATA_TYPES = ["", "image", "audio", "video", "text", "json", "csv", "html", "pdf", "pair", "file"];

const listOf = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const itemPreview = (item) => {
  if (item.thumbnail) return item.thumbnail;
  if (item.data && typeof item.data === "object") {
    const v = Object.values(item.data).find((x) => typeof x === "string");
    if (v) return v;
  }
  return "";
};

/** Two-panel Task Pool manager: dataset items (left) <-> task pool items (right). */
export const TaskPools = ({ workspaceId }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("task-pools"), []);

  const [pools, setPools] = useState([]);
  const [selectedPoolId, setSelectedPoolId] = useState(null);
  const [poolDetail, setPoolDetail] = useState(null);
  const [items, setItems] = useState([]);
  const [typeFilter, setTypeFilter] = useState("");
  const [search, setSearch] = useState("");
  const [leftSelected, setLeftSelected] = useState(() => new Set());
  const [rightSelected, setRightSelected] = useState(() => new Set());
  const [newPoolTitle, setNewPoolTitle] = useState("");
  const [loading, setLoading] = useState(true);

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
    if (typeFilter) params.data_type = typeFilter;
    if (search) params.search = search;
    if (selectedPoolId) params.task_pool = selectedPoolId;
    const res = await api.callApi("workspaceTaskSourceItems", { params });
    setItems(listOf(res));
  }, [api, workspaceId, typeFilter, search, selectedPoolId]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const rows = await loadPools();
      if (rows.length && selectedPoolId == null) setSelectedPoolId(rows[0].id);
      setLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);
  useEffect(() => {
    loadPoolDetail(selectedPoolId);
    setRightSelected(new Set());
    setLeftSelected(new Set());
  }, [selectedPoolId, loadPoolDetail]);

  const toggle = (setFn) => (id) =>
    setFn((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  const toggleLeft = toggle(setLeftSelected);
  const toggleRight = toggle(setRightSelected);

  // Items selectable on the left = those not already included in the current pool.
  const selectableIds = useMemo(() => items.filter((it) => !it.included).map((it) => it.id), [items]);
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => leftSelected.has(id));
  const toggleSelectAll = useCallback(() => {
    setLeftSelected((prev) => {
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
    await Promise.all([loadItems(), loadPoolDetail(selectedPoolId), loadPools()]);
    setLeftSelected(new Set());
    setRightSelected(new Set());
  }, [loadItems, loadPoolDetail, loadPools, selectedPoolId]);

  const addItems = useCallback(async () => {
    if (!selectedPoolId || leftSelected.size === 0) return;
    const res = await api.callApi("addTaskPoolItems", {
      params: { pk: workspaceId, poolPk: selectedPoolId },
      body: { task_source_item_ids: Array.from(leftSelected) },
    });
    if (res && !res.error) {
      toast.show({ message: t("taskpools.added", "Items added") });
      refreshAll();
    } else {
      toast.show({ message: res?.detail ?? t("taskpools.actionFailed", "Action failed"), type: "error" });
    }
  }, [api, workspaceId, selectedPoolId, leftSelected, toast, t, refreshAll]);

  const removeItems = useCallback(async () => {
    if (!selectedPoolId || rightSelected.size === 0) return;
    const res = await api.callApi("removeTaskPoolItems", {
      params: { pk: workspaceId, poolPk: selectedPoolId },
      body: { task_source_item_ids: Array.from(rightSelected) },
    });
    if (res && !res.error) {
      toast.show({ message: t("taskpools.removed", "Items removed") });
      refreshAll();
    }
  }, [api, workspaceId, selectedPoolId, rightSelected, toast, t, refreshAll]);

  const createPool = useCallback(async () => {
    const title = newPoolTitle.trim();
    if (!title) return;
    const res = await api.callApi("createTaskPool", { params: { pk: workspaceId }, body: { title } });
    if (res?.id) {
      setNewPoolTitle("");
      const rows = await loadPools();
      setSelectedPoolId(res.id);
      toast.show({ message: t("taskpools.created", "Task pool created") });
      void rows;
    } else {
      toast.show({ message: res?.detail ?? t("taskpools.actionFailed", "Action failed"), type: "error" });
    }
  }, [api, workspaceId, newPoolTitle, loadPools, toast, t]);

  const renamePool = useCallback(async () => {
    if (!poolDetail) return;
    const title = window.prompt(t("taskpools.renamePrompt", "New task pool name"), poolDetail.title);
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
    if (!window.confirm(t("taskpools.deleteConfirm", "Delete this task pool?"))) return;
    await api.callApi("deleteTaskPool", { params: { pk: workspaceId, poolPk: poolDetail.id } });
    setSelectedPoolId(null);
    const rows = await loadPools();
    setSelectedPoolId(rows[0]?.id ?? null);
  }, [api, workspaceId, poolDetail, t, loadPools]);

  const poolItems = poolDetail?.items ?? [];

  if (loading) return <div className={root.elem("loading").toClassName()}>…</div>;

  return (
    <div className={root.toClassName()}>
      {/* LEFT: dataset browser */}
      <section className={root.elem("panel").mod({ side: "left" }).toClassName()}>
        <header className={root.elem("panel-head").toClassName()}>
          <div className={root.elem("panel-title").toClassName()}>
            <strong>
              {t("taskpools.datasetItems", "Dataset items")}
              {leftSelected.size > 0 && (
                <span className={root.elem("selected-count").toClassName()}> ({leftSelected.size})</span>
              )}
            </strong>
            <Button size="smaller" look="string" onClick={toggleSelectAll} disabled={selectableIds.length === 0}>
              {allSelected ? t("taskpools.deselectAll", "Deselect all") : t("taskpools.selectAll", "Select all")}
            </Button>
          </div>
          <div className={root.elem("filters").toClassName()}>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              {DATA_TYPES.map((tp) => (
                <option key={tp || "all"} value={tp}>
                  {tp || t("taskpools.allTypes", "All types")}
                </option>
              ))}
            </select>
            <input
              placeholder={t("taskpools.search", "Search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </header>
        <ul className={root.elem("items").toClassName()}>
          {items.map((it) => {
            const preview = itemPreview(it);
            const disabled = it.included;
            return (
              <li
                key={it.id}
                className={root
                  .elem("item")
                  .mod({ included: it.included, selected: leftSelected.has(it.id) })
                  .toClassName()}
              >
                <input
                  type="checkbox"
                  disabled={disabled}
                  checked={leftSelected.has(it.id)}
                  onChange={() => toggleLeft(it.id)}
                />
                <span className={root.elem("thumb").toClassName()}>
                  {preview && /\.(png|jpe?g|gif|webp|svg)(\?|$)/i.test(preview) ? (
                    <img src={preview} alt="" />
                  ) : (
                    <span className={root.elem("thumb-type").toClassName()}>{it.data_type}</span>
                  )}
                </span>
                <span className={root.elem("item-meta").toClassName()}>
                  <span className={root.elem("item-id").toClassName()}>#{it.id}</span>
                  <span className={root.elem("item-text").toClassName()}>{preview}</span>
                </span>
                {it.included && (
                  <span className={root.elem("badge").toClassName()}>{t("taskpools.included", "Included")}</span>
                )}
              </li>
            );
          })}
          {items.length === 0 && (
            <li className={root.elem("muted").toClassName()}>{t("taskpools.noItems", "No items")}</li>
          )}
        </ul>
      </section>

      {/* CENTER: arrows */}
      <div className={root.elem("controls").toClassName()}>
        <Button size="small" onClick={addItems} disabled={!selectedPoolId || leftSelected.size === 0} aria-label="add">
          →
        </Button>
        <Button
          size="small"
          look="outlined"
          onClick={removeItems}
          disabled={!selectedPoolId || rightSelected.size === 0}
          aria-label="remove"
        >
          ←
        </Button>
      </div>

      {/* RIGHT: task pool manager */}
      <section className={root.elem("panel").mod({ side: "right" }).toClassName()}>
        <header className={root.elem("panel-head").toClassName()}>
          <select
            value={selectedPoolId ?? ""}
            onChange={(e) => setSelectedPoolId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("taskpools.selectPool", "Select a task pool")}</option>
            {pools.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title} ({p.item_count})
              </option>
            ))}
          </select>
          {poolDetail && (
            <div className={root.elem("pool-actions").toClassName()}>
              <Button size="smaller" look="string" onClick={renamePool}>
                {t("taskpools.rename", "Rename")}
              </Button>
              <Button size="smaller" look="string" variant="negative" onClick={deletePool}>
                {t("common.delete", "Delete")}
              </Button>
            </div>
          )}
        </header>

        <div className={root.elem("create").toClassName()}>
          <input
            placeholder={t("taskpools.newPoolTitle", "New task pool name")}
            value={newPoolTitle}
            onChange={(e) => setNewPoolTitle(e.target.value)}
          />
          <Button size="small" onClick={createPool} disabled={!newPoolTitle.trim()}>
            {t("taskpools.create", "Create")}
          </Button>
        </div>

        {poolDetail && (
          <>
            <div className={root.elem("count").toClassName()}>
              {t("taskpools.itemCount", "{{count}} items", { count: poolDetail.item_count ?? poolItems.length })}
            </div>
            <ul className={root.elem("items").toClassName()}>
              {poolItems.map((it) => (
                <li
                  key={it.id}
                  className={root
                    .elem("item")
                    .mod({ selected: rightSelected.has(it.id) })
                    .toClassName()}
                >
                  <input type="checkbox" checked={rightSelected.has(it.id)} onChange={() => toggleRight(it.id)} />
                  <span className={root.elem("item-meta").toClassName()}>
                    <span className={root.elem("item-id").toClassName()}>#{it.id}</span>
                    <span className={root.elem("item-text").toClassName()}>{itemPreview(it)}</span>
                  </span>
                </li>
              ))}
              {poolItems.length === 0 && (
                <li className={root.elem("muted").toClassName()}>{t("taskpools.empty", "No items in this pool")}</li>
              )}
            </ul>
          </>
        )}
      </section>
    </div>
  );
};
