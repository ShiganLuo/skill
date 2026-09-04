# Debugging Snakemake Source Code

When the project includes a local Snakemake source clone (e.g. `workflow/snakemake/`), you can debug the framework itself — not just your workflows.

## Setup: Editable Install

```bash
cd workflow/snakemake
pip install -e .   # editable mode — changes to src/snakemake/ take effect immediately
```

This allows setting breakpoints and modifying Snakemake internals without reinstalling.

## pdb/ipdb Breakpoints

Insert at the point you want to inspect:

```python
import pdb; pdb.set_trace()    # stdlib
import ipdb; ipdb.set_trace()   # friendlier (pip install ipdb)
```

Then run snakemake normally — execution pauses at the breakpoint.

**Common pdb commands:**
- `n` next line, `s` step into, `c` continue
- `p var` print variable, `bt` call stack, `l` show code location

## Key Source Entry Points

| Problem Area | File | Function/Location |
|---|---|---|
| CLI argument parsing | `cli.py` | `main()` |
| API entry point | `api.py` | `SnakemakeApi` class |
| Workflow API | `api.py` | `WorkflowApi` class (line 325) |
| Execute workflow | `api.py` | `WorkflowApi.execute_workflow()` (line 471) |
| Workflow execution | `workflow.py` | `Workflow.execute()` (line 1278) |
| Rule parsing | `rules.py` | `Rule.__init__` |
| DAG construction | `dag.py` | `DAG.init` |
| Job scheduling | `scheduling/job_scheduler.py` | `JobScheduler.schedule` |
| Local executor | `executors/local.py` | `Executor.run_job()` (line 88) |
| run_wrapper | `executors/local.py` | `run_wrapper()` (line 287) |
| Shell execution | `shell.py` | `shell.__new__()` (line 165) |
| subprocess.Popen | `shell.py` | line 320 |
| Plugin registry | `registry/` | `ExecutorPluginRegistry` |
| Settings types | `settings/types.py` | `ExecutionSettings`, `RemoteExecutionSettings` |

## API Execution Flow

```
CLI (cli.py)
  └─ SnakemakeApi.workflow()           # api.py:121 — creates WorkflowApi
       └─ WorkflowApi
            ├─ ._workflow (property)    # api.py:409 — lazy init
            │    ├─ _get_workflow()     # api.py:420 — instantiates Workflow
            │    ├─ workflow.include()  # loads Snakefile
            │    └─ workflow.check()    # validates rules
            └─ .execute_workflow()      # api.py:471
                 ├─ ExecutorPluginRegistry().get_plugin(executor)
                 ├─ validate settings
                 ├─ adjust shared_fs_usage based on executor
                 ├─ select scheduler (ilp/greedy)
                 └─ workflow.execute()  # workflow.py:1278
```

### execute_workflow key validations (api.py:471-652)

1. `immediate_submit` requires `notemp`
2. No shared FS → must configure storage provider
3. Local exec → must specify `--cores`
4. Remote exec → must specify `--jobs`, defaults to `full` resources
5. debug mode → single core, local only
6. ILP solver unavailable → fallback to greedy scheduler

### Key CLI parameters

| Parameter | Purpose |
|---|---|
| `--use-envmodules` | Load environment modules (`module load`) for rules with `envmodules:` |
| `--deploy-sources` | **Internal only** — download+extract workflow archive for remote execution |
| `--use-conda` | Use conda environments |
| `--use-apptainer` | Use Singularity/Apptainer containers |
| `--shared-fs-usage` | Control which FS operations assume shared storage |

### Local Executor: Two Execution Paths (run_wrapper vs spawn_job)

Local executor (`executors/local.py:174`) has TWO execution paths:

```python
def run_single_job(self, job):
    if (self.use_threads
        or (not job.is_shadow and not job.is_run)
        or job.is_template_engine):
        # Path 1: run_wrapper (in-thread)
        future = self.pool.submit(self.cached_or_run, job, run_wrapper, ...)
    else:
        # Path 2: spawn_job (subprocess)
        future = self.pool.submit(self.cached_or_run, job, self.spawn_job, job)
```

| Condition | Path | Function | Execution |
|---|---|---|---|
| `use_threads=True` | run_wrapper | `run()` directly | In-thread |
| Non-shadow, non-run | run_wrapper | `run()` directly | In-thread |
| template_engine | run_wrapper | `run()` directly | In-thread |
| shadow + run | spawn_job | `subprocess.check_call()` | Subprocess |

**Key insight**: `spawn_job` (line 226) calls `format_job_exec()` which generates
`python -m snakemake --snakefile ... --target-jobs ...` — it restarts a Snakemake
subprocess that eventually calls `run_wrapper` again. So **run_wrapper is the universal
convergence point** for all execution paths.

### Rule Class Execution Attributes (rules.py:125-132)

```python
self.run_func = None      # run: directive Python function
self.run_func_src = None  # run: directive source code (string)
self.shellcmd = None      # shell: directive command string
self.script = None        # script: directive path
self.notebook = None      # notebook: directive path
self.wrapper = None       # wrapper: directive URL
self.template_engine = None
self.cwl = None           # cwl: directive path
```

Set in `workflow.py:2079-2087` during rule registration:
```python
rule.run_func = ruleinfo.func
rule.run_func_src = self.get_rule_source(rule.run_func)  # if run: directive
rule.shellcmd = ruleinfo.shellcmd
rule.script = ruleinfo.script
rule.wrapper = ruleinfo.wrapper
```

**Implication for code capture**: To save ALL executed code, check these attributes
in `run_wrapper()` (line 287) which receives `job_rule` with all of them populated.

### shell.__new__() context dict keys

When `shell()` is called from a `run:` block, the context dict contains:

| Key | Type | Description |
|---|---|---|
| `jobid` | int | Unique job identifier |
| `rule` | str | Rule name |
| `output` | list | Output file paths |
| `input` | list | Input file paths |
| `wildcards` | dict | Wildcard values |
| `log` | Log | Log file object (use `str(log[0])` for path) |
| `conda_env` | str | Conda environment path |
| `container_img` | str | Singularity image path |
| `env_modules` | EnvModules | Environment modules |
| `shadow_dir` | str | Shadow directory path |
| `threads` | int | Allocated threads |
| `resources` | dict | Resource values |
| `is_shell` | bool | True if from `shell:` block (not `run:` block) |

## VS Code / PyCharm Debugging

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug Snakemake",
            "type": "debugpy",
            "request": "launch",
            "module": "snakemake",
            "args": [
                "--snakefile", "${workspaceFolder}/your_workflow.smk",
                "--configfile", "raw.json",
                "--cores", "4"
            ],
            "cwd": "${workspaceFolder}"
        }
    ]
}
```

## Quick Diagnostic Commands (no source edit needed)

```bash
# Dry-run with execution reasons
snakemake --snakefile xxx.smk --configfile raw.json --cores 1 -n -r

# DAG visualization
snakemake --snakefile xxx.smk --configfile raw.json --cores 1 --dag | dot -Tpng > dag.png
```

## Parser Architecture: How Snakefile Mixes Python and Rules

Snakemake's key insight: **Snakefile IS valid Python**. The parser (`src/snakemake/parser.py`) performs source-to-source transformation using Python's `tokenize` module before `exec()`.

### Transformation Pipeline

```
Snakefile → tokenize → TokenAutomaton (state machine) → Python code → exec()
```

### Key Components

| Component | Location | Role |
|---|---|---|
| `Snakefile` class | parser.py:1356 | Wraps file with `tokenize.generate_tokens()` |
| `Python` automaton | parser.py:1300 | Top-level state machine, dispatches keywords |
| `Rule` automaton | parser.py:782 | Transforms `rule name:` → `@workflow.rule(name=...)` |
| `Run` automaton | parser.py:573 | Transforms `run:` → `@workflow.run` + function def |
| `Shell` automaton | parser.py:674 | Transforms `shell:` → `@workflow.shellcmd()` + `shell()` |

### Transformation Examples

**Rule + Shell:**
```python
# Snakefile
rule hello:
    output: "out.txt"
    shell: "echo hello > {output}"

# Transformed Python
@workflow.rule(name='hello', lineno=1, ...)
@workflow.output("out.txt")
@workflow.shellcmd("echo hello > {output}")
def __rule_hello(input, output, params, wildcards, ...):
    shell("echo hello > {output}", bench_record=bench_record, ...)
```

**Rule + Run:**
```python
# Snakefile
rule hello:
    output: "out.txt"
    run:
        with open(output[0], 'w') as f:
            f.write("hello")

# Transformed Python
@workflow.rule(name='hello', lineno=1, ...)
@workflow.output("out.txt")
@workflow.run
def __rule_hello(input, output, params, wildcards, ...):
    with open(output[0], 'w') as f:
        f.write("hello")
```

### How It Works

1. **`Python.python()` (line 1336)**: Checks if token is at line start AND is a registered keyword
2. If keyword → call `subautomaton(token.string).consume()` to transform
3. If not keyword → yield token unchanged (it's regular Python)
4. Each subautomaton yields transformed tokens (decorators, function defs)

### Why This Matters for Debugging

- Parser errors show transformed Python line numbers, not original Snakefile lines
- `linemap` dict (parser.py:1404) maps transformed → original lines for error reporting
- Adding new keywords requires: (1) create automaton class, (2) register in `Python.subautomata`

## Pitfall: Version Mismatch

If you edit the local source but `snakemake --version` still shows the old version, the editable install may not be active in the current conda env. Verify with:

```bash
python -c "import snakemake; print(snakemake.__file__)"
```

The path should point to `workflow/snakemake/src/snakemake/`, not a site-packages directory.

## Pitfall: Activate smk conda env for Python commands

When inspecting snakemake source (e.g., `import snakemake; print(snakemake.__file__)` or
reading module source via Python), the `smk` conda environment must be activated first.

**Broken** — runs in base env, can't find snakemake:
```bash
python3 -c "import snakemake_interface_executor_plugins.registry; print(...)"
```

**Fixed** — activate smk env first:
```bash
conda run -n smk python3 -c "import snakemake; print(snakemake.__file__)"
```

Or find files directly without Python:
```bash
find /home/zhousha/miniforge3/envs/smk -path "*/snakemake/shell.py"
```

**Note**: `conda activate` doesn't work in non-interactive shells. Use `conda run -n smk`
or `source activate smk` instead.
