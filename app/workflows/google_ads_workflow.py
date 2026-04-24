from core.schema import WorkflowSchema, NodeConfig
from core.workflow import Workflow
from schemas.google_ads_event_schema import GoogleAdsReportEvent
from workflows.google_ads_workflow_nodes.load_csv_data_node import LoadCSVDataNode
from workflows.google_ads_workflow_nodes.classify_and_process_node import ClassifyAndProcessNode
from workflows.google_ads_workflow_nodes.generate_wl_report_node import GenerateWLReportNode
from workflows.google_ads_workflow_nodes.generate_nonwl_report_node import GenerateNonWLReportNode
from workflows.google_ads_workflow_nodes.write_reports_node import WriteReportsNode


class GoogleAdsWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        description="Daily Google Ads performance report from CSV exports",
        event_schema=GoogleAdsReportEvent,
        start=LoadCSVDataNode,
        nodes=[
            NodeConfig(
                node=LoadCSVDataNode,
                connections=[ClassifyAndProcessNode],
                description="Loads and parses CSV exports from app/data/",
            ),
            NodeConfig(
                node=ClassifyAndProcessNode,
                connections=[GenerateWLReportNode],
                description="Segments campaigns WL/Non-WL and computes metrics",
            ),
            NodeConfig(
                node=GenerateWLReportNode,
                connections=[GenerateNonWLReportNode],
                description="Generates Weight Loss report via Claude",
            ),
            NodeConfig(
                node=GenerateNonWLReportNode,
                connections=[WriteReportsNode],
                description="Generates Non-WL report via Claude",
            ),
            NodeConfig(
                node=WriteReportsNode,
                connections=[],
                description="Writes both reports to app/reports/",
            ),
        ],
    )
