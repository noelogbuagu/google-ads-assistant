import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "app"))
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / "app" / ".env")

from playground.utils.visualize_workflow import visualize_workflow
from workflows.google_ads_report_workflow import GoogleAdsReportWorkflow

output_path = Path(__file__).parent / "outputs" / "workflow.png"
output_path.parent.mkdir(exist_ok=True)

image = visualize_workflow(GoogleAdsReportWorkflow())
with open(output_path, "wb") as f:
    f.write(image.data)

print(f"Saved to {output_path}")
