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
    // Unknown/!ISO currency — fall back to a plain number + code.
    return `${value.toLocaleString()} ${currency}`;
  }
};

const fmtDate = (value) => {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString();
};

/** Workspace compensation dashboard (one row per member+currency) + member detail. */
export const Compensation = ({ workspaceId }) => {
  const { t } = useTranslation();
  const api = useAPI();
  const toast = useToast();
  const root = useMemo(() => cn("compensation"), []);

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null); // { memberId, currency }
  const [detail, setDetail] = useState(null);
  const [payAmount, setPayAmount] = useState("");
  const [payMemo, setPayMemo] = useState("");

  const loadRows = useCallback(async () => {
    setLoading(true);
    const res = await api.callApi("workspaceCompensation", { params: { pk: workspaceId } });
    setRows(listOf(res));
    setLoading(false);
  }, [api, workspaceId]);

  const loadDetail = useCallback(
    async (memberId) => {
      if (!memberId) {
        setDetail(null);
        return;
      }
      const res = await api.callApi("memberCompensation", { params: { pk: workspaceId, userPk: memberId } });
      setDetail(res && !res.error ? res : null);
    },
    [api, workspaceId],
  );

  useEffect(() => {
    loadRows();
  }, [loadRows]);
  useEffect(() => {
    loadDetail(selected?.memberId);
  }, [selected, loadDetail]);

  const recordPayment = useCallback(async () => {
    if (!selected) return;
    const amount = Number.parseFloat(payAmount);
    if (!(amount > 0)) {
      toast.show({ message: t("compensation.amountInvalid", "Enter an amount greater than 0"), type: "error" });
      return;
    }
    const res = await api.callApi("createWorkspacePayment", {
      params: { pk: workspaceId },
      body: { user: selected.memberId, currency: selected.currency, amount, memo: payMemo },
    });
    if (res && !res.error) {
      toast.show({ message: t("compensation.paymentRecorded", "Payment recorded") });
      setPayAmount("");
      setPayMemo("");
      await Promise.all([loadRows(), loadDetail(selected.memberId)]);
    } else {
      toast.show({ message: res?.detail ?? t("compensation.actionFailed", "Action failed"), type: "error" });
    }
  }, [api, workspaceId, selected, payAmount, payMemo, toast, t, loadRows, loadDetail]);

  const deletePayment = useCallback(
    async (paymentId) => {
      if (!window.confirm(t("compensation.deletePaymentConfirm", "Delete this payment record?"))) return;
      await api.callApi("deleteWorkspacePayment", { params: { pk: workspaceId, paymentPk: paymentId } });
      await Promise.all([loadRows(), loadDetail(selected?.memberId)]);
    },
    [api, workspaceId, selected, t, loadRows, loadDetail],
  );

  const statusLabel = (s) => t(`compensation.status.${s}`, s);

  if (loading) return <div className={root.elem("loading").toClassName()}>…</div>;

  return (
    <div className={root.toClassName()}>
      <table className={root.elem("table").toClassName()}>
        <thead>
          <tr>
            <th>{t("compensation.memberName", "Member")}</th>
            <th>{t("compensation.role", "Role")}</th>
            <th>{t("compensation.currency", "Currency")}</th>
            <th className={root.elem("num").toClassName()}>{t("compensation.totalEarned", "Total Earned")}</th>
            <th className={root.elem("num").toClassName()}>{t("compensation.totalPaid", "Total Paid")}</th>
            <th className={root.elem("num").toClassName()}>{t("compensation.remaining", "Remaining")}</th>
            <th>{t("compensation.statusLabel", "Status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isActive = selected?.memberId === r.member_id && selected?.currency === r.currency;
            return (
              <tr
                key={`${r.member_id}-${r.currency}`}
                className={root.elem("row").mod({ active: isActive }).toClassName()}
                onClick={() => setSelected({ memberId: r.member_id, currency: r.currency })}
              >
                <td>{r.member_name}</td>
                <td>{r.role ? t(`workspaces.roles.${r.role}`, r.role) : "—"}</td>
                <td>{r.currency}</td>
                <td className={root.elem("num").toClassName()}>{fmtMoney(r.total_earned, r.currency)}</td>
                <td className={root.elem("num").toClassName()}>{fmtMoney(r.total_paid, r.currency)}</td>
                <td className={root.elem("num").toClassName()}>{fmtMoney(r.remaining_balance, r.currency)}</td>
                <td>
                  <span className={root.elem("badge").mod({ status: r.status }).toClassName()}>
                    {statusLabel(r.status)}
                  </span>
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td colSpan={7} className={root.elem("muted").toClassName()}>
                {t("compensation.noData", "No compensation data yet.")}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {detail && (
        <section className={root.elem("detail").toClassName()}>
          <header className={root.elem("detail-head").toClassName()}>
            <strong>{detail.member_name}</strong>
            <Button size="smaller" look="string" onClick={() => setSelected(null)}>
              {t("common.close", "Close")}
            </Button>
          </header>

          <h4>{t("compensation.projectEarnings", "Project Compensation")}</h4>
          <table className={root.elem("table").toClassName()}>
            <thead>
              <tr>
                <th>{t("compensation.project", "Project")}</th>
                <th>{t("compensation.currency", "Currency")}</th>
                <th className={root.elem("num").toClassName()}>
                  {t("compensation.qAnnotations", "Qualified Annotations")}
                </th>
                <th className={root.elem("num").toClassName()}>
                  {t("compensation.annotationEarnings", "Annotation Earnings")}
                </th>
                <th className={root.elem("num").toClassName()}>{t("compensation.qReviews", "Qualified Reviews")}</th>
                <th className={root.elem("num").toClassName()}>
                  {t("compensation.reviewEarnings", "Review Earnings")}
                </th>
                <th className={root.elem("num").toClassName()}>{t("compensation.totalEarnings", "Total")}</th>
              </tr>
            </thead>
            <tbody>
              {detail.projects.map((p) => (
                <tr key={p.project_id}>
                  <td>{p.project_name}</td>
                  <td>{p.currency}</td>
                  <td className={root.elem("num").toClassName()}>{p.qualified_annotation_count}</td>
                  <td className={root.elem("num").toClassName()}>{fmtMoney(p.annotation_earnings, p.currency)}</td>
                  <td className={root.elem("num").toClassName()}>{p.qualified_review_count}</td>
                  <td className={root.elem("num").toClassName()}>{fmtMoney(p.review_earnings, p.currency)}</td>
                  <td className={root.elem("num").toClassName()}>
                    <strong>{fmtMoney(p.total_earnings, p.currency)}</strong>
                  </td>
                </tr>
              ))}
              {detail.projects.length === 0 && (
                <tr>
                  <td colSpan={7} className={root.elem("muted").toClassName()}>
                    {t("compensation.noEarnings", "No earnings yet.")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <h4>{t("compensation.paymentHistory", "Payment History")}</h4>
          <table className={root.elem("table").toClassName()}>
            <thead>
              <tr>
                <th>{t("compensation.paymentDate", "Date")}</th>
                <th className={root.elem("num").toClassName()}>{t("compensation.amount", "Amount")}</th>
                <th>{t("compensation.currency", "Currency")}</th>
                <th>{t("compensation.notes", "Notes")}</th>
                <th aria-label="actions" />
              </tr>
            </thead>
            <tbody>
              {detail.payments.map((p) => (
                <tr key={p.id}>
                  <td>{fmtDate(p.paid_at)}</td>
                  <td className={root.elem("num").toClassName()}>{fmtMoney(p.amount, p.currency)}</td>
                  <td>{p.currency}</td>
                  <td>{p.memo || "—"}</td>
                  <td>
                    <Button size="smaller" look="string" variant="negative" onClick={() => deletePayment(p.id)}>
                      {t("common.delete", "Delete")}
                    </Button>
                  </td>
                </tr>
              ))}
              {detail.payments.length === 0 && (
                <tr>
                  <td colSpan={5} className={root.elem("muted").toClassName()}>
                    {t("compensation.noPayments", "No payments recorded.")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {selected && (
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
          )}
        </section>
      )}
    </div>
  );
};
