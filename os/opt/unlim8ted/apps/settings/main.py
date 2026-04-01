def get_manifest():
    return {
        "id": "settings",
        "title": "Settings",
        "capabilities": ["account_access", "notifications"],
        "routes": ["system"],
        "required_services": ["accounts", "notifications", "system"],
    }


def _settings_payload(context):
    system = context["system"]
    owner = context["owner"]["name"]
    brightness = int(system["brightness"] * 100)
    idle_timeout = int(system["idle_timeout_sec"])
    toggles = [
        {
            "id": key,
            "label": key.replace("_", " ").title(),
            "enabled": bool(value),
        }
        for key, value in system["toggles"].items()
    ]
    badges = [
        {"id": key, "count": int(value)}
        for key, value in sorted(system.get("badges", {}).items())
        if int(value) > 0
    ]
    return {
        "view": "template",
        "title": "Settings",
        "owner": owner,
        "settings": {
            "brightness": brightness,
            "idle_timeout_sec": idle_timeout,
            "sleeping": bool(system.get("sleeping")),
            "toggles": toggles,
            "badges": badges,
            "device": [
                {"label": "Owner", "value": owner},
                {"label": "Brightness", "value": f"{brightness}%"},
                {"label": "Idle Timeout", "value": f"{idle_timeout}s"},
                {
                    "label": "State",
                    "value": "Sleeping" if system.get("sleeping") else "Awake",
                },
            ],
        },
    }


def get_app_payload(context):
    return _settings_payload(context)


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
