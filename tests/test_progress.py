from post_trip_summary.server.progress import ProgressTracker


def test_initial_state():
    tracker = ProgressTracker()
    state = tracker.get_state()
    assert state["phase"] == ""
    assert state["current"] == 0
    assert state["total"] == 0
    assert state["label"] == ""
    assert state["done"] is False


def test_update_and_read():
    tracker = ProgressTracker()
    tracker.update("photos", 5, 100, "IMG_001.jpg")
    state = tracker.get_state()
    assert state["phase"] == "photos"
    assert state["current"] == 5
    assert state["total"] == 100
    assert state["label"] == "IMG_001.jpg"


def test_complete():
    tracker = ProgressTracker()
    tracker.complete("review")
    state = tracker.get_state()
    assert state["done"] is True
    assert state["next_stage"] == "review"


def test_fail():
    tracker = ProgressTracker()
    tracker.fail("Something went wrong")
    state = tracker.get_state()
    assert state["failed"] is True
    assert state["error"] == "Something went wrong"


def test_callback():
    tracker = ProgressTracker()
    cb = tracker.callback()
    cb("scoring", 3, 50, "photo3.jpg")
    state = tracker.get_state()
    assert state["phase"] == "scoring"
    assert state["current"] == 3
