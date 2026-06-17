import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@humansignal/ui";
import { Modal } from "../../components/Modal/Modal";
import { Input, TextArea } from "../../components/Form";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./Workspaces.prefix.css";

/**
 * Build-safe workspace create modal: title + description only.
 * The richer dataset-import step lives behind the workspace import UI
 * (WorkspaceImport) and is wired separately.
 */
export const CreateWorkspace = ({ opened, onClose, onCreated }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const root = cn("workspace-create-form");

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState(null);
  const [waiting, setWaiting] = useState(false);

  const trimmedTitle = title.trim();
  const titleInvalid = trimmedTitle.length < 3;

  const reset = useCallback(() => {
    setTitle("");
    setDescription("");
    setError(null);
    setWaiting(false);
  }, []);

  const close = useCallback(() => {
    reset();
    onClose?.();
  }, [reset, onClose]);

  const onCreate = useCallback(async () => {
    if (titleInvalid) {
      setError(t("workspaces.create.titleTooShort", "Title must be at least 3 characters"));
      return;
    }
    setWaiting(true);
    const response = await api.callApi("createWorkspace", {
      body: { title: trimmedTitle, description },
    });
    setWaiting(false);

    if (!response || !response.id) {
      const detail = response?.response?.detail ?? response?.detail;
      setError(detail ?? t("workspaces.create.failed", "Failed to create workspace"));
      return;
    }

    toast.show({ message: t("workspaces.toast.created", { title: response.title }) });
    onCreated?.(response);
    reset();
  }, [titleInvalid, trimmedTitle, description, api, toast, t, onCreated, reset]);

  if (!opened) return null;

  return (
    <Modal
      visible
      title={t("workspaces.create.title")}
      onHide={close}
      closeOnClickOutside={false}
      style={{ width: 480 }}
    >
      <div className={root.toClassName()}>
        <div className={root.elem("field").toClassName()}>
          <label htmlFor="workspace_title">{t("workspaces.fields.title")}</label>
          <Input
            id="workspace_title"
            name="title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            minLength={3}
            maxLength={256}
            autoFocus
            required
          />
        </div>

        <div className={root.elem("field").toClassName()}>
          <label htmlFor="workspace_description">{t("workspaces.fields.description")}</label>
          <TextArea
            id="workspace_description"
            name="description"
            rows="4"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>

        {error && <span className={root.elem("error").toClassName()}>{error}</span>}

        <div className={root.elem("actions").toClassName()}>
          <Button variant="neutral" look="outlined" onClick={close} aria-label={t("common.cancel")}>
            {t("common.cancel")}
          </Button>
          <Button
            look="primary"
            onClick={onCreate}
            waiting={waiting}
            disabled={titleInvalid}
            aria-label={t("workspaces.create.submit")}
          >
            {t("workspaces.create.submit")}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
