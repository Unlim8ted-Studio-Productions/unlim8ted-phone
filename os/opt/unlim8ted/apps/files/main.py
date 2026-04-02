import os


def get_manifest():
    return {
        "id": "files",
        "title": "Files",
        "capabilities": ["files"],
        "routes": ["browser", "preview"],
        "required_services": ["files", "accounts"],
    }


def _state(context):
    return context["services"]["accounts"].store.read("files_app", {"path": context["paths"]["user_files_dir"], "preview": ""})


def _save(context, value):
    context["services"]["accounts"].store.write("files_app", value)


def get_app_payload(context):
    state = _state(context)
    listing = context["services"]["files"].list_dir(state["path"])
    preview = context["services"]["files"].read_text(state["preview"]) if state.get("preview") else ""
    items = []
    root_path = os.path.abspath(context["paths"]["user_files_dir"])
    current_path = os.path.abspath(listing["path"]) if listing["path"] else root_path
    if current_path != root_path:
        items.append({"title": "..", "subtitle": "Parent", "action": "open_path", "value": os.path.dirname(current_path) or root_path})
    items.extend({"title": item["name"], "subtitle": item["kind"], "action": "open_path" if item["kind"] == "dir" else "preview_file", "value": item["path"]} for item in listing["items"][:24])
    return {
        "view": "structured",
        "title": "Files",
        "sections": [
            {"type": "hero", "title": listing["path"], "body": "Personal storage only"},
            {"type": "form", "title": "Create Text File", "action": "create_file", "fields": [{"name": "name", "placeholder": "filename.txt"}, {"name": "body", "placeholder": "File contents"}], "submit_label": "Create"},
            {"type": "form", "title": "Create Folder", "action": "create_folder", "fields": [{"name": "name", "placeholder": "Folder name"}], "submit_label": "Create"},
            {"type": "list", "title": "Entries", "items": items},
            {"type": "text", "title": "Preview", "body": preview or "Select a text file to preview."},
            {"type": "form", "title": "Delete Path", "action": "delete_file", "fields": [{"name": "value", "placeholder": "Full path to delete"}], "submit_label": "Delete"},
        ],
    }


def handle_action(context, action, payload):
    state = _state(context)
    files = context["services"]["files"]
    if action == "create_file":
        name = str(payload.get("name", "")).strip()
        body = str(payload.get("body", ""))
        if name:
            files.create_text(state["path"], name, body)
    elif action == "create_folder":
        name = str(payload.get("name", "")).strip()
        if name:
            files.create_dir(state["path"], name)
    elif action == "open_path":
        target = str(payload.get("value", "")).strip()
        if target:
            state["path"] = target
            _save(context, state)
    elif action == "preview_file":
        target = str(payload.get("value", "")).strip()
        if target:
            state["preview"] = target
            _save(context, state)
    elif action == "delete_file":
        target = str(payload.get("value", "")).strip()
        if target:
            files.delete(target)
            if state.get("preview") == target:
                state["preview"] = ""
            _save(context, state)
    return {"app": get_app_payload(context), "system": context["system"]}

