def get_manifest():
    return {
        "id": "maps",
        "title": "Maps",
        "capabilities": ["network"],
        "routes": ["search", "route"],
        "required_services": [],
    }


def _state(context):
    return context["services"]["accounts"].store.read("maps", {"destination": "Lab Entrance", "saved_places": ["Lab Entrance", "Printer Room", "Camera Bench", "Roof Antenna Deck"], "recent_searches": []})


def _save(context, value):
    context["services"]["accounts"].store.write("maps", value)


def get_app_payload(context):
    state = _state(context)
    return {
        "view": "structured",
        "title": "Maps",
        "sections": [
            {"type": "hero", "title": state["destination"], "body": "Route provider not configured. Showing local destination state only."},
            {
                "type": "form",
                "title": "Search Destination",
                "action": "set_destination",
                "fields": [{"name": "value", "placeholder": "Destination"}],
                "submit_label": "Set",
            },
            {"type": "chips", "title": "Saved Places", "items": [{"label": item, "action": "set_destination", "value": item} for item in state["saved_places"]]},
            {"type": "list", "title": "Recent Searches", "items": [{"title": item, "subtitle": "Recent"} for item in state["recent_searches"][:8]]},
        ],
    }


def handle_action(context, action, payload):
    if action == "set_destination":
        state = _state(context)
        value = str(payload.get("value", "")).strip()
        if value:
            state["destination"] = value
            state["recent_searches"].insert(0, value)
            state["recent_searches"] = state["recent_searches"][:12]
            _save(context, state)
    return {"app": get_app_payload(context), "system": context["system"]}
