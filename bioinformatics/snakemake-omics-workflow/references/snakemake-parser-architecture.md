# Snakemake Parser Architecture — How Python Code Mixing Works

Source: `src/snakemake/parser.py` (Snakemake v9.x)

## Core Mechanism: Source-to-Source Transformation

Snakefile IS valid Python. Snakemake uses Python's `tokenize` module to decompose the
file into a token stream, then a **TokenAutomaton** state machine transforms Snakemake
keywords into standard Python function calls. The result is executed via `exec()`.

```
Snakefile (.smk)
    ↓ tokenize.generate_tokens()
Token stream
    ↓ Python (TokenAutomaton)
Transformed Python source
    ↓ exec()
Workflow object populated with rules
```

## Key Classes

### Snakefile (parser.py L1356-1379)
Wraps `tokenize.generate_tokens()` over the .smk file.

### TokenAutomaton (L98-197)
Base state machine. Has a `state` callable that processes each token. Key method:
`consume()` — iterates tokens, delegates to `self.state(token)`, yields output tokens.

### Python (L1300-1354) — Top-level automaton
State: `python()`. For each token:
- If it's a line-start keyword (e.g., `rule`, `include`, `configfile`) → delegate to subautomaton
- Otherwise → yield token unchanged (this is the Python code passthrough)

Subautomata registered:
```python
subautomata = dict(
    rule=Rule, checkpoint=Checkpoint,
    include=Include, configfile=Configfile, workdir=Workdir,
    module=Module, use=UseRule,
    onsuccess=OnSuccess, onerror=OnError, onstart=OnStart,
    # ... etc
)
```

### Rule (L782-876) — Handles `rule my_rule:`
Transforms to: `@workflow.rule(name='my_rule', lineno=N, snakefile='path')`

Subautomata for rule properties:
```python
rule_property_subautomata = dict(input=Input, output=Output, params=Params, ...)
rule_run_subautomata = dict(run=Run, shell=Shell, script=Script, ...)
```

When `block_content()` sees a keyword like `input:`, it delegates to the Input subautomaton.

### Run (L573-606) — Handles `run:` block
Transforms to:
```python
@workflow.run
def __rule_NAME(input, output, params, wildcards, threads, ...):
    <user's Python code here>
```

### Shell (L674-680) — Handles `shell:` block
Transforms to:
```python
@workflow.shellcmd("echo {input}")
def __rule_NAME(input, output, params, ...):
    shell("echo {input}", bench_record=bench_record, ...)
```

## Transformation Examples

### Example 1: Simple shell rule
```python
# Snakefile
rule hello:
    output: "out.txt"
    shell: "echo hello > {output}"
```
```python
# Transformed Python (simplified)
@workflow.rule(name='hello', lineno=1, snakefile='Snakefile')
@workflow.output("out.txt")
@workflow.shellcmd("echo hello > {output}")
def __rule_hello(input, output, params, wildcards, threads, ...):
    shell("echo hello > {output}", bench_record=bench_record, ...)
```

### Example 2: Run block with Python
```python
# Snakefile
rule calc:
    input: "in.txt"
    run:
        x = open(input[0]).read()
        print(f"Got {len(x)} chars")
```
```python
# Transformed Python
@workflow.rule(name='calc', lineno=1, snakefile='Snakefile')
@workflow.input("in.txt")
@workflow.run
def __rule_calc(input, output, params, wildcards, ...):
    x = open(input[0]).read()
    print(f"Got {len(x)} chars")
```

### Example 3: Global Python code
```python
# Snakefile
import os
outdir = "results"

rule all:
    input: outdir + "/final.txt"
```
```python
# Transformed Python — import and assignment pass through unchanged
import os
outdir = "results"

@workflow.rule(name='all', lineno=5, ...)
@workflow.input(outdir + "/final.txt")
@workflow.norun()
@workflow.run
def __rule_all(input, output, ...):
    pass
```

## Why Top-Level Imports Can Fail in Modules

When using `module X:` + `use rule`, Snakemake parses the module .smk immediately
during subworkflow loading. The token automaton runs, and any top-level Python code
(including imports) executes at that point. If the import depends on `sys.path`
modification using `config` values, the timing matters:

1. `config` IS available (passed via `config: X_config`)
2. But the execution context (cwd, environment) may differ from rule execution time
3. If `ROOT_DIR` resolves to a relative path, it's relative to the parser's cwd,
   which during `module` loading may be the subworkflow's directory, not the project root

This is why delayed imports in `run:` blocks are the safe pattern.

## Key Implementation Detail: `format_tokens()` (L1382-1388)

The transformed tokens are joined with spaces, but only between non-whitespace tokens.
This means indentation is handled by the `INDENT * effective_indent` logic in
`TokenAutomaton.consume()`, not by preserving original indentation.

## See Also
- `workflow.py` L1884: `Workflow.rule()` — the decorator that registers rules
- `workflow.py` L2405: `Workflow.run()` — returns `RuleInfo(func)`
- `workflow.py` L2349: `Workflow.shellcmd()` — sets `ruleinfo.shellcmd = cmd`
- `shell.py` — the `shell()` function that actually executes commands
