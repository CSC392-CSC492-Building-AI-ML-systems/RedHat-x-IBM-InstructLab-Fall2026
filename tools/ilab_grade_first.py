"""Run ilab with the grade-first SDG blocks registered.

ilab can only use pipeline blocks that are registered when it starts, and it has no option to
load blocks from a file. This imports tools/grade_first_blocks.py (which registers them) and then
runs the normal ilab command with the same arguments, so

    python tools/ilab_grade_first.py data generate --pipeline pipelines/grade_first ...

is `ilab data generate --pipeline pipelines/grade_first ...` with the blocks available. Use it in
the ilab environment, and don't add --detached (that would start a fresh process without them).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import grade_first_blocks  # noqa: E402,F401  (registers the blocks)
from instructlab.lab import ilab  # noqa: E402

if __name__ == "__main__":
    if "--detached" in sys.argv or "-dt" in sys.argv:
        sys.exit("ERROR: --detached would start a new process without the grade-first blocks. Leave it out.")
    sys.argv[0] = "ilab"
    sys.exit(ilab())
