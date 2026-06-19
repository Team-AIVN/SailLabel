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
import { WorkerAssignment } from "./WorkerAssignment";
import { Input, TextArea } from "../../components/Form";
import { FF_WORKSPACE, isFF } from "../../utils/feature-flags";

const CURRENCY_OPTIONS = ["USD", "EUR", "KRW", "JPY"].map((c) => ({ label: c, value: c }));

// Decimal places per currency: KRW/JPY have no minor unit, USD/EUR use 2.
const CURRENCY_DECIMALS = { USD: 2, EUR: 2, KRW: 0, JPY: 0 };

// Input step + placeholder formatted for the currency (e.g. "0" for KRW, "0.00" for USD).
const priceFormat = (currency) => {
  const decimals = CURRENCY_DECIMALS[currency] ?? 2;
  return {
    step: decimals === 0 ? "1" : `0.${"0".repeat(decimals - 1)}1`,
    placeholder: decimals === 0 ? "0" : `0.${"0".repeat(decimals)}`,
  };
};

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
  workspaceLocked = false,
  workPools = [],
  workPool,
  setWorkPool,
  currency,
  setCurrency,
  annotationUnitPrice,
  setAnnotationUnitPrice,
  reviewUnitPrice,
  setReviewUnitPrice,
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
            disabled={workspaceLocked}
            triggerClassName="!flex-1"
          />
          <Typography size="small" className="mt-tight mb-wider">
            {workspaceLocked
              ? t("createProject.name.workspaceLockedHint", "This project will be created in the current workspace.")
              : t("createProject.name.workspaceHint")}
          </Typography>
        </div>
      )}
      {isFF(FF_WORKSPACE) && workspace && (
        <div className="w-full flex flex-col gap-2">
          <label className="w-full" htmlFor="project_work_pool">
            {t("createProject.name.workPool", "Work Pool")}
          </label>
          <Select
            placeholder={t("createProject.name.workPoolPlaceholder", "Select a work pool")}
            value={workPool ?? null}
            onChange={setWorkPool}
            options={workPools.map((p) => ({ label: `${p.title} (${p.item_count})`, value: p.id }))}
            triggerClassName="!flex-1"
          />
          <Typography size="small" className="mt-tight mb-wider">
            {t(
              "createProject.name.workPoolHint",
              "Project tasks are created from the selected work pool. Datasets are managed by workspace admins.",
            )}
          </Typography>
        </div>
      )}
      {isFF(FF_WORKSPACE) && workspace && (
        <div className="w-full flex flex-col gap-2">
          <label className="w-full" htmlFor="project_currency">
            {t("createProject.name.currency", "Currency")}
          </label>
          <Select
            placeholder={t("createProject.name.currencyPlaceholder", "Select a currency")}
            value={currency ?? null}
            onChange={setCurrency}
            options={CURRENCY_OPTIONS}
            triggerClassName="!flex-1"
          />
          <Typography size="small" className="mt-tight mb-wider">
            {t(
              "createProject.name.compensationHint",
              "Workers are paid per qualified annotation and review in this currency.",
            )}
          </Typography>
          <div className="w-full flex gap-4">
            <div className="flex-1 flex flex-col gap-2">
              <label htmlFor="project_annotation_unit_price">
                {t("createProject.name.annotationUnitPrice", "Annotation Unit Price")}
              </label>
              <Input
                name="annotation_unit_price"
                id="project_annotation_unit_price"
                type="number"
                min="0"
                step={priceFormat(currency).step}
                placeholder={priceFormat(currency).placeholder}
                value={annotationUnitPrice}
                onChange={(e) => setAnnotationUnitPrice(e.target.value)}
                className="w-full"
              />
            </div>
            <div className="flex-1 flex flex-col gap-2">
              <label htmlFor="project_review_unit_price">
                {t("createProject.name.reviewUnitPrice", "Review Unit Price")}
              </label>
              <Input
                name="review_unit_price"
                id="project_review_unit_price"
                type="number"
                min="0"
                step={priceFormat(currency).step}
                placeholder={priceFormat(currency).placeholder}
                value={reviewUnitPrice}
                onChange={(e) => setReviewUnitPrice(e.target.value)}
                className="w-full"
              />
            </div>
          </div>
        </div>
      )}
    </form>
  );
};

export const CreateProject = ({ onClose, workspaceId = null }) => {
  const { t, i18n } = useTranslation();
  const [step, _setStep] = React.useState("name"); // name | import | config
  const [waiting, setWaitingStatus] = React.useState(false);

  const { project, setProject: updateProject } = useDraftProject();
  const history = useHistory();
  const api = useAPI();

  const [name, setName] = React.useState("");
  const [error, setError] = React.useState();
  const [description, setDescription] = React.useState("");
  // When opened from a workspace, the workspace is preset and locked.
  const [workspace, setWorkspace] = React.useState(workspaceId);
  const [workspaces, setWorkspaces] = React.useState([]);
  const [workPool, setWorkPool] = React.useState(null);
  const [workPools, setWorkPools] = React.useState([]);
  // Compensation policy (required when the project belongs to a workspace).
  // Default the currency to the UI language: Korean -> KRW, otherwise USD.
  const [currency, setCurrency] = React.useState(() =>
    (i18n.language || "").toLowerCase().startsWith("ko") ? "KRW" : "USD",
  );
  const [annotationUnitPrice, setAnnotationUnitPrice] = React.useState("");
  const [reviewUnitPrice, setReviewUnitPrice] = React.useState("");
  const workspaceLocked = workspaceId != null;

  // Load the org's workspaces so the project can be created inside one.
  React.useEffect(() => {
    if (!isFF(FF_WORKSPACE)) return;
    (async () => {
      const data = await api.callApi("workspaces");
      setWorkspaces(Array.isArray(data) ? data : (data?.results ?? []));
    })();
  }, [api]);

  // Load the chosen workspace's work pools. Projects pick a work pool, not raw datasets.
  React.useEffect(() => {
    if (!isFF(FF_WORKSPACE) || !workspace) {
      setWorkPools([]);
      return;
    }
    (async () => {
      const data = await api.callApi("workPools", { params: { pk: workspace } });
      setWorkPools(Array.isArray(data) ? data : (data?.results ?? []));
    })();
    setWorkPool(null);
  }, [api, workspace]);

  const setStep = React.useCallback((step) => {
    _setStep(step);
    const eventNameMap = {
      name: "project_name",
      assign: "worker_assignment",
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
  // Worker assignment lives between Project Name and Labeling Setup, and only for
  // workspace projects (the left pool is the workspace's members).
  const showAssign = isFF(FF_WORKSPACE) && !!workspace;
  const steps = {
    name: <span className={tabClass.mod({ disabled: !!error }).toClassName()}>{t("createProject.steps.name")}</span>,
    ...(showAssign ? { assign: t("createProject.steps.assign", "Worker Assignment") } : {}),
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
      work_pool: workPool ?? null,
    }),
    [name, description, project?.label_config, workspace, workPool],
  );

  // When a workspace is chosen, a work pool must be selected (no direct dataset access).
  const workPoolRequired = isFF(FF_WORKSPACE) && !!workspace;
  const workPoolMissing = workPoolRequired && !workPool;

  // Compensation must be configured for workspace projects.
  const compensationRequired = isFF(FF_WORKSPACE) && !!workspace;
  const annPriceValid = annotationUnitPrice !== "" && Number.parseFloat(annotationUnitPrice) >= 0;
  const revPriceValid = reviewUnitPrice !== "" && Number.parseFloat(reviewUnitPrice) >= 0;
  const compensationMissing = compensationRequired && (!currency || !annPriceValid || !revPriceValid);

  const onCreate = React.useCallback(async () => {
    setWaitingStatus(true);
    const response = await api.callApi("updateProject", {
      params: {
        pk: project.id,
      },
      body: { ...projectBody, is_draft: false },
    });

    // Persist the compensation policy for workspace projects (separate endpoint).
    if (response !== null && compensationRequired) {
      await api.callApi("setProjectCompensationPolicy", {
        params: { pk: project.id },
        body: {
          currency,
          annotation_unit_price: Number.parseFloat(annotationUnitPrice),
          review_unit_price: Number.parseFloat(reviewUnitPrice),
        },
      });
    }
    setWaitingStatus(false);

    if (response === null) return;

    __lsa("create_project.create");

    history.push(`/projects/${response.id}/data`);
  }, [project, projectBody, compensationRequired, currency, annotationUnitPrice, reviewUnitPrice]);

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
              disabled={!project || error || workPoolMissing || compensationMissing}
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
          workspaceLocked={workspaceLocked}
          workPools={workPools}
          workPool={workPool}
          setWorkPool={setWorkPool}
          currency={currency}
          setCurrency={setCurrency}
          annotationUnitPrice={annotationUnitPrice}
          setAnnotationUnitPrice={setAnnotationUnitPrice}
          reviewUnitPrice={reviewUnitPrice}
          setReviewUnitPrice={setReviewUnitPrice}
          show={step === "name"}
        />
        {showAssign && project?.id && (
          <WorkerAssignment projectId={project.id} workspaceId={workspace} show={step === "assign"} />
        )}
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
