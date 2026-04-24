from typing import Optional, Tuple, Literal

from pydantic import BaseModel

# (absolute_delta, pct_delta) — pct is None when baseline is 0
Delta = Tuple[Optional[float], Optional[float]]


class CampaignDayMetrics(BaseModel):
    cost_usd: float
    conversions: float
    clicks: int
    impressions: int
    ctr: Optional[float] = None      # clicks / impressions; None if impressions == 0
    cvr: Optional[float] = None      # conversions / clicks; None if clicks == 0
    cpa_usd: Optional[float] = None  # cost / conversions; None if conversions == 0
    avg_cpc: Optional[float] = None  # from CSV "Avg. CPC"; None if "--"


class WoWDeltas(BaseModel):
    cost_usd: Delta
    conversions: Delta
    clicks: Delta
    impressions: Delta
    ctr: Delta
    cvr: Delta
    cpa_usd: Delta


class ProcessedCampaign(BaseModel):
    name: str
    segment: Literal["WL", "NON_WL"]
    daily_budget_usd: float
    date_oldest: CampaignDayMetrics
    date_mid: CampaignDayMetrics
    date_latest: CampaignDayMetrics
    wow1: WoWDeltas  # oldest → mid
    wow2: WoWDeltas  # mid → latest


class SegmentAggregate(BaseModel):
    segment: Literal["WL", "NON_WL"]
    campaign_count: int
    total_cost_oldest: float
    total_cost_mid: float
    total_cost_latest: float
    total_conversions_oldest: float
    total_conversions_mid: float
    total_conversions_latest: float
    total_clicks_oldest: int
    total_clicks_mid: int
    total_clicks_latest: int
    total_impressions_oldest: int
    total_impressions_mid: int
    total_impressions_latest: int
    blended_cpa_oldest: Optional[float]
    blended_cpa_mid: Optional[float]
    blended_cpa_latest: Optional[float]
    avg_cvr_oldest: Optional[float]
    avg_cvr_mid: Optional[float]
    avg_cvr_latest: Optional[float]
    avg_ctr_oldest: Optional[float]
    avg_ctr_mid: Optional[float]
    avg_ctr_latest: Optional[float]
    wow1: WoWDeltas
    wow2: WoWDeltas
