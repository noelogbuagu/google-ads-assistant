from enum import Enum

from workflows.example_streaming_workflow import ExampleStreamingWorkflow


class WorkflowRegistry(Enum):
    EXAMPLE_STREAMING_WORKFLOW = ExampleStreamingWorkflow
