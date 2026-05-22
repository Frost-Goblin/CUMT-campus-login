from __future__ import annotations

import base64
import http.cookiejar
import json
import os
import re
import subprocess
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent


def resolve_user_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "CUMT Campus Login"
    return Path.home() / "CUMT Campus Login"


USER_DATA_DIR = resolve_user_data_dir()
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = USER_DATA_DIR / "config.json"
LOG_DIR = USER_DATA_DIR
LOG_PATH = USER_DATA_DIR / "campus-login.log"

SUCCESS_MARKERS = (
    "dr.comwebloginid_3.htm",
    "/self/dashboard",
    "logout",
)

LOGIN_MARKERS = (
    "dr.comwebloginid_0.htm",
    "a79.htm",
    "loginbox.js",
)

CONNECTIVITY_TEST_TARGETS = (
    (
        "Microsoft Connect Test",
        "http://www.msftconnecttest.com/connecttest.txt",
        "Microsoft Connect Test",
    ),
    (
        "NeverSSL",
        "http://neverssl.com/",
        "NeverSSL",
    ),
)


DEFAULT_CONFIG = {
    "request": {
        "timeout_seconds": 8,
        "skip_tls_verify": False,
    },
    "portal": {
        "target_ssid": "CUMT_Stu",
        "target_ssids": ["CUMT_Stu", "CUMT_Tec"],
        "landing_url": "http://10.2.5.251/",
        "login_base_url": "http://10.2.5.251:801/eportal/",
        "logout_path": "/eportal/?c=ACSetting&a=Logout&ver=1.0",
        "js_version": "3.0",
        "default_wlan_ac_name": "NAS",
        "default_wlan_ac_ip": "",
    },
    "login": {
        "username": "",
        "password": "",
        "account_suffix": "@telecom",
        "login_method": 1,
        "extra_params": {},
        "account_prefix": "",
    },
    "ui": {
        "close_behavior": "tray",
        "check_on_startup": True,
        "status_monitor_enabled": False,
        "open_log_on_error": False,
        "startup_enabled": False,
        "startup_mode": "show",
        "status_refresh_interval_seconds": 30,
        "auto_connect_enabled": False,
        "system_notifications_enabled": True,
        "tray_minimize_notice_shown": False,
    },
}


def get_default_config() -> dict:
    return json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        config = get_default_config()
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return config

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except PermissionError:
        pass
    print(line)


def build_opener(skip_tls_verify: bool) -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = []
    if skip_tls_verify:
        context = ssl._create_unverified_context()
        handlers.append(urllib.request.HTTPSHandler(context=context))

    cookie_jar = http.cookiejar.CookieJar()
    handlers.append(urllib.request.HTTPCookieProcessor(cookie_jar))

    opener = urllib.request.build_opener(*handlers)
    opener.addheaders = [
        (
            "User-Agent",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
            ),
        ),
        ("Accept", "*/*"),
    ]
    return opener


def request_text(
    opener: urllib.request.OpenerDirector,
    url: str,
    timeout: int,
    method: str = "GET",
    data: bytes | None = None,
) -> tuple[str, str]:
    req = urllib.request.Request(url=url, data=data, method=method)
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "gbk"
        try:
            body = raw.decode(charset, errors="ignore")
        except LookupError:
            body = raw.decode("gbk", errors="ignore")
        return body, resp.geturl()


def extract_jsonp_payload(text: str) -> dict:
    match = re.search(r"\((\{.*\})\)\s*;?\s*$", text)
    if not match:
        return {}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}


def maybe_decode_base64(value: str) -> str:
    try:
        raw = base64.b64decode(value, validate=True)
        for encoding in ("utf-8", "gbk", "gb2312"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return value


def extract_portal_message(payload: dict) -> str:
    for key in ("msg", "msga", "message", "error_msg", "ret_msg", "reason"):
        value = payload.get(key)
        if value:
            return maybe_decode_base64(str(value)).strip()
    return ""


def classify_login_response(payload: dict) -> dict:
    result = str(payload.get("result", ""))
    message = extract_portal_message(payload)
    normalized = message.lower()

    if result == "1":
        return {
            "ok": True,
            "reason": "success",
            "message": "登录成功",
            "portal_message": message,
            "payload": payload,
        }

    if (
        "终端ip已经在线" in normalized
        or "终端 ip 已经在线" in normalized
    ):
        return {
            "ok": True,
            "reason": "already_online",
            "message": "终端 IP 已经在线。",
            "portal_message": message,
            "payload": payload,
        }

    failure_patterns = (
        (
            "outside_access_window",
            "当前时段不允许上网。",
            (
                "authentication fail errcode=16",
                "当前时段不允许上网",
            ),
        ),
        (
            "account_not_found",
            "账号不存在，请确认账号或运营商选择是否正确。",
            ("账号不存在",),
        ),
        (
            "invalid_credentials",
            "统一身份认证用户名密码错误！",
            (
                "userid error",
                "用户名密码错误",
                "统一身份认证用户名密码错误",
            ),
        ),
        (
            "device_limit",
            "登录设备超限，请先下线其他设备。",
            (
                "rad;limit users err",
            ),
        ),
    )
    for reason, user_message, patterns in failure_patterns:
        if any(pattern in normalized for pattern in patterns):
            return {
                "ok": False,
                "reason": reason,
                "message": user_message,
                "portal_message": message,
                "payload": payload,
            }

    return {
        "ok": False,
        "reason": "portal_rejected",
        "message": message or "登录失败，门户未返回明确原因。",
        "portal_message": message,
        "payload": payload,
    }


def build_user_account(login_cfg: dict) -> str:
    username = login_cfg["username"].strip()
    prefix = login_cfg.get("account_prefix", "").strip()
    suffix = login_cfg.get("account_suffix", "").strip()
    return f"{prefix}{username}{suffix}"


def first_value(query: dict, *keys: str) -> str:
    for key in keys:
        values = query.get(key)
        if values and values[0]:
            return values[0]
    return ""


def normalize_mac(value: str) -> str:
    return value.replace("-", "").replace(":", "").lower()


def normalize_target_ssids(value: str | list[str] | tuple[str, ...] | set[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []

    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def get_portal_target_ssids(portal_cfg: dict) -> list[str]:
    target_ssids = normalize_target_ssids(portal_cfg.get("target_ssids"))
    if target_ssids:
        return target_ssids
    return normalize_target_ssids(portal_cfg.get("target_ssid", ""))


def ssid_matches_targets(current_ssid: str, target_ssids: list[str]) -> bool:
    return not target_ssids or current_ssid in target_ssids


def extract_context_from_url(url: str) -> dict:
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return {
        "wlan_user_ip": first_value(query, "wlanuserip", "userip", "wlan_user_ip"),
        "wlan_user_mac": normalize_mac(first_value(query, "mac", "wlanusermac", "wlan_user_mac")),
        "wlan_ac_name": first_value(query, "wlanacname", "wlan_ac_name"),
        "wlan_ac_ip": first_value(query, "wlanacip", "nasip", "wlan_ac_ip"),
        "ssid": first_value(query, "ssid"),
    }


def merge_context(base_context: dict, extra_context: dict) -> dict:
    merged = dict(base_context)
    for key, value in extra_context.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def run_command(command: list[str], timeout_seconds: int = 4) -> str:
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        check=True,
        timeout=timeout_seconds,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    return result.stdout


def run_powershell(script: str, timeout_seconds: int = 4) -> str:
    return run_command(
        ["powershell", "-NoProfile", "-Command", script],
        timeout_seconds=timeout_seconds,
    )


def detect_active_wifi_info(target_ssids: str | list[str] | tuple[str, ...] | set[str] | None) -> dict:
    allowed_ssids = normalize_target_ssids(target_ssids)
    detected = {
        "interface_name": "",
        "ssid": "",
        "wlan_user_ip": "",
        "wlan_user_mac": "",
        "network_type": "",
    }

    try:
        ps_output = run_powershell(
            "@("
            "$wifi = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' -and $_.Name -like 'WLAN*' } | Select-Object -First 1;"
            "if ($null -ne $wifi) {"
            "$ssid = (netsh wlan show interfaces | Select-String '^[ ]*SSID[ ]*:[ ]*(.+)$' | "
            "Where-Object { $_.Line -notmatch 'BSSID' } | Select-Object -First 1).Matches[0].Groups[1].Value.Trim();"
            "$ip = (Get-NetIPAddress -InterfaceIndex $wifi.ifIndex -AddressFamily IPv4 | "
            "Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1 -ExpandProperty IPAddress);"
            "[PSCustomObject]@{ Name=$wifi.Name; SSID=$ssid; MAC=($wifi.MacAddress -replace '-', '').ToLower(); IP=$ip } | ConvertTo-Json -Compress"
            "}"
            ")"
        ).strip()
        if ps_output:
            wifi = json.loads(ps_output)
            detected["interface_name"] = wifi.get("Name", "") or ""
            detected["ssid"] = wifi.get("SSID", "") or ""
            detected["wlan_user_mac"] = normalize_mac(wifi.get("MAC", "") or "")
            detected["wlan_user_ip"] = wifi.get("IP", "") or ""
            detected["network_type"] = "wifi"
            if detected["interface_name"] and detected["wlan_user_mac"]:
                if ssid_matches_targets(detected["ssid"], allowed_ssids):
                    return detected
    except Exception:
        pass

    try:
        netsh_output = run_command(["netsh", "wlan", "show", "interfaces"])
    except Exception:
        return detected

    current_name = ""
    current_ssid = ""
    current_mac = ""
    current_state = ""

    for raw_line in netsh_output.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        lowered_key = key.lower()
        if lowered_key == "name":
            current_name = value
        elif lowered_key == "state":
            current_state = value.lower()
        elif lowered_key == "ssid" and "bssid" not in lowered_key:
            current_ssid = value
        elif lowered_key == "physical address":
            current_mac = normalize_mac(value)

    if "connected" not in current_state:
        return detected
    if not ssid_matches_targets(current_ssid, allowed_ssids):
        return detected

    detected["interface_name"] = current_name
    detected["ssid"] = current_ssid
    detected["wlan_user_mac"] = current_mac
    detected["network_type"] = "wifi"

    try:
        ipconfig_output = run_command(["ipconfig"])
    except Exception:
        return detected

    current_section = ""
    for raw_line in ipconfig_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if raw_line.endswith(":"):
            current_section = raw_line.strip().rstrip(":")
            continue
        if current_name and current_name not in current_section:
            continue
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
        if match and ("IPv4" in line or "IPv4 地址" in line):
            detected["wlan_user_ip"] = match.group(1)
            break

    return detected


def detect_active_wired_info() -> dict:
    detected = {
        "interface_name": "",
        "ssid": "",
        "wlan_user_ip": "",
        "wlan_user_mac": "",
        "network_type": "",
    }

    try:
        ps_output = run_powershell(
            "@("
            "$ethernet = Get-NetAdapter | Where-Object { "
            "$_.Status -eq 'Up' -and $_.HardwareInterface -eq $true -and "
            "$_.Name -notlike 'WLAN*' -and "
            "$_.InterfaceDescription -notmatch 'Bluetooth|Virtual|VMware|Hyper-V|VPN|TAP|Loopback|vEthernet|Pseudo' "
            "} | Select-Object -First 1;"
            "if ($null -ne $ethernet) {"
            "$ip = (Get-NetIPAddress -InterfaceIndex $ethernet.ifIndex -AddressFamily IPv4 | "
            "Where-Object { $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1 -ExpandProperty IPAddress);"
            "[PSCustomObject]@{ Name=$ethernet.Name; MAC=($ethernet.MacAddress -replace '-', '').ToLower(); IP=$ip } | ConvertTo-Json -Compress"
            "}"
            ")"
        ).strip()
        if not ps_output:
            return detected

        adapter = json.loads(ps_output)
        detected["interface_name"] = adapter.get("Name", "") or ""
        detected["wlan_user_mac"] = normalize_mac(adapter.get("MAC", "") or "")
        detected["wlan_user_ip"] = adapter.get("IP", "") or ""
        detected["network_type"] = "ethernet"
        return detected
    except Exception:
        return detected


def has_active_network_identity(info: dict) -> bool:
    return bool(
        info.get("interface_name")
        and info.get("wlan_user_mac")
        and info.get("wlan_user_ip")
    )


def detect_active_network_info(
    target_ssids: str | list[str] | tuple[str, ...] | set[str] | None,
) -> dict:
    allowed_ssids = normalize_target_ssids(target_ssids)
    wifi_info = detect_active_wifi_info("")
    if has_active_network_identity(wifi_info):
        if ssid_matches_targets(wifi_info.get("ssid", ""), allowed_ssids):
            return wifi_info

    wired_info = detect_active_wired_info()
    if has_active_network_identity(wired_info):
        return wired_info

    if has_active_network_identity(wifi_info):
        return wifi_info

    return {
        "interface_name": "",
        "ssid": "",
        "wlan_user_ip": "",
        "wlan_user_mac": "",
        "network_type": "",
    }


def is_target_network_ready(
    info: dict,
    target_ssids: str | list[str] | tuple[str, ...] | set[str] | None,
) -> bool:
    allowed_ssids = normalize_target_ssids(target_ssids)
    if not has_active_network_identity(info):
        return False

    network_type = info.get("network_type", "")
    if network_type == "wifi":
        current_ssid = info.get("ssid", "")
        return ssid_matches_targets(current_ssid, allowed_ssids)
    if network_type == "ethernet":
        return True
    return False


def wait_for_target_network(
    target_ssids: str | list[str] | tuple[str, ...] | set[str] | None,
    poll_interval_seconds: int = 1,
    max_wait_seconds: int = 15,
) -> dict:
    allowed_ssids = normalize_target_ssids(target_ssids)
    target_text = ", ".join(allowed_ssids)
    if not allowed_ssids:
        return detect_active_network_info("")

    write_log(
        f"Waiting up to {max_wait_seconds} seconds for campus Wi-Fi {target_text} or wired campus access"
    )
    previous_status: tuple[str, str, str, str] | None = None
    deadline = time.monotonic() + max_wait_seconds

    while True:
        info = detect_active_network_info(allowed_ssids)
        status = (
            info.get("interface_name", ""),
            info.get("ssid", ""),
            info.get("wlan_user_ip", ""),
            info.get("wlan_user_mac", ""),
        )

        if is_target_network_ready(info, allowed_ssids):
            write_log(
                "Target campus network is ready: "
                f"type={info.get('network_type', '')}, "
                f"iface={info.get('interface_name', '')}, "
                f"ssid={info.get('ssid', '')}, "
                f"ip={info.get('wlan_user_ip', '')}, "
                f"mac={info.get('wlan_user_mac', '')}"
            )
            return info

        if time.monotonic() >= deadline:
            current_ssid = info.get("ssid", "")
            if info.get("network_type") == "wifi" and current_ssid in allowed_ssids:
                raise RuntimeError(
                    f"15 秒内校园网未就绪：已连接到 {current_ssid}，但未获得可用 IPv4"
                )
            raise RuntimeError(f"15 秒内未连接到校园网 {target_text} 或可用的校园网有线连接")

        if status != previous_status:
            current_ssid = info.get("ssid", "")
            if info.get("network_type") == "ethernet":
                write_log("Detected active wired network, waiting for campus portal availability")
            elif current_ssid and current_ssid not in allowed_ssids:
                write_log(f"Connected to SSID {current_ssid}, waiting for one of {target_text}")
            elif current_ssid in allowed_ssids:
                write_log(f"Connected to {current_ssid}, waiting for IPv4 assignment")
            else:
                write_log(f"Wi-Fi is not connected to any of {target_text} yet")
            previous_status = status

        remaining = max(0.1, deadline - time.monotonic())
        time.sleep(min(max(1, int(poll_interval_seconds)), remaining))


def get_campus_status(
    config: dict,
    timeout_seconds: int | None = None,
) -> dict:
    portal_cfg = config["portal"]
    request_cfg = config["request"]
    target_ssids = get_portal_target_ssids(portal_cfg)
    active_network = detect_active_network_info(target_ssids)
    network_type = active_network.get("network_type", "")
    wifi_matches_target = network_type == "wifi" and (
        ssid_matches_targets(active_network.get("ssid", ""), target_ssids)
    )
    wired_active = network_type == "ethernet" and has_active_network_identity(active_network)

    portal_reachable = False
    authenticated = False
    final_url = portal_cfg["landing_url"]

    if wifi_matches_target or wired_active:
        opener = build_opener(bool(request_cfg.get("skip_tls_verify", False)))
        timeout = timeout_seconds
        if timeout is None:
            timeout = min(3, int(request_cfg.get("timeout_seconds", 8)))
        try:
            body, final_url = request_text(opener, portal_cfg["landing_url"], int(timeout))
            portal_reachable = True
            authenticated = is_authenticated(body, final_url)
        except urllib.error.URLError:
            pass

    campus_connected = wifi_matches_target or (wired_active and portal_reachable)
    return {
        "network": active_network,
        "campus_connected": campus_connected,
        "campus_authenticated": campus_connected and authenticated,
        "portal_reachable": portal_reachable,
        "portal_url": final_url,
    }


def fetch_portal_context(
    opener: urllib.request.OpenerDirector,
    config: dict,
) -> tuple[dict, str, str]:
    portal_cfg = config["portal"]
    timeout = int(config["request"]["timeout_seconds"])
    target_ssids = get_portal_target_ssids(portal_cfg)

    local_context = detect_active_network_info(target_ssids)
    write_log(
        "Local network context: "
        f"type={local_context.get('network_type', '')}, "
        f"iface={local_context.get('interface_name', '')}, "
        f"ssid={local_context.get('ssid', '')}, "
        f"ip={local_context.get('wlan_user_ip', '')}, "
        f"mac={local_context.get('wlan_user_mac', '')}"
    )
    context = {
        "wlan_user_ip": local_context.get("wlan_user_ip", ""),
        "wlan_user_mac": local_context.get("wlan_user_mac", ""),
        "ssid": local_context.get("ssid", ""),
        "wlan_ac_name": "",
        "wlan_ac_ip": "",
    }
    body = ""
    final_url = portal_cfg["landing_url"]
    try:
        body, final_url = request_text(opener, portal_cfg["landing_url"], timeout)
        landing_context = extract_context_from_url(final_url)
        write_log(
            "Portal landing context: "
            f"url={final_url}, "
            f"ip={landing_context.get('wlan_user_ip', '')}, "
            f"mac={landing_context.get('wlan_user_mac', '')}, "
            f"ac_name={landing_context.get('wlan_ac_name', '')}"
        )
        # Trust the active local network session for IP/MAC; only fill portal-side context from the redirect.
        context = merge_context(
            context,
            {
                "wlan_ac_name": landing_context.get("wlan_ac_name", ""),
                "wlan_ac_ip": landing_context.get("wlan_ac_ip", ""),
                "ssid": landing_context.get("ssid", ""),
            },
        )
    except urllib.error.URLError as exc:
        write_log(f"Landing page fetch failed: {exc}")

    return context, body, final_url


def is_authenticated(body: str, final_url: str) -> bool:
    lowered_body = body.lower()
    lowered_url = final_url.lower()

    if any(marker in lowered_url for marker in LOGIN_MARKERS):
        return False
    if any(marker in lowered_body for marker in LOGIN_MARKERS):
        return False

    if any(marker in lowered_url for marker in SUCCESS_MARKERS):
        return True
    if any(marker in lowered_body for marker in SUCCESS_MARKERS):
        return True
    return False


def _host_of(url: str) -> str:
    return (urllib.parse.urlparse(url).hostname or "").lower()


def probe_external_connectivity(
    opener: urllib.request.OpenerDirector,
    timeout: int,
) -> dict:
    for label, url, expected_marker in CONNECTIVITY_TEST_TARGETS:
        try:
            body, final_url = request_text(opener, url, timeout)
        except Exception as exc:
            write_log(f"Connectivity probe {label} failed: {exc}")
            continue

        final_host = _host_of(final_url)
        expected_host = _host_of(url)
        body_lower = body.lower()
        expected_lower = expected_marker.lower()
        captive = any(marker in final_url.lower() for marker in LOGIN_MARKERS) or any(
            marker in body_lower for marker in LOGIN_MARKERS
        )
        success = False
        if not captive and final_host == expected_host:
            if expected_lower in body_lower:
                success = True
            elif len(body.strip()) > 0:
                success = True

        write_log(
            f"Connectivity probe {label}: success={success}, final_url={final_url}"
        )
        if success:
            return {
                "external_reachable": True,
                "external_test_name": label,
                "external_test_url": url,
                "external_final_url": final_url,
            }

    return {
        "external_reachable": False,
        "external_test_name": "",
        "external_test_url": "",
        "external_final_url": "",
    }


def run_connectivity_test(
    config: dict,
    timeout_seconds: int | None = None,
) -> dict:
    status = get_campus_status(config, timeout_seconds=timeout_seconds)
    request_cfg = config["request"]
    timeout = timeout_seconds
    if timeout is None:
        timeout = min(3, int(request_cfg.get("timeout_seconds", 8)))

    network = status.get("network", {})
    if not has_active_network_identity(network):
        write_log("Connectivity test skipped: no active network identity")
        status.update(
            {
                "external_reachable": False,
                "external_test_name": "",
                "external_test_url": "",
                "external_final_url": "",
            }
        )
        return status

    opener = build_opener(bool(request_cfg.get("skip_tls_verify", False)))
    status.update(probe_external_connectivity(opener, int(timeout)))
    return status


def build_login_url(config: dict, context: dict) -> str:
    portal_cfg = config["portal"]
    login_cfg = config["login"]
    timestamp = str(int(time.time() * 1000))
    callback = f"dr{timestamp}"

    params = {
        "c": "Portal",
        "a": "login",
        "callback": callback,
        "login_method": str(login_cfg.get("login_method", 1)),
        "user_account": build_user_account(login_cfg),
        "user_password": login_cfg["password"],
        "wlan_user_ip": context["wlan_user_ip"],
        "wlan_user_mac": context["wlan_user_mac"],
        "wlan_ac_ip": context.get("wlan_ac_ip", ""),
        "wlan_ac_name": context.get("wlan_ac_name", ""),
        "jsVersion": portal_cfg.get("js_version", "3.0"),
        "_": timestamp,
    }

    for key, value in login_cfg.get("extra_params", {}).items():
        params[key] = value

    query = urllib.parse.urlencode(params)
    return f"{portal_cfg['login_base_url']}?{query}"


def build_logout_url(config: dict) -> str:
    portal_cfg = config["portal"]
    logout_path = portal_cfg.get(
        "logout_path",
        "/eportal/?c=ACSetting&a=Logout&ver=1.0",
    )
    return urllib.parse.urljoin(portal_cfg["login_base_url"], logout_path)


def perform_login_with_result(opener: urllib.request.OpenerDirector, config: dict) -> dict:
    timeout = int(config["request"]["timeout_seconds"])
    context, body, final_url = fetch_portal_context(opener, config)
    write_log(f"Portal page resolved to: {final_url}")
    write_log(
        "Portal context: "
        f"ip={context.get('wlan_user_ip', '')}, "
        f"mac={context.get('wlan_user_mac', '')}, "
        f"ac_name={context.get('wlan_ac_name', '')}, "
        f"ac_ip={context.get('wlan_ac_ip', '')}, "
        f"ssid={context.get('ssid', '')}"
    )

    if is_authenticated(body, final_url):
        write_log("Portal already reports an authenticated session")
        return {
            "ok": True,
            "reason": "already_authenticated",
            "message": "终端 IP 已经在线。",
            "portal_message": "",
            "payload": {},
        }

    portal_cfg = config["portal"]
    if not context.get("wlan_ac_name"):
        fallback_ac_name = portal_cfg.get("default_wlan_ac_name", "").strip()
        if fallback_ac_name:
            context["wlan_ac_name"] = fallback_ac_name
            write_log(f"Using fallback wlan_ac_name: {fallback_ac_name}")
    if not context.get("wlan_ac_ip"):
        fallback_ac_ip = portal_cfg.get("default_wlan_ac_ip", "").strip()
        if fallback_ac_ip:
            context["wlan_ac_ip"] = fallback_ac_ip
            write_log(f"Using fallback wlan_ac_ip: {fallback_ac_ip}")

    if not context.get("wlan_user_ip") or not context.get("wlan_user_mac"):
        raise RuntimeError("Could not obtain current Wi-Fi IPv4/MAC for the active campus session")
    if not context.get("wlan_ac_name"):
        raise RuntimeError("Could not obtain wlan_ac_name from the portal flow")

    login_url = build_login_url(config, context)
    write_log(f"Sending portal login for IP {context['wlan_user_ip']}")
    response_text, _ = request_text(opener, login_url, timeout)

    payload = extract_jsonp_payload(response_text)
    rejected_result: dict | None = None
    if payload:
        login_result = classify_login_response(payload)
        result = str(payload.get("result", ""))
        message = login_result.get("portal_message", "")
        if login_result["ok"] and login_result["reason"] == "success":
            write_log("Portal response reported login success")
            return login_result
        if login_result["ok"]:
            write_log(f"Portal response indicates success: {message}")
            return login_result
        write_log(f"Portal response: result={result}, message={message}, payload={payload}")
        if login_result["reason"] != "portal_rejected":
            return login_result
        rejected_result = login_result
    else:
        write_log(f"Portal raw response: {response_text[:300]}")

    refreshed_body, refreshed_url = request_text(opener, config["portal"]["landing_url"], timeout)
    write_log(f"Portal check after login resolved to: {refreshed_url}")
    if is_authenticated(refreshed_body, refreshed_url):
        return {
            "ok": True,
            "reason": "success_after_check",
            "message": "登录成功",
            "portal_message": "",
            "payload": payload,
        }

    return rejected_result or {
        "ok": False,
        "reason": "not_confirmed",
        "message": "登录失败，未能确认联网成功。",
        "portal_message": "",
        "payload": payload,
    }


def perform_login(opener: urllib.request.OpenerDirector, config: dict) -> bool:
    return bool(perform_login_with_result(opener, config).get("ok"))


def perform_logout_with_result(opener: urllib.request.OpenerDirector, config: dict) -> dict:
    timeout = int(config["request"]["timeout_seconds"])
    logout_url = build_logout_url(config)
    write_log("Sending portal logout")
    response_text, _ = request_text(opener, logout_url, timeout)
    payload = extract_jsonp_payload(response_text)
    if payload:
        write_log(f"Portal logout response: {payload}")
    else:
        write_log(f"Portal logout raw response: {response_text[:300]}")

    refreshed_body, refreshed_url = request_text(opener, config["portal"]["landing_url"], timeout)
    if not is_authenticated(refreshed_body, refreshed_url):
        return {
            "ok": True,
            "reason": "logout_success",
            "message": "已注销校园网登录。",
            "payload": payload,
        }
    return {
        "ok": False,
        "reason": "logout_not_confirmed",
        "message": "注销请求已发送，但未能确认已下线。",
        "payload": payload,
    }


def main() -> int:
    try:
        config = load_config()
    except FileNotFoundError:
        print("config.json not found")
        return 1

    target_ssids = get_portal_target_ssids(config["portal"])
    if target_ssids:
        wait_for_target_network(target_ssids)

    request_cfg = config["request"]
    opener = build_opener(bool(request_cfg.get("skip_tls_verify", False)))

    write_log("Login attempt 1/1")
    try:
        if perform_login(opener, config):
            write_log("Campus network login succeeded")
            return 0
        write_log("Portal login finished but success was not confirmed")
    except urllib.error.URLError as exc:
        write_log(f"Login request failed: {exc}")
    except Exception as exc:
        write_log(f"Unexpected error: {exc}")

    write_log("Campus network login failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
