def get_manifest():
    return {
        "id": "mail",
        "title": "Mail",
        "capabilities": ["network", "account_access", "notifications"],
        "routes": ["mailboxes", "message", "compose"],
        "required_services": ["accounts"],
    }


def _mail_state(context):
    return context["services"]["accounts"].store.read("mail", {"mailboxes": {"inbox": [], "drafts": [], "sent": [], "archive": []}})


def _save_mail_state(context, value):
    context["services"]["accounts"].store.write("mail", value)


def get_app_payload(context):
    mail = _mail_state(context)
    inbox = mail["mailboxes"]["inbox"]
    accounts = context["services"]["accounts"].state()["mail_accounts"]
    return {
        "view": "structured",
        "title": "Mail",
        "sections": [
            {"type": "list", "title": "Accounts", "items": [{"title": item["label"], "subtitle": item["address"]} for item in accounts]},
            {
                "type": "form",
                "title": "Compose",
                "action": "compose_mail",
                "fields": [
                    {"name": "subject", "placeholder": "Subject"},
                    {"name": "body", "placeholder": "Message body"},
                ],
                "submit_label": "Queue",
            },
            {
                "type": "list",
                "title": "Inbox",
                "items": [{"title": item["subject"], "subtitle": item["from"]} for item in inbox[:12]],
            },
        ],
    }


def handle_action(context, action, payload):
    mail = _mail_state(context)
    if action == "compose_mail":
        subject = str(payload.get("subject", "")).strip() or "Untitled draft"
        body = str(payload.get("body", "")).strip()
        if body:
            mail["mailboxes"]["drafts"].insert(0, {"id": f"draft-{len(mail['mailboxes']['drafts']) + 1}", "from": context["services"]["accounts"].state()["mail_accounts"][0]["address"], "subject": subject, "body": body, "unread": False, "starred": False})
            _save_mail_state(context, mail)
    return {"app": get_app_payload(context), "system": context["system"]}
