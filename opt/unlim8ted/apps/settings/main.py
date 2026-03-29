def get_manifest():
    return {
        "id": "settings",
        "title": "Settings",
        "capabilities": ["account_access", "notifications"],
        "routes": ["system"],
        "required_services": ["accounts", "notifications", "system"],
    }


def get_app_payload(context):
    system = context["system"]
    return {
        "view": "structured",
        "title": "Settings",
        "sections": [
            {"type": "kv", "title": "Device", "rows": [{"label": "Owner", "value": context['owner']['name']}, {"label": "Brightness", "value": f"{int(system['brightness'] * 100)}%"}, {"label": "Idle Timeout", "value": f"{system['idle_timeout_sec']}s"}]},
            {"type": "chips", "title": "Connectivity", "items": [{"label": f"{key}: {'On' if value else 'Off'}", "action": "toggle_connectivity", "value": key} for key, value in system['toggles'].items()]},
            {"type": "form", "title": "Display", "action": "set_brightness", "fields": [{"name": "value", "placeholder": "Brightness percent 5-100"}], "submit_label": "Apply"},
            {"type": "form", "title": "Idle Timeout", "action": "set_idle_timeout", "fields": [{"name": "value", "placeholder": "Seconds"}], "submit_label": "Apply"},
            {"type": "kv", "title": "Badges", "rows": [{"label": key, "value": str(value)} for key, value in system.get('badges', {}).items()]},
        ],
    }


def handle_action(context, action, payload):
    system = context["services"]["system"]
    if action == "toggle_connectivity":
        key = str(payload.get("value", "")).strip()
        if key:
            system.set_toggle(key)
    elif action == "set_brightness":
        value = str(payload.get("value", "")).strip()
        if value.isdigit():
            system.set_brightness(int(value) / 100)
    elif action == "set_idle_timeout":
        value = str(payload.get("value", "")).strip()
        if value.isdigit():
            system.system_state.state["idle_timeout_sec"] = max(10, min(600, int(value)))
            system.system_state.save()
    return {"app": get_app_payload(context), "system": system.get_state()}
