# Workflow System - Key Insights

## Architecture Pattern

The workflow system implements **Chain of Responsibility** where nodes process `TaskContext` sequentially. The `Workflow` class acts as orchestrator, not participant.

## Critical Execution Details

### Node Instantiation

**Nodes are instantiated fresh on each execution** (`workflow.py:146`). This ensures statelessness but means you cannot store state in node instance variables between executions.

### Router Execution  

Routers have a **two-phase execution**:

1. Their `process()` method is NEVER called (`workflow.py:145`)
2. Only their `route()` method executes to determine the next node

This is why BaseRouter can have an empty `process()` implementation.

### Concurrent Nodes

When `concurrent_nodes` is specified in NodeConfig, those nodes execute **in parallel with the main node**, not instead of it. All must complete before the workflow proceeds to connections.

## Non-Obvious Behaviors

### TaskContext Metadata

- The entire `self.nodes` dict is stored in `task_context.metadata["nodes"]` during execution
- This is **removed after execution completes** (`workflow.py:151`)
- Useful for nodes to inspect the workflow structure at runtime

### Event Validation Timing

Event validation against the Pydantic schema happens **after** TaskContext creation but **before** any node execution (`workflow.py:134`). The raw event is replaced with the validated model.

### Node Results Storage

Nodes must explicitly call `task_context.update_node()` to store results. There's no automatic capture of return values or node state.

### Workflow Termination

Setting `task_context.should_stop = True` doesn't immediately halt execution - the current node completes first. The check happens at the start of each iteration.

## Validation Constraints

1. **DAG Enforcement**: Uses DFS with recursion stack. A node appearing twice in the schema causes a cycle error, even if connections don't create a loop.

2. **Router Connection Rule**: Non-router nodes with >1 connection fail validation. This is checked even if those connections are never used.

3. **Start Node Reachability**: The start node must appear in the nodes list, not just as the start attribute.

## Common Pitfalls

### Missing Terminal Nodes

Forgetting `connections=[]` for terminal nodes causes validation errors about unreachable nodes.

### Router Without is_router

Having multiple connections without `is_router=True` fails validation, even if the node inherits from BaseRouter.

### Concurrent Node Dependencies

Concurrent nodes cannot depend on each other's results - they run in true parallel, not sequentially.

### Router Route Order

In BaseRouter, routes are evaluated sequentially. First match wins. The fallback only executes if NO route matches.

### Event Mutation

The original event is replaced with the Pydantic model instance. Any dict-specific operations will fail after validation.

## Design Rationale

### Why Fresh Node Instances?

Prevents state leakage between workflow executions and makes nodes inherently thread-safe.

### Why Skip Router process()?

Routers make decisions, not transformations. Skipping process() enforces this separation of concerns.

### Why Remove nodes from metadata?

Prevents circular references when serializing TaskContext and reduces memory footprint of results.

### Why Validate as DAG?

Ensures predictable execution flow and prevents infinite loops. The workflow must eventually terminate.

## Extension Patterns

**Multi-path Processing**: Use routers for branching logic  
**Parallel Validation**: Use concurrent_nodes for independent checks  
**Checkpointing**: Store intermediate state in task_context.nodes  
**Early Exit**: Use task_context.stop_workflow() with clear reason  
**Error Recovery**: Implement retry logic in router decisions  

## Integration Gotchas

- `run()` creates a new event loop - use in sync contexts only
- `run_async()` requires existing event loop - use in async contexts
- Node execution logs are automatic - don't duplicate logging
- Workflow validation happens at instantiation, not execution
