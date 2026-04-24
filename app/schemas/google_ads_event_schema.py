from pathlib import Path

from pydantic import BaseModel, Field


class GoogleAdsReportEvent(BaseModel):
    data_dir: Path = Field(default=Path("app/data"), description="Directory containing CSV files")
    files: list[Path] | None = Field(default=None, description="Explicit list of exactly 3 CSV paths")
