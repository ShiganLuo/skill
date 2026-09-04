# Argparse Bugs and Pitfalls

## Common argparse Bugs in Bioinformatics Tools

### Bug 1: `not 'string'` vs `'string' not in sys.argv`

**Example from mimseq**:
```python
# BROKEN: not '--species' always evaluates to False (string is truthy)
required = (not '--species' or '-s' in sys.argv) or ('-t' in sys.argv)

# CORRECT: should be
required = not ('--species' in sys.argv or '-s' in sys.argv)
```

**Symptom**: Parameter marked as "optional" in help text is actually required.

**Diagnosis**: Run the tool with the parameter omitted:
```bash
tool --species Mmus --other-args  # Without the "optional" parameter
# If it says "the following arguments are required: --param", it's a bug
```

### Bug 2: `default=None` with `required=True`

**Example from fumi_tools**:
```python
parser.add_argument('--umi-length', default=None, required=True, type=int)
```

**Help text shows**: `--umi-length UMI_LENGTH (default: None)`
**Actual behavior**: Parameter is required, cannot be omitted or set to None

**Diagnosis**: Test both scenarios:
```bash
# Test 1: Omit parameter
tool --other-args  # Should work if truly optional

# Test 2: Pass None
tool --param None --other-args  # Should work if default is None
```

## Workarounds

### For Bug 1 (wrong required logic)
The parameter IS required. Provide it in your Snakemake rule:
```python
cmd = ["tool", "--required-param", value, "--actually-required-param", value]
```

### For Bug 2 (default=None but required)
The parameter is required. Provide it even if you want "None":
```python
# If the parameter must be an integer, provide a dummy value
cmd = ["tool", "--umi-length", "12"]  # Use actual value, not None
```

## Testing Checklist

Before writing Snakemake rules for a new tool:

1. **Run `tool --help`** to see parameter documentation
2. **Test with parameters omitted** to verify which are truly optional
3. **Test with `None` values** to verify default behavior
4. **Check tool source code** if behavior doesn't match documentation

## Real Examples

### mimseq `--control-condition`
- Help says: "REQUIRED"
- Actual: IS required, no workaround

### fumi_tools `--umi-length`
- Help says: "(default: None)"
- Actual: Required, must be integer

### mimseq `--trnaout`
- Help says: "tRNA.out file"
- Actual: Required even with `--species` (argparse bug)

## General Pattern: Empty String Breaks argparse

When a Snakemake `.smk` file generates a bash script with `"--param", ""` where the value
is an empty string, the generated command becomes:

```bash
python script.py --param --next-arg value
```

argparse then consumes `--next-arg` as the value of `--param`, causing either:
- `error: argument --next-arg: expected one argument` (if --next-arg requires a value)
- Wrong value assignment (silent)

**Fix**: Conditionally add the argument in the `.smk` file:
```python
cmd = ["python", "script.py"]
if params.optional_param:
    cmd += ["--param", params.optional_param]
```

And in `run.py`, use `default=""` not `required=True`:
```python
parser.add_argument("--param", default="", help="Optional parameter")
```

**Affected parameters in mimseq modular pipeline**:
- `--control-cond` (coverage.smk, deseq.smk)
