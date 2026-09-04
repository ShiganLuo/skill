# fumitools module notes

## fumi_tools copy_umi (v0.19.0)

### --umi-length is REQUIRED despite docs saying `(default: None)`

`fumi_tools copy_umi --help` shows `(default: None)` but omitting the parameter
causes `error: the following arguments are required: --umi-length`. Passing
`--umi-length None` causes `error: invalid int value: 'None'`.

This is a tool bug — `required=True` is set in argparse despite `default=None`.

### UMI extraction is NOT idempotent

Running `fumi_tools copy_umi` on FASTQ with UMI already in header will:
1. Take first N bp from READ SEQUENCE as UMI (UMI was already removed)
2. Append to header → double UMI
3. Truncate read sequence by N bp (data loss)

### UMI detection pattern

**Detection function** (`bin/detect_umi.py`):
```python
import gzip, re

_UMI_SUFFIX_RE = re.compile(r"_([ACGTNacgtn]+)$")

def has_umi_in_header(fastq_path, umi_length=None):
    """Check if first read already has UMI in header."""
    opener = gzip.open if fastq_path.endswith(".gz") else open
    with opener(fastq_path, "rt") as fh:
        first_line = fh.readline().rstrip("\n")
    if not first_line.startswith("@"):
        return False
    read_name = first_line.split()[0][1:]  # strip '@'
    m = _UMI_SUFFIX_RE.search(read_name)
    if m is None:
        return False
    umi_seq = m.group(1)
    if umi_length is not None and len(umi_seq) != umi_length:
        return False
    return True
```

**Import via ROOT_DIR** (not `__file__`):
```python
_fumitools_bin_dir = os.path.join(ROOT_DIR, "modules", "fumitools", "bin")
if _fumitools_bin_dir not in sys.path:
    sys.path.insert(0, _fumitools_bin_dir)
from detect_umi import has_umi_in_header
```

**Usage in fumitools.smk** (symlink instead of re-extract):
```python
if has_umi_in_header(input.r1):
    # UMI already present, symlink to output
    os.makedirs(os.path.dirname(output.r1), exist_ok=True)
    if os.path.exists(output.r1) or os.path.islink(output.r1):
        os.remove(output.r1)
    os.symlink(os.path.abspath(input.r1), output.r1)
else:
    # Run fumi_tools copy_umi
    cmd = [params.fumi_tools, "copy_umi", "-i", input.r1, "-o", output.r1, ...]
```

### FASTQ header format (Illumina NovaSeq X)

```
@LH00326:331:22THVWLT3:7:1101:1407:1064_ANGGCTTCCCTG 1:N:0:CAAGCTAG+CGCTATGT
└─ instrument    └─ UMI (12bp)           └─ read info
```

UMI is `_<ACGT]{N}` appended after coordinate field, separated by underscore.

### Config defaults

`fumitools.json` sets `umi_length: 12`. The code guards with:
```python
if params.umi_length:
    cmd += ["--umi-length", str(params.umi_length)]
```

Since `--umi-length` is required, config MUST always set `umi_length` to an integer.

## mimseq tool notes (v1.3.6)

### -o/--trnaout always required even with -s

mimseq argparse bug: `-o` is always required even when `-s species` is provided.
Help says "prioritized over -t, -o and -m" but argparse has:
```python
required = (not '--species' or '-s' in sys.argv) or ('-t' in sys.argv)
```
`not '--species'` is always `False` (string is truthy), so `-o` is always required.

**Workaround**: Provide the built-in tRNA.out file path when using `-s`:
```python
species_trnaout_map = {
    "Hsap": "hg38-eColitK/hg38-tRNAs-detailed.out",
    "Mmus": "mm39-eColitK/mm39-tRNAs-detailed.out",
    # ... etc
}
mimseq_data_dir = os.path.join(env_path, "lib/python3.7/site-packages/mimseq/data")
cmd += ["-o", os.path.join(mimseq_data_dir, species_trnaout_map[species])]
```

### --control-condition is required, single value only

`--control-condition` takes ONE value (not multiple). The tool compares ALL other
conditions against this single control for DESeq2 differential expression.

### Species reference path mapping

When `-s species` is provided, mimseq internally sets:
```python
args.trnas = os.path.dirname(__file__) + "/data/<species_dir>/<tRNA_fasta>"
args.trnaout = os.path.dirname(__file__) + "/data/<species_dir>/<tRNA_out>"
```

Species → data directory mapping:
- Hsap → hg38-eColitK
- Mmus → mm39-eColitK
- Scer → sacCer3-eColitK
- Dmel → dm6-eColitK
- Drer → danRer11-eColitK
- Cele → ce11-eColitK

### usearch dependency

mimseq requires `usearch` for tRNA sequence clustering. Install via:
```bash
conda install --prefix /path/to/env -c bioconda usearch
```

### --out-dir cannot be existing directory (docs claim, but test shows it works)

Help says "Cannot be an existing directory" but testing shows mimseq accepts
existing directories. The warning may be outdated.

### mimseq module splitting pattern

Split monolithic mimseq into independent Snakemake sub-modules:

```
modules/mimseq/
├── bin/
│   ├── serialize.py          # pickle/JSON state serialization
│   ├── utils.py              # shared utilities
│   ├── tRNAtools/run.py      # wrapper for tRNA parsing + SNP index
│   ├── align/run.py          # wrapper for GSNAP alignment
│   ├── clusters/run.py       # wrapper for cluster splitting
│   ├── mods/run.py           # wrapper for modification quantification
│   ├── coverage/run.py       # wrapper for coverage + plots
│   └── deseq/run.py          # wrapper for DESeq2
├── tRNAtools/tRNAtools.smk   # Snakemake rules (one per module)
├── align/align.smk
├── clusters/clusters.smk
├── mods/mods.smk
├── coverage/coverage.smk
├── deseq/deseq.smk
├── mimseq.smk                # main orchestrator (includes all sub-modules)
└── mimseq/                   # original source code
```

**State serialization** (`bin/serialize.py`):
```python
def save_pickle(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)

def load_pickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)
```

Each module saves state to `outdir/state/*.pkl`, next module loads it.

**Sub-module .smk pattern**:
```python
rule mimseq_tRNAtools:
    input: unpack(get_tRNAtools_input)
    output: state_dir = directory(outdir + "/state")
    log: logdir + "/mimseq_tRNAtools.log"
    params:
        script = os.path.join(ROOT_DIR, "modules", "mimseq", "bin", "tRNAtools", "run.py"),
        ...
    run:
        cmd = ["/path/to/env/bin/python", params.script, ...]
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\n")
            f.write(" ".join(cmd) + "\n")
        shell(f"bash {script_path} >> {log_path} 2>&1")
```

**Dependency chain**: `prepare_sample_data → tRNAtools → align → clusters → mods → coverage → deseq`

**Subworkflow imports**: Must import ALL intermediate rules, not just first/last:
```python
use rule mimseq_all from mimseq as tRNAseq_mimseq_run
use rule mimseq_result from mimseq as tRNAseq_mimseq_result
use rule mimseq_tRNAtools from mimseq as tRNAseq_mimseq_tRNAtools
use rule mimseq_align from mimseq as tRNAseq_mimseq_align
# ... all intermediate rules
```

## argparse `(default: None)` can lie

When a tool's `--help` shows `(default: None)` for a parameter, it does NOT
mean the parameter is optional. Always test by omitting the parameter.

**Real examples**:
- fumi_tools `--umi-length`: required=True despite default=None
- mimseq `-o/--trnaout`: required even with `-s` due to broken logic

**Testing pattern**:
```bash
# Test 1: omit entirely
tool --required-args
# If "the following arguments are required: --param", it's mandatory

# Test 2: pass None
tool --param None --required-args
# If "invalid int value: 'None'", type constraint is stricter
```

## conda: + run: incompatibility (Snakemake limitation)

`conda:` directive ONLY activates for `shell:` commands, NOT for `run:` block
Python code. Having `conda:` with `run:` causes:
```
RuleException: Conda environments are only allowed with shell, script, notebook,
or wrapper directives (not with run or template_engine).
```

**Fix options** (pick one):

1. **Remove `conda:` and use full Python path in cmd list** (preferred):
```python
cmd = [
    "/data/pub/zhousha/env/mutation_0.1/<hash>_/bin/python",
    params.script, ...
]
```

2. **Remove `conda:` and activate in generated shell script**:
```python
with open(script_path, "w") as f:
    f.write("#!/bin/bash\n")
    f.write("source /home/zhousha/miniforge3/bin/activate /path/to/env\n")
    f.write(" ".join(cmd) + "\n")
```

3. **Change `run:` to `shell:`** — loses flexibility of Python logic in the rule.

**Scope**: This is a GLOBAL issue. When creating new modules, NEVER use `conda:`
with `run:`. When fixing existing modules, search all `.smk` files:
```bash
# Find all files with both conda: and run:
for f in modules/*/[!m]*.smk modules/*/[^_]*.smk; do
  grep -q "conda:" "$f" && grep -q "run:" "$f" && echo "$f"
done
```

**Batch fix** (remove conda: blocks from run: rules):
```bash
sed -i '/^    conda:$/,/^        ".*\.yaml"$/d' file.smk
```

## Import path in module X: + use rule context

When a module .smk is loaded via `module X:` + `use rule`, `__file__` may not
resolve correctly. Use `ROOT_DIR` from config instead:

```python
# WRONG — __file__ may not resolve in module context
_bin_dir = os.path.join(os.path.dirname(__file__), "bin")

# CORRECT — use ROOT_DIR from config
_bin_dir = os.path.join(ROOT_DIR, "modules", "toolname", "bin")
```
