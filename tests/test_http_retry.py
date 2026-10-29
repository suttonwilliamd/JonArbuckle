"""Offline HTTP contract tests. Never start the application or load config.json."""
from contextlib import ExitStack, contextmanager
from functools import partial
import builtins
import importlib
import io
import socket
import threading
import tkinter
import unittest
from unittest.mock import Mock, call, patch
import warnings

import plyer
import requests


class ForbiddenAttempts:
    """One scope's sticky audit; never retain arguments (possibly secrets).

    No reset/allowlist: deliberate guard probes belong in separate oracle tests,
    not in a product-test scope. Even caught guard exceptions fail scope exit.
    """

    def __init__(self):
        self._attempts = []

    @property
    def attempts(self):
        return tuple(self._attempts)

    def blocked(self, surface, *args, **kwargs):
        self._attempts.append(surface)
        raise AssertionError(f"Forbidden operation attempted: {surface}")

    def assert_clean(self):
        if self._attempts:
            raise AssertionError(f"Sticky forbidden attempts: {self.attempts!r}")


@contextmanager
def safety_guards():
    audit = ForbiddenAttempts()
    # The finally also checks import/setup/body failures, after restoring patches.
    try:
        with ExitStack() as stack:
            for target in (
                "socket.socket", "socket.create_connection", "socket.getaddrinfo",
                "socket.gethostbyname", "socket.gethostbyname_ex",
                "requests.sessions.Session.request", "requests.adapters.HTTPAdapter.send",
                "tkinter.Tk", "threading.Thread.start",
            ):
                stack.enter_context(patch(target, side_effect=partial(audit.blocked, target)))
            # Do not force plyer's lazy native notification backend to load.
            stack.enter_context(patch.object(plyer, "notification", Mock(
                notify=partial(audit.blocked, "plyer.notification.notify"))))
            for module in (builtins, io):
                original = module.open
                surface = f"{module.__name__}.open(config.json)"

                def guarded_open(file, *args, _open=original, _surface=surface, **kwargs):
                    if str(file).endswith("config.json"):
                        audit.blocked(_surface)
                    return _open(file, *args, **kwargs)
                stack.enter_context(patch.object(module, "open", guarded_open))
            yield audit
    finally:
        audit.assert_clean()


# Actual product dependencies, no stub modules. Restore the pre-existing warning
# filters because core's existing global warning policy is outside this change.
with safety_guards(), warnings.catch_warnings():
    core = importlib.import_module("jonarbuckle_core")


class HttpRetryTests(unittest.TestCase):
    def setUp(self):
        audit = self.enterContext(safety_guards())
        self.enterContext(patch.object(core, "load_config", side_effect=partial(
            audit.blocked, "core.load_config")))
        self.enterContext(patch.object(core, "_global_config", {}))
        self.get = self.enterContext(patch.object(core.requests, "get"))
        self.sleep = self.enterContext(patch.object(core.time, "sleep"))
        self.ep = {"url": "https://retry-fixture.invalid/health", "retries": 2,
                   "backoff_ms": 125}

    def response(self, code):
        response = requests.Response()
        response.status_code = code
        response._content = b"synthetic fixture"
        response.close = Mock()
        return response

    def test_503_then_200_recovers(self):
        first, final = self.response(503), self.response(200)
        self.get.side_effect = [first, final]
        result = core._http_request_with_retry(self.ep)
        print(f"503->200: returned={result.status_code}, attempts={self.get.call_count}")
        self.assertIs(result, final)
        self.assertEqual(self.get.call_count, 2)
        first.close.assert_called_once_with()
        final.close.assert_not_called()
        self.sleep.assert_called_once_with(0.125)

    def test_every_5xx_exhaustion_returns_final_response(self):
        for code in range(500, 600):
            with self.subTest(code=code):
                self.get.reset_mock()
                self.sleep.reset_mock()
                responses = [self.response(code) for _ in range(3)]
                self.get.side_effect = responses
                self.assertIs(core._http_request_with_retry(self.ep), responses[-1])
                self.assertEqual(self.get.call_count, 3)
                self.assertEqual(self.sleep.call_args_list, [call(0.125)] * 2)
                for response in responses[:-1]:
                    response.close.assert_called_once_with()
                responses[-1].close.assert_not_called()

    def test_exhausted_5xx_stays_yellow_http(self):
        self.get.side_effect = [self.response(503) for _ in range(3)]
        result = core.check_endpoint(self.ep)
        self.assertEqual((result.status, result.message), ("yellow", "HTTP 503"))
        self.assertEqual(self.get.call_count, 3)

    def test_zero_retries_returns_5xx_without_sleep_or_close(self):
        response = self.response(503)
        self.get.return_value = response
        self.assertIs(core._http_request_with_retry({**self.ep, "retries": 0}), response)
        self.get.assert_called_once()
        response.close.assert_not_called()
        self.sleep.assert_not_called()

    def test_non_5xx_returns_immediately(self):
        for code in (200, 301, 399, *range(400, 500), 600):
            with self.subTest(code=code):
                self.get.reset_mock()
                response = self.response(code)
                self.get.return_value = response
                self.assertIs(core._http_request_with_retry(self.ep), response)
                self.get.assert_called_once()
                response.close.assert_not_called()
        self.sleep.assert_not_called()

    def test_transient_exceptions_recover_and_exhaust(self):
        http_error = requests.HTTPError(response=self.response(503))
        for error in (requests.ConnectionError("synthetic"),
                      requests.Timeout("synthetic"), http_error):
            with self.subTest(error=type(error).__name__):
                self.get.reset_mock()
                self.sleep.reset_mock()
                final = self.response(200)
                self.get.side_effect = [error, final]
                self.assertIs(core._http_request_with_retry(self.ep), final)
                self.assertEqual(self.get.call_count, 2)
                self.sleep.assert_called_once_with(0.125)
                self.get.reset_mock()
                self.sleep.reset_mock()
                self.get.side_effect = [error] * 3
                with self.assertRaises(type(error)) as raised:
                    core._http_request_with_retry(self.ep)
                self.assertIs(raised.exception, error)
                self.assertEqual(self.get.call_count, 3)
                self.assertEqual(self.sleep.call_args_list, [call(0.125)] * 2)

    def test_non_transient_exceptions_raise_immediately(self):
        for error in (ValueError("synthetic"), requests.HTTPError(),
                      requests.HTTPError(response=self.response(404))):
            with self.subTest(error=repr(error)):
                self.get.reset_mock()
                self.get.side_effect = error
                with self.assertRaises(type(error)) as raised:
                    core._http_request_with_retry(self.ep)
                self.assertIs(raised.exception, error)
                self.get.assert_called_once()
        self.sleep.assert_not_called()

    def test_mixed_exception_response_budget_and_close_order(self):
        first, final = self.response(502), self.response(200)
        events = Mock()
        events.attach_mock(first.close, "close")
        events.attach_mock(self.get, "get")
        events.attach_mock(self.sleep, "sleep")
        self.get.side_effect = [first, requests.Timeout("synthetic"), final]
        self.assertIs(core._http_request_with_retry(self.ep), final)
        request = call.get(self.ep["url"], timeout=5, verify=True)
        self.assertEqual(events.mock_calls, [request, call.close(), call.sleep(0.125),
                                            request, call.sleep(0.125), request])

    def test_defaults_and_global_vs_endpoint_settings(self):
        cases = [({}, {}, 2, 0.2),
                 ({"default_retries": 2, "default_backoff_ms": 75}, {}, 3, 0.075),
                 ({"default_retries": 4, "default_backoff_ms": 999},
                  {"retries": 1, "backoff_ms": 0}, 2, 0.0)]
        for config, overrides, attempts, delay in cases:
            with self.subTest(config=config, overrides=overrides):
                self.get.reset_mock()
                self.sleep.reset_mock()
                self.get.side_effect = [self.response(503) for _ in range(attempts)]
                with patch.object(core, "_global_config", config):
                    core._http_request_with_retry({"url": self.ep["url"], **overrides})
                self.assertEqual(self.get.call_count, attempts)
                self.assertEqual(self.sleep.call_args_list, [call(delay)] * (attempts - 1))

    def test_timeout_tls_forwarded_on_every_attempt(self):
        for overrides, timeout, tls in (({}, 5, True),
                                        ({"timeout": 1.25, "verify_tls": False}, 1.25, False)):
            with self.subTest(overrides=overrides):
                self.get.reset_mock()
                self.get.side_effect = [self.response(503), self.response(200)]
                core._http_request_with_retry({**self.ep, **overrides})
                self.assertEqual(self.get.call_args_list,
                                 [call(self.ep["url"], timeout=timeout, verify=tls)] * 2)

if __name__ == "__main__":
    unittest.main()
