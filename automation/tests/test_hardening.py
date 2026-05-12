#!/usr/bin/env python3
"""
Phase 4.1 hardening tests.

Covers: dry-run, emergency stop, cooldown, retry, approval gate,
schema validation, rule enable/disable, webhook HMAC signing.
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

_AUT = Path(__file__).resolve().parents[1]
_ROOT = _AUT.parent
sys.path.insert(0, str(_ROOT / "shared"))
sys.path.insert(0, str(_AUT))


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_rule(
    *,
    rule_id: str = "test_rule",
    risk_tier: str = "low",
    max_retries: int = 0,
    cooldown_seconds: int = 0,
    action_type: str = "notify",
) -> dict:
    return {
        "id": rule_id,
        "description": "test",
        "enabled": True,
        "risk_tier": risk_tier,
        "max_retries": max_retries,
        "cooldown_seconds": cooldown_seconds,
        "trigger": {"type": "interval", "seconds": 60},
        "conditions": [],
        "action": {"type": action_type, "channel": "log", "message": "test"},
    }


def _make_job(rule: dict, handler=None):
    from scheduler import Job

    fired = []
    if handler is None:
        def handler(_r):
            fired.append(1)

    def ctx():
        return {}

    job = Job(rule, handler, ctx)
    return job, fired


# ── Dry-run ────────────────────────────────────────────────────────────────────

class TestDryRun(unittest.TestCase):
    def test_dry_run_does_not_call_handler(self):
        from scheduler import Job

        rule = _make_rule()
        fired = []

        with patch.dict(os.environ, {"AUTOMATION_DRY_RUN": "1"}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch("scheduler._AUDIT_FILE", Path(tmpdir) / "audit.jsonl"), \
                     patch("scheduler._FAILURE_FILE", Path(tmpdir) / "fail.jsonl"), \
                     patch("scheduler._STOP_FILE", Path(tmpdir) / "stop"):
                    def handler(_r):
                        fired.append(1)

                    job = Job(rule, handler, lambda: {})
                    job.mark_ran()
                    # Force due by faking _last_run to 0
                    job._last_run = 0.0
                    self.assertTrue(job.is_due())
                    job.fire()

        self.assertEqual(fired, [], "handler must NOT be called in dry-run mode")

    def test_dry_run_writes_audit_entry(self):
        from scheduler import Job

        rule = _make_rule()

        with patch.dict(os.environ, {"AUTOMATION_DRY_RUN": "1"}):
            with tempfile.TemporaryDirectory() as tmpdir:
                audit = Path(tmpdir) / "audit.jsonl"
                with patch("scheduler._AUDIT_FILE", audit), \
                     patch("scheduler._FAILURE_FILE", Path(tmpdir) / "fail.jsonl"), \
                     patch("scheduler._STOP_FILE", Path(tmpdir) / "stop"):
                    job = Job(rule, lambda _r: None, lambda: {})
                    job._last_run = 0.0
                    job.fire()
                # read while tmpdir still exists
                entries = [json.loads(l) for l in audit.read_text().splitlines()]

        self.assertTrue(any(e["status"] == "dry_run" for e in entries))


# ── Emergency stop ─────────────────────────────────────────────────────────────

class TestEmergencyStop(unittest.TestCase):
    def test_emergency_stop_file_prevents_execution(self):
        from scheduler import Job

        rule = _make_rule()

        with tempfile.TemporaryDirectory() as tmpdir:
            stop_file = Path(tmpdir) / "automation.STOP"
            stop_file.write_text("stop")
            fired = []

            with patch("scheduler._STOP_FILE", stop_file), \
                 patch("scheduler._AUDIT_FILE", Path(tmpdir) / "audit.jsonl"), \
                 patch("scheduler._FAILURE_FILE", Path(tmpdir) / "fail.jsonl"), \
                 patch.dict(os.environ, {"AUTOMATION_DRY_RUN": "0"}):
                def handler(_r):
                    fired.append(1)

                job = Job(rule, handler, lambda: {})
                job._last_run = 0.0
                job.fire()

        self.assertEqual(fired, [], "handler must NOT fire when STOP file exists")

    def test_no_stop_file_allows_execution(self):
        rule = _make_rule()

        with tempfile.TemporaryDirectory() as tmpdir:
            stop_file = Path(tmpdir) / "automation.STOP"
            fired = []

            with patch("scheduler._STOP_FILE", stop_file), \
                 patch("scheduler._AUDIT_FILE", Path(tmpdir) / "audit.jsonl"), \
                 patch("scheduler._FAILURE_FILE", Path(tmpdir) / "fail.jsonl"), \
                 patch.dict(os.environ, {"AUTOMATION_DRY_RUN": "0"}):
                from scheduler import Job

                def handler(_r):
                    fired.append(1)

                job = Job(rule, handler, lambda: {})
                job._last_run = 0.0
                job.fire()

        self.assertGreater(len(fired), 0)


# ── Cooldown ───────────────────────────────────────────────────────────────────

class TestCooldown(unittest.TestCase):
    def test_cooldown_prevents_immediate_refiring(self):
        from scheduler import Job

        rule = _make_rule(cooldown_seconds=300)
        job = Job(rule, lambda _r: None, lambda: {})
        job._last_run = 0.0  # interval is 60s; force due
        job._last_success_time = time.monotonic()  # just succeeded

        self.assertFalse(job.is_due(), "should be blocked by cooldown")

    def test_cooldown_expired_allows_firing(self):
        from scheduler import Job

        rule = _make_rule(cooldown_seconds=1)
        job = Job(rule, lambda _r: None, lambda: {})
        job._last_run = 0.0
        job._last_success_time = time.monotonic() - 2  # cooldown elapsed

        self.assertTrue(job.is_due())


# ── Retry ──────────────────────────────────────────────────────────────────────

class TestRetry(unittest.TestCase):
    def test_retry_schedules_after_failure(self):
        from scheduler import Job

        rule = _make_rule(max_retries=2)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scheduler._STOP_FILE", Path(tmpdir) / "stop"), \
                 patch("scheduler._AUDIT_FILE", Path(tmpdir) / "audit.jsonl"), \
                 patch("scheduler._FAILURE_FILE", Path(tmpdir) / "fail.jsonl"), \
                 patch.dict(os.environ, {"AUTOMATION_DRY_RUN": "0"}):
                def failing_handler(_r):
                    raise RuntimeError("test failure")

                job = Job(rule, failing_handler, lambda: {})
                job._last_run = 0.0
                job.fire()

        self.assertEqual(job._retry_count, 1)
        self.assertGreater(job._retry_at, 0)

    def test_retry_exhaustion_resets_count(self):
        from scheduler import Job

        rule = _make_rule(max_retries=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scheduler._STOP_FILE", Path(tmpdir) / "stop"), \
                 patch("scheduler._AUDIT_FILE", Path(tmpdir) / "audit.jsonl"), \
                 patch("scheduler._FAILURE_FILE", Path(tmpdir) / "fail.jsonl"), \
                 patch("rules.set_rule_enabled", lambda *_: None), \
                 patch.dict(os.environ, {"AUTOMATION_DRY_RUN": "0"}):
                def failing_handler(_r):
                    raise RuntimeError("fail")

                job = Job(rule, failing_handler, lambda: {})
                job._last_run = 0.0
                # First fire: retry_count → 1
                job.fire()
                self.assertEqual(job._retry_count, 1)
                # Simulate retry due
                job._retry_at = 0.0
                # Second fire: exhausted → reset to 0
                job.fire()
                self.assertEqual(job._retry_count, 0)


# ── Approval gate ──────────────────────────────────────────────────────────────

class TestApprovalGate(unittest.TestCase):
    def test_high_risk_rule_goes_to_pending(self):
        from scheduler import Job

        rule = _make_rule(risk_tier="high")

        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "automation_pending.json"
            fired = []

            with patch("scheduler._STOP_FILE", Path(tmpdir) / "stop"), \
                 patch("scheduler._AUDIT_FILE", Path(tmpdir) / "audit.jsonl"), \
                 patch("scheduler._FAILURE_FILE", Path(tmpdir) / "fail.jsonl"), \
                 patch("scheduler._PENDING_FILE", pending_file), \
                 patch.dict(os.environ, {"AUTOMATION_DRY_RUN": "0"}):
                def handler(_r):
                    fired.append(1)

                job = Job(rule, handler, lambda: {})
                job._last_run = 0.0
                job.fire()

            # read while tmpdir still exists
            pending = json.loads(pending_file.read_text())

        self.assertEqual(fired, [], "high-risk action must not auto-execute")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["rule_id"], "test_rule")

    def test_low_risk_rule_executes_directly(self):
        rule = _make_rule(risk_tier="low")

        with tempfile.TemporaryDirectory() as tmpdir:
            fired = []

            with patch("scheduler._STOP_FILE", Path(tmpdir) / "stop"), \
                 patch("scheduler._AUDIT_FILE", Path(tmpdir) / "audit.jsonl"), \
                 patch("scheduler._FAILURE_FILE", Path(tmpdir) / "fail.jsonl"), \
                 patch.dict(os.environ, {"AUTOMATION_DRY_RUN": "0"}):
                from scheduler import Job

                def handler(_r):
                    fired.append(1)

                job = Job(rule, handler, lambda: {})
                job._last_run = 0.0
                job.fire()

        self.assertGreater(len(fired), 0)


# ── Schema validation ──────────────────────────────────────────────────────────

class TestSchemaValidation(unittest.TestCase):
    def test_valid_rule_no_errors(self):
        from rules import validate_rule

        rule = {
            "id": "good_rule",
            "description": "test",
            "enabled": True,
            "risk_tier": "low",
            "max_retries": 0,
            "cooldown_seconds": 0,
            "trigger": {"type": "interval", "seconds": 60},
            "conditions": [],
            "action": {"type": "notify", "channel": "log", "message": "ok"},
        }
        self.assertEqual(validate_rule(rule), [])

    def test_missing_id_reports_error(self):
        from rules import validate_rule

        rule = {"description": "no id", "trigger": {"type": "interval", "seconds": 60},
                "action": {"type": "notify"}}
        errors = validate_rule(rule)
        self.assertTrue(any("id" in e for e in errors))

    def test_unknown_trigger_type_error(self):
        from rules import validate_rule

        rule = {"id": "x", "description": "y",
                "trigger": {"type": "unknown_type"},
                "action": {"type": "notify"}}
        errors = validate_rule(rule)
        self.assertTrue(any("trigger type" in e for e in errors))

    def test_unknown_action_type_error(self):
        from rules import validate_rule

        rule = {"id": "x", "description": "y",
                "trigger": {"type": "interval", "seconds": 10},
                "action": {"type": "bad_action"}}
        errors = validate_rule(rule)
        self.assertTrue(any("action type" in e for e in errors))

    def test_duplicate_id_detected(self):
        from rules import validate_rules

        rule = {"id": "dup", "description": "x",
                "trigger": {"type": "interval", "seconds": 10},
                "action": {"type": "notify"}}
        errors = validate_rules([rule, rule])
        self.assertIn("dup", errors)

    def test_negative_max_retries_error(self):
        from rules import validate_rule

        rule = {"id": "x", "description": "y", "max_retries": -1,
                "trigger": {"type": "interval", "seconds": 10},
                "action": {"type": "notify"}}
        errors = validate_rule(rule)
        self.assertTrue(any("max_retries" in e for e in errors))


# ── Rule enable/disable ────────────────────────────────────────────────────────

class TestRuleEnableDisable(unittest.TestCase):
    def setUp(self):
        import rules as _rules_mod
        self._tmpdir = tempfile.TemporaryDirectory()
        self._rules_file = Path(self._tmpdir.name) / "rules.json"
        self._orig = _rules_mod._RULES_FILE
        _rules_mod._RULES_FILE = self._rules_file
        data = [{"id": "my_rule", "description": "test", "enabled": True,
                 "trigger": {"type": "interval", "seconds": 60},
                 "action": {"type": "notify"}}]
        self._rules_file.write_text(json.dumps(data))

    def tearDown(self):
        import rules as _rules_mod
        _rules_mod._RULES_FILE = self._orig
        self._tmpdir.cleanup()

    def test_disable_sets_enabled_false(self):
        from rules import load_all_rules, set_rule_enabled

        set_rule_enabled("my_rule", False)
        rules = load_all_rules()
        self.assertFalse(rules[0]["enabled"])

    def test_enable_sets_enabled_true(self):
        from rules import load_all_rules, set_rule_enabled

        set_rule_enabled("my_rule", False)
        set_rule_enabled("my_rule", True)
        rules = load_all_rules()
        self.assertTrue(rules[0]["enabled"])

    def test_unknown_rule_returns_message(self):
        from rules import set_rule_enabled

        msg = set_rule_enabled("no_such_rule", False)
        self.assertIn("not found", msg)


# ── Webhook HMAC signing ───────────────────────────────────────────────────────

class TestWebhookSigning(unittest.TestCase):
    def test_signature_header_present_when_secret_set(self):
        from notifier import _webhook_signature

        with patch.dict(os.environ, {"AUTOMATION_WEBHOOK_SECRET": "mysecret"}):
            sig = _webhook_signature(b'{"test":1}')
        self.assertIsNotNone(sig)
        self.assertTrue(sig.startswith("sha256="))

    def test_no_signature_when_secret_absent(self):
        from notifier import _webhook_signature

        env = {k: v for k, v in os.environ.items() if k != "AUTOMATION_WEBHOOK_SECRET"}
        with patch.dict(os.environ, env, clear=True):
            sig = _webhook_signature(b'{"test":1}')
        self.assertIsNone(sig)

    def test_signature_is_deterministic(self):
        from notifier import _webhook_signature

        data = b'{"rule_id":"test"}'
        with patch.dict(os.environ, {"AUTOMATION_WEBHOOK_SECRET": "abc123"}):
            s1 = _webhook_signature(data)
            s2 = _webhook_signature(data)
        self.assertEqual(s1, s2)

    def test_different_payloads_produce_different_signatures(self):
        from notifier import _webhook_signature

        with patch.dict(os.environ, {"AUTOMATION_WEBHOOK_SECRET": "abc123"}):
            s1 = _webhook_signature(b"payload_a")
            s2 = _webhook_signature(b"payload_b")
        self.assertNotEqual(s1, s2)


if __name__ == "__main__":
    unittest.main()
