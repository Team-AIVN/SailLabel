import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./WorkPools.prefix.css";

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

/** Two-panel Work Pool manager: dataset items (left) <-> work pool items (right). */
export const WorkPools = ({ workspaceId }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("work-pools"), []);

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
    const res = await api.callApi("workPools", { params: { pk: workspaceId } });
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
      const res = await api.callApi("workPool", { params: { pk: workspaceId, poolPk: poolId } });
      setPoolDetail(res && !res.error ? res : null);
    },
    [api, workspaceId],
  );

  const loadItems = useCallback(async () => {
    const params = { pk: workspaceId };
    if (typeFilter) params.data_type = typeFilter;
    if (search) params.search = search;
    if (selectedPoolId) params.work_pool = selectedPoolId;
    const res = await api.callApi("workspaceDatasetItems", { params });
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

  const refreshAll = useCallback(async () => {
    await Promise.all([loadItems(), loadPoolDetail(selectedPoolId), loadPools()]);
    setLeftSelected(new Set());
    setRightSelected(new Set());
  }, [loadItems, loadPoolDetail, loadPools, selectedPoolId]);

  const addItems = useCallback(async () => {
    if (!selectedPoolId || leftSelected.size === 0) return;
    const res = await api.callApi("addWorkPoolItems", {
      params: { pk: workspaceId, poolPk: selectedPoolId },
      body: { dataset_item_ids: Array.from(leftSelected) },
    });
    if (res && !res.error) {
      toast.show({ message: t("workpools.added", "Items added") });
      refreshAll();
    } else {
      toast.show({ message: res?.detail ?? t("workpools.actionFailed", "Action failed"), type: "error" });
    }
  }, [api, workspaceId, selectedPoolId, leftSelected, toast, t, refreshAll]);

  const removeItems = useCallback(async () => {
    if (!selectedPoolId || rightSelected.size === 0) return;
    const res = await api.callApi("removeWorkPoolItems", {
      params: { pk: workspaceId, poolPk: selectedPoolId },
      body: { dataset_item_ids: Array.from(rightSelected) },
    });
    if (res && !res.error) {
      toast.show({ message: t("workpools.removed", "Items removed") });
      refreshAll();
    }
  }, [api, workspaceId, selectedPoolId, rightSelected, toast, t, refreshAll]);

  const createPool = useCallback(async () => {
    const title = newPoolTitle.trim();
    if (!title) return;
    const res = await api.callApi("createWorkPool", { params: { pk: workspaceId }, body: { title } });
    if (res?.id) {
      setNewPoolTitle("");
      const rows = await loadPools();
      setSelectedPoolId(res.id);
      toast.show({ message: t("workpools.created", "Work pool created") });
      void rows;
    } else {
      toast.show({ message: res?.detail ?? t("workpools.actionFailed", "Action failed"), type: "error" });
    }
  }, [api, workspaceId, newPoolTitle, loadPools, toast, t]);

  const renamePool = useCallback(async () => {
    if (!poolDetail) return;
    const title = window.prompt(t("workpools.renamePrompt", "New work pool name"), poolDetail.title);
    if (!title || !title.trim()) return;
    const res = await api.callApi("updateWorkPool", {
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
    if (!window.confirm(t("workpools.deleteConfirm", "Delete this work pool?"))) return;
    await api.callApi("deleteWorkPool", { params: { pk: workspaceId, poolPk: poolDetail.id } });
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
          <strong>{t("workpools.datasetItems", "Dataset items")}</strong>
          <div className={root.elem("filters").toClassName()}>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              {DATA_TYPES.map((tp) => (
                <option key={tp || "all"} value={tp}>
                  {tp || t("workpools.allTypes", "All types")}
                </option>
              ))}
            </select>
            <input
              placeholder={t("workpools.search", "Search")}
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
                  <span className={root.elem("badge").toClassName()}>{t("workpools.included", "Included")}</span>
                )}
              </li>
            );
          })}
          {items.length === 0 && (
            <li className={root.elem("muted").toClassName()}>{t("workpools.noItems", "No items")}</li>
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

      {/* RIGHT: work pool manager */}
      <section className={root.elem("panel").mod({ side: "right" }).toClassName()}>
        <header className={root.elem("panel-head").toClassName()}>
          <select
            value={selectedPoolId ?? ""}
            onChange={(e) => setSelectedPoolId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">{t("workpools.selectPool", "Select a work pool")}</option>
            {pools.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title} ({p.item_count})
              </option>
            ))}
          </select>
          {poolDetail && (
            <div className={root.elem("pool-actions").toClassName()}>
              <Button size="smaller" look="string" onClick={renamePool}>
                {t("workpools.rename", "Rename")}
              </Button>
              <Button size="smaller" look="string" variant="negative" onClick={deletePool}>
                {t("common.delete", "Delete")}
              </Button>
            </div>
          )}
        </header>

        <div className={root.elem("create").toClassName()}>
          <input
            placeholder={t("workpools.newPoolTitle", "New work pool name")}
            value={newPoolTitle}
            onChange={(e) => setNewPoolTitle(e.target.value)}
          />
          <Button size="small" onClick={createPool} disabled={!newPoolTitle.trim()}>
            {t("workpools.create", "Create")}
          </Button>
        </div>

        {poolDetail && (
          <>
            <div className={root.elem("count").toClassName()}>
              {t("workpools.itemCount", "{{count}} items", { count: poolDetail.item_count ?? poolItems.length })}
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
                <li className={root.elem("muted").toClassName()}>{t("workpools.empty", "No items in this pool")}</li>
              )}
            </ul>
          </>
        )}
      </section>
    </div>
  );
};
