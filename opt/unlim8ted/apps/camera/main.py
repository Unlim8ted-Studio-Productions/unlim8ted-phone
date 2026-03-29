import os
import shutil
import threading
import time
from datetime import datetime


DEFAULT_CAMERA_STATE = {
    "available": False,
    "preview_active": False,
    "last_capture": "",
    "last_error": "",
}

_MANAGER = None


def _ensure_parent(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _camera_state(system_state):
    state = system_state.state.setdefault("camera", dict(DEFAULT_CAMERA_STATE))
    for key, value in DEFAULT_CAMERA_STATE.items():
        state.setdefault(key, value)
    return state


class CameraManager:
    def __init__(self, system_state, runner, captures_dir, preview_path, media_prefix):
        self.system_state = system_state
        self.runner = runner
        self.captures_dir = captures_dir
        self.preview_path = preview_path
        self.media_prefix = media_prefix
        self.lock = threading.Lock()
        self.preview_thread = None
        self.stop_event = threading.Event()
        _ensure_parent(os.path.join(self.captures_dir, ".keep"))

    def _camera_command(self):
        for candidate in ("libcamera-jpeg", "rpicam-jpeg"):
            path = shutil.which(candidate)
            if path:
                return path
        return None

    def _list_command(self):
        for candidate in ("libcamera-hello", "rpicam-hello"):
            path = shutil.which(candidate)
            if path:
                return path
        return None

    def refresh_availability(self):
        command = self._list_command()
        camera = _camera_state(self.system_state)
        if not command:
            camera["available"] = False
            camera["last_error"] = "libcamera tools not installed"
            return False

        ok, out, err = self.runner.run([command, "--list-cameras"], timeout=10)
        camera["available"] = ok and bool(out)
        if not camera["available"]:
            camera["last_error"] = err or out or "No camera detected"
        else:
            camera["last_error"] = ""
        return camera["available"]

    def _capture_file(self, path, width, height, immediate=True):
        command = self._camera_command()
        if not command:
            return False, "libcamera capture command not found"

        args = [command, "-n", "--width", str(width), "--height", str(height)]
        if immediate:
            args.append("--immediate")
        else:
            args.extend(["-t", "1200"])
        args.extend(["-o", path])
        ok, _, err = self.runner.run(args, timeout=20)
        return ok, err or ""

    def _preview_loop(self):
        while not self.stop_event.is_set():
            with self.lock:
                active = _camera_state(self.system_state)["preview_active"]
            if not active:
                break

            ok, err = self._capture_file(self.preview_path, 864, 486, immediate=True)
            if not ok:
                with self.lock:
                    camera = _camera_state(self.system_state)
                    camera["last_error"] = err or "Preview capture failed"
                    camera["preview_active"] = False
                    self.system_state.save()
                break

            time.sleep(1.1)

    def start_preview(self):
        with self.lock:
            available = self.refresh_availability()
            camera = _camera_state(self.system_state)
            if not available:
                camera["preview_active"] = False
                self.system_state.save()
                return dict(camera)

            camera["preview_active"] = True
            camera["last_error"] = ""
            self.system_state.save()

            if self.preview_thread and self.preview_thread.is_alive():
                return dict(camera)

            self.stop_event.clear()
            self.preview_thread = threading.Thread(target=self._preview_loop, daemon=True)
            self.preview_thread.start()
            return dict(camera)

    def stop_preview(self):
        with self.lock:
            camera = _camera_state(self.system_state)
            camera["preview_active"] = False
            self.system_state.save()
            self.stop_event.set()

    def capture_photo(self):
        with self.lock:
            available = self.refresh_availability()
            if not available:
                self.system_state.save()
                return None

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"capture-{timestamp}.jpg"
        path = os.path.join(self.captures_dir, filename)
        _ensure_parent(path)
        ok, err = self._capture_file(path, 1456, 1088, immediate=False)

        with self.lock:
            camera = _camera_state(self.system_state)
            if not ok:
                camera["last_error"] = err or "Capture failed"
                self.system_state.save()
                return None

            camera["last_capture"] = filename
            camera["last_error"] = ""
            self.system_state.save()
            return filename

    def camera_state(self):
        with self.lock:
            state = dict(_camera_state(self.system_state))
        state["last_capture_url"] = f"{self.media_prefix}{state['last_capture']}" if state.get("last_capture") else ""
        return state

    def preview_response(self):
        if os.path.exists(self.preview_path):
            with open(self.preview_path, "rb") as handle:
                return "image/jpeg", handle.read()

        camera = self.camera_state()
        message = camera.get("last_error") or "Camera preview not available"
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 864 486'>"
            "<defs><linearGradient id='g' x1='0' x2='1'><stop stop-color='#141824'/>"
            "<stop offset='1' stop-color='#05070b'/></linearGradient></defs>"
            "<rect width='100%' height='100%' fill='url(#g)'/>"
            "<circle cx='432' cy='208' r='70' fill='none' stroke='#cdd8ff' stroke-width='10' opacity='0.85'/>"
            "<path d='M332 162h74l18-28h80l18 28h74v164H332z' fill='none' stroke='#cdd8ff' stroke-width='10' opacity='0.55'/>"
            f"<text x='432' y='356' fill='#eef3ff' font-size='26' text-anchor='middle'>{message}</text>"
            "</svg>"
        )
        return "image/svg+xml", svg.encode("utf-8")


def _manager(context):
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = CameraManager(
            context["services"]["system_state"],
            context["services"]["runner"],
            context["paths"]["captures_dir"],
            context["paths"]["preview_path"],
            context["paths"]["media_prefix"],
        )
    return _MANAGER


def get_manifest():
    return {
        "id": "camera",
        "title": "Camera",
        "capabilities": ["camera", "files"],
        "routes": ["capture", "frame", "start", "stop"],
        "required_services": ["runner", "system_state", "media"],
    }


def get_app_payload(context):
    manager = _manager(context)
    manager.refresh_availability()
    return {
        "view": "camera",
        "title": "Camera",
        "camera": manager.camera_state(),
        "sections": [],
    }


def handle_action(context, action, payload):
    return {"app": get_app_payload(context), "system": context["services"]["system"].get_state()}


def handle_http(context, request):
    manager = _manager(context)
    method = request["method"]
    subpath = request["subpath"]

    if method == "GET" and subpath == "frame":
        content_type, body = manager.preview_response()
        return {"type": "raw", "status": 200, "content_type": content_type, "body": body}

    if method == "POST" and subpath == "start":
        camera = manager.start_preview()
        return {"type": "json", "status": 200, "body": {"ok": True, "camera": camera, "system": context["services"]["system"].get_state()}}

    if method == "POST" and subpath == "stop":
        manager.stop_preview()
        return {"type": "json", "status": 200, "body": {"ok": True, "camera": manager.camera_state(), "system": context["services"]["system"].get_state()}}

    if method == "POST" and subpath == "capture":
        filename = manager.capture_photo()
        return {
            "type": "json",
            "status": 200,
            "body": {
                "ok": bool(filename),
                "code": "" if filename else "capture_failed",
                "camera": manager.camera_state(),
                "photo_url": f"{context['paths']['media_prefix']}{filename}" if filename else "",
                "system": context["services"]["system"].get_state(),
            },
        }

    return {"type": "json", "status": 404, "body": {"ok": False, "code": "route_not_found"}}


def handle_system_event(context, event, payload):
    if event == "sleep":
        _manager(context).stop_preview()
