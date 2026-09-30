# Docker Mirror Diagnostic (CN Network)

## Symptom

`apptainer build --fakeroot` fails during `INFO: Fetching OCI image...` with
errors like:
```
FATAL: While performing build: conveyor failed to get: stream error:
  stream ID 23; INTERNAL_ERROR; received from peer
```
or
```
FATAL: While performing build: conveyor failed to get: reading digest latest in
  <mirror>/<repo>: StatusCode: 403, ""
```

Both are upstream Docker registry mirror failures, NOT a def file problem.

## Why

CN-friendly mirrors in EnvUtil default config:
- `docker.1ms.run` (default): often streams-corrupt mid-download
- `docker.m.daocloud.io`: returns HTTP 401 (needs token auth apptainer can't perform)

Empirically the **only mirror that reliably returns `200 OK` for arbitrary repos
including `mambaorg/micromamba:latest`** in this CN environment is
**`dockerproxy.net`**.

## Mirror availability matrix (tested 2026-09-17)

| Mirror                             | mambaorg/micromamba | Notes                    |
|------------------------------------|---------------------|--------------------------|
| docker.1ms.run                     | 401 (default fails) | Needs token              |
| docker.m.daocloud.io               | 401 / 403           | Needs token              |
| **dockerproxy.net**                | **200 ✓**           | **Use this**             |
| docker.ketches.cn                  | 502                 | Unreliable               |
| docker.mirrors.ustc.edu.cn         | DNS NXDOMAIN        | Not available            |
| hub-mirror.c.163.com               | DNS NXDOMAIN        | Not available            |
| mirror.baidubce.com                | DNS NXDOMAIN        | Not available            |

## Fix in EnvUtil.py (already applied)

1. `BACKENDS` defaults: `docker.1ms.run` → `dockerproxy.net` for all 4 backends
   (micromamba / mamba / conda / uv) + `DOCKER_FROM` + `UV_FROM`.
2. `_diagnose_build_mirror()` probes configured mirror + 7 known alternatives
   before every `apptainer build`, logs `✓`/`✗` with HTTP status, and
   auto-patches the def file to the first working mirror if the configured
   one fails. Also clears stale `~/.apptainer/cache/blob` (often hundreds
   of MB of corrupt partial downloads).
3. `_run_streaming()` captures full subprocess output and on failure
   re-emits the last 60 lines at ERROR level plus dumps full output to
   `<cwd>/apptainer_build_failure.log`.

## Workaround if `dockerproxy.net` itself goes down

Run the probe directly to find a live mirror:
```bash
python -c "
import sys; sys.path.insert(0, '<repo>/workflow/Omics/src/common/util')
from EnvUtil import EnvUtil
for m in ['dockerproxy.net', 'docker.1ms.run', 'docker.m.daocloud.io']:
    ok, d = EnvUtil.probe_registry_mirror(m, repo='mambaorg/micromamba', timeout=4)
    print(f'{m}:', ok, d)
"
```

Then manually edit the def:
```
sed -i 's|From: .*|From: <working-mirror>/mambaorg/micromamba:latest|' function.def
```

## Cache hygiene

Partial failed pulls leave hundreds of MB in `~/.apptainer/cache/blob`.
Always clear before retrying with a different mirror:
```bash
rm -rf ~/.apptainer/cache/blob ~/.apptainer/cache/oci-tmp
```
Or use EnvUtil's auto-clean (added in `_diagnose_build_mirror`).
