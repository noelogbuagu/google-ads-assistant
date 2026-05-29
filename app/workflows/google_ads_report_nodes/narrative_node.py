from pydantic import BaseModel

from core.nodes.agent import AgentConfig, AgentNode, ModelProvider
from core.task import TaskContext

SYSTEM_PROMPT = """You are an expert Google Ads analyst for SOP, a UK-based online healthcare brand.
SOP campaigns cover weight loss injections (Wegovy, Mounjaro), ED treatment, hair loss, birth control, and online pharmacy services.

Write three sections of a daily performance report for the SOP marketing team:

1. HEADLINE (2-3 sentences): state total spend with direction vs baseline, CPA direction, and the single most important story in the account today.
2. WHAT STANDS OUT (3-5 paragraphs): analyse specific anomalies. Name every campaign explicitly. Use exact £ figures. Explain context — is this expected? seasonal? structural? Each paragraph covers one story. No generic phrases like "performance was mixed."
3. RECOMMENDATIONS (3-5 bullet points): specific and actionable. Name the campaign. Describe the observation and the suggested manual action in Google Ads. Never suggest automated changes.

Rules:
- Always use exact campaign names and exact £ figures.
- Flag uncertainty where data is ambiguous (e.g. "this may reflect normal Monday seasonality").
- Do not make any claims about medical efficacy of any advertised product.
- Currency is GBP. Format: £X,XXX for spend over £1,000, £XX for CPA.
- Attribution model is Last Click. Numbers may differ from Google Ads UI due to attribution window differences."""


class NarrativeOutput(BaseModel):
    headline: str
    what_stands_out: str
    recommendations: str


class NarrativeNode(AgentNode):
    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            model_provider=ModelProvider.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            output_type=NarrativeOutput,
            instructions=SYSTEM_PROMPT,
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        if task_context.metadata.get("error"):
            return task_context

        try:
            p = task_context.nodes["ProcessingNode"]
            snap = p["account_snapshot"]
            anomalies = p["anomalies"]
            funnel = p["funnel_snapshot"]
            campaigns = p["campaign_rows"]
            reporting_date = p["reporting_date"]
            data_lag_flag = p["data_lag_flag"]

            lag_note = " ⚠️ D-1 data incomplete — using D-2." if data_lag_flag else ""

            anomaly_lines = "\n".join(
                f"  - [{a['severity'].upper()}] {a['campaign']}: {'; '.join(a['reasons'])}"
                for a in anomalies
            ) or "  - No anomalies flagged."

            top_campaigns = campaigns[:10]
            camp_lines = []
            for r in top_campaigns:
                spend_str = f"£{r['cost']:,.0f}"
                avg_str = f"£{r['cost_avg']:,.0f}" if r["cost_avg"] else "n/a"
                cost_d = f"{r['cost_delta_pct']:+.0f}%" if r["cost_delta_pct"] is not None else "n/a"
                cpa_str = f"£{r['cpa']:.0f}" if r["cpa"] else "n/a"
                cpa_avg_str = f"£{r['cpa_avg']:.0f}" if r["cpa_avg"] else "n/a"
                cpa_d = f"{r['cpa_delta_pct']:+.0f}%" if r["cpa_delta_pct"] is not None else "n/a"
                flag = f" [{r['anomaly_severity'].upper()}]" if r["anomaly_severity"] else ""
                orders_avg_str = f"{r['new_orders_avg']:.1f}" if r["new_orders_avg"] is not None else "n/a"
                camp_lines.append(
                    f"  - {r['campaign']}{flag} ({r['channel']}): "
                    f"spend {spend_str} (avg {avg_str}, {cost_d}), "
                    f"conversions {r['new_orders']} (avg {orders_avg_str}), "
                    f"CPA {cpa_str} (avg {cpa_avg_str}, {cpa_d})"
                )

            def _f(v, fmt=".1f", prefix="", suffix=""):
                if v is None:
                    return "n/a"
                return f"{prefix}{v:{fmt}}{suffix}"

            prompt = f"""Reporting date: {reporting_date}{lag_note}

ACCOUNT SUMMARY
  Spend:       £{snap['cost']:,.0f}  (7d avg: {_f(snap['cost_avg'], ',.0f', '£')}  |  {_f(snap['cost_delta_pct'], '+.1f', '', '%')})
  Conversions: {snap['new_orders']}  (7d avg: {_f(snap['new_orders_avg'], '.1f')}  |  {_f(snap['new_orders_delta_pct'], '+.1f', '', '%')})
  CPA:         {_f(snap['cpa'], '.2f', '£')}  (7d avg: {_f(snap['cpa_avg'], '.2f', '£')})
  ROAS:        {_f(snap['roas'], '.2f')}  (7d avg: {_f(snap['roas_avg'], '.2f')})
  Impressions: {snap['impressions']:,}  ({_f(snap['impressions_delta_pct'], '+.1f', '', '%')})
  Clicks:      {snap['clicks']:,}  ({_f(snap['clicks_delta_pct'], '+.1f', '', '%')})

ANOMALIES DETECTED
{anomaly_lines}

TOP CAMPAIGNS BY SPEND
{chr(10).join(camp_lines)}

FUNNEL OVERVIEW (new users, reporting day)
  Sessions:              {funnel['sessions']:,}
  Started assessment:    {funnel['started_assessment']:,}  ({(funnel['session_to_assessment_rate'] or 0)*100:.1f}% of sessions)
  Submitted assessment:  {funnel['submitted_assessment']:,}  ({(funnel['assessment_completion_rate'] or 0)*100:.1f}% of started)
  Basket page:           {funnel['basket_page']:,}  ({(funnel['assessment_to_basket_rate'] or 0)*100:.1f}% of submitted)
  Purchased:             {funnel['purchased']:,}  ({(funnel['basket_to_purchase_rate'] or 0)*100:.1f}% of basket)

Write the three report sections now."""

            result = await self.agent.run(prompt)

            task_context.update_node(
                "NarrativeNode",
                headline=result.output.headline,
                what_stands_out=result.output.what_stands_out,
                recommendations=result.output.recommendations,
            )

        except Exception as e:
            task_context.metadata["error"] = f"NarrativeNode failed: {e}"

        return task_context
