import csv
from datetime import date, datetime
from pathlib import Path


class CSVLoader:
    """Loads and parses Google Ads campaign CSV exports from a directory."""

    def load_csvs(self, data_dir: Path) -> dict:
        """
        Loads all cr_*.csv files from data_dir, sorted chronologically by the
        date embedded in row 2 of each file.

        Returns:
            {
              "oldest":  {"date": date, "campaigns": {name: cleaned_row}},
              "mid":     {"date": date, "campaigns": {name: cleaned_row}},
              "latest":  {"date": date, "campaigns": {name: cleaned_row}},
            }

        Raises:
            FileNotFoundError: If data_dir missing or fewer than 3 CSVs found.
        """
        csv_files = sorted(data_dir.glob("cr_*.csv"))
        if len(csv_files) < 3:
            raise FileNotFoundError(
                f"Expected at least 3 CSV files in '{data_dir}', found {len(csv_files)}. "
                f"Files must match pattern cr_*.csv"
            )

        dated = [(self._parse_date_from_header(f), f) for f in csv_files]
        dated.sort(key=lambda x: x[0])

        labels = ["oldest", "mid", "latest"]
        return {
            label: {"date": d, "campaigns": self._load_file(f)}
            for label, (d, f) in zip(labels, dated)
        }

    def _parse_date_from_header(self, path: Path) -> date:
        """
        Reads row 2 to extract the report date.
        Format: '"April 10, 2026 - April 10, 2026"'
        """
        with open(path, encoding="utf-8") as f:
            next(f)  # skip "Campaign report"
            date_line = next(f).strip().strip('"')
            date_str = date_line.split(" - ")[0].strip()
            return datetime.strptime(date_str, "%B %d, %Y").date()

    def _load_file(self, path: Path) -> dict[str, dict]:
        """
        Parses a CSV file. Returns {campaign_name: cleaned_row} for rows
        where Cost > 0. Skips header rows and "Total:" summary rows.
        """
        result = {}
        with open(path, encoding="utf-8") as f:
            next(f)  # skip "Campaign report"
            next(f)  # skip date line
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Campaign", "").strip()
                status = row.get("Campaign status", "").strip()
                # Skip summary/total rows and rows with no campaign name
                if not name or name == "--" or status.startswith("Total"):
                    continue
                cleaned = self._parse_row(row)
                if cleaned["cost_usd"] > 0:
                    result[name] = cleaned
        return result

    def _parse_row(self, row: dict) -> dict:
        """Cleans a raw CSV row into typed Python values."""

        def to_float(val: str) -> float:
            if not val or val.strip() in ("--", ""):
                return 0.0
            return float(val.replace(",", "").replace("%", "").strip())

        def to_optional_float(val: str) -> float | None:
            if not val or val.strip() in ("--", ""):
                return None
            try:
                return float(val.replace(",", "").replace("%", "").strip())
            except ValueError:
                return None

        cost = to_float(row.get("Cost", "0"))
        conversions = to_float(row.get("Conversions", "0"))
        clicks = int(to_float(row.get("Clicks", "0")))
        impressions = int(to_float(row.get("Impr.", "0")))
        budget = to_float(row.get("Budget", "0"))

        # Conv. rate is a percentage string like "8.81%" — convert to decimal
        cvr_raw = row.get("Conv. rate", "--")
        cvr = (to_float(cvr_raw) / 100.0) if cvr_raw.strip() not in ("--", "") else None

        avg_cpc = to_optional_float(row.get("Avg. CPC", "--"))
        cpa = to_optional_float(row.get("Cost / conv.", "--"))
        # Treat CPA as None if no conversions
        if conversions == 0:
            cpa = None

        return {
            "cost_usd": cost,
            "conversions": conversions,
            "clicks": clicks,
            "impressions": impressions,
            "cvr": cvr,
            "cpa_usd": cpa,
            "avg_cpc": avg_cpc,
            "daily_budget_usd": budget,
        }
