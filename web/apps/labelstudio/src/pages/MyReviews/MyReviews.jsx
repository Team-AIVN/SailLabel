import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useHistory } from "react-router";
import { useUpdatePageTitle } from "@humansignal/core";
import { Button, useToast } from "@humansignal/ui";
import { Spinner } from "../../components/Spinner/Spinner";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import { useReleaseReviewLock } from "./useReleaseReviewLock";
import "./MyReviews.prefix.css";

const parseList = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const STATE_OPTIONS = ["ALL", "ACCEPTED", "REJECTED"];
const ALL_PROJECTS = "ALL";

const formatTimestamp = (iso, locale) => {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString(locale);
  } catch {
    return iso;
  }
};

const buildProjectMap = (projects) => {
  const map = new Map();
  for (const project of projects) {
    if (project?.id != null) map.set(project.id, project);
  }
  return map;
};

export const MyReviewsPage = () => {
  const { t, i18n } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const history = useHistory();

  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [networkState, setNetworkState] = useState("loading");
  const [stateFilter, setStateFilter] = useState("ALL");
  const [projectFilter, setProjectFilter] = useState(ALL_PROJECTS);
  const [nextReviewLoading, setNextReviewLoading] = useState(false);
  const [activeLockAnnotation, setActiveLockAnnotation] = useState(null);

  useUpdatePageTitle(t("myReviews.pageTitle"));
  useReleaseReviewLock(activeLockAnnotation);

  const fetchReviews = useCallback(async () => {
    setNetworkState("loading");
    const params = {};
    if (stateFilter !== "ALL") params.state = stateFilter;
    if (projectFilter !== ALL_PROJECTS) params.project = projectFilter;
    const response = await api.callApi("currentUserReviews", { params });
    setRows(parseList(response));
    setNetworkState("loaded");
  }, [api, stateFilter, projectFilter]);

  const fetchProjects = useCallback(async () => {
    const response = await api.callApi("projects", {
      params: { include: "id,title", page_size: 500 },
    });
    setProjects(parseList(response));
  }, [api]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const projectMap = useMemo(() => buildProjectMap(projects), [projects]);

  const handleReviewNext = useCallback(async () => {
    if (projectFilter === ALL_PROJECTS) {
      toast.show({ message: t("myReviews.reviewNextRequiresProject") });
      return;
    }
    setNextReviewLoading(true);
    const response = await api.callApi("projectNextReview", {
      params: { pk: projectFilter },
      suppressError: true,
    });
    setNextReviewLoading(false);
    if (!response || response.error) {
      toast.show({ message: t("myReviews.reviewNextEmpty") });
      return;
    }
    const taskId = response.task?.id;
    const annotationId = response.annotation?.id;
    if (!taskId) {
      toast.show({ message: t("myReviews.reviewNextEmpty") });
      return;
    }
    setActiveLockAnnotation(annotationId ?? null);
    const search = new URLSearchParams();
    search.set("task", String(taskId));
    if (annotationId) search.set("annotation", String(annotationId));
    history.push(`/projects/${projectFilter}/data?${search.toString()}`);
  }, [api, history, projectFilter, t, toast]);

  const root = useMemo(() => cn("my-reviews-page"), []);
  const isEmpty = networkState === "loaded" && rows.length === 0;

  return (
    <div className={root.toClassName()}>
      <div className={root.elem("toolbar").toClassName()}>
        <label className={root.elem("filter").toClassName()}>
          <span>{t("myReviews.filter.state")}</span>
          <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}>
            {STATE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(`myReviews.states.${option.toLowerCase()}`)}
              </option>
            ))}
          </select>
        </label>

        <label className={root.elem("filter").toClassName()}>
          <span>{t("myReviews.filter.project")}</span>
          <select value={projectFilter} onChange={(event) => setProjectFilter(event.target.value)}>
            <option value={ALL_PROJECTS}>{t("myReviews.filter.allProjects")}</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.title || `#${project.id}`}
              </option>
            ))}
          </select>
        </label>

        <div className={root.elem("actions").toClassName()}>
          <Button variant="primary" look="filled" size="small" onClick={handleReviewNext} disabled={nextReviewLoading}>
            {nextReviewLoading ? t("common.loading") : t("myReviews.reviewNext")}
          </Button>
        </div>
      </div>

      {networkState === "loading" ? (
        <div className={root.elem("loading").toClassName()}>
          <Spinner size={48} />
        </div>
      ) : isEmpty ? (
        <div className={root.elem("empty").toClassName()}>
          <div>
            <div className={root.elem("empty-title").toClassName()}>{t("myReviews.empty.title")}</div>
            <div className={root.elem("empty-description").toClassName()}>{t("myReviews.empty.description")}</div>
          </div>
        </div>
      ) : (
        <div className={root.elem("table-wrapper").toClassName()}>
          <table className={root.elem("table").toClassName()}>
            <thead>
              <tr>
                <th>{t("myReviews.columns.task")}</th>
                <th>{t("myReviews.columns.project")}</th>
                <th>{t("myReviews.columns.annotation")}</th>
                <th>{t("myReviews.columns.transition")}</th>
                <th>{t("myReviews.columns.state")}</th>
                <th>{t("myReviews.columns.comment")}</th>
                <th>{t("myReviews.columns.reviewedAt")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const project = projectMap.get(row.project_id);
                return (
                  <tr key={row.id}>
                    <td>
                      <a href={`/projects/${row.project_id}/data?task=${row.task_id}`}>#{row.task_id}</a>
                    </td>
                    <td>{project?.title || `#${row.project_id}`}</td>
                    <td>#{row.annotation_id}</td>
                    <td>{t(`myReviews.transitions.${row.transition_name}`, { defaultValue: row.transition_name })}</td>
                    <td>
                      <span className={root.elem("state-badge").mod({ value: row.state?.toLowerCase() }).toClassName()}>
                        {t(`myReviews.states.${row.state?.toLowerCase()}`, { defaultValue: row.state })}
                      </span>
                    </td>
                    <td className={root.elem("comment").toClassName()}>{row.comment || ""}</td>
                    <td>{formatTimestamp(row.created_at, i18n.language)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

MyReviewsPage.title = "My Reviews";
MyReviewsPage.path = "/reviews";
MyReviewsPage.exact = true;
