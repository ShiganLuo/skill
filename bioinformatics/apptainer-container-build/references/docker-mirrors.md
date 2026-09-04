# Chinese Docker Mirror Registry (for container builds)

EnvUtil.py uses Docker mirrors for Apptainer/Docker container builds. These mirrors can go down or become slow.

## Current mirror (as of 2026-09)
- `docker.1ms.run` (毫秒镜像) - recommended

## Fallback mirrors
- `docker.xuanyuan.me` (轩辕镜像)
- `docker.hlmirror.com` (厚浪镜像)
- `docker-0.unsee.tech`
- `docker.m.daocloud.io` (DaoCloud - can have TLS timeout issues)

## Where to update in EnvUtil.py

Mirror is configured in the `BACKENDS` dictionary (not separate constants):
```python
BACKENDS = {
    "micromamba": {"apptainer_from": "docker.1ms.run/mambaorg/micromamba:latest", ...},
    "mamba":      {"apptainer_from": "docker.1ms.run/condaforge/miniforge3:latest", ...},
    "conda":      {"apptainer_from": "docker.1ms.run/condaforge/miniforge3:latest", ...},
    "uv":         {"apptainer_from": "docker.1ms.run/python:3.11-slim", ...},
}
```

To change mirror: update all `apptainer_from` and `docker_from` values in BACKENDS.

**Alternative base images**:
- `mambaorg/micromamba:latest` — fastest, smallest (~30 MB), recommended
- `condaforge/miniforge3:latest` — traditional, larger (~300 MB)

## Symptoms of mirror failure
- `TLS handshake timeout` → mirror is slow/down, try another
- `429 Too Many Requests` → rate limited, wait or switch
- `connection refused` → mirror is down

## When to update
- When build fails with network errors
- When user reports slow builds
- Periodically check if current mirror is still responsive
