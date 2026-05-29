from core.schema import NodeConfig, WorkflowSchema
from core.workflow import Workflow
from schemas.google_ads_schema import GoogleAdsReportEventSchema
from workflows.google_ads_report_nodes.narrative_node import NarrativeNode
from workflows.google_ads_report_nodes.processing_node import ProcessingNode
from workflows.google_ads_report_nodes.snowflake_query_node import SnowflakeQueryNode
from workflows.google_ads_report_nodes.teams_delivery_node import TeamsDeliveryNode


class GoogleAdsReportWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        description="Daily Google Ads performance report for SOP (UK)",
        event_schema=GoogleAdsReportEventSchema,
        start=SnowflakeQueryNode,
        nodes=[
            NodeConfig(node=SnowflakeQueryNode, connections=[ProcessingNode]),
            NodeConfig(node=ProcessingNode, connections=[NarrativeNode]),
            NodeConfig(node=NarrativeNode, connections=[TeamsDeliveryNode]),
            NodeConfig(node=TeamsDeliveryNode, connections=[]),
        ],
    )
