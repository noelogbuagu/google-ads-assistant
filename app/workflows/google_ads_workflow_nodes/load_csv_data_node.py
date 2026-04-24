from core.nodes.base import Node
from core.task import TaskContext
from services.csv_loader import CSVLoader


class LoadCSVDataNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        print("Loading CSV data...")
        loader = CSVLoader()
        data = loader.load_csvs(task_context.event.data_dir)

        print(
            f"  Loaded: {data['oldest']['date']} | "
            f"{data['mid']['date']} | "
            f"{data['latest']['date']}"
        )

        task_context.update_node(self.node_name, **data)
        return task_context
