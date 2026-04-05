import importlib.util
import json
import os
import secrets
import shutil
import tempfile
import time
from datetime import datetime


def _default_contacts():
    return {
        "contacts": [
            {"id": "alex", "name": "Alex Chen", "favorite": True, "phone": "alex://voip", "email": "alex@unlim8ted.local"},
            {"id": "studio", "name": "Studio Desk", "favorite": True, "phone": "studio://desk", "email": "desk@unlim8ted.local"},
            {"id": "gate", "name": "Front Gate", "favorite": False, "phone": "gate://intercom", "email": "gate@unlim8ted.local"},
            {"id": "bench", "name": "CM4 Bench", "favorite": True, "phone": "bench://cm4", "email": "bench@unlim8ted.local"},
        ]
    }


def _default_comms():
    return {
        "sync_version": 1,
        "calls": [],
        "threads": [
            {
                "id": "alex",
                "title": "Alex Chen",
                "participants": ["Alex Chen"],
                "unread": 0,
                "messages": [
                    {"id": "m1", "sender": "Alex Chen", "body": "Meet at the lab at 6?", "timestamp": "2026-03-27T17:30:00Z", "status": "delivered"}
                ],
            },
            {
                "id": "studio",
                "title": "Studio",
                "participants": ["Studio"],
                "unread": 0,
                "messages": [
                    {"id": "m2", "sender": "Studio", "body": "Render build finished successfully.", "timestamp": "2026-03-27T16:45:00Z", "status": "delivered"}
                ],
            },
        ],
    }


def _default_accounts():
    return {
        "owner": {"name": "Primary Owner", "device_name": "Unlim8ted Phone"},
        "mail_accounts": [
            {"id": "local", "label": "Local Mail", "address": "owner@unlim8ted.local", "enabled": True}
        ],
    }


def _default_mail():
    return {
        "mailboxes": {
            "inbox": [
                {"id": "mail-1", "from": "vendor@panel.local", "subject": "Vendor Quote", "body": "Panel carrier quote received.", "unread": True, "starred": False},
                {"id": "mail-2", "from": "print@shop.local", "subject": "Print Batch", "body": "The enclosure sample batch is complete.", "unread": False, "starred": True},
            ],
            "drafts": [],
            "sent": [],
            "archive": [],
        }
    }


def _default_music():
    return {
        "playing": False,
        "index": 0,
        "queue": ["Signal Bloom", "DSI Afterglow", "Midnight Compile", "Aurora Bus"],
        "playlists": [{"name": "Favorites", "tracks": ["Signal Bloom", "Aurora Bus"]}],
    }


def _default_maps():
    return {
        "destination": "Lab Entrance",
        "saved_places": ["Lab Entrance", "Printer Room", "Camera Bench", "Roof Antenna Deck"],
        "recent_searches": [],
    }


def _default_notes():
    return {
        "notes": [
            {"id": "n1", "title": "Display", "body": "Validate DSI panel output name on target hardware."},
            {"id": "n2", "title": "Camera", "body": "Tune libcamera resolution and exposure profile."},
        ]
    }


def _default_clock():
    return {
        "alarms": [{"id": "a1", "label": "Wake", "time": "07:00", "enabled": True}],
        "timers": [{"id": "t1", "label": "Dev Sync", "minutes": 10}],
        "world": [{"city": "UTC", "offset": "+00:00"}, {"city": "New York", "offset": "-04:00"}],
    }


def _default_notifications():
    return {"items": []}


def _default_companion(accounts_state=None):
    owner = (accounts_state or _default_accounts())["owner"]
    phone_id = owner.get("device_name", "Unlim8ted Phone").lower().replace(" ", "-")
    return {
        "phone_id": phone_id or "unlim8ted-phone",
        "pairing_codes": [],
        "devices": [],
        "push_events": [],
    }


class StateStore:
    def __init__(self, state_dir):
        self.state_dir = state_dir
        os.makedirs(self.state_dir, exist_ok=True)

    def _path(self, name):
        return os.path.join(self.state_dir, f"{name}.json")

    def read(self, name, default):
        path = self._path(name)
        if not os.path.exists(path):
            return json.loads(json.dumps(default))
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return json.loads(json.dumps(default))

    def write(self, name, value):
        path = self._path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(path), prefix=f".{name}-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2)
            replace_error = None
            for _attempt in range(4):
                try:
                    os.replace(temp_path, path)
                    replace_error = None
                    break
                except PermissionError as exc:
                    replace_error = exc
                    time.sleep(0.05)
            if replace_error is not None:
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(value, handle, indent=2)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class ContactsService:
    def __init__(self, store):
        self.store = store
        self.key = "contacts"

    def list(self):
        return self.store.read(self.key, _default_contacts())["contacts"]

    def favorites(self):
        return [contact for contact in self.list() if contact.get("favorite")]

    def search(self, query):
        query_lower = query.lower().strip()
        if not query_lower:
            return self.list()
        return [contact for contact in self.list() if query_lower in contact["name"].lower()]


class CommunicationsService:
    def __init__(self, store):
        self.store = store
        self.key = "communications"

    def _state(self):
        return self.store.read(self.key, _default_comms())

    def _save(self, state):
        self.store.write(self.key, state)

    def _bump_sync_version(self, state):
        state["sync_version"] = int(state.get("sync_version", 0)) + 1
        return state["sync_version"]

    def list_calls(self):
        return self._state()["calls"]

    def add_call(self, target):
        state = self._state()
        state["calls"].insert(0, {"target": target, "timestamp": datetime.utcnow().isoformat() + "Z", "status": "ended"})
        state["calls"] = state["calls"][:30]
        self._bump_sync_version(state)
        self._save(state)
        return state["calls"]

    def list_threads(self):
        return self._state()["threads"]

    def get_thread(self, thread_id):
        for thread in self._state()["threads"]:
            if thread["id"] == thread_id:
                return thread
        return None

    def send_message(self, thread_id, sender, body, client_message_id=""):
        state = self._state()
        thread = next((item for item in state["threads"] if item["id"] == thread_id), None)
        if not thread:
            thread = {"id": thread_id, "title": thread_id.title(), "participants": [thread_id.title()], "unread": 0, "messages": []}
            state["threads"].insert(0, thread)
        message = {
            "id": f"msg-{len(thread['messages']) + 1}",
            "sender": sender,
            "body": body,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "sent",
        }
        if str(client_message_id or "").strip():
            message["client_message_id"] = str(client_message_id).strip()
        thread["messages"].append(message)
        thread["unread"] = 0
        self._bump_sync_version(state)
        self._save(state)
        return message

    def mark_thread_read(self, thread_id):
        state = self._state()
        thread = next((item for item in state["threads"] if item["id"] == thread_id), None)
        if not thread:
            return None
        if int(thread.get("unread", 0)) != 0:
            thread["unread"] = 0
            self._bump_sync_version(state)
            self._save(state)
        return thread

    def sync_version(self):
        return int(self._state().get("sync_version", 0))


class AccountsService:
    def __init__(self, store):
        self.store = store
        self.key = "accounts"

    def state(self):
        return self.store.read(self.key, _default_accounts())


class MediaService:
    def __init__(self, store, captures_dir):
        self.store = store
        self.captures_dir = captures_dir
        self.music_key = "music"

    def captures(self, media_prefix, limit=48):
        if not os.path.isdir(self.captures_dir):
            return []
        names = sorted([name for name in os.listdir(self.captures_dir) if name.lower().endswith(".jpg")], reverse=True)
        return [{"name": name, "url": f"{media_prefix}{name}"} for name in names[:limit]]

    def delete_capture(self, name):
        target = os.path.join(self.captures_dir, name)
        if os.path.isfile(target):
            os.remove(target)
            return True
        return False

    def music_state(self):
        return self.store.read(self.music_key, _default_music())

    def save_music_state(self, value):
        self.store.write(self.music_key, value)


class FilesService:
    def __init__(self, roots):
        self.roots = [os.path.abspath(root) for root in roots if os.path.exists(root)]

    def _is_hidden(self, name):
        return str(name or "").startswith(".")

    def _safe(self, path):
        try:
            candidate = os.path.abspath(path)
        except (TypeError, ValueError):
            return None
        for root in self.roots:
            try:
                if os.path.commonpath([candidate, root]) == root:
                    return candidate
            except ValueError:
                continue
        return None

    def _safe_child_name(self, name):
        candidate = os.path.basename(str(name or "").strip())
        if not candidate or candidate in {".", ".."} or candidate != str(name or "").strip():
            return None
        return candidate

    def list_dir(self, path):
        target = self._safe(path) or (self.roots[0] if self.roots else None)
        if not target or not os.path.isdir(target):
            return {"path": target or "", "items": []}
        items = []
        for name in sorted(os.listdir(target)):
            if self._is_hidden(name):
                continue
            full = os.path.join(target, name)
            items.append({"name": name, "path": full, "kind": "dir" if os.path.isdir(full) else "file"})
        return {"path": target, "items": items}

    def read_text(self, path, limit=4000):
        target = self._safe(path)
        if not target or not os.path.isfile(target):
            return ""
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read(limit)
        except OSError:
            return ""

    def create_text(self, dir_path, name, body=""):
        target_dir = self._safe(dir_path)
        safe_name = self._safe_child_name(name)
        if not target_dir or not os.path.isdir(target_dir):
            return False
        if not safe_name:
            return False
        target = os.path.join(target_dir, safe_name)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(body)
        return True

    def create_dir(self, dir_path, name):
        target_dir = self._safe(dir_path)
        safe_name = self._safe_child_name(name)
        if not target_dir or not os.path.isdir(target_dir):
            return False
        if not safe_name:
            return False
        os.makedirs(os.path.join(target_dir, safe_name), exist_ok=True)
        return True

    def delete(self, path):
        target = self._safe(path)
        if not target:
            return False
        if os.path.isdir(target):
            shutil.rmtree(target)
        elif os.path.exists(target):
            os.remove(target)
        return True


class NotificationsService:
    def __init__(self, store):
        self.store = store
        self.key = "notifications"

    def state(self):
        return self.store.read(self.key, _default_notifications())

    def badge_counts(self, comms_service, mail_state):
        return {
            "messages": sum(thread.get("unread", 0) for thread in comms_service.list_threads()),
            "mail": sum(1 for item in mail_state["mailboxes"]["inbox"] if item.get("unread")),
        }


class CompanionService:
    def __init__(self, store):
        self.store = store
        self.key = "companion"

    def _state(self):
        accounts_state = self.store.read("accounts", _default_accounts())
        return self.store.read(self.key, _default_companion(accounts_state))

    def _save(self, state):
        self.store.write(self.key, state)

    def _now(self):
        return int(time.time())

    def _now_iso(self):
        return datetime.utcnow().isoformat() + "Z"

    def _new_token(self, size=32):
        return secrets.token_urlsafe(size)

    def _redact_push_token(self, token):
        token = str(token or "")
        if len(token) <= 8:
            return token
        return f"{token[:4]}...{token[-4:]}"

    def create_pairing_code(self, label="Companion Device", ttl_sec=600):
        state = self._state()
        now = self._now()
        state["pairing_codes"] = [
            item for item in state.get("pairing_codes", [])
            if int(item.get("expires_at_epoch", 0)) > now and not item.get("used")
        ]
        code = secrets.token_hex(3).upper()
        record = {
            "code": code,
            "label": str(label or "Companion Device").strip() or "Companion Device",
            "created_at": self._now_iso(),
            "expires_at_epoch": now + max(60, int(ttl_sec)),
            "used": False,
        }
        state["pairing_codes"].insert(0, record)
        self._save(state)
        return record

    def complete_pairing(self, pairing_code, device_name, worker_url):
        state = self._state()
        now = self._now()
        record = next(
            (
                item for item in state.get("pairing_codes", [])
                if str(item.get("code", "")).upper() == str(pairing_code or "").upper()
            ),
            None,
        )
        if not record or record.get("used") or int(record.get("expires_at_epoch", 0)) <= now:
            return None
        device_id = self._new_token(12)
        refresh_token = self._new_token(32)
        access_token = self._new_token(24)
        access_expires_at_epoch = now + 3600
        device = {
            "device_id": device_id,
            "device_name": str(device_name or "").strip() or record.get("label", "Companion Device"),
            "worker_url": str(worker_url or "").strip(),
            "paired_at": self._now_iso(),
            "last_seen_at": self._now_iso(),
            "revoked": False,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "access_expires_at_epoch": access_expires_at_epoch,
            "push_token": "",
            "push_platform": "",
            "push_updated_at": "",
        }
        record["used"] = True
        state.setdefault("devices", []).append(device)
        self._save(state)
        return {
            "phone_id": state.get("phone_id", "unlim8ted-phone"),
            "phone_name": self.store.read("accounts", _default_accounts())["owner"].get("device_name", "Unlim8ted Phone"),
            "device_id": device_id,
            "device_name": device["device_name"],
            "access_token": access_token,
            "access_expires_at_epoch": access_expires_at_epoch,
            "refresh_token": refresh_token,
        }

    def refresh_session(self, refresh_token, device_id):
        state = self._state()
        device = next(
            (
                item for item in state.get("devices", [])
                if item.get("device_id") == device_id
                and item.get("refresh_token") == refresh_token
                and not item.get("revoked")
            ),
            None,
        )
        if not device:
            return None
        device["access_token"] = self._new_token(24)
        device["access_expires_at_epoch"] = self._now() + 3600
        device["last_seen_at"] = self._now_iso()
        self._save(state)
        return {
            "device_id": device["device_id"],
            "access_token": device["access_token"],
            "access_expires_at_epoch": device["access_expires_at_epoch"],
            "refresh_token": device["refresh_token"],
        }

    def authenticate_access_token(self, access_token):
        state = self._state()
        now = self._now()
        device = next(
            (
                item for item in state.get("devices", [])
                if item.get("access_token") == access_token
                and not item.get("revoked")
                and int(item.get("access_expires_at_epoch", 0)) > now
            ),
            None,
        )
        if not device:
            return None
        device["last_seen_at"] = self._now_iso()
        self._save(state)
        return {
            "device_id": device["device_id"],
            "device_name": device["device_name"],
            "worker_url": device.get("worker_url", ""),
        }

    def register_push_token(self, device_id, push_token, platform="android"):
        state = self._state()
        device = next((item for item in state.get("devices", []) if item.get("device_id") == device_id and not item.get("revoked")), None)
        if not device:
            return None
        device["push_token"] = str(push_token or "").strip()
        device["push_platform"] = str(platform or "android").strip() or "android"
        device["push_updated_at"] = self._now_iso()
        self._save(state)
        return {
            "device_id": device["device_id"],
            "push_token_masked": self._redact_push_token(device["push_token"]),
            "push_platform": device["push_platform"],
            "push_updated_at": device["push_updated_at"],
        }

    def list_devices(self):
        state = self._state()
        return [
            {
                "device_id": item.get("device_id", ""),
                "device_name": item.get("device_name", "Companion Device"),
                "paired_at": item.get("paired_at", ""),
                "last_seen_at": item.get("last_seen_at", ""),
                "revoked": bool(item.get("revoked")),
                "push_token_masked": self._redact_push_token(item.get("push_token", "")),
                "push_platform": item.get("push_platform", ""),
            }
            for item in state.get("devices", [])
        ]

    def revoke_device(self, target_device_id):
        state = self._state()
        device = next((item for item in state.get("devices", []) if item.get("device_id") == target_device_id), None)
        if not device:
            return None
        device["revoked"] = True
        device["access_token"] = ""
        self._save(state)
        return {
            "device_id": device.get("device_id", ""),
            "revoked": True,
        }

    def note_push_event(self, thread_id, message_id):
        state = self._state()
        state.setdefault("push_events", []).insert(
            0,
            {
                "thread_id": str(thread_id or ""),
                "message_id": str(message_id or ""),
                "timestamp": self._now_iso(),
            },
        )
        state["push_events"] = state["push_events"][:40]
        self._save(state)

    def latest_pairing_codes(self):
        now = self._now()
        state = self._state()
        return [
            {
                "code": item.get("code", ""),
                "label": item.get("label", ""),
                "created_at": item.get("created_at", ""),
                "expires_at_epoch": int(item.get("expires_at_epoch", 0)),
            }
            for item in state.get("pairing_codes", [])
            if int(item.get("expires_at_epoch", 0)) > now and not item.get("used")
        ]


class AppRegistry:
    def __init__(self, apps_dir, log=None):
        self.apps_dir = apps_dir
        self.log = log or (lambda *_: None)
        self._cache = {}

    def discover(self):
        apps = []
        if not os.path.isdir(self.apps_dir):
            return apps
        for name in sorted(os.listdir(self.apps_dir)):
            path = os.path.join(self.apps_dir, name, "main.py")
            if os.path.isfile(path):
                apps.append(name)
        return apps

    def load(self, app_id):
        if app_id in self._cache:
            return self._cache[app_id]
        path = os.path.join(self.apps_dir, app_id, "main.py")
        if not os.path.isfile(path):
            return None
        spec = importlib.util.spec_from_file_location(f"unlim8ted_app_{app_id}", path)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._cache[app_id] = module
        return module
