import json
import mimetypes
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from runtime import (
    AccountsService,
    AppRegistry,
    CommunicationsService,
    ContactsService,
    FilesService,
    MediaService,
    NotificationsService,
    StateStore,
)

PORT = 8080
MAX_REQUEST_BYTES = 64 * 1024
VALID_APP_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

if platform.system() == "Windows":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    STATE_DIR = os.path.join(BASE_DIR, "state")
    ENV_PATH = None
else:
    BASE_DIR = "/opt/unlim8ted"
    STATE_DIR = os.path.join(BASE_DIR, "state")
    ENV_PATH = "/etc/default/unlim8ted"

UI_PATH = os.path.join(BASE_DIR, "ui", "index.html")
APP_JS_PATH = os.path.join(BASE_DIR, "ui", "app.js")
APPS_DIR = os.path.join(BASE_DIR, "apps")
STATE_PATH = os.path.join(STATE_DIR, "system.json")
CAPTURES_DIR = os.path.join(STATE_DIR, "captures")
PREVIEW_PATH = os.path.join(STATE_DIR, "camera-preview.jpg")
REGISTRY_PATH = os.path.join(BASE_DIR, "commands", "registry.json")
MEDIA_PREFIX = "/media/captures/"
CHROMIUM_PROFILE_DIR = os.path.join(STATE_DIR, "chromium-profile")

server_instance = None


def log(msg):
    print(msg, flush=True)


def log_client_event(payload):
    scope = str(payload.get("scope", "client") or "client")
    level = str(payload.get("level", "log") or "log").upper()
    message = str(payload.get("message", "") or "")
    extra = payload.get("extra")
    if extra is None:
        log(f"[CLIENT/{level}/{scope}] {message}")
        return
    try:
        detail = json.dumps(extra, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        detail = str(extra)
    log(f"[CLIENT/{level}/{scope}] {message} :: {detail}")


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def read_json(path, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback


def is_valid_app_id(value):
    return bool(VALID_APP_ID.fullmatch(str(value or "")))


def load_env_file(path):
    values = {}
    if not path or not os.path.exists(path):
        return values

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def merge_dict(base, override):
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


class CommandRunner:
    def __init__(self, config):
        self.config = config
        self.platform = platform.system()

    def run(self, args, env=None, timeout=8):
        try:
            completed = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env=env,
                check=False,
                text=True,
            )
            return (
                completed.returncode == 0,
                completed.stdout.strip(),
                completed.stderr.strip(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, "", str(exc)

    def _display_env(self):
        env = os.environ.copy()
        display = self.config.get("UNLIM8TED_DISPLAY", "")
        xauthority = self.config.get("UNLIM8TED_XAUTHORITY", "")
        if display:
            env["DISPLAY"] = display
        if xauthority:
            env["XAUTHORITY"] = xauthority
        return env

    def set_display_power(self, awake):
        if self.platform == "Windows":
            return True, "windows-noop"

        env = self._display_env()

        if shutil.which("xset") and env.get("DISPLAY"):
            command = ["xset", "dpms", "force", "on" if awake else "off"]
            ok, _, err = self.run(command, env=env)
            if ok:
                return True, "xset"
            if err:
                log(f"[DISPLAY] xset failed: {err}")

        output_name = self.config.get("UNLIM8TED_WLR_OUTPUT", "")
        if shutil.which("wlr-randr") and output_name:
            command = [
                "wlr-randr",
                "--output",
                output_name,
                "--on" if awake else "--off",
            ]
            ok, _, err = self.run(command, env=os.environ.copy())
            if ok:
                return True, "wlr-randr"
            if err:
                log(f"[DISPLAY] wlr-randr failed: {err}")

        return False, "unavailable"

    def set_brightness(self, level):
        clamped = max(0.05, min(1.0, float(level)))

        if self.platform == "Windows":
            return True, "windows-noop"

        for backlight in (
            self.config.get("UNLIM8TED_BACKLIGHT_PATH", ""),
            "/sys/class/backlight/10-0045/brightness",
            "/sys/class/backlight/rpi_backlight/brightness",
        ):
            if not backlight or not os.path.exists(backlight):
                continue
            max_path = os.path.join(os.path.dirname(backlight), "max_brightness")
            try:
                with open(max_path, "r", encoding="utf-8") as handle:
                    max_value = int(handle.read().strip())
                target = max(1, int(round(clamped * max_value)))
                with open(backlight, "w", encoding="utf-8") as handle:
                    handle.write(str(target))
                return True, "sysfs"
            except (OSError, ValueError) as exc:
                log(f"[DISPLAY] sysfs brightness failed: {exc}")

        if shutil.which("brightnessctl"):
            percent = f"{int(round(clamped * 100))}%"
            ok, _, err = self.run(["brightnessctl", "set", percent])
            if ok:
                return True, "brightnessctl"
            if err:
                log(f"[DISPLAY] brightnessctl failed: {err}")

        env = self._display_env()
        if shutil.which("xrandr") and env.get("DISPLAY"):
            output_name = self.config.get("UNLIM8TED_XRANDR_OUTPUT", "")
            if not output_name:
                return False, "xrandr-output-missing"
            command = [
                "xrandr",
                "--output",
                output_name,
                "--brightness",
                f"{clamped:.2f}",
            ]
            ok, _, err = self.run(command, env=env)
            if ok:
                return True, "xrandr"
            if err:
                log(f"[DISPLAY] xrandr brightness failed: {err}")

        return False, "unavailable"


class SystemState:
    def __init__(self):
        self.lock = threading.Lock()
        default_state = {
            "sleeping": False,
            "display_awake": True,
            "brightness": 0.68,
            "idle_timeout_sec": 45,
            "last_sleep_reason": "",
            "last_interaction": time.time(),
            "toggles": {
                "wifi": True,
                "bluetooth": True,
                "airplane": False,
                "focus": False,
            },
        }
        ensure_parent(STATE_PATH)
        ensure_parent(os.path.join(CAPTURES_DIR, ".keep"))
        self.state = merge_dict(default_state, read_json(STATE_PATH, {}))

    def save(self):
        with self.lock:
            ensure_parent(STATE_PATH)
            with open(STATE_PATH, "w", encoding="utf-8") as handle:
                json.dump(self.state, handle, indent=2, sort_keys=True)

    def public_state(self):
        with self.lock:
            return json.loads(json.dumps(self.state))


class DeviceService:
    def __init__(self):
        self.config = merge_dict(load_env_file(ENV_PATH), dict(os.environ))
        self.system_state = SystemState()
        self.runner = CommandRunner(self.config)
        self.store = StateStore(STATE_DIR)
        self.registry = AppRegistry(APPS_DIR, log)
        self.contacts = ContactsService(self.store)
        self.comms = CommunicationsService(self.store)
        self.accounts = AccountsService(self.store)
        self.media = MediaService(self.store, CAPTURES_DIR)
        self.files = FilesService([STATE_DIR, BASE_DIR])
        self.notifications = NotificationsService(self.store)
        self.ui_process = None
        self._restore_hardware_state()

    def _restore_hardware_state(self):
        state = self.system_state.state
        self.runner.set_brightness(state["brightness"])
        self.runner.set_display_power(not state["sleeping"])
        self.system_state.save()

    def _emit_app_event(self, event, payload=None):
        for app_id in self.installed_apps():
            module, _manifest = self.app_contract(app_id)
            if not module or not hasattr(module, "handle_system_event"):
                continue
            try:
                module.handle_system_event(
                    self.build_app_context(app_id), event, payload or {}
                )
            except Exception as exc:
                log(f"[APP:{app_id}] event '{event}' failed: {exc}")

    def start_activity_watchdog(self):
        thread = threading.Thread(target=self._activity_loop, daemon=True)
        thread.start()

    def _activity_loop(self):
        while True:
            time.sleep(2)
            state = self.system_state.state
            if state["sleeping"]:
                continue
            inactive_for = time.time() - float(
                state.get("last_interaction", time.time())
            )
            if inactive_for >= int(state.get("idle_timeout_sec", 45)):
                self.sleep("idle")

    def remember_activity(self):
        self.system_state.state["last_interaction"] = time.time()
        self.system_state.save()
        return self.get_state()

    def set_toggle(self, action, value=None):
        toggles = self.system_state.state["toggles"]
        if action not in toggles:
            return self.get_state()
        toggles[action] = (not toggles[action]) if value is None else bool(value)
        if action == "airplane" and toggles[action]:
            toggles["wifi"] = False
            toggles["bluetooth"] = False
        self.system_state.save()
        return self.get_state()

    def set_brightness(self, brightness):
        value = max(0.05, min(1.0, float(brightness)))
        self.system_state.state["brightness"] = value
        self.runner.set_brightness(value)
        self.system_state.save()
        return self.get_state()

    def sleep(self, reason="manual"):
        if self.system_state.state["sleeping"]:
            return self.get_state()
        self.system_state.state["sleeping"] = True
        self.system_state.state["display_awake"] = False
        self.system_state.state["last_sleep_reason"] = reason
        self._emit_app_event("sleep", {"reason": reason})
        self.runner.set_display_power(False)
        self.system_state.save()
        return self.get_state()

    def wake(self, reason="tap"):
        self.system_state.state["sleeping"] = False
        self.system_state.state["display_awake"] = True
        self.system_state.state["last_sleep_reason"] = ""
        self.system_state.state["last_interaction"] = time.time()
        self.runner.set_display_power(True)
        self.runner.set_brightness(self.system_state.state["brightness"])
        self._emit_app_event("wake", {"reason": reason})
        self.system_state.save()
        return self.get_state()

    def get_state(self):
        state = self.system_state.public_state()
        state["owner"] = self.accounts.state()["owner"]
        state["badges"] = self.notifications.badge_counts(
            self.comms, self.store.read("mail", {"mailboxes": {"inbox": []}})
        )
        return state

    def installed_apps(self):
        return self.registry.discover()

    def capture_urls(self, limit=12):
        return [item["url"] for item in self.media.captures(MEDIA_PREFIX, limit=limit)]

    def build_app_context(self, app):
        return {
            "app_id": app,
            "title": app.replace("-", " ").title(),
            "system": self.get_state(),
            "owner": self.accounts.state()["owner"],
            "installed_apps": self.installed_apps(),
            "captures": self.capture_urls(),
            "registry": read_json(REGISTRY_PATH, {}),
            "state_dir": STATE_DIR,
            "media_prefix": MEDIA_PREFIX,
            "capabilities": [
                "camera",
                "files",
                "network",
                "audio",
                "notifications",
                "account_access",
            ],
            "paths": {
                "base_dir": BASE_DIR,
                "state_dir": STATE_DIR,
                "apps_dir": APPS_DIR,
                "captures_dir": CAPTURES_DIR,
                "preview_path": PREVIEW_PATH,
                "media_prefix": MEDIA_PREFIX,
                "registry_path": REGISTRY_PATH,
            },
            "services": {
                "contacts": self.contacts,
                "communications": self.comms,
                "accounts": self.accounts,
                "media": self.media,
                "files": self.files,
                "notifications": self.notifications,
                "store": self.store,
                "runner": self.runner,
                "system_state": self.system_state,
                "system": self,
            },
            "now": datetime.utcnow().isoformat() + "Z",
        }

    def app_contract(self, app):
        if not is_valid_app_id(app):
            return None, None
        module = self.registry.load(app)
        if not module:
            return None, None
        manifest = (
            module.get_manifest()
            if hasattr(module, "get_manifest")
            else {
                "id": app,
                "title": app.replace("-", " ").title(),
                "capabilities": [],
                "routes": [],
                "required_services": [],
            }
        )
        return module, manifest

    def app_payload(self, app):
        module, manifest = self.app_contract(app)
        if not module:
            return None
        payload = (
            module.get_app_payload(self.build_app_context(app))
            if hasattr(module, "get_app_payload")
            else {}
        )
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault(
            "title", manifest.get("title", app.replace("-", " ").title())
        )
        payload.setdefault("app_id", app)
        payload.setdefault("view", "structured")
        payload.setdefault("sections", [])
        template_path = os.path.join(APPS_DIR, app, "index.html")
        if os.path.exists(template_path):
            payload.setdefault("template_url", f"/apps/{app}/index.html")
        client_script_path = os.path.join(APPS_DIR, app, "client.js")
        if os.path.exists(client_script_path):
            payload.setdefault("client_script_url", f"/apps/{app}/client.js")
        payload["manifest"] = manifest
        return payload

    def open_app(self, app):
        payload = self.app_payload(app)
        if payload:
            return {
                "ok": True,
                "status": "integrated",
                "app": payload,
                "system": self.get_state(),
            }

        path = os.path.join(APPS_DIR, app, "main.py")
        if os.path.exists(path):
            subprocess.Popen([sys.executable, path])
            return {
                "ok": True,
                "status": "opened",
                "app": {"app_id": app},
                "system": self.get_state(),
            }
        return {
            "ok": False,
            "code": "app_not_found",
            "message": f"Unknown app: {app}",
            "details": {"app_id": app},
        }

    def app_action(self, app, action, payload):
        module, _manifest = self.app_contract(app)
        if not module:
            return {
                "ok": False,
                "code": "app_not_found",
                "message": f"Unknown app: {app}",
                "details": {"app_id": app},
            }
        if not hasattr(module, "handle_action"):
            return {
                "ok": True,
                "app": self.app_payload(app),
                "system": self.get_state(),
            }
        result = module.handle_action(self.build_app_context(app), action, payload)
        if isinstance(result, dict):
            result.setdefault("ok", True)
            result["app"] = self.app_payload(app)
            result["system"] = self.get_state()
            return result
        return {"ok": True, "app": self.app_payload(app), "system": self.get_state()}

    def app_http(self, app, method, subpath, query=None, payload=None):
        module, _manifest = self.app_contract(app)
        if not module:
            return {
                "type": "json",
                "status": 404,
                "body": {
                    "ok": False,
                    "code": "app_not_found",
                    "message": f"Unknown app: {app}",
                },
            }

        if method == "GET" and not subpath:
            return {
                "type": "json",
                "status": 200,
                "body": {
                    "ok": True,
                    "app": self.app_payload(app),
                    "system": self.get_state(),
                },
            }

        if method == "POST" and subpath == "action":
            return {
                "type": "json",
                "status": 200,
                "body": self.app_action(
                    app,
                    (payload or {}).get("action", ""),
                    (payload or {}).get("payload", {}),
                ),
            }

        if hasattr(module, "handle_http"):
            response = module.handle_http(
                self.build_app_context(app),
                {
                    "method": method,
                    "subpath": subpath,
                    "query": query or {},
                    "payload": payload or {},
                    "path": f"/api/apps/{app}" + (f"/{subpath}" if subpath else ""),
                },
            )
            if isinstance(response, dict):
                response.setdefault("type", "json")
                response.setdefault("status", 200)
                if response["type"] == "json":
                    response.setdefault("body", {"ok": True})
                else:
                    response.setdefault("content_type", "application/octet-stream")
                    response.setdefault("body", b"")
                return response

        return {
            "type": "json",
            "status": 404,
            "body": {
                "ok": False,
                "code": "route_not_found",
                "message": f"Unknown app route: {app}/{subpath}",
            },
        }

    def handle_command(self, action, payload):
        log(f"[CMD] {action}")
        if action == "sleep":
            return {"ok": True, "system": self.sleep(payload.get("reason", "manual"))}
        if action == "wake":
            return {"ok": True, "system": self.wake(payload.get("reason", "tap"))}
        if action in self.system_state.state["toggles"]:
            return {"ok": True, "system": self.set_toggle(action)}
        if action == "brightness":
            level = payload.get("brightness", self.system_state.state["brightness"])
            return {"ok": True, "system": self.set_brightness(level)}
        return {
            "ok": False,
            "code": "unknown_command",
            "message": f"Unsupported command: {action}",
            "system": self.get_state(),
        }


device_service = DeviceService()


def parse_app_route(path):
    prefix = "/api/apps/"
    if not path.startswith(prefix):
        return None, None
    remainder = path[len(prefix) :]
    parts = [part for part in remainder.split("/") if part]
    if not parts:
        return "", ""
    app_id = parts[0]
    if not is_valid_app_id(app_id):
        return None, None
    return app_id, "/".join(parts[1:])


class Handler(BaseHTTPRequestHandler):
    server_version = "Unlim8tedHTTP/1.0"

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send(
        self,
        status=200,
        content_type="application/json",
        body=b"",
        apply_security_headers=True,
    ):
        self.send_response(status)
        self.send_header("Content-type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self._send(status=status, content_type="application/json", body=body)

    def _send_html(self, body, status=200):
        self._send(
            status=status,
            content_type="text/html; charset=utf-8",
            body=body.encode("utf-8"),
        )

    def _send_not_found(self, path, status=404):
        self._send_html(
            f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<title>Not Found</title>
<style>
body {{
    margin: 0;
    min-height: 100vh;
    display: grid;
    place-items: center;
    background: linear-gradient(180deg, #07111d 0%, #02060c 100%);
    color: #eef3ff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.card {{
    width: min(520px, calc(100vw - 32px));
    padding: 24px;
    border-radius: 24px;
    background: rgba(17, 26, 45, 0.92);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28);
}}
.eyebrow {{
    font-size: 12px;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: #8ea8cc;
    margin-bottom: 8px;
}}
.title {{
    font-size: 28px;
    font-weight: 800;
    margin-bottom: 10px;
}}
.copy {{
    font-size: 15px;
    line-height: 1.55;
    color: #b7c8e3;
}}
.path {{
    margin-top: 16px;
    padding: 12px 14px;
    border-radius: 16px;
    background: rgba(255,255,255,.06);
    color: #eef3ff;
    font-size: 13px;
    word-break: break-word;
}}
</style>
</head>
<body>
<section class="card">
<div class="eyebrow">Unlim8ted OS</div>
<div class="title">Route Not Found</div>
<div class="copy">The local backend does not expose this path.</div>
<div class="path">{path}</div>
</section>
</body>
</html>""",
            status=status,
        )

    def _send_app_response(self, response):
        if response.get("type") == "raw":
            self._send(
                status=int(response.get("status", 200)),
                content_type=response.get("content_type", "application/octet-stream"),
                body=response.get("body", b""),
                apply_security_headers=bool(
                    response.get("apply_security_headers", True)
                ),
            )
            return
        self._send_json(
            response.get("body", {}), status=int(response.get("status", 200))
        )

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_REQUEST_BYTES:
            self._send_json(
                {
                    "ok": False,
                    "code": "payload_too_large",
                    "message": "Request body too large",
                },
                status=413,
            )
            return None
        body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in (
            "/favicon.ico",
            "/robots.txt",
            "/manifest.json",
            "/apple-touch-icon.png",
        ):
            self._send(status=204, content_type="text/plain; charset=utf-8", body=b"")
            return

        if path in ("/", "/index.html"):
            with open(UI_PATH, "rb") as handle:
                self._send(
                    status=200,
                    content_type="text/html; charset=utf-8",
                    body=handle.read(),
                )
            return

        if path == "/app.js":
            with open(APP_JS_PATH, "rb") as handle:
                self._send(
                    status=200,
                    content_type="application/javascript; charset=utf-8",
                    body=handle.read(),
                )
            return

        if path.startswith("/apps/"):
            parts = [part for part in path.split("/") if part]
            if len(parts) >= 3:
                app_root = os.path.abspath(os.path.join(APPS_DIR, parts[1]))
                target = os.path.abspath(os.path.join(app_root, *parts[2:]))
                if target.startswith(app_root + os.sep) and os.path.isfile(target):
                    content_type, _encoding = mimetypes.guess_type(target)
                    if target.endswith(".js"):
                        content_type = "application/javascript; charset=utf-8"
                    elif target.endswith(".html"):
                        content_type = "text/html; charset=utf-8"
                    elif content_type and content_type.startswith("text/"):
                        content_type = f"{content_type}; charset=utf-8"
                    else:
                        content_type = content_type or "application/octet-stream"
                    with open(target, "rb") as handle:
                        self._send(
                            status=200, content_type=content_type, body=handle.read()
                        )
                    return
            self._send_not_found(path)
            return

        if path == "/api/state":
            self._send_json({"ok": True, "system": device_service.get_state()})
            return

        app_id, subpath = parse_app_route(path)
        if app_id is not None:
            self._send_app_response(
                device_service.app_http(
                    app_id, "GET", subpath, query=parse_qs(parsed.query)
                )
            )
            return

        if path.startswith(MEDIA_PREFIX):
            filename = os.path.basename(path)
            target = os.path.join(CAPTURES_DIR, filename)
            if os.path.exists(target):
                with open(target, "rb") as handle:
                    self._send(
                        status=200, content_type="image/jpeg", body=handle.read()
                    )
                return
            self._send_not_found(path)
            return

        self._send_not_found(path)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._read_json()
        if data is None:
            return

        if path == "/open":
            self._send_json(device_service.open_app(data.get("app", "")))
            return

        if path == "/cmd":
            self._send_json(device_service.handle_command(data.get("action", ""), data))
            return

        if path == "/api/system/sleep":
            self._send_json(
                {
                    "ok": True,
                    "system": device_service.sleep(data.get("reason", "manual")),
                }
            )
            return

        if path == "/api/system/wake":
            self._send_json(
                {"ok": True, "system": device_service.wake(data.get("reason", "tap"))}
            )
            return

        if path == "/api/system/brightness":
            brightness = data.get(
                "brightness", device_service.get_state()["brightness"]
            )
            self._send_json(
                {"ok": True, "system": device_service.set_brightness(brightness)}
            )
            return

        if path == "/api/system/activity":
            self._send_json({"ok": True, "system": device_service.remember_activity()})
            return

        if path == "/api/log/client":
            log_client_event(data)
            self._send_json({"ok": True})
            return

        app_id, subpath = parse_app_route(path)
        if app_id is not None:
            self._send_app_response(
                device_service.app_http(
                    app_id, "POST", subpath, query=parse_qs(parsed.query), payload=data
                )
            )
            return

        self._send_json(
            {
                "ok": False,
                "code": "route_not_found",
                "message": f"Unknown route: {path}",
            },
            status=404,
        )

    def log_message(self, *args):
        return


def display_exists(display, xauthority):
    env = os.environ.copy()
    env["DISPLAY"] = display
    if xauthority:
        env["XAUTHORITY"] = xauthority

    try:
        return (
            subprocess.run(
                ["xdpyinfo"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=6,
                check=False,
            ).returncode
            == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


def detect_display(config):
    explicit = config.get("UNLIM8TED_DISPLAY", "")
    xauthority = config.get("UNLIM8TED_XAUTHORITY", "")
    if explicit and display_exists(explicit, xauthority):
        return explicit

    for candidate in (":0", ":1", ":2"):
        if display_exists(candidate, xauthority):
            return candidate
    return None


def start_backend():
    global server_instance
    server_instance = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log(f"[SYSTEM] Backend running on {PORT}")
    server_instance.serve_forever()


def stop_backend():
    global server_instance
    if server_instance:
        server_instance.shutdown()


def start_ui():
    system = platform.system()
    config = device_service.config
    os.makedirs(CHROMIUM_PROFILE_DIR, exist_ok=True)

    if system == "Windows":
        user = os.environ.get("USERNAME")
        chromium_path = (
            rf"C:\Users\{user}\AppData\Local\Chromium\Application\chrome.exe"
        )
        if not os.path.exists(chromium_path):
            log("[DISPLAY] Chromium not found")
            return None
        log("[DISPLAY] Launching Chromium (windowed mobile size)")
        return subprocess.Popen(
            [
                chromium_path,
                "--window-size=360,780",
                "--window-position=0,0",
                "--force-device-scale-factor=1",
                f"--user-data-dir={CHROMIUM_PROFILE_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-session-crashed-bubble",
                "--disable-component-update",
                "--user-agent=Mozilla/5.0 (Linux; Android 10; Mobile)",
                f"--app=http://localhost:{PORT}",
            ]
        )

    display = None
    for _ in range(20):
        display = detect_display(config)
        if display:
            break
        time.sleep(1)

    if not display:
        log("[DISPLAY] No display found")
        return None

    env = os.environ.copy()
    env["DISPLAY"] = display
    xauthority = config.get("UNLIM8TED_XAUTHORITY", "")
    if xauthority:
        env["XAUTHORITY"] = xauthority

    browser = config.get("UNLIM8TED_BROWSER", "chromium-browser")
    browser_args = [
        browser,
        "--window-size=720,1560",
        "--no-sandbox",
        f"--user-data-dir={CHROMIUM_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--disable-infobars",
        "--disable-component-update",
        "--check-for-update-interval=31536000",
        f"--app=http://localhost:{PORT}",
    ]
    return subprocess.Popen(browser_args, env=env)


if __name__ == "__main__":
    log("[SYSTEM] Boot")
    device_service.start_activity_watchdog()

    if not port_in_use(PORT):
        threading.Thread(target=start_backend, daemon=True).start()

    time.sleep(1.5)
    ui = start_ui()
    if ui:
        ui.wait()

    stop_backend()
