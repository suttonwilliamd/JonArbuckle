"""Isolated guard self-tests: expected attempts never share product-test audits.

All operations below hit patched entrypoints, never real network/desktop/config.
The nested unittest result is intentional: catching the immediate exception must
not make an enclosing ordinary test pass. No production allowlist is involved.
"""
import builtins
import io
import socket
import threading
import tkinter
import unittest
from functools import partial
from pathlib import Path
from unittest.mock import patch

import plyer
import requests
from test_http_retry import core, safety_guards


class StickyGuardOracleTests(unittest.TestCase):
    def test_every_guard_records_before_raising_and_fails_scope_exit(self):
        probes = {
            "socket.socket": lambda: socket.socket(),
            "socket.create_connection": lambda: socket.create_connection(("fixture.invalid", 443)),
            "socket.getaddrinfo": lambda: socket.getaddrinfo("fixture.invalid", 443),
            "socket.gethostbyname": lambda: socket.gethostbyname("fixture.invalid"),
            "socket.gethostbyname_ex": lambda: socket.gethostbyname_ex("fixture.invalid"),
            "requests.sessions.Session.request": lambda: requests.Session().get("https://fixture.invalid"),
            "requests.adapters.HTTPAdapter.send": lambda: requests.adapters.HTTPAdapter().send(None),
            "tkinter.Tk": lambda: tkinter.Tk(),
            "threading.Thread.start": lambda: threading.Thread().start(),
            "plyer.notification.notify": lambda: plyer.notification.notify(),
            "builtins.open(config.json)": lambda: builtins.open(Path("config.json")),
            "io.open(config.json)": lambda: io.open(Path("config.json")),
        }
        for surface, probe in probes.items():
            with self.subTest(surface=surface):
                with self.assertRaisesRegex(AssertionError, "Sticky forbidden attempts"):
                    with safety_guards() as audit:
                        with self.assertRaisesRegex(AssertionError, "Forbidden operation attempted"):
                            probe()
                        self.assertEqual(audit.attempts, (surface,))
                # Retained after the final assertion, not cleared to make it pass.
                self.assertEqual(audit.attempts, (surface,))

    def test_repeated_caught_attempts_are_not_reset(self):
        with self.assertRaisesRegex(AssertionError, "Sticky forbidden attempts"):
            with safety_guards() as audit:
                for _ in range(2):
                    try:
                        socket.socket()
                    except AssertionError:
                        pass
        self.assertEqual(audit.attempts, ("socket.socket", "socket.socket"))

    def test_clean_scope_and_next_scope_are_independent(self):
        with safety_guards() as first:
            self.assertEqual(first.attempts, ())
        with safety_guards() as second:
            self.assertIsNot(first, second)
            self.assertEqual(second.attempts, ())

    def test_broad_product_handlers_cannot_hide_attempts_from_unittest(self):
        for scenario, expected in (("socket", "socket.socket"),
                                   ("config", "core.load_config"),
                                   ("http", "requests.sessions.Session.request")):
            with self.subTest(scenario=scenario):
                class SwallowedAttempt(unittest.TestCase):
                    def runTest(inner):
                        audit = inner.enterContext(safety_guards())
                        inner.enterContext(patch.object(core, "_global_config", {}))
                        if scenario == "socket":
                            inner.assertEqual(core.check_socket("fixture.invalid", 443), -1)
                        elif scenario == "config":
                            inner.enterContext(patch.object(core, "_global_config", None))
                            inner.enterContext(patch.object(core, "load_config", side_effect=partial(
                                audit.blocked, "core.load_config")))
                            inner.assertIsNone(core._get_global_config())
                        else:
                            result = core.check_endpoint({"url": "https://fixture.invalid", "retries": 0})
                            inner.assertEqual(result.status, "red")
                        inner.assertEqual(audit.attempts, (expected,))

                result = unittest.TestResult()
                SwallowedAttempt().run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertEqual(result.errors, [])
                self.assertEqual(len(result.failures), 1)
                self.assertIn("Sticky forbidden attempts", result.failures[0][1])
                self.assertIn(expected, result.failures[0][1])

    def test_import_style_scope_detects_swallowed_guard(self):
        # Same context used around actual core import, without reimporting core or
        # dependencies under synthetic module identities.
        with self.assertRaisesRegex(AssertionError, "Sticky forbidden attempts"):
            with safety_guards() as audit:
                try:
                    io.open("config.json")
                except Exception:
                    pass
        self.assertEqual(audit.attempts, ("io.open(config.json)",))


if __name__ == "__main__":
    unittest.main()
