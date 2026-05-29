from enum import Enum

from workflows.google_ads_report_workflow import GoogleAdsReportWorkflow


class WorkflowRegistry(Enum):
    GOOGLE_ADS_REPORT_WORKFLOW = GoogleAdsReportWorkflow
