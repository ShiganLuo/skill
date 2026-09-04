---
name: development-runtime-orchestration
description: >-
  Use when local debugging needs Docker-managed infra only.
tags: [development, docker, scripts, local-debugging, verification]
related_skills: [safe-file-editing, full-stack-project-scaffolding]
---

# Development Runtime Orchestration

## When to use
- A full-stack repo already has Docker Compose for all services, but local debugging needs only infrastructure dependencies such as MySQL, Redis, MQ, MinIO, etc.
- The user asks for a "debug startup script" or says the project lacks a script for non-source services.
- You need to add or extend a deploy/startup wrapper without replacing the existing app launch workflow.

## Core pattern
Prefer extending the repo's existing deploy/startup entrypoint if one already exists (for example `docker-deploy.sh`) instead of creating a brand-new parallel script.

Typical goal:
- Docker manages infra dependencies
- backend/frontend source code is started locally by the developer
- the script clearly separates `full start` from `dependency-only debug start`

## Recommended workflow
1. Read the current wrapper script and `docker-compose.yml` first.
2. Identify which services are true infra dependencies versus source-built app services.
3. Add a dedicated command such as `debug`, `deps`, or `dev` that starts only infra services.
4. Keep the existing `start`/`rebuild` behavior unchanged unless the user asked otherwise.
5. Print the exact local connection targets after startup:
   - host/port for DB, Redis, MQ, etc.
   - reminder that backend/frontend should be run from source
   - if relevant, note which Spring/Vite/profile/env mode should be used locally
6. Update `help` output and top-of-file usage comments in the same change.

## Command design guidance
Good dependency-only commands look like:
- `docker compose up -d mysql redis`
- `docker compose up -d db redis minio`

Avoid making the dependency-only command also start backend/frontend containers unless the user explicitly wants a full containerized run.

## Verification pattern for startup scripts
When the changed branch would start real containers or mutate services, do targeted ad-hoc verification instead of pretending you ran the whole environment:

1. Syntax check
   - Shell: `bash -n script.sh`
2. Help output check
   - Verify the new command appears in `./script.sh help`
3. Safe behavior verification with a stub dependency
   - Put a stub `docker` binary earlier in `PATH`
   - Run the new command
   - Assert the exact `docker compose ...` invocation happened
   - Assert user-facing output includes the expected local endpoints
4. Report this honestly as `ad-hoc verification`, not as a full integration pass

This is the right trade-off when the task is to validate script wiring rather than to boot and test the whole stack.

## Pitfalls
- Creating a second script when the repo already has one canonical startup wrapper
- Starting app containers in the dependency-only path, defeating local source debugging
- Forgetting to update `help` output after adding the new command
- Claiming a stubbed verification is equivalent to an end-to-end environment test
- Hardcoding advice that conflicts with the repo's actual local ports or profiles

## Reference Files
- `references/spring-boot-mysql-connection-timeout.md` — MySQL SocketTimeoutException diagnosis and HikariCP pool tuning

## Output expectations
When finished, report:
- which script was changed
- the new command name
- which services it starts
- whether verification was full integration or targeted ad-hoc script verification
