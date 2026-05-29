import os
import traceback
from collections import defaultdict

from core.nodes.base import Node
from core.task import TaskContext

MIN_SPEND = float(os.environ.get("REPORT_MIN_SPEND_GBP", "10.0"))

NUMERIC_COLS = [
    "COST", "IMPRESSIONS", "CLICKS", "NEW_ORDERS", "ORDERS",
    "GROSS_REVENUE", "NEW_GROSS_REVENUE", "GROSS_PROFIT", "NEW_GROSS_PROFIT",
    "SESSIONS", "NEW_SESSIONS", "STARTED_ASSESSMENT", "NEW_STARTED_ASSESSMENT",
    "SUBMITTED_ASSESSMENT", "NEW_SUBMITTED_ASSESSMENT",
    "BASKET_PAGE", "NEW_BASKET_PAGE", "PURCHASED", "NEW_PURCHASED",
]

# Metrics where a positive delta is bad (higher = worse)
INVERTED_METRICS = {"CPA", "CPC", "CPM"}


def safe_div(numerator, denominator):
    if numerator is None or not denominator or denominator == 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def delta_pct(val, avg):
    if avg is None or avg == 0 or val is None:
        return None
    return round((val - avg) / avg * 100, 1)


def direction(metric, pct):
    if pct is None or abs(pct) <= 5:
        return "→"
    up = pct > 0
    if metric in INVERTED_METRICS:
        return "▲" if up else "▼"
    return "▲" if up else "▼"


def aggregate(rows):
    totals = defaultdict(float)
    for r in rows:
        for col in NUMERIC_COLS:
            totals[col] += float(r.get(col) or 0)
    return dict(totals)


def trailing_averages(trailing_rows):
    by_campaign = defaultdict(list)
    for r in trailing_rows:
        by_campaign[r["CAMPAIGN"]].append(r)

    avgs = {}
    for campaign, rows in by_campaign.items():
        sums = defaultdict(float)
        for r in rows:
            for col in NUMERIC_COLS:
                sums[col] += float(r.get(col) or 0)
        n_days = len({r["DATE"] for r in rows}) or 1
        avgs[campaign] = {col: sums[col] / n_days for col in NUMERIC_COLS}
    return avgs


class ProcessingNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        if task_context.metadata.get("error"):
            return task_context

        try:
            src = task_context.nodes["SnowflakeQueryNode"]
            reporting_day_rows = src["reporting_day_rows"]
            trailing_rows = src["trailing_rows"]
            reporting_date = src["reporting_date"]
            data_lag_flag = src["data_lag_flag"]

            trail_avgs = trailing_averages(trailing_rows)

            trailing_spend_by_campaign = defaultdict(float)
            for r in trailing_rows:
                trailing_spend_by_campaign[r["CAMPAIGN"]] += float(r.get("COST") or 0)

            day_by_campaign: dict[str, dict] = defaultdict(lambda: defaultdict(float))
            campaign_channel: dict[str, str] = {}
            for r in reporting_day_rows:
                c = r["CAMPAIGN"]
                campaign_channel[c] = r.get("CHANNEL", "")
                for col in NUMERIC_COLS:
                    day_by_campaign[c][col] += float(r.get(col) or 0)

            all_campaigns = set(day_by_campaign) | set(trail_avgs)

            campaign_rows = []
            anomalies = []

            for campaign in all_campaigns:
                day = day_by_campaign.get(campaign, {})
                avg = trail_avgs.get(campaign, {})
                trail_spend = trailing_spend_by_campaign.get(campaign, 0.0)
                day_spend = day.get("COST", 0.0)

                if trail_spend < MIN_SPEND and day_spend == 0:
                    continue

                cost = day_spend
                impressions = day.get("IMPRESSIONS", 0.0)
                clicks = day.get("CLICKS", 0.0)
                new_orders = day.get("NEW_ORDERS", 0.0)
                gross_revenue = day.get("GROSS_REVENUE", 0.0)
                sessions = day.get("SESSIONS", 0.0)

                cpa = safe_div(cost, new_orders)
                roas = safe_div(gross_revenue, cost)
                ctr = safe_div(clicks, impressions)
                cpc = safe_div(cost, clicks)

                avg_cost = avg.get("COST", 0.0) or None
                avg_orders = avg.get("NEW_ORDERS", 0.0) or None
                avg_revenue = avg.get("GROSS_REVENUE", 0.0) or None
                avg_impressions = avg.get("IMPRESSIONS", 0.0) or None
                avg_clicks = avg.get("CLICKS", 0.0) or None
                avg_cpa = safe_div(avg_cost, avg_orders) if avg_cost else None
                avg_roas = safe_div(avg_revenue, avg_cost) if avg_cost else None

                cost_d = delta_pct(cost, avg_cost)
                orders_d = delta_pct(new_orders, avg_orders)
                cpa_d = delta_pct(cpa, avg_cpa)
                impr_d = delta_pct(impressions, avg_impressions)
                roas_d = delta_pct(roas, avg_roas)
                clicks_d = delta_pct(clicks, avg_clicks)

                # --- anomaly detection ---
                severity = None
                reasons = []

                if cpa_d is not None and abs(cpa_d) > 30:
                    reasons.append(f"CPA {'up' if cpa_d > 0 else 'down'} {abs(cpa_d):.0f}% vs 7d avg")
                    severity = "critical" if abs(cpa_d) > 100 else "warning"

                if cost_d is not None and abs(cost_d) > 50:
                    reasons.append(f"Spend {'up' if cost_d > 0 else 'down'} {abs(cost_d):.0f}% vs 7d avg")
                    severity = severity or "warning"

                if impr_d is not None and abs(impr_d) > 40:
                    sev = "critical" if impr_d < -80 and cost > 0 else "warning"
                    reasons.append(f"Impressions {'up' if impr_d > 0 else 'down'} {abs(impr_d):.0f}% vs 7d avg")
                    if sev == "critical":
                        severity = "critical"
                    else:
                        severity = severity or "warning"

                if orders_d is not None and abs(orders_d) > 40:
                    reasons.append(f"Conversions {'up' if orders_d > 0 else 'down'} {abs(orders_d):.0f}% vs 7d avg")
                    severity = severity or "warning"

                if cost > 0 and new_orders == 0:
                    reasons.append("Spend with zero conversions")
                    severity = severity or "warning"

                if trail_spend >= MIN_SPEND and cost == 0:
                    reasons.append("Active campaign — no spend yesterday")
                    severity = severity or "warning"

                if severity and reasons:
                    anomalies.append({
                        "campaign": campaign,
                        "severity": severity,
                        "reasons": reasons,
                        "cost": cost,
                        "cpa": cpa,
                        "cpa_delta_pct": cpa_d,
                    })

                campaign_rows.append({
                    "campaign": campaign,
                    "channel": campaign_channel.get(campaign, ""),
                    "cost": cost,
                    "cost_avg": avg_cost,
                    "cost_delta_pct": cost_d,
                    "cost_indicator": direction("COST", cost_d),
                    "new_orders": int(new_orders),
                    "new_orders_avg": avg_orders,
                    "new_orders_delta_pct": orders_d,
                    "orders_indicator": direction("ORDERS", orders_d),
                    "cpa": cpa,
                    "cpa_avg": avg_cpa,
                    "cpa_delta_pct": cpa_d,
                    "cpa_indicator": direction("CPA", cpa_d),
                    "roas": roas,
                    "roas_avg": avg_roas,
                    "roas_delta_pct": roas_d,
                    "impressions": int(impressions),
                    "impressions_delta_pct": impr_d,
                    "clicks": int(clicks),
                    "clicks_delta_pct": clicks_d,
                    "ctr": ctr,
                    "cpc": cpc,
                    "sessions": int(sessions),
                    "has_spend": cost > 0,
                    "anomaly_severity": severity,
                    "anomaly_reasons": reasons,
                    "trailing_spend": trail_spend,
                })

            campaign_rows.sort(key=lambda r: (0 if r["has_spend"] else 1, -r["cost"]))

            # account-level rollup
            all_day = aggregate(reporting_day_rows)
            total_cost = all_day.get("COST", 0.0)
            total_orders = all_day.get("NEW_ORDERS", 0.0)
            total_revenue = all_day.get("GROSS_REVENUE", 0.0)
            total_impressions = all_day.get("IMPRESSIONS", 0.0)
            total_clicks = all_day.get("CLICKS", 0.0)
            total_sessions = all_day.get("SESSIONS", 0.0)

            all_trailing = aggregate(trailing_rows)
            n_days = len({r["DATE"] for r in trailing_rows}) or 1
            acct_avg = {col: all_trailing.get(col, 0.0) / n_days for col in NUMERIC_COLS}

            acct_cost_avg = acct_avg["COST"] or None
            acct_orders_avg = acct_avg["NEW_ORDERS"] or None
            acct_revenue_avg = acct_avg["GROSS_REVENUE"] or None

            account_snapshot = {
                "cost": total_cost,
                "cost_avg": acct_cost_avg,
                "cost_delta_pct": delta_pct(total_cost, acct_cost_avg),
                "new_orders": int(total_orders),
                "new_orders_avg": acct_orders_avg,
                "new_orders_delta_pct": delta_pct(total_orders, acct_orders_avg),
                "cpa": safe_div(total_cost, total_orders),
                "cpa_avg": safe_div(acct_cost_avg, acct_orders_avg),
                "roas": safe_div(total_revenue, total_cost),
                "roas_avg": safe_div(acct_revenue_avg, acct_cost_avg),
                "impressions": int(total_impressions),
                "impressions_delta_pct": delta_pct(total_impressions, acct_avg["IMPRESSIONS"] or None),
                "clicks": int(total_clicks),
                "clicks_delta_pct": delta_pct(total_clicks, acct_avg["CLICKS"] or None),
                "ctr": safe_div(total_clicks, total_impressions),
                "cpc": safe_div(total_cost, total_clicks),
            }

            # funnel snapshot (account-level, reporting day)
            started = all_day.get("STARTED_ASSESSMENT", 0.0)
            submitted = all_day.get("SUBMITTED_ASSESSMENT", 0.0)
            basket = all_day.get("BASKET_PAGE", 0.0)
            purchased = all_day.get("PURCHASED", 0.0)

            funnel_snapshot = {
                "sessions": int(total_sessions),
                "started_assessment": int(started),
                "submitted_assessment": int(submitted),
                "basket_page": int(basket),
                "purchased": int(purchased),
                "session_to_assessment_rate": safe_div(started, total_sessions),
                "assessment_completion_rate": safe_div(submitted, started),
                "assessment_to_basket_rate": safe_div(basket, submitted),
                "basket_to_purchase_rate": safe_div(purchased, basket),
            }

            task_context.update_node(
                "ProcessingNode",
                reporting_date=reporting_date,
                data_lag_flag=data_lag_flag,
                account_snapshot=account_snapshot,
                campaign_rows=campaign_rows,
                anomalies=anomalies,
                funnel_snapshot=funnel_snapshot,
            )

        except Exception as e:
            task_context.metadata["error"] = f"ProcessingNode failed: {e}\n{traceback.format_exc()}"

        return task_context
