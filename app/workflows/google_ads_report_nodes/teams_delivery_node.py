from datetime import datetime

from core.nodes.base import Node
from core.task import TaskContext


def _fmt_gbp(val) -> str:
    if val is None:
        return "n/a"
    if val >= 1000:
        return f"£{val:,.0f}"
    return f"£{val:.2f}"


def _fmt_delta(pct) -> str:
    if pct is None:
        return "—"
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "→")
    return f"{arrow} {pct:+.1f}%"


def _pct(val) -> str:
    return f"{(val or 0) * 100:.1f}%" if val is not None else "—"


def _delta_pct(a, b):
    if a and b and b != 0:
        return round((a - b) / b * 100, 1)
    return None


def _build_report(p: dict, n: dict) -> str:
    snap = p["account_snapshot"]
    campaigns = p["campaign_rows"]
    funnel = p["funnel_snapshot"]
    reporting_date = p["reporting_date"]
    data_lag_flag = p["data_lag_flag"]

    try:
        date_str = reporting_date.strftime("%A %-d %B %Y")
    except Exception:
        date_str = str(reporting_date)

    lag_note = " | ⚠️ D-1 incomplete — reporting on D-2" if data_lag_flag else ""

    cpa_d = _delta_pct(snap.get("cpa"), snap.get("cpa_avg"))
    roas_d = _delta_pct(snap.get("roas"), snap.get("roas_avg"))

    lines = [
        f"📊 **SOP Google Ads — Daily Report | {date_str}**",
        f"*Source: Snowflake ACQUISITION_MASTER | Attribution: Last Click{lag_note}*",
        "",
        f"**{n['headline']}**",
        "",
        "---",
        "",
        "### Account Snapshot",
        "| Metric | Yesterday | 7d Avg | Δ |",
        "|---|---|---|---|",
        f"| Spend | {_fmt_gbp(snap['cost'])} | {_fmt_gbp(snap['cost_avg'])} | {_fmt_delta(snap['cost_delta_pct'])} |",
        f"| Conversions (LC) | {snap['new_orders']} | {snap['new_orders_avg'] or 0:.1f} | {_fmt_delta(snap['new_orders_delta_pct'])} |",
        f"| CPA | {_fmt_gbp(snap['cpa'])} | {_fmt_gbp(snap['cpa_avg'])} | {_fmt_delta(cpa_d)} |",
        f"| ROAS | {snap['roas'] or 0:.2f} | {snap['roas_avg'] or 0:.2f} | {_fmt_delta(roas_d)} |",
        f"| Impressions | {snap['impressions']:,} | — | {_fmt_delta(snap['impressions_delta_pct'])} |",
        f"| Clicks | {snap['clicks']:,} | — | {_fmt_delta(snap['clicks_delta_pct'])} |",
        f"| CTR | {(snap['ctr'] or 0)*100:.2f}% | — | — |",
        f"| CPC | {_fmt_gbp(snap['cpc'])} | — | — |",
        "",
        "### Campaign Breakdown",
        "| Campaign | Spend | Δ | Conv | Δ | CPA | Δ | ROAS |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in campaigns:
        flag = "🔴 " if r["anomaly_severity"] == "critical" else ("🟡 " if r["anomaly_severity"] == "warning" else "")
        suffix = " *(no spend)*" if not r["has_spend"] else ""
        roas_str = f"{r['roas']:.2f}" if r["roas"] else "—"
        lines.append(
            f"| {flag}{r['campaign']}{suffix} "
            f"| {_fmt_gbp(r['cost'])} | {_fmt_delta(r['cost_delta_pct'])} "
            f"| {r['new_orders']} | {_fmt_delta(r['new_orders_delta_pct'])} "
            f"| {_fmt_gbp(r['cpa'])} | {_fmt_delta(r['cpa_delta_pct'])} "
            f"| {roas_str} |"
        )

    lines += [
        "",
        "### Funnel Overview (New Users)",
        "| Stage | Volume | Rate |",
        "|---|---|---|",
        f"| Sessions | {funnel['sessions']:,} | — |",
        f"| Started Assessment | {funnel['started_assessment']:,} | {_pct(funnel['session_to_assessment_rate'])} |",
        f"| Submitted Assessment | {funnel['submitted_assessment']:,} | {_pct(funnel['assessment_completion_rate'])} |",
        f"| Basket Page | {funnel['basket_page']:,} | {_pct(funnel['assessment_to_basket_rate'])} |",
        f"| Purchased | {funnel['purchased']:,} | {_pct(funnel['basket_to_purchase_rate'])} |",
        "",
        "---",
        "",
        "### What Stands Out",
        n["what_stands_out"],
        "",
        "### Recommendations",
        n["recommendations"],
    ]

    return "\n".join(lines)


class TeamsDeliveryNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        error = task_context.metadata.get("error")

        if error:
            alert = (
                f"\n{'='*80}\n"
                f"⚠️  SOP Google Ads report FAILED\n"
                f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n"
                f"Error: {error}\n"
                f"Action: Check pipeline logs or run manually.\n"
                f"{'='*80}\n"
            )
            print(alert)
            task_context.update_node(
                "TeamsDeliveryNode",
                delivery_status="failed",
                delivery_error=error,
            )
            task_context.stop_workflow()
            return task_context

        p = task_context.nodes["ProcessingNode"]
        n = task_context.nodes["NarrativeNode"]
        report = _build_report(p, n)

        print("\n" + "=" * 80)
        print(report)
        print("=" * 80 + "\n")

        task_context.update_node(
            "TeamsDeliveryNode",
            delivery_status="console_demo",
            delivery_error=None,
        )
        return task_context
