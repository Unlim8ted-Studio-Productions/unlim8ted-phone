def get_manifest():
    return {
        "id": "notes",
        "title": "Notes",
        "capabilities": [],
        "routes": ["list", "edit"],
        "required_services": [],
    }


def _state(context):
    return context["services"]["accounts"].store.read("notes", {"notes": []})


def _save(context, value):
    context["services"]["accounts"].store.write("notes", value)


def get_app_payload(context):
    notes = _state(context)["notes"]
    return {
        "view": "structured",
        "title": "Notes",
        "sections": [
            {
                "type": "form",
                "title": "New Note",
                "action": "create_note",
                "fields": [{"name": "title", "placeholder": "Title"}, {"name": "body", "placeholder": "Body"}],
                "submit_label": "Save",
            },
            {"type": "list", "title": "Notes", "items": [{"title": item["title"], "subtitle": item["body"]} for item in notes[:12]]},
        ],
    }


def handle_action(context, action, payload):
    if action == "create_note":
        state = _state(context)
        title = str(payload.get("title", "")).strip() or "Untitled"
        body = str(payload.get("body", "")).strip()
        if body:
            state["notes"].insert(0, {"id": f"note-{len(state['notes']) + 1}", "title": title, "body": body})
            _save(context, state)
    return {"app": get_app_payload(context), "system": context["system"]}
