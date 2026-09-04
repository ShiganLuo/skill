# Template: Module header with delayed imports for `module` + `use rule` pattern
# Copy this header when creating a new module that needs project-internal imports.
# See pitfall §30 for why top-level imports fail.

import sys
import os
import time
import shutil

# ── Config (safe at top level — only stdlib + config dict) ──
outdir = config.get("outdir", "output")
logdir = config.get("logdir", "log")
indir = config.get("indir", "input")
samples = config.get("samples", [])
ROOT_DIR = config.get("ROOT_DIR", ".")


# ── Delayed import helper ──
# Call this at the START of each `run:` block.
# Returns setup_logger factory function; each rule creates its own logger instance.
def _import_logger():
    """Import setup_logger from common.LogUtil (delayed to run time)."""
    # If PYTHONPATH is set by run.py, src_dir is already in sys.path.
    src_dir = os.path.join(ROOT_DIR, "src")
    if not os.path.exists(src_dir):
        raise FileNotFoundError(f"Source directory not found: {src_dir}")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from common.LogUtil import setup_logger
    return setup_logger


# ── Example rule using delayed import ──
# rule my_rule:
#     """Description."""
#     input:
#         bam = indir + "/{sample_id}/{sample_id}.bam"
#     output:
#         result = outdir + "/{sample_id}/{sample_id}.result.txt"
#     log:
#         logdir + "/{sample_id}/my_rule.log"
#     threads: 4
#     conda: "my_tool.yaml"
#     params:
#         my_tool = config.get("Procedure", {}).get("my_tool") or "my_tool"
#     run:
#         setup_logger = _import_logger()
#         open(log, "w").close()
#         logger = setup_logger(logger_name="my_rule", log_file=log)
#         try:
#             current_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
#             logger.info(f"Start my_rule for sample {wildcards.sample_id} at {current_time}")
#             script = os.path.join(outdir, f"{wildcards.sample_id}/my_rule_{current_time}.sh")
#             cmd = [params.my_tool, "-i", input.bam, "-o", output.result]
#             with open(script, "w") as f:
#                 f.write("#!/bin/bash\n")
#                 f.write(" ".join(cmd) + "\n")
#             shell(f"bash {script} >> {log} 2>&1")
#         except Exception as e:
#             logger.error(f"my_rule failed for sample {wildcards.sample_id}: {e}")
#             raise e
