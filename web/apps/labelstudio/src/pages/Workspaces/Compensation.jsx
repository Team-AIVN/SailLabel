import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, useToast } from "@humansignal/ui";
import { useAPI } from "../../providers/ApiProvider";
import { cn } from "../../utils/bem";
import "./Compensation.prefix.css";

const listOf = (response) => {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.results)) return response.results;
  return [];
};

const fmtMoney = (amount, currency) => {
  const value = Number(amount ?? 0);
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(value);
  } catch {
    return `${value.toLocaleString()} ${currency}`;
  }
};

const fmtDate = (value) => {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString();
};

/** Per-project compensation: one row per (project, member), with a project filter and
 *  per-project payment recording. Rows are scoped by the backend to the caller's projects. */
export const Compensation = ({ workspaceId }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("compensation"), []);

  const [rows, setRows] = useState([]);
  const [projects, setProjects] = useState([]);
  const [projectFilter, setProjectFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null); // { projectId, memberId, currency, projectName, memberName }
  const [payments, setPayments] = useState([]);
  const [payAmount, setPayAmount] = useState("");
  const [payMemo, setPayMemo] = useState("");
  // 단가 편집: 프로젝트를 하나 고른 경우에만 노출한다. 생성 이후 단가를 고칠 화면이
  // 없어서, 잘못 저장된 정책을 되돌릴 방법이 없었다.
  const [policy, setPolicy] = useState(null); // {currency, annotation_unit_price, review_unit_price}
  const [savingPolicy, setSavingPolicy] = useState(false);

  const loadRows = useCallback(async () => {
    setLoading(true);
    const params = { pk: workspaceId };
    if (projectFilter) params.project = projectFilter;
    const res = await api.callApi("workspaceCompensation", { params });
    setRows(listOf(res?.results ?? res));
    setProjects(Array.isArray(res?.projects) ? res.projects : []);
    setLoading(false);
  }, [api, workspaceId, projectFilter]);

  const loadPayments = useCallback(
    async (sel) => {
      if (!sel) {
        setPayments([]);
        return;
      }
      const res = await api.callApi("workspacePayments", {
        params: { pk: workspaceId, project: sel.projectId, user: sel.memberId },
      });
      setPayments(listOf(res));
    },
    [api, workspaceId],
  );

  const loadPolicy = useCallback(async () => {
    if (!projectFilter) {
      setPolicy(null);
      return;
    }
    const res = await api.callApi("projectCompensationPolicy", {
      params: { pk: projectFilter },
      errorFilter: () => true,
    });
    setPolicy(
      res?.$meta?.ok === false
        ? { currency: "KRW", annotation_unit_price: "0", review_unit_price: "0" }
        : {
            currency: res.currency,
            annotation_unit_price: String(res.annotation_unit_price),
            review_unit_price: String(res.review_unit_price),
          },
    );
  }, [api, projectFilter]);

  const savePolicy = useCallback(async () => {
    if (!projectFilter || !policy) return;
    setSavingPolicy(true);
    const res = await api.callApi("setProjectCompensationPolicy", {
      params: { pk: projectFilter },
      body: {
        currency: policy.currency,
        annotation_unit_price: Number.parseFloat(policy.annotation_unit_price || "0"),
        review_unit_price: Number.parseFloat(policy.review_unit_price || "0"),
      },
      errorFilter: () => true,
    });
    setSavingPolicy(false);
    if (!res?.$meta?.ok) {
      toast?.show({ message: t("compensation.policySaveFailed", "단가 저장에 실패했습니다."), type: "error" });
      return;
    }
    toast?.show({ message: t("compensation.policySaved", "단가를 저장했습니다.") });
    await Promise.all([loadRows(), loadPolicy()]);
  }, [api, projectFilter, policy, toast, t, loadRows, loadPolicy]);

  useEffect(() => {
    loadRows();
  }, [loadRows]);
  useEffect(() => {
    loadPolicy();
  }, [loadPolicy]);
  useEffect(() => {
    loadPayments(selected);
  }, [selected, loadPayments]);

  const recordPayment = useCallback(async () => {
    if (!selected) return;
    const amount = Number.parseFloat(payAmount);
    if (!(amount > 0)) {
      toast.show({ message: t("compensation.amountInvalid", "Enter an amount greater than 0"), type: "error" });
      return;
    }
    const res = await api.callApi("createWorkspacePayment", {
      params: { pk: workspaceId },
      body: {
        project: selected.projectId,
        user: selected.memberId,
        currency: selected.currency,
        amount,
        memo: payMemo,
      },
    });
    if (res && !res.error) {
      toast.show({ message: t("compensation.paymentRecorded", "Payment recorded") });
      setPayAmount("");
      setPayMemo("");
      await Promise.all([loadRows(), loadPayments(selected)]);
    } else {
      toast.show({ message: res?.detail ?? t("compensation.actionFailed", "Action failed"), type: "error" });
    }
  }, [api, workspaceId, selected, payAmount, payMemo, toast, t, loadRows, loadPayments]);

  const deletePayment = useCallback(
    async (paymentId) => {
      if (!window.confirm(t("compensation.deletePaymentConfirm", "Delete this payment record?"))) return;
      await api.callApi("deleteWorkspacePayment", { params: { pk: workspaceId, paymentPk: paymentId } });
      await Promise.all([loadRows(), loadPayments(selected)]);
    },
    [api, workspaceId, selected, t, loadRows, loadPayments],
  );

  const statusLabel = (s) => t(`compensation.status.${s}`, s);
  const isSelected = (r) => selected?.projectId === r.project_id && selected?.memberId === r.member_id;

  if (loading) return <div className={root.elem("loading").toClassName()}>…</div>;

  return (
    <div className={root.toClassName()}>
      <div className={root.elem("toolbar").toClassName()}>
        <label>
          {t("compensation.project", "Project")}:{" "}
          <select value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)}>
            <option value="">{t("compensation.allProjects", "All projects")}</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
        {projectFilter && policy && (
          <div className={root.elem("policy").toClassName()}>
            <label>
              {t("compensation.currency", "통화")}:{" "}
              <select value={policy.currency} onChange={(e) => setPolicy({ ...policy, currency: e.target.value })}>
                {["KRW", "USD", "EUR", "JPY"].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t("compensation.annotationUnitPrice", "어노테이션 단가")}:{" "}
              <input
                type="number"
                min="0"
                step="any"
                value={policy.annotation_unit_price}
                onChange={(e) => setPolicy({ ...policy, annotation_unit_price: e.target.value })}
              />
            </label>
            <label>
              {t("compensation.reviewUnitPrice", "검수 단가")}:{" "}
              <input
                type="number"
                min="0"
                step="any"
                value={policy.review_unit_price}
                onChange={(e) => setPolicy({ ...policy, review_unit_price: e.target.value })}
              />
            </label>
            <Button size="small" waiting={savingPolicy} onClick={savePolicy}>
              {t("compensation.savePolicy", "단가 저장")}
            </Button>
          </div>
        )}
      </div>

      <table className={root.elem("table").toClassName()}>
        <thead>
          <tr>
            <th>{t("compensation.project", "Project")}</th>
            <th>{t("compensation.memberName", "Member")}</th>
            <th>{t("compensation.role", "Role")}</th>
            <th className={root.elem("num").toClassName()}>{t("compensation.annotations", "Annotations")}</th>
            <th className={root.elem("num").toClassName()}>{t("compensation.reviews", "Reviews")}</th>
            <th className={root.elem("num").toClassName()}>{t("compensation.totalEarned", "Total Earned")}</th>
            <th className={root.elem("num").toClassName()}>{t("compensation.totalPaid", "Total Paid")}</th>
            <th className={root.elem("num").toClassName()}>{t("compensation.remaining", "Remaining")}</th>
            <th>{t("compensation.statusLabel", "Status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={`${r.project_id}-${r.member_id}`}
              className={root
                .elem("row")
                .mod({ active: isSelected(r) })
                .toClassName()}
              onClick={() =>
                setSelected({
                  projectId: r.project_id,
                  memberId: r.member_id,
                  currency: r.currency,
                  projectName: r.project_name,
                  memberName: r.member_name,
                })
              }
            >
              <td>{r.project_name}</td>
              <td>{r.member_name}</td>
              <td>{r.role ? t(`workspaces.roles.${r.role}`, r.role) : "—"}</td>
              <td className={root.elem("num").toClassName()}>{r.annotation_count}</td>
              <td className={root.elem("num").toClassName()}>{r.review_count}</td>
              <td className={root.elem("num").toClassName()}>{fmtMoney(r.total_earned, r.currency)}</td>
              <td className={root.elem("num").toClassName()}>{fmtMoney(r.total_paid, r.currency)}</td>
              <td className={root.elem("num").toClassName()}>{fmtMoney(r.remaining_balance, r.currency)}</td>
              <td>
                <span className={root.elem("badge").mod({ status: r.status }).toClassName()}>
                  {statusLabel(r.status)}
                </span>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={9} className={root.elem("muted").toClassName()}>
                {t("compensation.noData", "No compensation data yet.")}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {selected &&
        (() => {
          const row = rows.find(isSelected);
          return (
            <section className={root.elem("detail").toClassName()}>
              <header className={root.elem("detail-head").toClassName()}>
                <strong>
                  {selected.projectName} · {selected.memberName}
                </strong>
                <Button size="smaller" look="string" onClick={() => setSelected(null)}>
                  {t("common.close", "Close")}
                </Button>
              </header>

              {row && (
                <div className={root.elem("breakdown").toClassName()}>
                  <span>
                    {t("compensation.qAnnotations", "Qualified Annotations")}: <b>{row.annotation_count}</b> (
                    {fmtMoney(row.annotation_earnings, row.currency)})
                  </span>
                  <span>
                    {t("compensation.qReviews", "Qualified Reviews")}: <b>{row.review_count}</b> (
                    {fmtMoney(row.review_earnings, row.currency)})
                  </span>
                  <span>
                    {t("compensation.totalEarned", "Total Earned")}: <b>{fmtMoney(row.total_earned, row.currency)}</b> ·{" "}
                    {t("compensation.totalPaid", "Total Paid")}: {fmtMoney(row.total_paid, row.currency)} ·{" "}
                    {t("compensation.remaining", "Remaining")}: {fmtMoney(row.remaining_balance, row.currency)}
                  </span>
                </div>
              )}

              <h4>{t("compensation.paymentHistory", "Payment History")}</h4>
              <table className={root.elem("table").toClassName()}>
                <thead>
                  <tr>
                    <th>{t("compensation.paymentDate", "Date")}</th>
                    <th className={root.elem("num").toClassName()}>{t("compensation.amount", "Amount")}</th>
                    <th>{t("compensation.notes", "Notes")}</th>
                    <th aria-label="actions" />
                  </tr>
                </thead>
                <tbody>
                  {payments.map((p) => (
                    <tr key={p.id}>
                      <td>{fmtDate(p.paid_at)}</td>
                      <td className={root.elem("num").toClassName()}>{fmtMoney(p.amount, p.currency)}</td>
                      <td>{p.memo || "—"}</td>
                      <td>
                        <Button size="smaller" look="string" variant="negative" onClick={() => deletePayment(p.id)}>
                          {t("common.delete", "Delete")}
                        </Button>
                      </td>
                    </tr>
                  ))}
                  {payments.length === 0 && (
                    <tr>
                      <td colSpan={4} className={root.elem("muted").toClassName()}>
                        {t("compensation.noPayments", "No payments recorded.")}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              <div className={root.elem("pay-form").toClassName()}>
                <span className={root.elem("pay-label").toClassName()}>
                  {t("compensation.recordPaymentIn", "Record payment in {{currency}}", { currency: selected.currency })}
                </span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="0.00"
                  value={payAmount}
                  onChange={(e) => setPayAmount(e.target.value)}
                />
                <input
                  placeholder={t("compensation.notes", "Notes")}
                  value={payMemo}
                  onChange={(e) => setPayMemo(e.target.value)}
                />
                <Button size="small" onClick={recordPayment} disabled={!(Number.parseFloat(payAmount) > 0)}>
                  {t("compensation.record", "Record")}
                </Button>
              </div>
            </section>
          );
        })()}
    </div>
  );
};
