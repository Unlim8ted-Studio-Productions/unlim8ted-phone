def get_manifest():
    return {
        "id": "gallery",
        "title": "Gallery",
        "capabilities": ["files"],
        "routes": ["grid", "detail"],
        "required_services": ["media", "accounts"],
    }


def _state(context):
    return context["services"]["accounts"].store.read("gallery", {"selected": ""})


def _save(context, value):
    context["services"]["accounts"].store.write("gallery", value)


def get_app_payload(context):
    state = _state(context)
    captures = context["services"]["media"].captures(context["media_prefix"], limit=24)
    selected = next((item for item in captures if item["name"] == state["selected"]), None)
    return {
        "view": "structured",
        "title": "Gallery",
        "sections": [
            {"type": "grid", "title": "Captures", "items": [{"title": item["name"], "subtitle": item["url"], "image_url": item["url"]} for item in captures] or [{"title": "No photos yet", "subtitle": "Open Camera and capture an image."}]},
            {"type": "list", "title": "Select Capture", "items": [{"title": item["name"], "subtitle": item["url"], "action": "select_capture", "value": item["name"]} for item in captures]},
            {"type": "hero", "title": selected["name"] if selected else "No capture selected", "body": selected["url"] if selected else "Select an image to inspect or delete."},
            {"type": "chips", "title": "Actions", "items": ([{"label": "Delete Selected", "action": "delete_capture", "value": selected["name"]}] if selected else [])},
        ],
    }


def handle_action(context, action, payload):
    state = _state(context)
    if action == "select_capture":
        state["selected"] = str(payload.get("value", "")).strip()
        _save(context, state)
    elif action == "delete_capture":
        name = str(payload.get("value", "")).strip()
        if name and context["services"]["media"].delete_capture(name):
            if state["selected"] == name:
                state["selected"] = ""
            _save(context, state)
    return {"app": get_app_payload(context), "system": context["system"]}
