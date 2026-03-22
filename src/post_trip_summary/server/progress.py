"""Thread-safe progress tracker for compute stages."""
import threading


class ProgressTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            "phase": "", "current": 0, "total": 0, "label": "",
            "done": False, "failed": False, "error": "", "next_stage": "",
        }

    def update(self, phase: str, current: int, total: int, label: str = ""):
        with self._lock:
            self._state["phase"] = phase
            self._state["current"] = current
            self._state["total"] = total
            self._state["label"] = label

    def complete(self, next_stage: str):
        with self._lock:
            self._state["done"] = True
            self._state["next_stage"] = next_stage

    def fail(self, error: str):
        with self._lock:
            self._state["failed"] = True
            self._state["error"] = error

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def callback(self):
        def _cb(phase: str, current: int, total: int, label: str = ""):
            self.update(phase, current, total, label)
        return _cb
