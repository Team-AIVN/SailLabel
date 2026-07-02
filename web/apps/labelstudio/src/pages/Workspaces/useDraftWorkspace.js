import React from "react";
import { useAPI } from "../../providers/ApiProvider";

export const useDraftWorkspace = (enabled = true) => {
  const api = useAPI();
  const [workspace, setWorkspace] = React.useState(null);
  const fetchedRef = React.useRef(false);

  const fetchDraftWorkspace = React.useCallback(async () => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;

    const listing = await api.callApi("workspaces");
    const existing = Array.isArray(listing) ? listing : (listing?.results ?? []);
    const taken = new Set(existing.map((w) => w?.title).filter(Boolean));

    let n = existing.length + 1;
    let title = `New Workspace #${n}`;
    while (taken.has(title)) {
      n += 1;
      title = `New Workspace #${n}`;
    }

    const draft = await api.callApi("createWorkspace", {
      body: { title, description: "" },
    });

    if (draft?.id) setWorkspace(draft);
  }, [api]);

  React.useEffect(() => {
    if (!enabled) return;
    fetchDraftWorkspace();
  }, [enabled, fetchDraftWorkspace]);

  return { workspace, setWorkspace };
};
