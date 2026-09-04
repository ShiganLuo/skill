# Docker Deploy Script Template

When creating a new full-stack project, always generate a `docker-deploy.sh` alongside `docker-compose.yml`. Reference the user's existing projects for style consistency.

## Script Pattern

The script must support these commands (in priority order):

| Command | Action |
|---------|--------|
| `start` | `docker compose up -d` — start all services |
| `debug` | Start only infra dependencies (MySQL/Redis/MinIO) for local source debugging |
| `stop` | `docker compose down` |
| `restart` | `docker compose restart` |
| `rebuild` | `docker compose build --no-cache && docker compose up -d` |
| `logs [service]` | `docker compose logs -f [service]` |
| `status` | `docker compose ps` + `docker stats --no-stream` |
| `init` | First-time setup: check Docker installed, create data dirs, build, start, wait for DB |
| `help` | Usage text |

## Key Elements

1. **Color output**: RED/GREEN/YELLOW/BLUE + NC for info/success/warning/error
2. **Service URLs**: Print access URLs after start (frontend, admin, API, DB, Redis, MinIO)
3. **Debug mode**: List the exact connection strings (host:port, credentials) for local dev
4. **Init mode**: Check Docker/Compose installed, create persistent data directories, build images, start, wait for DB readiness
5. **Help**: Show all commands with descriptions

## Extraction from docker-compose.yml

When adapting the template for a new project, extract from docker-compose.yml:
- Service names (for `debug` command: `docker compose up -d <infra services>`)
- Port mappings (for URL display: `localhost:<host_port>`)
- Credentials from environment variables (for debug/init output)
- Volume paths (for `mkdir -p` in init command)

## Verification

```bash
chmod +x docker-deploy.sh
bash -n docker-deploy.sh    # syntax check
./docker-deploy.sh help     # runtime check
./docker-deploy.sh status   # functional check (requires running containers)
```

## User Convention

User expects all their projects to have this script. After creating docker-compose.yml, ALWAYS create docker-deploy.sh in the same step. The script should be self-contained (no external dependencies beyond Docker).
