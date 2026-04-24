from pathlib import Path

from core.nodes.base import Node
from core.task import TaskContext


class WriteReportsNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        reports_dir = Path("app/reports")
        reports_dir.mkdir(exist_ok=True)

        latest_date = task_context.nodes["ClassifyAndProcessNode"]["dates"]["latest"]
        wl_path = reports_dir / f"report_wl_{latest_date}.md"
        nonwl_path = reports_dir / f"report_nonwl_{latest_date}.md"

        wl_path.write_text(
            task_context.nodes["GenerateWLReportNode"]["report_markdown"],
            encoding="utf-8",
        )
        nonwl_path.write_text(
            task_context.nodes["GenerateNonWLReportNode"]["report_markdown"],
            encoding="utf-8",
        )

        print(f"\nReports written:")
        print(f"  {wl_path}")
        print(f"  {nonwl_path}")

        task_context.update_node(
            self.node_name,
            wl_path=str(wl_path),
            nonwl_path=str(nonwl_path),
        )
        return task_context
