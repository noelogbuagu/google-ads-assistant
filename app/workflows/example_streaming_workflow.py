from core.schema import WorkflowSchema, NodeConfig
from core.workflow import Workflow
from schemas.openai_schema import OpenAIChatSchema
from workflows.example_streaming_workflow_nodes.structured_streaming_node import (
    StructuredStreamingNode,
)
from workflows.example_streaming_workflow_nodes.text_streaming_node import (
    TextStreamingNode,
)


class ExampleStreamingWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        description="",
        event_schema=OpenAIChatSchema,
        start=TextStreamingNode,
        nodes=[
            NodeConfig(
                node=TextStreamingNode,
                connections=[StructuredStreamingNode],
                description="",
            ),
            NodeConfig(
                node=StructuredStreamingNode,
                connections=[],
                description="",
            ),
        ],
    )
