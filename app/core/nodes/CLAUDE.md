# Node Implementation - Key Insights

## Node Base Classes

### Node (base.py)

- **Fresh instantiation**: Nodes are created anew for EACH workflow execution
- `node_name` property auto-derives from class name (e.g., `AnalyzeNode` → "AnalyzeNode")
- Must implement `async process(task_context) -> TaskContext`
- Results MUST be stored via `task_context.update_node()` - no automatic capture

### BaseRouter (router.py)

- **process() is NEVER called** - only `route()` executes
- `route()` returns the next Node instance (not class)
- Routes evaluated sequentially - first match wins
- `fallback` only used if NO route matches (can be None)
- Empty `process()` implementation is expected and correct

### RouterNode (router.py)

- Helper class for individual routing rules
- `determine_next_node()` returns Node instance or None
- None means "this route doesn't apply, try next"

## AgentNode Deep Dive

### Architecture

`AgentNode` wraps pydantic_ai's `Agent` class, providing:

- Multi-provider LLM support (OpenAI, Anthropic, Gemini, Bedrock, Ollama)
- Type-safe input/output with Pydantic models
- Built-in retry logic and error handling
- Tool registration and execution
- Structured output enforcement

### Key Implementation Details

1. **Agent Creation Timing**
   - Agent instance created in `__init__`, NOT in `process()`
   - This means Agent exists for workflow lifetime, but Node is recreated
   - HttpClient (`__async_client`) persists across calls within one workflow

2. **Model Resolution**
   - Models resolved via provider-specific methods
   - Environment variables required for providers:
     - Ollama: `OLLAMA_BASE_URL`
     - Bedrock: `BEDROCK_AWS_ACCESS_KEY_ID`, `BEDROCK_AWS_SECRET_ACCESS_KEY`, `BEDROCK_AWS_REGION`
   - Falls back to OpenAI GPT-4.1 if provider unknown

3. **Type System**
   - `DepsType`: Dependencies injected into agent tools
   - `OutputType`: Validated output structure
   - Both default to BaseModel but should be overridden

### pydantic_ai Agent Internals

1. **Run Execution**
   - `run()` creates new event loop - sync contexts only
   - `run_async()` uses existing loop - async contexts
   - Builds internal graph for each run
   - Tools execute in dependency order

2. **Output Validation**
   - Output type validated AFTER model response
   - Can use `ToolOutput` for custom validation logic
   - Retries on validation failure up to `output_retries`

3. **Tool Execution**
   - Tools can be sync or async functions
   - Access to `RunContext` with model info, retry count
   - Tools can raise exceptions to trigger retries

## Non-Obvious Behaviors

### Node State Management

- Instance variables in nodes DON'T persist between workflow runs
- Use `task_context.metadata` for workflow-level state
- Use `task_context.nodes[self.node_name]` for node results

### Router Decision Making

- Router's `route()` called with current TaskContext
- Can inspect ALL previous node results via `task_context.nodes`
- Router itself doesn't modify TaskContext

### AgentNode Considerations

- Agent instance persists within workflow execution
- Model selection happens at Agent creation, not runtime
- Tools registered at Agent creation can't be modified
- Agent's internal graph rebuilt for each `process()` call

## Common Implementation Patterns

### Basic Processing Node

```python
class AnalyzeNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        # Always update context with results
        task_context.update_node(
            self.node_name,
            analysis=result,
            confidence=0.95
        )
        return task_context
```

### Router with Multiple Routes

```python
class PriorityRouter(BaseRouter):
    def __init__(self):
        self.routes = [
            HighPriorityRoute(),
            MediumPriorityRoute()
        ]
        self.fallback = LowPriorityHandler()
```

### AgentNode with Custom Types

```python
class SmartAnalyzer(AgentNode):
    class DepsType(BaseModel):
        database: Database
        cache: Cache
    
    class OutputType(BaseModel):
        category: str
        confidence: float
        reasoning: str
    
    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            model_provider=ModelProvider.ANTHROPIC,
            model_name="claude-3-5-sonnet-latest",
            output_type=self.OutputType,
            deps_type=self.DepsType,
            instructions="Analyze and categorize the input"
        )
```

## Critical Gotchas

1. **No State Between Runs**: Node instances don't persist
2. **Router process() Skip**: Don't put logic in router's process()
3. **Result Storage**: Must explicitly call update_node()
4. **Agent Creation**: Happens in **init**, not process()
5. **Environment Dependencies**: Provider-specific env vars required
6. **Type Inference**: Agent generics affect tool signatures

## Design Philosophy

- **Nodes are stateless functions**: Think functional, not OOP
- **Routers are decision points**: No data transformation
- **Agents are LLM wrappers**: Heavy lifting via pydantic_ai
- **Context carries state**: All data flows through TaskContext
