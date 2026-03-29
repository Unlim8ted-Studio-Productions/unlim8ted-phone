def get_manifest():
    return {
        "id": "phone",
        "title": "Phone",
        "capabilities": ["network", "audio"],
        "routes": ["dialer", "recents", "contacts"],
        "required_services": ["communications", "contacts"],
    }


def get_app_payload(context):
    contacts = context["services"]["contacts"].list()
    favorites = context["services"]["contacts"].favorites()
    recents = context["services"]["communications"].list_calls()
    return {
        "view": "structured",
        "title": "Phone",
        "sections": [
            {
                "type": "chips",
                "title": "Favorites",
                "items": [{"label": item["name"], "action": "place_call", "value": item["name"]} for item in favorites],
            },
            {
                "type": "form",
                "title": "Dial",
                "action": "place_call",
                "fields": [{"name": "value", "placeholder": "Contact or number"}],
                "submit_label": "Call",
            },
            {
                "type": "list",
                "title": "Recents",
                "items": [{"title": call["target"], "subtitle": call["timestamp"]} for call in recents[:12]],
            },
            {
                "type": "list",
                "title": "Contacts",
                "items": [{"title": item["name"], "subtitle": item["phone"], "action": "place_call", "value": item["name"]} for item in contacts],
            },
        ],
    }


def handle_action(context, action, payload):
    if action == "place_call":
        target = str(payload.get("value", "")).strip()
        if target:
            context["services"]["communications"].add_call(target)
    return {"app": get_app_payload(context), "system": context["system"]}
