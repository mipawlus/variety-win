"""Entry point of the packaged executable."""

import os
import sys

# A windowed executable has no console streams; argparse and logging expect them to exist.
for _name in ("stdout", "stderr"):
    if getattr(sys, _name) is None:
        setattr(sys, _name, open(os.devnull, "w", encoding="utf-8"))

from varietywin.app import main  # noqa: E402

# Build check: `VarietyWin.exe --check-lock-screen <image>` sets the lock screen and exits,
# to confirm the packaged copy contains everything the lock screen support needs.
if len(sys.argv) == 3 and sys.argv[1] == "--check-lock-screen":
    import logging
    from pathlib import Path

    from varietywin.util.logging_setup import setup_logging

    setup_logging()
    import threading

    from varietywin.platform_win import lockscreen

    failed = []

    def check() -> None:
        try:
            lockscreen.set_lock_screen(Path(sys.argv[2]))
        except Exception:
            logging.getLogger("build-check").exception("Lock screen check failed")
            failed.append(True)

    # On a worker thread, like the app does: Windows refuses to block the main thread here.
    worker = threading.Thread(target=check)
    worker.start()
    worker.join(60)
    sys.exit(1 if failed or worker.is_alive() else 0)

sys.exit(main())
