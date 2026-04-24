from typing import Optional

from core.nodes.base import Node
from core.task import TaskContext
from schemas.google_ads_models import (
    CampaignDayMetrics,
    ProcessedCampaign,
    SegmentAggregate,
    WoWDeltas,
)


class ClassifyAndProcessNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        print("Classifying campaigns and computing metrics...")
        raw = task_context.nodes["LoadCSVDataNode"]

        oldest_campaigns = raw["oldest"]["campaigns"]
        mid_campaigns = raw["mid"]["campaigns"]
        latest_campaigns = raw["latest"]["campaigns"]

        all_names = set(oldest_campaigns) | set(mid_campaigns) | set(latest_campaigns)

        wl, nonwl = [], []
        for name in sorted(all_names):
            segment = "WL" if "weight" in name.lower() else "NON_WL"

            oldest = _build_metrics(oldest_campaigns.get(name, {}))
            mid = _build_metrics(mid_campaigns.get(name, {}))
            latest = _build_metrics(latest_campaigns.get(name, {}))

            # Use budget from most recent file that has this campaign
            raw_row = (
                latest_campaigns.get(name)
                or mid_campaigns.get(name)
                or oldest_campaigns.get(name)
                or {}
            )
            budget = raw_row.get("daily_budget_usd", 0.0)

            pc = ProcessedCampaign(
                name=name,
                segment=segment,
                daily_budget_usd=budget,
                date_oldest=oldest,
                date_mid=mid,
                date_latest=latest,
                wow1=_compute_deltas(oldest, mid),
                wow2=_compute_deltas(mid, latest),
            )
            (wl if segment == "WL" else nonwl).append(pc)

        print(f"  WL campaigns: {len(wl)} | Non-WL campaigns: {len(nonwl)}")

        task_context.update_node(
            self.node_name,
            dates={
                "oldest": str(raw["oldest"]["date"]),
                "mid": str(raw["mid"]["date"]),
                "latest": str(raw["latest"]["date"]),
            },
            wl_campaigns=[c.model_dump() for c in wl],
            nonwl_campaigns=[c.model_dump() for c in nonwl],
            wl_aggregates=_build_aggregate("WL", wl).model_dump(),
            nonwl_aggregates=_build_aggregate("NON_WL", nonwl).model_dump(),
        )
        return task_context


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_metrics(raw: dict) -> CampaignDayMetrics:
    cost = raw.get("cost_usd", 0.0)
    conversions = raw.get("conversions", 0.0)
    clicks = raw.get("clicks", 0)
    impressions = raw.get("impressions", 0)
    return CampaignDayMetrics(
        cost_usd=cost,
        conversions=conversions,
        clicks=clicks,
        impressions=impressions,
        ctr=clicks / impressions if impressions > 0 else None,
        cvr=conversions / clicks if clicks > 0 else None,
        cpa_usd=cost / conversions if conversions > 0 else None,
        avg_cpc=raw.get("avg_cpc"),
    )


def _delta(a: Optional[float], b: Optional[float]) -> tuple:
    if a is None or b is None:
        return (None, None)
    abs_d = round(a - b, 4)
    pct_d = round((abs_d / b) * 100, 2) if b != 0 else None
    return (abs_d, pct_d)


def _compute_deltas(from_: CampaignDayMetrics, to_: CampaignDayMetrics) -> WoWDeltas:
    return WoWDeltas(
        cost_usd=_delta(to_.cost_usd, from_.cost_usd),
        conversions=_delta(to_.conversions, from_.conversions),
        clicks=_delta(to_.clicks, from_.clicks),
        impressions=_delta(to_.impressions, from_.impressions),
        ctr=_delta(to_.ctr, from_.ctr),
        cvr=_delta(to_.cvr, from_.cvr),
        cpa_usd=_delta(to_.cpa_usd, from_.cpa_usd),
    )


def _build_aggregate(segment: str, campaigns: list[ProcessedCampaign]) -> SegmentAggregate:
    def total(attr: str, period: str) -> float:
        return sum(getattr(getattr(c, period), attr) or 0.0 for c in campaigns)

    def blended_cpa(period: str) -> Optional[float]:
        cost = total("cost_usd", period)
        conv = total("conversions", period)
        return cost / conv if conv > 0 else None

    def avg_cvr(period: str) -> Optional[float]:
        conv = total("conversions", period)
        clicks = total("clicks", period)
        return conv / clicks if clicks > 0 else None

    def avg_ctr(period: str) -> Optional[float]:
        clicks = total("clicks", period)
        impr = total("impressions", period)
        return clicks / impr if impr > 0 else None

    def agg_metrics(period: str) -> CampaignDayMetrics:
        return CampaignDayMetrics(
            cost_usd=total("cost_usd", period),
            conversions=total("conversions", period),
            clicks=int(total("clicks", period)),
            impressions=int(total("impressions", period)),
            ctr=avg_ctr(period),
            cvr=avg_cvr(period),
            cpa_usd=blended_cpa(period),
            avg_cpc=None,
        )

    agg_oldest = agg_metrics("date_oldest")
    agg_mid = agg_metrics("date_mid")
    agg_latest = agg_metrics("date_latest")

    return SegmentAggregate(
        segment=segment,
        campaign_count=len(campaigns),
        total_cost_oldest=agg_oldest.cost_usd,
        total_cost_mid=agg_mid.cost_usd,
        total_cost_latest=agg_latest.cost_usd,
        total_conversions_oldest=agg_oldest.conversions,
        total_conversions_mid=agg_mid.conversions,
        total_conversions_latest=agg_latest.conversions,
        total_clicks_oldest=agg_oldest.clicks,
        total_clicks_mid=agg_mid.clicks,
        total_clicks_latest=agg_latest.clicks,
        total_impressions_oldest=agg_oldest.impressions,
        total_impressions_mid=agg_mid.impressions,
        total_impressions_latest=agg_latest.impressions,
        blended_cpa_oldest=blended_cpa("date_oldest"),
        blended_cpa_mid=blended_cpa("date_mid"),
        blended_cpa_latest=blended_cpa("date_latest"),
        avg_cvr_oldest=avg_cvr("date_oldest"),
        avg_cvr_mid=avg_cvr("date_mid"),
        avg_cvr_latest=avg_cvr("date_latest"),
        avg_ctr_oldest=avg_ctr("date_oldest"),
        avg_ctr_mid=avg_ctr("date_mid"),
        avg_ctr_latest=avg_ctr("date_latest"),
        wow1=_compute_deltas(agg_oldest, agg_mid),
        wow2=_compute_deltas(agg_mid, agg_latest),
    )
