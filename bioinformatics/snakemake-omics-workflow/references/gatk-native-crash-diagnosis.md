# GATK Native Crash (SIGSEGV) Diagnosis

## Symptom

GATK HaplotypeCaller (or other GATK tools) stops mid-execution with no error message
in the log. The log shows normal ProgressMeter output then abruptly stops. The wrapper
reports exit status ≠ 0, typically **245**.

No Java stack trace, no "Shutting down engine", no hs_err_pid.log.

## Root Cause: SIGSEGV in Intel GKL native libraries

GATK uses Intel GKL (Genomics Kernel Library) for AVX-512 accelerated PairHMM and
SmithWaterman alignment. These are native C++ libraries loaded via JNI. A segfault
in native code bypasses JVM exception handling:

- No Java stack trace written
- No stderr output flushed
- No hs_err crash dump generated
- All buffered output (stdout, stderr, log4j) is lost

## Exit Code Math

The GATK Python wrapper (`bin/gatk`) uses `check_call()` + `sys.exit(e.returncode)`:

```python
# From gatk launcher script
from subprocess import check_call, CalledProcessError
try:
    check_call(cmd, env=gatk_env)
except CalledProcessError as e:
    sys.exit(e.returncode)
```

When the Java process is killed by signal N, `CalledProcessError.returncode = -N`.
Python's `sys.exit(-N)` truncates to unsigned 8-bit: `(-N) & 0xFF`.

| Signal       | Signal # | sys.exit(-N) | Exit code |
|-------------|----------|-------------|-----------|
| SIGKILL     | 9        | sys.exit(-9) | 247       |
| **SIGSEGV** | **11**   | **sys.exit(-11)** | **245** |
| SIGBUS      | 7        | sys.exit(-7) | 249       |
| SIGABRT     | 6        | sys.exit(-6) | 250       |

**Exit code 245 = SIGSEGV (segmentation fault) in native code.**

## Why no stderr output?

With `>> log 2>&1`, all stdout and stderr go to the same file. But SIGSEGV terminates
the process at the kernel level — user-space code (libc buffers, JVM, Python) never
gets a chance to flush. The last line in the log is whatever was flushed before the crash.

## Diagnosis Checklist

1. **Check exit code**: 245 = SIGSEGV, 247 = SIGKILL, 250 = SIGABRT
2. **Check for hs_err file**: `find <workdir> -name "hs_err_*"`. If present, JVM
   caught the crash and wrote diagnostics. If absent, the crash was in native code
   that bypassed JVM's signal handler.
3. **Check log tail**: Normal ProgressMeter output → abrupt stop = native crash.
   Error message before stop = Java-level error (different root cause).
4. **Check GATK command**: Look for `--pair-hmm-implementation` and `-Xmx` settings.

## Fixes

### Option A: Disable native PairHMM (most reliable)

```bash
gatk --java-options "-Xms20g -Xmx80g" HaplotypeCaller \
  -R ref.fa -I input.bam -O output.vcf.gz \
  --pair-hmm-implementation VECTOR_LOGLESS_CACHING
```

`VECTOR_LOGLESS_CACHING` uses pure Java implementation — no native code, no SIGSEGV.
Slightly slower but deterministic and crash-free.

### Option B: Reduce native threads

```bash
--native-pair-hmm-threads 4
```

Fewer threads = less contention in native code. Default is `task.cpus` (often 10+).

### Option C: Set -Xmx explicitly

```bash
--java-options "-Xms40g -Xmx40g"
```

Without `-Xmx`, JVM defaults to 1/4 of system RAM (on a 2TB machine = 500GB).
While this doesn't directly fix SIGSEGV, it prevents the heap from growing
uncontrollably and reduces memory pressure.

## JVM Memory Flags Reference

| Flag    | Meaning                                    | Default          |
|---------|--------------------------------------------|------------------|
| `-Xms`  | Initial heap size                          | varies           |
| `-Xmx`  | Maximum heap size                          | 1/4 system RAM   |
| `-XX:GCTimeLimit=50` | Max % time on GC before OOM   | 98               |
| `-XX:GCHeapFreeLimit=10` | Min % free heap after GC  | 2                |
| `-XX:-UsePerfData` | Disable JVM perf counters      | enabled          |

nf-core pattern: `avail_mem = (task.memory.mega * 0.8).intValue()` — allocates 80%
of container memory to JVM heap, leaving 20% for native memory, thread stacks,
metaspace, and OS overhead.

## Verification

After applying fix, confirm the job completes:
```bash
# Check log for completion message
tail -5 <log_file>
# Should see: "Shutting down engine" and "Process hours elapsed"

# Check output exists
ls -la output.vcf.gz output.vcf.gz.tbi
```
