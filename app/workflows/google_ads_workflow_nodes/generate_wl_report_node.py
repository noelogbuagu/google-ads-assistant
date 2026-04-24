import os

from core.nodes.agent import AgentNode, AgentConfig, ModelProvider
from core.task import TaskContext
from services.prompt_loader import PromptManager


class GenerateWLReportNode(AgentNode):

    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            model_provider=ModelProvider.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            output_type=str,
            instructions=PromptManager.get_prompt(
                "report_generation",
                cpa_target=os.getenv("CPA_TARGET_USD", "500"),
            ),
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        print("Generating Weight Loss report...")
        data = task_context.nodes["ClassifyAndProcessNode"]
        user_prompt = _format_prompt(
            segment="Weight Loss (WL)",
            campaigns=data["wl_campaigns"],
            aggregates=data["wl_aggregates"],
            dates=data["dates"],
        )
        result = await self.agent.run(user_prompt)
        task_context.update_node(self.node_name, report_markdown=result.output)
        return task_context


def _format_prompt(segment: str, campaigns: list, aggregates: dict, dates: dict) -> str:
    agg = aggregates
    d = dates

    def fmt_pct(v):
        return f"{v*100:.2f}%" if v is not None else "N/A"

    def fmt_usd(v):
        return f"${v:.2f}" if v is not None else "N/A"

    def fmt_delta(delta_tuple):
        abs_d, pct_d = delta_tuple
        if abs_d is None:
            return "—"
        pct_str = f" ({pct_d:+.1f}%)" if pct_d is not None else " (—%)"
        return f"{abs_d:+.2f}{pct_str}"

    lines = [
        f"SEGMENT: {segment}",
        f"DATES: oldest={d['oldest']}, mid={d['mid']}, latest={d['latest']}",
        "",
        "=== SEGMENT AGGREGATES ===",
        f"{d['oldest']}: spend={fmt_usd(agg['total_cost_oldest'])}, "
        f"conv={agg['total_conversions_oldest']:.2f}, "
        f"CPA={fmt_usd(agg['blended_cpa_oldest'])}, "
        f"CVR={fmt_pct(agg['avg_cvr_oldest'])}, "
        f"CTR={fmt_pct(agg['avg_ctr_oldest'])}, "
        f"impressions={agg['total_impressions_oldest']:,}, "
        f"clicks={agg['total_clicks_oldest']:,}",
        f"{d['mid']}: spend={fmt_usd(agg['total_cost_mid'])}, "
        f"conv={agg['total_conversions_mid']:.2f}, "
        f"CPA={fmt_usd(agg['blended_cpa_mid'])}, "
        f"CVR={fmt_pct(agg['avg_cvr_mid'])}, "
        f"CTR={fmt_pct(agg['avg_ctr_mid'])}, "
        f"impressions={agg['total_impressions_mid']:,}, "
        f"clicks={agg['total_clicks_mid']:,}",
        f"{d['latest']}: spend={fmt_usd(agg['total_cost_latest'])}, "
        f"conv={agg['total_conversions_latest']:.2f}, "
        f"CPA={fmt_usd(agg['blended_cpa_latest'])}, "
        f"CVR={fmt_pct(agg['avg_cvr_latest'])}, "
        f"CTR={fmt_pct(agg['avg_ctr_latest'])}, "
        f"impressions={agg['total_impressions_latest']:,}, "
        f"clicks={agg['total_clicks_latest']:,}",
        f"WoW 1 ({d['oldest']}→{d['mid']}): "
        f"spend Δ={fmt_delta(agg['wow1']['cost_usd'])}, "
        f"conv Δ={fmt_delta(agg['wow1']['conversions'])}, "
        f"CPA Δ={fmt_delta(agg['wow1']['cpa_usd'])}, "
        f"CVR Δ={fmt_delta(agg['wow1']['cvr'])}, "
        f"CTR Δ={fmt_delta(agg['wow1']['ctr'])}",
        f"WoW 2 ({d['mid']}→{d['latest']}): "
        f"spend Δ={fmt_delta(agg['wow2']['cost_usd'])}, "
        f"conv Δ={fmt_delta(agg['wow2']['conversions'])}, "
        f"CPA Δ={fmt_delta(agg['wow2']['cpa_usd'])}, "
        f"CVR Δ={fmt_delta(agg['wow2']['cvr'])}, "
        f"CTR Δ={fmt_delta(agg['wow2']['ctr'])}",
        "",
        f"=== CAMPAIGNS ({len(campaigns)} total) ===",
    ]

    for c in campaigns:
        wow1 = c["wow1"]
        wow2 = c["wow2"]
        od = c["date_oldest"]
        md = c["date_mid"]
        ld = c["date_latest"]
        lines += [
            f"\nCampaign: {c['name']}",
            f"  Budget: {fmt_usd(c['daily_budget_usd'])}/day",
            f"  {d['oldest']}: spend={fmt_usd(od['cost_usd'])}, conv={od['conversions']:.2f}, "
            f"CPA={fmt_usd(od['cpa_usd'])}, CVR={fmt_pct(od['cvr'])}, "
            f"CTR={fmt_pct(od['ctr'])}, impressions={od['impressions']:,}, "
            f"avg_cpc={fmt_usd(od['avg_cpc'])}",
            f"  {d['mid']}: spend={fmt_usd(md['cost_usd'])}, conv={md['conversions']:.2f}, "
            f"CPA={fmt_usd(md['cpa_usd'])}, CVR={fmt_pct(md['cvr'])}, "
            f"CTR={fmt_pct(md['ctr'])}, impressions={md['impressions']:,}, "
            f"avg_cpc={fmt_usd(md['avg_cpc'])}",
            f"  {d['latest']}: spend={fmt_usd(ld['cost_usd'])}, conv={ld['conversions']:.2f}, "
            f"CPA={fmt_usd(ld['cpa_usd'])}, CVR={fmt_pct(ld['cvr'])}, "
            f"CTR={fmt_pct(ld['ctr'])}, impressions={ld['impressions']:,}, "
            f"avg_cpc={fmt_usd(ld['avg_cpc'])}",
            f"  WoW 1 ({d['oldest']}→{d['mid']}): "
            f"spend Δ={fmt_delta(wow1['cost_usd'])}, conv Δ={fmt_delta(wow1['conversions'])}, "
            f"CPA Δ={fmt_delta(wow1['cpa_usd'])}, CVR Δ={fmt_delta(wow1['cvr'])}, "
            f"CTR Δ={fmt_delta(wow1['ctr'])}",
            f"  WoW 2 ({d['mid']}→{d['latest']}): "
            f"spend Δ={fmt_delta(wow2['cost_usd'])}, conv Δ={fmt_delta(wow2['conversions'])}, "
            f"CPA Δ={fmt_delta(wow2['cpa_usd'])}, CVR Δ={fmt_delta(wow2['cvr'])}, "
            f"CTR Δ={fmt_delta(wow2['ctr'])}",
        ]

    return "\n".join(lines)
