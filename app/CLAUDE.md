# Application Architecture - System Insights

## Core Application Pattern

This is an **event-driven workflow orchestration system** that implements an "accept-and-delegate" architecture:

1. **HTTP API** accepts events synchronously (FastAPI)
2. **Database** persists events immediately (PostgreSQL + SQLAlchemy)
3. **Worker** processes events asynchronously (Celery)
4. **Workflows** execute business logic (Chain of Responsibility)

## Data Flow Architecture

### Event Lifecycle

```txt
API Endpoint → Database (Event) → Celery Queue → Worker Task → Workflow → Database (TaskContext)
```

Key insight: **Events are immutable once stored**. Processing results are stored separately in `task_context` field.

### Workflow Selection

- `WorkflowRegistry` enum maps workflow types to classes
- `get_workflow_type()` in endpoint determines routing
- Currently hardcoded to PLACEHOLDER - **extend here for multi-workflow support**

## Key Architectural Decisions

### 1. Sync Accept, Async Process

- API returns 202 immediately after queueing
- No synchronous workflow execution in API layer
- Ensures API availability under load

### 2. Event Storage Pattern

- Raw events stored as JSON (flexible schema)
- Processing results stored separately
- Enables event replay and debugging

### 3. Workflow Registration

- Enum-based registry (type-safe)
- Each workflow type maps to a class
- No dynamic registration - **compile-time safety**

### 4. Schema Validation Layers

1. **API Layer**: Pydantic models validate incoming events
2. **Workflow Layer**: Event schema re-validated before processing
3. **Node Layer**: Individual nodes validate their inputs/outputs

## Directory Responsibilities

- **api/**: HTTP interface only - no business logic
- **worker/**: Task orchestration - retrieves events, invokes workflows
- **workflows/**: Concrete workflow implementations
- **database/**: Persistence layer with generic repository pattern
- **schemas/**: Shared Pydantic models for validation
- **services/**: Cross-cutting concerns (prompt management)
- **prompts/**: Jinja2 templates with frontmatter metadata

## Extension Points

### Adding New Workflows

1. Create workflow class in `workflows/`
2. Add to `WorkflowRegistry` enum
3. Implement `get_workflow_type()` logic
4. Create corresponding schema in `schemas/`

### Adding New Nodes

1. Create node classes in workflow-specific subdirectory
2. Nodes are workflow-specific, not shared
3. Use `workflows/placeholder_workflow_nodes/` as template

### Database Migrations

- Alembic manages schema changes
- `makemigration.sh` generates migrations
- `migrate.sh` applies them
- **Critical**: Don't modify existing migrations

## Non-Obvious Behaviors

### Worker Context Management

- Database session created per task execution
- Commits happen automatically on task completion
- Rollback on exceptions - event remains unprocessed

### Prompt Management

- Templates support frontmatter for metadata
- Singleton Jinja2 environment
- StrictUndefined enforces all variables provided
- Templates in `prompts/` directory

### Event Type Routing

- Currently single workflow (PLACEHOLDER)
- `workflow_type` field determines routing
- Stored with event for audit trail
