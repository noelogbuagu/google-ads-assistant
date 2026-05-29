import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "app", ".env"))

from workflows.google_ads_report_workflow import GoogleAdsReportWorkflow

if __name__ == "__main__":
    override_date = sys.argv[1] if len(sys.argv) > 1 else None
    event = {"brand": "sop", "override_date": override_date}

    print(f"Running SOP Google Ads report | override_date={override_date or 'auto (D-1/D-2)'}")
    workflow = GoogleAdsReportWorkflow()
    result = workflow.run(event)
    status = result.nodes.get("TeamsDeliveryNode", {}).get("delivery_status", "unknown")
    print(f"\n[delivery_status] {status}")
