# GenAI Launchpad Project Guide

## Project Overview

An event-driven workflow orchestration system for building AI-powered applications. Events are accepted via API, persisted to database, and processed asynchronously through configurable workflows composed of AI agent nodes.

## Directory Structure & Documentation

**IMPORTANT**: When working in any directory, read its CLAUDE.md file first:

- `app/CLAUDE.md` - Application architecture and data flow
- `app/core/CLAUDE.md` - Workflow system mechanics  
- `app/core/nodes/CLAUDE.md` - Node implementation patterns
- `docker/CLAUDE.md` - Container setup and database connection

## Project Conventions

### Import Style

- Absolute imports from app root: `from core.nodes.base import Node`
- No relative imports between modules
- Group imports: stdlib, third-party, local

### Naming Conventions

- **Workflows**: `{Domain}Workflow` (e.g., `CustomerSupportWorkflow`)
- **Nodes**: `{Action}Node` (e.g., `AnalyzeRequestNode`)
- **Routers**: `{Decision}Router` (e.g., `PriorityRouter`)
- **Schemas**: `{Domain}EventSchema` (e.g., `SupportEventSchema`)

### File Organization

- Workflow-specific nodes in subdirectories: `workflows/{workflow_name}_nodes/`
- One class per file for nodes
- Workflows register in `WorkflowRegistry` enum

### Environment Variables

- **Docker services**: Use `docker/.env` (database, project name, LLM keys)
- **Local development**: Use `app/.env` if running outside Docker
- Database config uses `${PROJECT_NAME}` prefix
- No hardcoded secrets in code

## Development Workflow

1. **Start Services**: `cd docker && ./start.sh`
2. **Create Workflow**: Add to `app/workflows/`
3. **Register Workflow**: Update `WorkflowRegistry`
4. **Define Schema**: Add to `app/schemas/`
5. **Implement Nodes**: Create in workflow subdirectory
6. **Test Locally**: POST to `http://localhost:8080/events/`

## Key Design Principles

- **Stateless Nodes**: No state between executions
- **Type Safety**: Pydantic models everywhere
- **Async First**: All I/O operations async
- **Fail Fast**: Validate early, error clearly
- **Event Immutability**: Never modify stored events

## Extension Points

- **New Workflow**: Create class, add to registry
- **New Node Type**: Extend `Node` or `AgentNode`
- **New Provider**: Add to `ModelProvider` enum
- **New Schema**: Create Pydantic model in schemas/

## Quick Reference

### Running Locally

```bash
cd docker && ./start.sh          # Start all services
docker logs -f genai_api         # View API logs
docker logs -f genai_celery_worker # View worker logs
```

### Testing Workflow

```bash
curl -X POST http://localhost:8080/events/ \
  -H "Content-Type: application/json" \
  -d '{"data": "test"}'
```

### Database Access

```bash
docker exec -it supabase-db psql -U postgres -d postgres
```

## Critical Gotchas

1. **Network Not Found**: Use `docker/start.sh`, not direct compose
2. **Import Errors**: Ensure absolute imports from app root
3. **Node Not Storing Results**: Must call `task_context.update_node()`
4. **Workflow Not Found**: Add to `WorkflowRegistry` enum
5. **Provider Auth Failed**: Check `.env` for required keys
