def get_manifest():
    return {
        "id": "messages",
        "title": "Messages",
        "capabilities": ["network", "notifications"],
        "routes": ["threads", "conversation"],
        "required_services": ["communications", "accounts"],
    }


def _state(context):
    return context["services"]["accounts"].store.read("messages_app", {"thread_id": "alex"})


def _save(context, value):
    context["services"]["accounts"].store.write("messages_app", value)


def get_app_payload(context):
    app_state = _state(context)
    threads = context["services"]["communications"].list_threads()
    selected = next((item for item in threads if item["id"] == app_state["thread_id"]), threads[0] if threads else None)
    return {
        "view": "structured",
        "title": "Messages",
        "sections": [
            {"type": "list", "title": "Threads", "items": [{"title": item["title"], "subtitle": item["messages"][-1]["body"] if item["messages"] else "", "action": "open_thread", "value": item["id"]} for item in threads]},
            {"type": "list", "title": selected["title"] if selected else "Conversation", "items": [{"title": msg["sender"], "subtitle": msg["body"]} for msg in (selected["messages"] if selected else [])[-12:] ]},
            {
                "type": "form",
                "title": "Reply",
                "action": "send_message",
                "fields": [
                    {"name": "body", "placeholder": "Message"},
                ],
                "submit_label": "Send",
            },
        ],
    }


def handle_action(context, action, payload):
    app_state = _state(context)
    if action == "open_thread":
        app_state["thread_id"] = str(payload.get("value", "")).strip() or app_state["thread_id"]
        _save(context, app_state)
    elif action == "send_message":
        body = str(payload.get("body", "")).strip()
        if body:
            context["services"]["communications"].send_message(app_state["thread_id"], context["owner"]["name"], body)
    return {"app": get_app_payload(context), "system": context["system"]}
