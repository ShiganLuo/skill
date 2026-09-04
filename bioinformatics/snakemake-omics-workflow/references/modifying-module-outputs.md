# Modifying Module Outputs (e.g., Adding BroadPeak)

## When to use
Extending an existing rule to produce additional output files alongside existing ones.

## Checklist

### 1. Module .smk (`modules/<module>/<module>.smk`)
- Add new entries to `output:` block (use unique name prefix to avoid conflict)
- Add command in the SAME `run:` block, ONE .sh script with `set -e`
- Update `result` aggregation rule to include new outputs

```python
# ❌ Wrong: separate script
with open(script, "w") as f:
    f.write("macs3 callpeak ...\n")
shell(f"bash {script} >> {log} 2>&1")
broad_script = os.path.join(outdir, "macs3_broad.sh")
with open(broad_script, "w") as f:
    f.write("macs3 callpeak --broad ...\n")
shell(f"bash {broad_script} >> {log} 2>&1")

# ✅ Correct: one script
with open(script, "w") as f:
    f.write("#!/bin/bash\nset -e\n")
    f.write("macs3 callpeak ...\n")
    f.write("macs3 callpeak --broad ...\n")
shell(f"bash {script} >> {log} 2>&1")
```

### 2. Module JSON (`modules/<module>/<module>.json`)
- Add new params if needed (e.g., `broad_cutoff`)

### 3. Config JSON (`config/<Workflow>.json`)
- Add new params to `Params.<module>` section

### 4. Schema JSON (`config/<Workflow>.schema.json`)
- Add new param schema entries

### 5. node.py
- Add new output files to `outfiles` in BOTH branches (with-control and without-control)

### 6. README
- Document new outputs, params, and usage

## Pitfalls

### ❌ Creating a new rule for the same tool
When extending existing behavior, modify the existing rule.
User: "不必增加规则" / "直接在改规则上增加命令即可"

### ❌ Unused params
Every `params:` entry must be used in `run:`. Remove unused ones.
User: "broad这个参数一点作用没有,你放在那干嘛"

### ❌ Making always-on features configurable
If a feature should always run (e.g., `--cutoff-analysis`), hardcode it.
Don't create a configurable boolean that defaults to False.
User: "为...添加...自动开启cutoff_analysis"

### ❌ Missing cross-server portability in test meta
Test meta files should use relative paths (e.g., `fastq/TestIP1/TestIP1_1.fq.gz`).
Resolution happens in `run.py`'s `_resolve_test_meta()`, NOT in `MetaUtil.py`.
User: "谁把metaMetaUtil.py的呢，我请问" → fix in run.py test framework
