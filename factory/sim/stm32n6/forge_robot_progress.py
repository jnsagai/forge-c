"""Robot Framework listener (API v3) for the factory floor's live test bar (owner 2026-11-01: "how many tests to run,
and from those how many already ran, in the form of a progress bar"). Writes {total, done, passed, failed} as JSON to
the path it is given, when the top suite starts and after every test. Display only: never a verdict source."""
import json
import os
import time

ROBOT_LISTENER_API_VERSION = 3


class Progress:
    def __init__(self, path):
        self.path, self.base = path, {}
        try:
            with open(path) as f:
                self.base = json.load(f)
        except (OSError, ValueError):
            self.base = {}
        self.total, self.done, self.passed, self.failed, self.top = None, 0, 0, 0, None

    def _write(self, running=True):
        rec = {**self.base, "total": self.total, "done": self.done, "passed": self.passed, "failed": self.failed,
               "running": running, "updated": time.time()}
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            json.dump(rec, f)
        os.replace(tmp, self.path)

    def start_suite(self, data, result):
        if self.top is None:
            self.top = data.longname
            self.total = data.test_count
            self._write()

    def end_test(self, data, result):
        self.done += 1
        self.passed += result.status == "PASS"
        self.failed += result.status != "PASS"
        self._write()
