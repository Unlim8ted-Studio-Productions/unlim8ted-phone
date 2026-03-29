def get_manifest():
    return {
        "id": "music",
        "title": "Music",
        "capabilities": ["audio"],
        "routes": ["player", "library"],
        "required_services": ["media"],
    }


def get_app_payload(context):
    music = context["services"]["media"].music_state()
    current = music["queue"][music["index"]] if music["queue"] else "Nothing queued"
    return {
        "view": "structured",
        "title": "Music",
        "sections": [
            {"type": "hero", "title": current, "body": "Playing" if music["playing"] else "Paused", "actions": [{"label": "Play/Pause", "action": "toggle_playback"}, {"label": "Next", "action": "next_track"}]},
            {"type": "list", "title": "Queue", "items": [{"title": track, "subtitle": "Active" if idx == music["index"] else "Queued"} for idx, track in enumerate(music["queue"])]},
            {"type": "list", "title": "Playlists", "items": [{"title": item["name"], "subtitle": ", ".join(item["tracks"])} for item in music.get("playlists", [])]},
        ],
    }


def handle_action(context, action, payload):
    music = context["services"]["media"].music_state()
    if action == "toggle_playback":
        music["playing"] = not music["playing"]
    elif action == "next_track" and music["queue"]:
        music["index"] = (music["index"] + 1) % len(music["queue"])
        music["playing"] = True
    context["services"]["media"].save_music_state(music)
    return {"app": get_app_payload(context), "system": context["system"]}
