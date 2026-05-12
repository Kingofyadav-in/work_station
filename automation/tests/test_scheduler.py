#!/usr/bin/env python3
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestJobDue(unittest.TestCase):
    def _make_job(self, seconds: int) -> object:
        from scheduler import Job

        rule = {
            "id": "test_interval",
            "trigger": {"type": "interval", "seconds": seconds},
            "conditions": [],
            "action": {"type": "notify", "channel": "log", "message": "test"},
        }

        def noop_handler(_rule):
            pass

        def noop_context():
            return {}

        return Job(rule, noop_handler, noop_context)

    def test_new_job_is_due_immediately(self):
        job = self._make_job(300)
        self.assertTrue(job.is_due())

    def test_job_not_due_after_marking_ran(self):
        job = self._make_job(300)
        job.mark_ran()
        self.assertFalse(job.is_due())

    def test_job_due_after_interval_elapsed(self):
        job = self._make_job(1)
        job.mark_ran()
        time.sleep(1.1)
        self.assertTrue(job.is_due())


class TestSchedulerStartStop(unittest.TestCase):
    def test_start_and_stop(self):
        from scheduler import Scheduler

        fired = []

        def noop_handler(_rule):
            fired.append(1)

        def noop_context():
            return {}

        from scheduler import Job

        rule = {
            "id": "quick",
            "trigger": {"type": "interval", "seconds": 1},
            "conditions": [],
            "action": {"type": "notify", "channel": "log", "message": "x"},
        }
        s = Scheduler(tick=0.1)
        s.add_job(Job(rule, noop_handler, noop_context))
        s.start()
        time.sleep(0.5)
        s.stop(timeout=2.0)
        self.assertGreaterEqual(len(fired), 1)


if __name__ == "__main__":
    unittest.main()
