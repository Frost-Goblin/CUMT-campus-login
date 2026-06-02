from __future__ import annotations

import copy
import time
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, Signal

from constants import (
    LATENCY_TARGETS,
)
import main as portal_core

class LoginWorker(QObject):
    finished = Signal(dict)
    log = Signal(str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = copy.deepcopy(config)

    def run(self) -> None:
        opener = portal_core.build_opener(
            bool(self.config["request"].get("skip_tls_verify", False))
        )

        def emit_log(message: str) -> None:
            self.log.emit(message)

        log_token = portal_core.set_thread_log_writer(emit_log)
        try:
            context, _, final_url = portal_core.fetch_portal_context(opener, self.config)
            self.log.emit(
                "Resolved context: "
                f"ip={context.get('wlan_user_ip', '')}, "
                f"mac={context.get('wlan_user_mac', '')}, "
                f"ac_name={context.get('wlan_ac_name', '')}, "
                f"ssid={context.get('ssid', '')}, "
                f"url={final_url}"
            )
            self.finished.emit(portal_core.perform_login_with_result(opener, self.config))
        except Exception as exc:
            self.finished.emit(
                {
                    "ok": False,
                    "message": str(exc),
                }
            )
        finally:
            portal_core.reset_thread_log_writer(log_token)


class LogoutWorker(QObject):
    finished = Signal(dict)
    log = Signal(str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = copy.deepcopy(config)

    def run(self) -> None:
        opener = portal_core.build_opener(
            bool(self.config["request"].get("skip_tls_verify", False))
        )

        def emit_log(message: str) -> None:
            self.log.emit(message)

        log_token = portal_core.set_thread_log_writer(emit_log)
        try:
            self.finished.emit(portal_core.perform_logout_with_result(opener, self.config))
        except Exception as exc:
            self.finished.emit(
                {
                    "ok": False,
                    "message": str(exc),
                }
            )
        finally:
            portal_core.reset_thread_log_writer(log_token)


class StatusWorker(QObject):
    finished = Signal(dict)

    def __init__(self, config: dict, timeout_seconds: int = 2):
        super().__init__()
        self.config = copy.deepcopy(config)
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        try:
            status = portal_core.get_campus_status(
                self.config,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as exc:
            status = {
                "network": {
                    "interface_name": "",
                    "network_type": "",
                    "ssid": "",
                    "wlan_user_ip": "",
                    "wlan_user_mac": "",
                },
                "campus_connected": False,
                "campus_authenticated": False,
                "portal_reachable": False,
                "portal_url": "",
                "virtual_network": {
                    "active": False,
                    "interface_name": "",
                    "interface_description": "",
                },
                "error": str(exc),
            }
        self.finished.emit(status)


class ConnectivityWorker(QObject):
    finished = Signal(dict)

    def __init__(self, config: dict, timeout_seconds: int = 3):
        super().__init__()
        self.config = copy.deepcopy(config)
        self.timeout_seconds = timeout_seconds

    def run(self) -> None:
        log_token = portal_core.set_thread_log_writer(lambda _message: None)
        try:
            result = portal_core.get_campus_status(
                self.config,
                timeout_seconds=self.timeout_seconds,
            )
            opener = portal_core.build_opener(
                bool(self.config["request"].get("skip_tls_verify", False))
            )
            request_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CampusLoginDesktop/1.0"
            }
            latency_results: list[dict] = []
            for name, url in LATENCY_TARGETS:
                started = time.perf_counter()
                try:
                    request = urllib.request.Request(url, headers=request_headers)
                    with opener.open(request, timeout=self.timeout_seconds) as response:
                        response.read(1)
                        elapsed_ms = round((time.perf_counter() - started) * 1000)
                        status_code = getattr(response, "status", None) or response.getcode()
                        final_url = response.geturl()
                        latency_results.append(
                            {
                                "name": name,
                                "url": url,
                                "ok": True,
                                "latency_ms": elapsed_ms,
                                "status_code": status_code,
                                "final_url": final_url,
                                "note": f"HTTP {status_code}",
                            }
                        )
                except urllib.error.HTTPError as exc:
                    elapsed_ms = round((time.perf_counter() - started) * 1000)
                    latency_results.append(
                        {
                            "name": name,
                            "url": url,
                            "ok": True,
                            "latency_ms": elapsed_ms,
                            "status_code": exc.code,
                            "final_url": exc.geturl(),
                            "note": f"HTTP {exc.code}",
                        }
                    )
                except Exception as exc:
                    latency_results.append(
                        {
                            "name": name,
                            "url": url,
                            "ok": False,
                            "latency_ms": None,
                            "status_code": None,
                            "final_url": "",
                            "note": str(exc),
                        }
                    )
            result["latency_tests"] = latency_results
            self.finished.emit(result)
        except Exception as exc:
            self.finished.emit(
                {
                    "network": {
                        "interface_name": "",
                        "network_type": "",
                        "ssid": "",
                        "wlan_user_ip": "",
                        "wlan_user_mac": "",
                    },
                    "campus_connected": False,
                    "campus_authenticated": False,
                    "portal_reachable": False,
                    "portal_url": "",
                    "virtual_network": {
                        "active": False,
                        "interface_name": "",
                        "interface_description": "",
                    },
                    "latency_tests": [],
                    "error": str(exc),
                }
            )
        finally:
            portal_core.reset_thread_log_writer(log_token)
