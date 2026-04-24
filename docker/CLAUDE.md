# Docker Infrastructure - Key Insights

## Critical Setup Requirements

### Network Creation

**Must use `start.sh`**, not direct `docker-compose up`. The script creates an external network that prevents Docker from appending random suffixes:

```bash
docker network create ${PROJECT_NAME}_network
```

Without this, services can't find each other.

### Build Context

```yaml
build:
  context: ..  # Parent directory, NOT docker/
  dockerfile: docker/Dockerfile.api
```

Context must be parent directory to access `pyproject.toml` and `app/`.

## Database Connection

### From Application Code

- Host: `db` (service name)
- Port: `5432`
- User: `postgres` (hardcoded)
- Password: `${POSTGRES_PASSWORD}`
- Database: `${POSTGRES_DB}`

### Direct Access

```bash
docker exec -it supabase-db psql -U postgres -d ${POSTGRES_DB}
```

### SQL Script Execution Order

Files in `volumes/db/` run by numeric prefix:

- `97-*.sql`: Base tables
- `98-*.sql`: Superuser operations
- `99-*.sql`: Application setup

Order matters - later scripts depend on earlier ones.

## Non-Obvious Behaviors

### Celery Auto-Reload

```bash
watchmedo auto-restart --directory=./ --pattern='*.py' --recursive -- celery...
```

Worker auto-restarts on Python changes. Requires `watchdog` package.

### Kong Configuration

```yaml
entrypoint: bash -c 'eval "echo \"$$(cat ~/temp.yml)\"" > ~/kong.yml && /docker-entrypoint.sh kong docker-start'
```

Templates config at runtime using shell evaluation - allows environment variable substitution.

### Volume Persistence

- `db_data`: Postgres data
- `db_config`: Encryption keys (pgsodium)
- Both survive container removal

## Common Issues

1. **"network not found"**: Run `./start.sh` first
2. **Database not ready**: Services use `condition: service_healthy`, not just `depends_on`
3. **Permission denied in worker**: Celery runs as non-root user, needs ownership
4. **Port already in use**: All ports bind to `127.0.0.1:` for local-only access
