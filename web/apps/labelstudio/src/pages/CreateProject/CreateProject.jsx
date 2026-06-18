import { Select, Typography } from "@humansignal/ui";
import React from "react";
import { useTranslation } from "react-i18next";
import { useHistory } from "react-router";
import { ToggleItems } from "../../components";
import { Button } from "@humansignal/ui";
import { Modal } from "../../components/Modal/Modal";
import { Space } from "../../components/Space/Space";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import { ConfigPage } from "./Config/Config";
import "./CreateProject.prefix.css";
import { useDraftProject } from "./utils/useDraftProject";
import { Input, TextArea } from "../../components/Form";
import { FF_WORKSPACE, isFF } from "../../utils/feature-flags";

const ProjectName = ({
  name,
  setName,
  onSaveName,
  onSubmit,
  error,
  description,
  setDescription,
  workspaces = [],
  workspace,
  setWorkspace,
  show = true,
}) => {
  const { t } = useTranslation();
  if (!show) return null;
  return (
    <form
      className={cn("project-name").toClassName()}
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="w-full flex flex-col gap-2">
        <label className="w-full" htmlFor="project_name">
          {t("createProject.name.projectName")}
        </label>
        <Input
          name="name"
          id="project_name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={onSaveName}
          className="project-title w-full"
        />
        {error && <span className="-mt-1 text-negative-content">{error}</span>}
      </div>
      <div className="w-full flex flex-col gap-2">
        <label className="w-full" htmlFor="project_description">
          {t("createProject.name.description")}
        </label>
        <TextArea
          name="description"
          id="project_description"
          placeholder={t("createProject.name.descriptionPlaceholder")}
          rows="4"
          style={{ minHeight: 100 }}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="project-description w-full"
        />
      </div>
      {isFF(FF_WORKSPACE) && (
        <div className="w-full flex flex-col gap-2">
          <label className="w-full" htmlFor="project_workspace">
            {t("createProject.name.workspace")}
          </label>
          <Select
            placeholder={t("createProject.name.workspacePlaceholder")}
            value={workspace ?? null}
            onChange={setWorkspace}
            options={workspaces.map((w) => ({ label: w.title, value: w.id }))}
            triggerClassName="!flex-1"
          />
          <Typography size="small" className="mt-tight mb-wider">
            {t("createProject.name.workspaceHint")}
          </Typography>
        </div>
      )}
    </form>
  );
};

export const CreateProject = ({ onClose }) => {
  const { t } = useTranslation();
  const [step, _setStep] = React.useState("name"); // name | import | config
  const [waiting, setWaitingStatus] = React.useState(false);

  const { project, setProject: updateProject } = useDraftProject();
  const history = useHistory();
  const api = useAPI();

  const [name, setName] = React.useState("");
  const [error, setError] = React.useState();
  const [description, setDescription] = React.useState("");
  const [workspace, setWorkspace] = React.useState(null);
  const [workspaces, setWorkspaces] = React.useState([]);

  // Load the org's workspaces so the project can be created inside one.
  React.useEffect(() => {
    if (!isFF(FF_WORKSPACE)) return;
    (async () => {
      const data = await api.callApi("workspaces");
      setWorkspaces(Array.isArray(data) ? data : (data?.results ?? []));
    })();
  }, [api]);

  const setStep = React.useCallback((step) => {
    _setStep(step);
    const eventNameMap = {
      name: "project_name",
      import: "data_import",
      config: "labeling_setup",
    };
    __lsa(`create_project.tab.${eventNameMap[step]}`);
  }, []);

  React.useEffect(() => {
    setError(null);
  }, [name]);

  const rootClass = cn("create-project");
  const tabClass = rootClass.elem("tab");
  const steps = {
    name: <span className={tabClass.mod({ disabled: !!error }).toClassName()}>{t("createProject.steps.name")}</span>,
    config: t("createProject.steps.config"),
  };

  // name intentionally skipped from deps:
  // this should trigger only once when we got project loaded
  React.useEffect(() => {
    project && !name && setName(project.title);
  }, [project]);

  const projectBody = React.useMemo(
    () => ({
      title: name,
      description,
      label_config: project?.label_config ?? "<View></View>",
      workspace: workspace ?? null,
    }),
    [name, description, project?.label_config, workspace],
  );

  const onCreate = React.useCallback(async () => {
    setWaitingStatus(true);
    const response = await api.callApi("updateProject", {
      params: {
        pk: project.id,
      },
      body: { ...projectBody, is_draft: false },
    });
    setWaitingStatus(false);

    if (response === null) return;

    __lsa("create_project.create");

    history.push(`/projects/${response.id}/data`);
  }, [project, projectBody]);

  const onSaveName = async () => {
    if (error) return;
    const res = await api.callApi("updateProjectRaw", {
      params: {
        pk: project.id,
      },
      body: {
        title: name,
      },
    });

    if (res.ok) return;
    const err = await res.json();

    setError(err.validation_errors?.title);
  };

  const onDelete = React.useCallback(() => {
    const performClose = async () => {
      setWaitingStatus(true);
      if (project)
        await api.callApi("deleteProject", {
          params: {
            pk: project.id,
          },
        });
      setWaitingStatus(false);
      updateProject(null);
      onClose?.();
    };
    performClose();
  }, [project]);

  return (
    <Modal onHide={onDelete} closeOnClickOutside={false} allowToInterceptEscape fullscreen visible bare>
      <div className={rootClass}>
        <Modal.Header>
          <h1>{t("createProject.title")}</h1>
          <ToggleItems items={steps} active={step} onSelect={setStep} />

          <Space>
            <Button
              variant="negative"
              look="outlined"
              onClick={onDelete}
              waiting={waiting}
              aria-label={t("createProject.cancelAriaLabel")}
            >
              {t("common.cancel")}
            </Button>
            <Button
              look="primary"
              onClick={onCreate}
              waiting={waiting}
              waitingClickable={false}
              disabled={!project || error}
            >
              {t("common.save")}
            </Button>
          </Space>
        </Modal.Header>
        <ProjectName
          name={name}
          setName={setName}
          error={error}
          onSaveName={onSaveName}
          onSubmit={onCreate}
          description={description}
          setDescription={setDescription}
          workspaces={workspaces}
          workspace={workspace}
          setWorkspace={setWorkspace}
          show={step === "name"}
        />
        <ConfigPage
          project={project}
          onUpdate={(config) => {
            updateProject({ ...project, label_config: config });
          }}
          show={step === "config"}
          columns={[]}
          disableSaveButton={true}
        />
      </div>
    </Modal>
  );
};
