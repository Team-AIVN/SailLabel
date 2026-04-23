import { SimpleCard, Spinner, Typography } from "@humansignal/ui";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useAPI } from "../../providers/ApiProvider";

type Completion = { total: number; finished: number; percent: number };

type SuperAdminSummary = {
  organization_count: number;
  workspace_count: number;
  user_count: number;
  project_count: number;
  completion: Completion;
};

type WorkspaceBlock = {
  workspace_id: number;
  title: string;
  project_count: number;
  completion: Completion;
};

type WorkerProgress = { user_id: number; accepted: number };

type EstimatedSettlement = {
  currency: string;
  label_amount: string;
  review_amount: string;
  total_amount: string;
  accepted_count: number;
  review_count: number;
} | null;

type ProjectBlock = {
  project_id: number;
  title: string;
  type: string;
  total: number;
  finished: number;
  percent: number;
  worker_progress: WorkerProgress[];
  estimated_settlement: EstimatedSettlement;
};

type RejectedTask = {
  annotation_id: number;
  task_id: number;
  project_id: number;
  rejected_at: string;
};

type AnnotatorSummary = {
  today_assigned: number;
  rejected_open: number;
  rejected_tasks: RejectedTask[];
  deadlines: Array<{ project_id: number; title: string; due_at: string }>;
};

type ReviewerDecision = {
  annotation_id: number;
  project_id: number;
  state: string;
  transition: string;
  reviewed_at: string;
};

type ReviewerSummary = {
  pending_review: number;
  recent_decisions: ReviewerDecision[];
};

type DashboardPayload = {
  roles: string[];
  organization_id: number | null;
  summary: {
    super_admin?: SuperAdminSummary;
    workspace_manager?: { workspaces: WorkspaceBlock[] };
    project_manager?: { projects: ProjectBlock[] };
    annotator?: AnnotatorSummary;
    reviewer?: ReviewerSummary;
  };
  generated_at: string;
};

function formatAmount(raw: string, currency: string): string {
  const value = Number.parseFloat(raw);
  if (Number.isNaN(value)) return `${raw} ${currency}`;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: currency === "KRW" || currency === "JPY" ? 0 : 2,
    }).format(value);
  } catch {
    return `${value.toLocaleString()} ${currency}`;
  }
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-1 p-3 rounded-md bg-neutral-surface">
      <span className="text-sm text-neutral-content-subtler">{label}</span>
      <span className="text-2xl font-semibold text-neutral-content">{value}</span>
    </div>
  );
}

function ProgressBar({ percent }: { percent: number }) {
  return (
    <div className="w-full h-2 bg-neutral-surface rounded-full overflow-hidden">
      <div
        className="h-full bg-positive-surface-hover"
        style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
      />
    </div>
  );
}

function SuperAdminCard({ data }: { data: SuperAdminSummary }) {
  const { t } = useTranslation();
  return (
    <SimpleCard title={t("dashboard.superAdmin.heading")}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Metric label={t("dashboard.superAdmin.workspaces")} value={data.workspace_count} />
        <Metric label={t("dashboard.superAdmin.users")} value={data.user_count} />
        <Metric label={t("dashboard.superAdmin.projects")} value={data.project_count} />
        <Metric
          label={t("dashboard.superAdmin.completion")}
          value={`${data.completion.percent}%`}
        />
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-sm text-neutral-content-subtler">
          {t("home.tasksProgress", {
            finished: data.completion.finished,
            total: data.completion.total,
            percent: data.completion.percent,
          })}
        </span>
        <ProgressBar percent={data.completion.percent} />
      </div>
    </SimpleCard>
  );
}

function WorkspaceManagerCard({ blocks }: { blocks: WorkspaceBlock[] }) {
  const { t } = useTranslation();
  if (blocks.length === 0) {
    return (
      <SimpleCard title={t("dashboard.workspaceManager.heading")}>
        <div className="text-neutral-content-subtler text-sm">
          {t("dashboard.workspaceManager.empty")}
        </div>
      </SimpleCard>
    );
  }
  return (
    <SimpleCard title={t("dashboard.workspaceManager.heading")}>
      <div className="flex flex-col gap-3">
        {blocks.map((ws) => (
          <div key={ws.workspace_id} className="flex flex-col gap-1 p-3 rounded-md bg-neutral-surface">
            <div className="flex justify-between">
              <span className="font-medium text-neutral-content">{ws.title}</span>
              <span className="text-sm text-neutral-content-subtler">
                {t("dashboard.workspaceManager.projectCount", { count: ws.project_count })}
              </span>
            </div>
            <div className="text-xs text-neutral-content-subtler">
              {t("home.tasksProgress", {
                finished: ws.completion.finished,
                total: ws.completion.total,
                percent: ws.completion.percent,
              })}
            </div>
            <ProgressBar percent={ws.completion.percent} />
          </div>
        ))}
      </div>
    </SimpleCard>
  );
}

function ProjectManagerCard({ projects }: { projects: ProjectBlock[] }) {
  const { t } = useTranslation();
  if (projects.length === 0) {
    return (
      <SimpleCard title={t("dashboard.projectManager.heading")}>
        <div className="text-neutral-content-subtler text-sm">
          {t("dashboard.projectManager.empty")}
        </div>
      </SimpleCard>
    );
  }
  return (
    <SimpleCard title={t("dashboard.projectManager.heading")}>
      <div className="flex flex-col gap-4">
        {projects.map((p) => (
          <div
            key={p.project_id}
            className="flex flex-col gap-3 p-3 rounded-md border border-neutral-border-subtle"
          >
            <div className="flex justify-between items-center">
              <a
                href={`/projects/${p.project_id}`}
                className="font-medium text-neutral-content hover:underline"
              >
                {p.title || `Project #${p.project_id}`}
              </a>
              <span className="text-sm text-neutral-content-subtler">
                {t("home.tasksProgress", {
                  finished: p.finished,
                  total: p.total,
                  percent: p.percent,
                })}
              </span>
            </div>
            <ProgressBar percent={p.percent} />
            <div>
              <div className="text-xs text-neutral-content-subtler mb-1">
                {t("dashboard.projectManager.workerProgress")}
              </div>
              {p.worker_progress.length === 0 ? (
                <div className="text-xs text-neutral-content-subtler">
                  {t("dashboard.projectManager.workerRowEmpty")}
                </div>
              ) : (
                <ul className="flex flex-col gap-1">
                  {p.worker_progress.slice(0, 6).map((w) => (
                    <li key={w.user_id} className="flex justify-between text-sm">
                      <span className="text-neutral-content">#{w.user_id}</span>
                      <span className="text-neutral-content-subtler">
                        {t("dashboard.projectManager.workerAccepted", { count: w.accepted })}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <div className="text-xs text-neutral-content-subtler mb-1">
                {t("dashboard.projectManager.estimatedSettlement")}
              </div>
              {p.estimated_settlement ? (
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <div className="text-neutral-content-subtler">
                      {t("dashboard.projectManager.labelAmount")}
                    </div>
                    <div className="text-neutral-content">
                      {formatAmount(
                        p.estimated_settlement.label_amount,
                        p.estimated_settlement.currency,
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="text-neutral-content-subtler">
                      {t("dashboard.projectManager.reviewAmount")}
                    </div>
                    <div className="text-neutral-content">
                      {formatAmount(
                        p.estimated_settlement.review_amount,
                        p.estimated_settlement.currency,
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="text-neutral-content-subtler">
                      {t("dashboard.projectManager.total")}
                    </div>
                    <div className="font-semibold text-neutral-content">
                      {formatAmount(
                        p.estimated_settlement.total_amount,
                        p.estimated_settlement.currency,
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-neutral-content-subtler">
                  {t("dashboard.projectManager.pricingMissing")}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </SimpleCard>
  );
}

function AnnotatorCard({ data }: { data: AnnotatorSummary }) {
  const { t } = useTranslation();
  return (
    <SimpleCard title={t("dashboard.annotator.heading")}>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <Metric label={t("dashboard.annotator.todayAssigned")} value={data.today_assigned} />
        <Metric label={t("dashboard.annotator.rejectedOpen")} value={data.rejected_open} />
      </div>
      <div className="mb-3">
        <div className="text-xs text-neutral-content-subtler mb-1">
          {t("dashboard.annotator.rejectedTitle")}
        </div>
        {data.rejected_tasks.length === 0 ? (
          <div className="text-xs text-neutral-content-subtler">
            {t("dashboard.annotator.rejectedEmpty")}
          </div>
        ) : (
          <ul className="flex flex-col gap-1">
            {data.rejected_tasks.slice(0, 8).map((r) => (
              <li key={r.annotation_id} className="text-sm">
                <a
                  href={`/projects/${r.project_id}/data?task=${r.task_id}`}
                  className="text-neutral-content hover:underline"
                >
                  {t("dashboard.annotator.rejectedRow", {
                    projectId: r.project_id,
                    taskId: r.task_id,
                  })}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <div className="text-xs text-neutral-content-subtler mb-1">
          {t("dashboard.annotator.deadlines")}
        </div>
        <div className="text-xs text-neutral-content-subtler">
          {t("dashboard.annotator.deadlinesEmpty")}
        </div>
      </div>
    </SimpleCard>
  );
}

function ReviewerCard({ data }: { data: ReviewerSummary }) {
  const { t } = useTranslation();
  return (
    <SimpleCard title={t("dashboard.reviewer.heading")}>
      <div className="grid grid-cols-1 gap-3 mb-4">
        <Metric label={t("dashboard.reviewer.pendingReview")} value={data.pending_review} />
      </div>
      <div>
        <div className="text-xs text-neutral-content-subtler mb-1">
          {t("dashboard.reviewer.recentHeading")}
        </div>
        {data.recent_decisions.length === 0 ? (
          <div className="text-xs text-neutral-content-subtler">
            {t("dashboard.reviewer.recentEmpty")}
          </div>
        ) : (
          <ul className="flex flex-col gap-1">
            {data.recent_decisions.slice(0, 8).map((d) => (
              <li key={d.annotation_id} className="flex justify-between text-sm">
                <a
                  href={`/projects/${d.project_id}`}
                  className="text-neutral-content hover:underline"
                >
                  {t("dashboard.reviewer.decisionRow", {
                    projectId: d.project_id,
                    annotationId: d.annotation_id,
                  })}
                </a>
                <span className="text-neutral-content-subtler">
                  {t(`dashboard.reviewer.transitions.${d.transition}`, d.transition)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SimpleCard>
  );
}

export function DashboardWidgets() {
  const { t } = useTranslation();
  const api = useAPI();

  const { data, isFetching, isError } = useQuery<DashboardPayload>({
    queryKey: ["dashboard-summary"],
    async queryFn() {
      const response = await api.callApi<DashboardPayload>("dashboardSummary");
      return response as DashboardPayload;
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  if (isFetching && !data) {
    return (
      <SimpleCard>
        <div className="h-32 flex justify-center items-center">
          <Spinner />
        </div>
      </SimpleCard>
    );
  }
  if (isError || !data) {
    return (
      <SimpleCard>
        <div className="h-32 flex justify-center items-center text-neutral-content-subtler">
          {t("dashboard.loadError")}
        </div>
      </SimpleCard>
    );
  }

  const { summary } = data;
  const hasAny =
    summary.super_admin ||
    summary.workspace_manager?.workspaces?.length ||
    summary.project_manager?.projects?.length ||
    summary.annotator ||
    summary.reviewer;

  if (!hasAny) {
    return (
      <SimpleCard title={t("dashboard.empty.title")}>
        <div className="text-sm text-neutral-content-subtler">
          {t("dashboard.empty.description")}
        </div>
      </SimpleCard>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between">
        <Typography variant="headline" size="small">
          {t("dashboard.pageTitle")}
        </Typography>
        <span className="text-xs text-neutral-content-subtler">
          {t("dashboard.generatedAt", {
            timestamp: new Date(data.generated_at).toLocaleString(),
          })}
        </span>
      </div>
      {summary.super_admin ? <SuperAdminCard data={summary.super_admin} /> : null}
      {summary.workspace_manager ? (
        <WorkspaceManagerCard blocks={summary.workspace_manager.workspaces} />
      ) : null}
      {summary.project_manager ? (
        <ProjectManagerCard projects={summary.project_manager.projects} />
      ) : null}
      {summary.annotator ? <AnnotatorCard data={summary.annotator} /> : null}
      {summary.reviewer ? <ReviewerCard data={summary.reviewer} /> : null}
    </div>
  );
}
