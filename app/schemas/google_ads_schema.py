from datetime import date
from typing import Optional
from pydantic import BaseModel


class GoogleAdsReportEventSchema(BaseModel):
    brand: str = "sop"
    override_date: Optional[date] = None
