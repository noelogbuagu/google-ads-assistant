import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load env before importing framework modules
load_dotenv(dotenv_path="app/.env")

sys.path.insert(0, "app")

from schemas.google_ads_event_schema import GoogleAdsReportEvent
from workflows.google_ads_workflow import GoogleAdsWorkflow


def main():
    parser = argparse.ArgumentParser(
        description="Google Ads Daily Report Generator — reads CSVs, outputs Markdown reports"
    )
    parser.add_argument(
        "--data-dir",
        default="app/data",
        help="Directory containing cr_*.csv files (default: app/data)",
    )
    parser.add_argument(
        "--files",
        nargs=3,
        metavar="CSV",
        help="Exactly 3 CSV file paths to use (oldest, mid, latest). Overrides --data-dir.",
    )
    args = parser.parse_args()

    files = None
    if args.files:
        files = [Path(f) for f in args.files]
        for f in files:
            if not f.exists():
                print(f"Error: file '{f}' does not exist.")
                sys.exit(1)
        data_dir = files[0].parent
        print("Google Ads Assistant — Report Generator")
        print(f"Files: {', '.join(f.name for f in files)}")
    else:
        data_dir = Path(args.data_dir)
        if not data_dir.exists():
            print(f"Error: data directory '{data_dir}' does not exist.")
            sys.exit(1)
        csv_files = list(data_dir.glob("cr_*.csv"))
        if len(csv_files) < 3:
            print(f"Error: found {len(csv_files)} CSV file(s) in '{data_dir}', need at least 3.")
            sys.exit(1)
        print("Google Ads Assistant — Report Generator")
        print(f"Data directory: {data_dir} ({len(csv_files)} CSVs found)")

    print("─" * 50)

    workflow = GoogleAdsWorkflow()
    workflow.run({"data_dir": data_dir, "files": files})


if __name__ == "__main__":
    main()
