"""Entry point of the packaged executable."""

import os
import sys

# A windowed executable has no console streams; argparse and logging expect them to exist.
for _name in ("stdout", "stderr"):
    if getattr(sys, _name) is None:
        setattr(sys, _name, open(os.devnull, "w", encoding="utf-8"))

from varietywin.app import main  # noqa: E402

sys.exit(main())
