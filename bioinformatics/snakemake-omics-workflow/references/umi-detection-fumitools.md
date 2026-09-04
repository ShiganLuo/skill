# UMI detection and fumi_tools quirks

## UMI detection in FASTQ headers

When UMI has been extracted (by umi_tools extract or fumi_tools copy_umi), the UMI
is appended to the read name with underscore separator:

```
@LH00326:331:22THVWLT3:7:1101:1407:1064_ANGGCTTCCCTG 1:N:0:CAAGCTAG+CGCTATGT
                                         ^^^^^^^^^^^^
                                         12bp UMI
```

### Detection function

```python
import re

_UMI_SUFFIX_RE = re.compile(r"_([ACGTNacgtn]+)$")

def has_umi_in_header(fastq_path: str) -> bool:
    """Check if first read already carries a UMI."""
    opener = gzip.open if fastq_path.endswith(".gz") else open
    with opener(fastq_path, "rt") as fh:
        first_line = fh.readline().rstrip("\n")
    
    if not first_line.startswith("@"):
        return False
    
    read_name = first_line.split()[0]
    name_body = read_name[1:]  # strip '@'
    
    return _UMI_SUFFIX_RE.search(name_body) is not None
```

### Usage in fumitools.smk

```python
# Import detection helper
_bin_dir = os.path.join(ROOT_DIR, "modules", "fumitools", "bin")
sys.path.insert(0, _bin_dir)
from detect_umi import has_umi_in_header

rule fumitools_copy_umi_single:
    input: r1 = indir + "/{sample_id}.single.fq.gz"
    output: r1 = outdir + "/{sample_id}/{sample_id}.umi.single.fq.gz"
    run:
        if has_umi_in_header(input.r1):
            # UMI already extracted, symlink instead of re-extracting
            os.symlink(os.path.abspath(input.r1), output.r1)
        else:
            # Run fumi_tools copy_umi
            shell(f"fumi_tools copy_umi -i {input.r1} -o {output.r1} ...")
```

## fumi_tools copy_umi argparse bug

**Bug**: `--umi-length` is required despite help showing `(default: None)`.

```bash
# Omitting --umi-length → ERROR
fumi_tools copy_umi -i in.fq.gz -o out.fq.gz
# → error: the following arguments are required: --umi-length

# Passing None → ERROR
fumi_tools copy_umi -i in.fq.gz -o out.fq.gz --umi-length None
# → error: invalid int value: 'None'
```

**Root cause**: argparse has both `default=None` and `required=True`.

**Fix**: Always provide `--umi-length` in config (default: 12).

## UMI extraction is NOT idempotent

Running UMI extraction on FASTQ that already has UMI in header will:
1. Take first N bp from READ SEQUENCE as UMI (UMI was already removed)
2. Append to header → double UMI in name
3. Truncate read sequence by N bp (data loss)

**Always check with has_umi_in_header() before running copy_umi.**
