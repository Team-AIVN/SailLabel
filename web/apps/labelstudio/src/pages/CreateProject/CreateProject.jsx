import { EnterpriseBadge, Select, Typography } from "@humansignal/ui";
import React from "react";
import { useTranslation } from "react-i18next";
import { useHistory } from "react-router";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { ToggleItems } from "../../components";
import { Button } from "@humansignal/ui";
import { Modal } from "../../components/Modal/Modal";
import { Space } from "../../components/Space/Space";
import { HeidiTips } from "../../components/HeidiTips/HeidiTips";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import { ConfigPage } from "./Config/Config";
import "./CreateProject.prefix.css";
import { ImportPage } from "./Import/Import";
import { useImportPage } from "./Import/useImportPage";
import { useDraftProject } from "./utils/useDraftProject";
import { Input, TextArea } from "../../components/Form";
import { FF_LSDV_E_297, isFF } from "../../utils/feature-flags";
import { createURL } from "../../components/HeidiTips/utils";
import { MembersPage } from "./Members/Members";
import { SchedulePage } from "./Schedule/Schedule";
import { SettlementPage } from "./Settlement/Settlement";

const ProjectName = ({ name, setName, onSaveName, onSubmit, error, description, setDescription, show = true }) => {
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
      {isFF(FF_LSDV_E_297) && (
        <div className="w-full flex flex-col gap-2">
          <label>
            {t("createProject.name.workspace")}
            <EnterpriseBadge className="ml-tight" />
          </label>
          <Select placeholder={t("createProject.name.workspacePlaceholder")} disabled options={[]} triggerClassName="!flex-1" />
          <Typography size="small" className="mt-tight mb-wider">
            {t("createProject.name.workspaceHint")}{" "}
            <a
              href={createURL(
                "https://docs.humansignal.com/guide/manage_projects#Create-workspaces-to-organize-projects",
                {
                  experiment: "project_creation_dropdown",
                  treatment: "simplify_project_management",
                },
              )}
              target="_blank"
              rel="noreferrer"
              className="underline hover:no-underline"
            >
              {t("common.learnMore")}
            </a>
          </Typography>
          <HeidiTips collection="projectCreation" />
        </div>
      )}
    </form>
  );
};

export const CreateProject = ({ onClose }) => {
  const { t } = useTranslation();
  const [step, _setStep] = React.useState("name"); // name | import | config | members | schedule | settlement
  const [waiting, setWaitingStatus] = React.useState(false);

  const { project, setProject: updateProject } = useDraftProject();
  const history = useHistory();
  const api = useAPI();
  const { user } = useAuth();

  const [name, setName] = React.useState("");
  const [error, setError] = React.useState();
  const [description, setDescription] = React.useState("");
  const [sample, setSample] = React.useState(null);

  const [memberAssignments, setMemberAssignments] = React.useState([]);
  const [schedule, setSchedule] = React.useState({ start_date: "", end_date: "", task_due_hours: "" });
  const [scheduleError, setScheduleError] = React.useState(null);
  const [pricing, setPricing] = React.useState({ currency: "USD", label_price: "", review_price: "" });
  const [settlementError, setSettlementError] = React.useState(null);

  const setStep = React.useCallback((step) => {
    _setStep(step);
    const eventNameMap = {
      name: "project_name",
      import: "data_import",
      config: "labeling_setup",
      members: "members",
      schedule: "schedule",
      settlement: "settlement",
    };
    __lsa(`create_project.tab.${eventNameMap[step]}`);
  }, []);

  React.useEffect(() => {
    setError(null);
  }, [name]);

  React.useEffect(() => {
    if (!schedule.start_date || !schedule.end_date) {
      setScheduleError(null);
      return;
    }
    if (new Date(schedule.end_date) <= new Date(schedule.start_date)) {
      setScheduleError(t("createProject.schedule.invalidRange"));
    } else {
      setScheduleError(null);
    }
  }, [schedule.start_date, schedule.end_date, t]);

  const { columns, uploading, uploadDisabled, finishUpload, pageProps, uploadSample } = useImportPage(project, sample);

  const rootClass = cn("create-project");
  const tabClass = rootClass.elem("tab");
  const steps = {
    name: <span className={tabClass.mod({ disabled: !!error }).toClassName()}>{t("createProject.steps.name")}</span>,
    import: (
      <span className={tabClass.mod({ disabled: uploadDisabled }).toClassName()}>{t("createProject.steps.import")}</span>
    ),
    config: t("createProject.steps.config"),
    members: t("createProject.steps.members"),
    schedule: (
      <span className={tabClass.mod({ disabled: !!scheduleError }).toClassName()}>
        {t("createProject.steps.schedule")}
      </span>
    ),
    settlement: t("createProject.steps.settlement"),
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
    }),
    [name, description, project?.label_config],
  );

  const applyMemberAssignments = React.useCallback(
    async (projectId) => {
      if (!memberAssignments.length) return;
      const failures = [];
      for (const assignment of memberAssignments) {
        const resp = await api.callApi("createProjectMember", {
          params: { pk: projectId },
          body: { user: assignment.user, role: assignment.role },
          suppressError: true,
        });
        if (!resp || resp.error) failures.push(assignment);
      }
      if (failures.length) {
        console.warn("Some project member assignments failed", failures);
      }
    },
    [memberAssignments, api],
  );

  const applyPricing = React.useCallback(
    async (projectId) => {
      const label = pricing.label_price === "" ? null : Number.parseFloat(pricing.label_price);
      const review = pricing.review_price === "" ? null : Number.parseFloat(pricing.review_price);
      if (label === null && review === null) return;
      const body = { currency: pricing.currency || "USD" };
      if (label !== null && !Number.isNaN(label)) body.label_price = label;
      if (review !== null && !Number.isNaN(review)) body.review_price = review;
      const resp = await api.callApi("updateProjectPricing", {
        params: { pk: projectId },
        body,
        suppressError: true,
      });
      if (!resp || resp.error) {
        setSettlementError(t("createProject.settlement.saveError"));
        setStep("settlement");
        return false;
      }
      return true;
    },
    [pricing, api, t, setStep],
  );

  const onCreate = React.useCallback(async () => {
    if (scheduleError) {
      setStep("schedule");
      return;
    }
    // First, persist project with label_config so import/reimport validates against it
    const response = await api.callApi("updateProject", {
      params: {
        pk: project.id,
      },
      body: { ...projectBody, is_draft: false },
    });

    if (response === null) return;

    const imported = await finishUpload();

    if (!imported) return;

    setWaitingStatus(true);

    if (sample) await uploadSample(sample);

    await applyMemberAssignments(response.id);
    await applyPricing(response.id);

    __lsa("create_project.create", { sample: sample?.url });

    setWaitingStatus(false);

    history.push(`/projects/${response.id}/data`);
  }, [project, projectBody, finishUpload, scheduleError, applyMemberAssignments, applyPricing, setStep]);

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
              waiting={waiting || uploading}
              waitingClickable={false}
              disabled={!project || uploadDisabled || error || !!scheduleError}
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
          show={step === "name"}
        />
        <ImportPage
          project={project}
          show={step === "import"}
          sample={sample}
          onSampleDatasetSelect={setSample}
          openLabelingConfig={() => setStep("config")}
          {...pageProps}
        />
        <ConfigPage
          project={project}
          onUpdate={(config) => {
            updateProject({ ...project, label_config: config });
          }}
          show={step === "config"}
          columns={columns}
          disableSaveButton={true}
        />
        <MembersPage
          show={step === "members"}
          assignments={memberAssignments}
          setAssignments={setMemberAssignments}
          organizationId={user?.active_organization}
        />
        <SchedulePage
          show={step === "schedule"}
          schedule={schedule}
          setSchedule={setSchedule}
          error={scheduleError}
        />
        <SettlementPage
          show={step === "settlement"}
          pricing={pricing}
          setPricing={setPricing}
          error={settlementError}
        />
      </div>
    </Modal>
  );
};
