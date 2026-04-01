def get_manifest():
    return {
        "id": "store",
        "title": "Store",
        "capabilities": ["network"],
        "routes": ["catalog"],
        "required_services": [],
    }


def get_app_payload(context):
    registry = context.get("registry", {})
    commands = registry.get("commands", {})
    return {
        "view": "structured",
        "title": "Store",
        "sections": [
            {"type": "list", "title": "Installed Apps", "items": [{"title": item, "subtitle": "Installed"} for item in context.get("installed_apps", [])]},
            {"type": "list", "title": "Command Surface", "items": [{"title": key, "subtitle": value.get("description", "")} for key, value in commands.items()]},
        ],
    }


def handle_action(context, action, payload):
    return {"app": get_app_payload(context), "system": context["system"]}
