# Fibertools-rs Container Build Recipe

## Problem

bioconda's `fibertools-rs` package (all versions) does NOT include the pytorch backend. Without pytorch, `ft predict-m6a` fails on Revio chemistry (BINDINGKIT=103-496-900) and other newer PacBio kits.

Building from source with `cargo install fibertools-rs --all-features` requires:
- Rust toolchain (from conda: `rust>=1.75`)
- C/C++ compiler (from conda: `gcc_linux-64>=12`, `gxx_linux-64>=12`)
- libtorch with C++ headers (from pip `torch` — conda's `libtorch` and `pytorch::pytorch-cpu` both lack C++ headers)
- OpenSSL development headers (from conda `openssl` package)

## YAML (working recipe — pip for torch)

```yaml
name: fibertools
channels:
  - conda-forge
  - bioconda
  - defaults
dependencies:
  - rust>=1.75
  - gcc_linux-64>=12
  - gxx_linux-64>=12
  - python>=3.10
  - pip
  - samtools>=1.18
  - pbmm2>=2.0.0
```

**Why no conda pytorch?** Conda's `libtorch` package lacks C++ headers (`torch/torch.h`). `pytorch::pytorch-cpu` from the pytorch channel installs headers but was abandoned because: (a) it pulls CUDA deps even with `cpuonly`, (b) the `pytorch` channel conflicts with bioconda resolution. Pip's `torch` CPU-only wheel includes all headers and is isolated from conda conflicts.

## .post.sh (working recipe)

```bash
set +euo pipefail
export PATH="/opt/conda/envs/fibertools/bin:$PATH"
export CC=x86_64-conda-linux-gnu-gcc
export CXX=x86_64-conda-linux-gnu-g++

# Source conda activation scripts (sets PKG_CONFIG_PATH, CPATH, etc.)
for f in /opt/conda/envs/fibertools/etc/conda/activate.d/*.sh; do
    source "$f" 2>/dev/null || true
done

# Install CPU-only PyTorch via pip (includes C++ headers)
pip install --no-cache-dir torch==2.9.0 --index-url https://download.pytorch.org/whl/cpu

# Set LIBTORCH from installed torch
export LIBTORCH=$(python3 -c "import os, torch; print(os.path.dirname(torch.__file__))")
export LD_LIBRARY_PATH="${LIBTORCH}/lib:${LD_LIBRARY_PATH:-}"
export LIBTORCH_CXX11_ABI=1
export CARGO_HOME=/opt/conda/.cargo
export CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=x86_64-conda-linux-gnu-gcc
export OPENSSL_DIR=/opt/conda/envs/fibertools
export OPENSSL_NO_VENDOR=1
set -e
cargo install fibertools-rs --all-features --version ">=0.13.0"
cp ${CARGO_HOME}/bin/ft /opt/conda/envs/fibertools/bin/ft
ft --version

# Persist LD_LIBRARY_PATH for runtime (Apptainer auto-sources /.singularity.d/env/)*
mkdir -p /.singularity.d/env
echo "export LD_LIBRARY_PATH=\"${LIBTORCH}/lib:\${LD_LIBRARY_PATH:-}\"" >> /.singularity.d/env/99-fibertools.sh
# Also write to conda activation for non-Apptainer use
echo "export LD_LIBRARY_PATH=\"${LIBTORCH}/lib:\${LD_LIBRARY_PATH:-}\"" >> /etc/profile.d/conda_fibertools.sh
rm -rf ${CARGO_HOME}/registry ${CARGO_HOME}/git
```

**Key notes:**
- `torch==2.9.0` is the oldest version on the CPU-only index. Versions <2.9.0 are not available there.
- `LIBTORCH_CXX11_ABI=1` (NOT 0) — pip torch uses the new C++ ABI. Using 0 causes `undefined reference to c10::detail::torchInternalAssertFail`.
- Torch 2.9.0+ requires C++17 (not C++20). If using a newer torch version, check if it requires C++20 — `torch-sys` passes `-std=c++17` and won't compile with C++20-only headers.
- `LIBTORCH` path is dynamic (`python3 -c "..."`) because the Python version in the container may vary.
- Do NOT use `rm -rf /tmp/*` — `/tmp` is bind-mounted from the host in Apptainer, causes `Operation not permitted`.

## Build command

```bash
python workflow/Omics/src/common/util/EnvUtil.py apptainer all \
    -y workflow/Omics/modules/fibertools/fibertools.yaml \
    -o /home/<USER>/Database/env/fibertools --force
```

SIF ends up at `<output_dir>/fibertools/fibertools.sif` (EnvUtil creates a subdirectory). Move to expected location if needed:
```bash
mv <output_dir>/fibertools/fibertools.sif <output_dir>/fibertools.sif
```

## EnvUtil bugs (fixed 2026-09-19)

Two bugs in `src/common/util/EnvUtil.py` prevented `.post.sh` from executing:

### 1. ENDOFSCRIPT indentation (line 835)

The heredoc closing marker `ENDOFSCRIPT` was indented with 4 spaces. Bash `<<` requires the delimiter at column 0. With indentation, the heredoc never closes — everything after `micromamba env create` becomes part of the heredoc content but is never executed.

**Fix:** Change `    ENDOFSCRIPT` to `ENDOFSCRIPT` (no leading spaces) on line 835 and 908.

### 2. micromamba stdin consumption (line 798)

`micromamba env create` reads from stdin when inside a heredoc. It consumes ALL remaining lines of the heredoc, so nothing after it executes. No error is produced.

**Fix:** Add `< /dev/null` to the micromamba command:
```python
install_cmd = f"""    export MAMBA_ROOT_PREFIX="/opt/conda"
    micromamba env create -f /opt/conda/{yaml_filename} < /dev/null && \
```

### Debugging heredoc issues

If `.post.sh` content doesn't appear in the build log:
1. Check `ENDOFSCRIPT` is at column 0: `grep -n "ENDOFSCRIPT" modules/fibertools/fibertools.def`
2. Check for stdin consumption: add `echo "TEST MARKER"` before and after suspected commands
3. Minimal test: create a .def with just `echo "HELLO"` inside the heredoc to verify the mechanism works
4. Check the failure log: `cat modules/fibertools/apptainer_build_failure.log`

## Environment variables explained

| Variable | Why |
|---|---|
| `CC=x86_64-conda-linux-gnu-gcc` | conda gcc_linux-64 binary name (not `cc`) |
| `CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER` | Tells cargo to use conda's gcc as linker (default `cc` not found) |
| `LIBTORCH_CXX11_ABI=1` | Match pip torch's ABI (new ABI). Using 0 causes linker errors. |
| `OPENSSL_DIR` | Points to conda env's openssl (cargo can't find it otherwise) |
| `OPENSSL_NO_VENDOR=1` | Don't try to build openssl from source |
| `set +euo pipefail` at start | Source activation scripts may have non-fatal errors; `set -e` re-enabled before cargo |

## Common build failures

| Error | Cause | Fix |
|---|---|---|
| `linker 'cc' not found` | Missing `CARGO_TARGET_*_LINKER` | Set `CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=x86_64-conda-linux-gnu-gcc` |
| `torch/torch.h: No such file` | libtorch lacks C++ headers | Use `pip install torch` instead of conda libtorch |
| `C++20 or later required` | torch version too new for torch-sys C++17 | Pin `torch==2.9.0` (oldest on CPU index) |
| `undefined reference to c10::*` | ABI mismatch | Set `LIBTORCH_CXX11_ABI=1` (not 0) for pip torch |
| `rm: cannot remove /tmp/*: Operation not permitted` | `/tmp` bind-mounted from host | Remove `rm -rf /tmp/*` from cleanup |
| Build succeeds but ft not in SIF | .post.sh never ran (heredoc issue) | Check ENDOFSCRIPT indentation + micromamba stdin |