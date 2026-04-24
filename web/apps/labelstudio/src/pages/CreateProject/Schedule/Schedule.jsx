import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "../../../utils/bem";
import "./Schedule.prefix.css";

export const SchedulePage = ({ show, schedule, setSchedule, error }) => {
  const { t } = useTranslation();
  const rootClass = useMemo(() => cn("project-schedule"), []);

  if (!show) return null;

  const update = (field, value) => setSchedule((prev) => ({ ...prev, [field]: value }));

  return (
    <div className={rootClass.toClassName()}>
      <div className={rootClass.elem("note").toClassName()}>{t("createProject.schedule.note")}</div>

      <div className={rootClass.elem("grid").toClassName()}>
        <label className={rootClass.elem("field").toClassName()}>
          <span>{t("createProject.schedule.startLabel")}</span>
          <input
            type="date"
            value={schedule.start_date ?? ""}
            onChange={(event) => update("start_date", event.target.value)}
          />
        </label>

        <label className={rootClass.elem("field").toClassName()}>
          <span>{t("createProject.schedule.endLabel")}</span>
          <input
            type="date"
            value={schedule.end_date ?? ""}
            onChange={(event) => update("end_date", event.target.value)}
          />
        </label>

        <label className={rootClass.elem("field").toClassName()}>
          <span>{t("createProject.schedule.taskDueLabel")}</span>
          <input
            type="number"
            min="0"
            step="1"
            value={schedule.task_due_hours ?? ""}
            onChange={(event) => update("task_due_hours", event.target.value)}
          />
          <small>{t("createProject.schedule.taskDueHint")}</small>
        </label>
      </div>

      {error && <div className={rootClass.elem("error").toClassName()}>{error}</div>}
    </div>
  );
};
