# Docker Compose dependency-only startup verification

Use this reference when adding a `debug`/`deps` command to an existing startup wrapper.

## Safe verification recipe

Goal: verify script wiring without actually starting project containers.

1. Syntax-check the shell script
   - `bash -n ./docker-deploy.sh`
2. Verify the new command is listed in help
   - `bash ./docker-deploy.sh help`
3. Stub the `docker` executable via `PATH`
   - create a temporary directory
   - add an executable named `docker`
   - have it assert the expected argv, e.g. `compose up -d mysql redis`
4. Run the new command with the stubbed PATH
5. Assert user-facing output still includes the intended local endpoints and guidance

## Why this matters
A real `docker compose up` is not always appropriate during code-review or script-only changes. Stubbed verification proves:
- the command branch is reachable
- the script invokes the expected compose subcommand
- the user-facing help text and output are updated

It does NOT prove the full environment boots successfully, so report it as ad-hoc verification rather than integration testing.
