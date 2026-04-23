import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@humansignal/ui";
import { Modal } from "../../components/Modal/ModalPopup";
import { Input, TextArea } from "../../components/Form";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";

export const CreateWorkspace = ({ opened, onClose, onCreated }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const reset = useCallback(() => {
    setTitle("");
    setDescription("");
    setSubmitting(false);
  }, []);

  const handleSubmit = useCallback(
    async (event) => {
      event.preventDefault();
      if (!title.trim()) return;

      setSubmitting(true);
      const response = await api.callApi("createWorkspace", {
        body: { title: title.trim(), description },
      });
      setSubmitting(false);

      if (response && response.id) {
        toast.show({ message: t("workspaces.toast.created", { title: response.title }) });
        reset();
        onCreated?.(response);
      }
    },
    [api, title, description, toast, t, reset, onCreated],
  );

  return (
    <Modal
      title={t("workspaces.create.title")}
      opened={opened}
      onHide={() => {
        reset();
        onClose?.();
      }}
      bareFooter
      style={{ width: 480 }}
      body={
        <form className={cn("workspace-create-form").toClassName()} onSubmit={handleSubmit}>
          <Input
            name="title"
            label={t("workspaces.fields.title")}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            minLength={3}
            maxLength={256}
            autoFocus
          />
          <TextArea
            name="description"
            label={t("workspaces.fields.description")}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={{ minHeight: 96 }}
          />
          <div className={cn("workspace-create-form").elem("actions").toClassName()}>
            <Button
              type="button"
              look="outlined"
              onClick={() => {
                reset();
                onClose?.();
              }}
              aria-label={t("common.cancel")}
            >
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={!title.trim() || submitting} aria-label={t("workspaces.create.submit")}>
              {submitting ? t("common.loading") : t("workspaces.create.submit")}
            </Button>
          </div>
        </form>
      }
    />
  );
};
