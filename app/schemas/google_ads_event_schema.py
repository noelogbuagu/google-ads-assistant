from pathlib import Path

from pydantic import BaseModel, Field


class GoogleAdsReportEvent(BaseModel):
    data_dir: Path = Field(default=Path("app/data"), description="Directory containing CSV files")
