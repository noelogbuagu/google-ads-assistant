import os

from core.nodes.agent import AgentNode, AgentConfig, ModelProvider
from core.task import TaskContext
from services.prompt_loader import PromptManager
from workflows.google_ads_workflow_nodes.generate_wl_report_node import _format_prompt


class GenerateNonWLReportNode(AgentNode):

    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            model_provider=ModelProvider.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            output_type=str,
            instructions=PromptManager.get_prompt(
                "report_generation",
                cpa_target=os.getenv("CPA_TARGET_USD", "500"),
            ),
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        print("Generating Non-Weight Loss report...")
        data = task_context.nodes["ClassifyAndProcessNode"]
        user_prompt = _format_prompt(
            segment="Non-Weight Loss (Non-WL)",
            campaigns=data["nonwl_campaigns"],
            aggregates=data["nonwl_aggregates"],
            dates=data["dates"],
        )
        result = await self.agent.run(user_prompt)
        task_context.update_node(self.node_name, report_markdown=result.output)
        return task_context
