from enum import Enum

from workflows.example_streaming_workflow import ExampleStreamingWorkflow
from workflows.google_ads_report_workflow import GoogleAdsReportWorkflow


class WorkflowRegistry(Enum):
    EXAMPLE_STREAMING_WORKFLOW = ExampleStreamingWorkflow
    GOOGLE_ADS_REPORT_WORKFLOW = GoogleAdsReportWorkflow
