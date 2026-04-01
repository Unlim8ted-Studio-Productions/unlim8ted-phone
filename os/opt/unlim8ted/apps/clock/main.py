def get_manifest():
    return {
        "id": "clock",
        "title": "Clock",
        "capabilities": [],
        "routes": ["world", "alarms", "timers"],
        "required_services": [],
    }


def _state(context):
    return context["services"]["accounts"].store.read("clock", {"alarms": [{"id": "a1", "label": "Wake", "time": "07:00", "enabled": True}], "timers": [{"id": "t1", "label": "Dev Sync", "minutes": 10}], "world": [{"city": "UTC", "offset": "+00:00"}, {"city": "New York", "offset": "-04:00"}]})


def _save(context, value):
    context["services"]["accounts"].store.write("clock", value)


def get_app_payload(context):
    state = _state(context)
    return {"view": "structured", "title": "Clock", "sections": [
        {"type": "list", "title": "World Clock", "items": [{"title": item["city"], "subtitle": item["offset"]} for item in state["world"]]},
        {"type": "list", "title": "Alarms", "items": [{"title": item["label"], "subtitle": item["time"]} for item in state["alarms"]]},
        {"type": "form", "title": "Add Alarm", "action": "add_alarm", "fields": [{"name": "label", "placeholder": "Label"}, {"name": "time", "placeholder": "07:30"}], "submit_label": "Add"},
        {"type": "list", "title": "Timers", "items": [{"title": item["label"], "subtitle": f"{item['minutes']} min"} for item in state["timers"]]},
    ]}


def handle_action(context, action, payload):
    if action == "add_alarm":
        state = _state(context)
        label = str(payload.get("label", "")).strip() or "Alarm"
        alarm_time = str(payload.get("time", "")).strip() or "07:00"
        state["alarms"].append({"id": f"a{len(state['alarms']) + 1}", "label": label, "time": alarm_time, "enabled": True})
        _save(context, state)
    return {"app": get_app_payload(context), "system": context["system"]}
