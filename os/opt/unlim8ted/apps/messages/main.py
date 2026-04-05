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


def _thread_summary(context, thread):
    owner_name = context["owner"]["name"]
    messages = thread.get("messages", [])
    last_message = messages[-1] if messages else None
    return {
        "id": thread["id"],
        "title": thread["title"],
        "participants": list(thread.get("participants", [])),
        "unread": int(thread.get("unread", 0)),
        "last_message": {
            "id": last_message.get("id", "") if last_message else "",
            "sender": last_message.get("sender", "") if last_message else "",
            "body": last_message.get("body", "") if last_message else "",
            "timestamp": last_message.get("timestamp", "") if last_message else "",
            "status": last_message.get("status", "") if last_message else "",
            "direction": (
                "outbound"
                if last_message and last_message.get("sender") == owner_name
                else "inbound"
            ) if last_message else "",
        },
    }


def _sync_payload(context, selected_thread_id=None):
    app_state = _state(context)
    threads = context["services"]["communications"].list_threads()
    selected_id = selected_thread_id or app_state["thread_id"]
    selected = next((item for item in threads if item["id"] == selected_id), threads[0] if threads else None)
    return {
        "ok": True,
        "owner": context["owner"],
        "selected_thread_id": selected["id"] if selected else "",
        "threads": [_thread_summary(context, item) for item in threads],
        "conversation": {
            "id": selected["id"],
            "title": selected["title"],
            "messages": list(selected.get("messages", []))[-25:],
        } if selected else None,
        "timestamp": context["now"],
    }


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


def handle_http(context, request):
    method = request.get("method", "GET")
    subpath = request.get("subpath", "")
    payload = request.get("payload", {})

    if method == "GET" and subpath == "sync":
        return {"type": "json", "status": 200, "body": _sync_payload(context)}

    if method == "POST" and subpath == "sync":
        selected_thread_id = str(payload.get("thread_id", "")).strip() or None
        return {"type": "json", "status": 200, "body": _sync_payload(context, selected_thread_id)}

    return {
        "type": "json",
        "status": 404,
        "body": {
            "ok": False,
            "code": "route_not_found",
            "message": f"Unknown messages route: {subpath}",
        },
    }
