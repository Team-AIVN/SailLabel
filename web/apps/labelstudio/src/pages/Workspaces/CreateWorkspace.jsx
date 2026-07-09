import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@humansignal/ui";
import { ToggleItems } from "../../components";
import { Modal } from "../../components/Modal/Modal";
import { Space } from "../../components/Space/Space";
import { Input, TextArea } from "../../components/Form";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import { WorkspaceImportPage } from "./WorkspaceImport";
import { useDraftWorkspace } from "./useDraftWorkspace";
import { useWorkspaceImport } from "./useWorkspaceImport";
import "./CreateWorkspace.prefix.css";

const WorkspaceName = ({ title, setTitle, description, setDescription, show, error }) => {
  const { t } = useTranslation();
  if (!show) return null;
  return (
    <form className={cn("workspace-name").toClassName()} onSubmit={(event) => event.preventDefault()}>
      <div className="w-full flex flex-col gap-2">
        <label className="w-full" htmlFor="workspace_name">
          {t("workspaces.fields.title")}
        </label>
        <Input
          name="title"
          id="workspace_name"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          className="workspace-title w-full"
          minLength={3}
          maxLength={256}
          autoFocus
          required
        />
        {error && <span className="-mt-1 text-negative-content">{error}</span>}
      </div>
      <div className="w-full flex flex-col gap-2">
        <label className="w-full" htmlFor="workspace_description">
          {t("workspaces.fields.description")}
        </label>
        <TextArea
          name="description"
          id="workspace_description"
          rows="4"
          style={{ minHeight: 100 }}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className="workspace-description w-full"
        />
      </div>
    </form>
  );
};

export const CreateWorkspace = ({ opened, onClose, onCreated }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();

  const [step, setStep] = useState("name");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState(null);
  const [waiting, setWaiting] = useState(false);

  // Clear a previous save error when the title changes, so a failed attempt (e.g. a
  // duplicate-name 400) doesn't leave the Save button permanently disabled.
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset only when title changes
  useEffect(() => {
    if (error) setError(null);
  }, [title]);

  const { workspace, setWorkspace } = useDraftWorkspace(opened);
  const { uploading, fileIds, pageProps } = useWorkspaceImport();

  const rootClass = cn("create-workspace");
  const tabClass = rootClass.elem("tab");

  const trimmedTitle = title.trim();
  const titleInvalid = trimmedTitle.length < 3;

  const steps = useMemo(
    () => ({
      name: (
        <span className={tabClass.mod({ disabled: titleInvalid || !!error }).toClassName()}>
          {t("workspaces.steps.name")}
        </span>
      ),
      import: t("workspaces.steps.import"),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [titleInvalid, error, t],
  );

  const resetAndClose = useCallback(() => {
    setTitle("");
    setDescription("");
    setError(null);
    setStep("name");
    setWorkspace(null);
    onClose?.();
  }, [onClose, setWorkspace]);

  const onCancel = useCallback(async () => {
    if (workspace?.id) {
      setWaiting(true);
      await api.callApi("deleteWorkspace", {
        params: { pk: workspace.id },
        suppressError: true,
      });
      setWaiting(false);
    }
    resetAndClose();
  }, [api, workspace?.id, resetAndClose]);

  const onCreate = useCallback(async () => {
    if (titleInvalid) {
      setError(t("workspaces.create.titleTooShort", "Title must be at least 3 characters"));
      setStep("name");
      return;
    }
    if (!workspace?.id) {
      setError(t("workspaces.create.failed", "Failed to create workspace"));
      return;
    }

    setWaiting(true);
    const response = await api.callApi("updateWorkspace", {
      params: { pk: workspace.id },
      body: { title: trimmedTitle, description },
    });
    setWaiting(false);

    if (!response || !response.id) {
      const detail = response?.response?.detail ?? response?.detail;
      setError(detail ?? t("workspaces.create.failed", "Failed to create workspace"));
      return;
    }

    if (fileIds.length > 0) {
      toast.show({
        message: t("workspaces.toast.importBound", 'Workspace "{{title}}" created with {{count}} file(s).', {
          title: response.title,
          count: fileIds.length,
        }),
      });
    } else {
      toast.show({ message: t("workspaces.toast.created", { title: response.title }) });
    }

    onCreated?.(response);
    // Skip delete — workspace is kept.
    setTitle("");
    setDescription("");
    setError(null);
    setStep("name");
    setWorkspace(null);
    onClose?.();
  }, [
    titleInvalid,
    trimmedTitle,
    description,
    workspace?.id,
    fileIds.length,
    api,
    toast,
    t,
    onCreated,
    onClose,
    setWorkspace,
  ]);

  if (!opened) return null;

  return (
    <Modal onHide={onCancel} closeOnClickOutside={false} allowToInterceptEscape fullscreen visible bare>
      <div className={rootClass.toClassName()}>
        <Modal.Header>
          <h1>{t("workspaces.create.title")}</h1>
          <ToggleItems items={steps} active={step} onSelect={setStep} />

          <Space>
            <Button
              variant="negative"
              look="outlined"
              onClick={onCancel}
              waiting={waiting}
              aria-label={t("common.cancel")}
            >
              {t("common.cancel")}
            </Button>
            <Button
              look="primary"
              onClick={onCreate}
              waiting={waiting || uploading}
              waitingClickable={false}
              disabled={!workspace || titleInvalid || !!error}
              aria-label={t("workspaces.create.submit")}
            >
              {t("workspaces.create.submit")}
            </Button>
          </Space>
        </Modal.Header>
        <WorkspaceName
          title={title}
          setTitle={setTitle}
          description={description}
          setDescription={setDescription}
          show={step === "name"}
          error={error}
        />
        <WorkspaceImportPage workspace={workspace} show={step === "import"} {...pageProps} />
      </div>
    </Modal>
  );
};
