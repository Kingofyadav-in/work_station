#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rules import evaluate_rule


class TestEvaluateRule(unittest.TestCase):
    def _rule(self, conditions: list) -> dict:
        return {"id": "test", "conditions": conditions}

    def test_no_conditions_always_passes(self):
        self.assertTrue(evaluate_rule(self._rule([]), {}))

    def test_health_fail_count_pass(self):
        rule = self._rule([{"type": "health_fail_count", "min": 1}])
        self.assertTrue(evaluate_rule(rule, {"health_fail_count": 2}))

    def test_health_fail_count_block(self):
        rule = self._rule([{"type": "health_fail_count", "min": 1}])
        self.assertFalse(evaluate_rule(rule, {"health_fail_count": 0}))

    def test_process_down_pass(self):
        rule = self._rule([{"type": "process_down", "name": "jarvis-api"}])
        self.assertTrue(evaluate_rule(rule, {"down_processes": ["jarvis-api"]}))

    def test_process_down_block(self):
        rule = self._rule([{"type": "process_down", "name": "jarvis-api"}])
        self.assertFalse(evaluate_rule(rule, {"down_processes": []}))

    def test_log_pattern_match(self):
        rule = self._rule([{"type": "log_pattern", "pattern": "ERROR"}])
        ctx = {"recent_log_lines": ["2026-01-01 INFO ok", "2026-01-01 ERROR something broke"]}
        self.assertTrue(evaluate_rule(rule, ctx))

    def test_log_pattern_no_match(self):
        rule = self._rule([{"type": "log_pattern", "pattern": "CRITICAL"}])
        ctx = {"recent_log_lines": ["INFO all good"]}
        self.assertFalse(evaluate_rule(rule, ctx))

    def test_multiple_conditions_all_must_pass(self):
        rule = self._rule([
            {"type": "health_fail_count", "min": 1},
            {"type": "process_down", "name": "jarvis-api"},
        ])
        ctx = {"health_fail_count": 2, "down_processes": []}
        self.assertFalse(evaluate_rule(rule, ctx))

    def test_always_condition(self):
        rule = self._rule([{"type": "always"}])
        self.assertTrue(evaluate_rule(rule, {}))

    def test_unknown_condition_type_fails_closed(self):
        rule = self._rule([{"type": "nonexistent_type"}])
        self.assertFalse(evaluate_rule(rule, {}))


if __name__ == "__main__":
    unittest.main()
