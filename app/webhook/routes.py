import json
from flask import Blueprint, request, jsonify
from datetime import datetime
from ..extensions import mongo

webhook = Blueprint('Webhook', __name__, url_prefix='/webhook')


def _safe_json():
    """Parse request body as JSON; never raise. Returns dict."""
    try:
        raw = request.get_data(as_text=True) or "{}"
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def format_timestamp(dt):
    """Format datetime to '1st April 2021 - 9:30 PM UTC' format"""
    day = dt.day
    # Handle special cases: 11th, 12th, 13th
    if 11 <= day <= 13:
        suffix = "th"
    elif day % 10 == 1:
        suffix = "st"
    elif day % 10 == 2:
        suffix = "nd"
    elif day % 10 == 3:
        suffix = "rd"
    else:
        suffix = "th"
    
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    
    hour = dt.hour
    minute = dt.minute
    
    # Convert to 12-hour format
    if hour == 0:
        hour_12 = 12
        am_pm = "AM"
    elif hour < 12:
        hour_12 = hour
        am_pm = "AM"
    elif hour == 12:
        hour_12 = 12
        am_pm = "PM"
    else:
        hour_12 = hour - 12
        am_pm = "PM"
    
    return f"{day}{suffix} {month_names[dt.month - 1]} {dt.year} - {hour_12}:{minute:02d} {am_pm} UTC"

@webhook.route('/receiver', methods=["POST", "GET"])
def receiver():
    """
    GitHub webhook receiver. NEVER returns 4xx/5xx so GitHub delivery always succeeds.
    """
    try:
        if request.method == "GET":
            return jsonify({"message": "Webhook OK", "status": "active"}), 200

        data = _safe_json()
        event_type = (request.headers.get("X-GitHub-Event") or "").strip()

        if event_type.lower() == "ping":
            return jsonify({"message": "pong", "zen": data.get("zen", "")}), 200

        if not event_type:
            return jsonify({"message": "ok"}), 200

        github_event = event_type.lower()
        ts = format_timestamp(datetime.utcnow())
        event = {
            "request_id": "",
            "author": "Unknown",
            "action": "",
            "from_branch": "",
            "to_branch": "",
            "timestamp": ts,
        }
        action = None

        if github_event == "push":
            action = "PUSH"
            event["action"] = "PUSH"
            event["request_id"] = (
                data.get("after")
                or (data.get("head_commit") or {}).get("id")
                or ("push-%s" % ts.replace(" ", "-").replace(":", "-")[:50])
            )
            commits = data.get("commits") or []
            if commits:
                author = (commits[0] or {}).get("author") or {}
                event["author"] = (
                    author.get("name")
                    or author.get("username")
                    or ((author.get("email") or "").split("@")[0])
                    or "Unknown"
                )
            if event["author"] == "Unknown":
                pusher = data.get("pusher") or {}
                event["author"] = pusher.get("name") or pusher.get("login") or "Unknown"
            ref = (data.get("ref") or "").strip()
            event["to_branch"] = ref.split("/")[-1] if ref else "main"

        elif github_event == "pull_request":
            pr = data.get("pull_request") or {}
            pr_action = (data.get("action") or "").lower()
            is_merged = pr.get("merged", False)
            if pr_action == "closed" and is_merged:
                action = "MERGE"
            elif pr_action in ("opened", "synchronize", "reopened"):
                action = "PULL_REQUEST"
            else:
                return jsonify({"message": "ok", "action": pr_action}), 200

            event["action"] = action
            event["request_id"] = str(data.get("number") or "")
            sender = data.get("sender") or {}
            pr_user = pr.get("user") or {}
            event["author"] = sender.get("login") or pr_user.get("login") or "Unknown"
            event["from_branch"] = (pr.get("head") or {}).get("ref") or ""
            event["to_branch"] = (pr.get("base") or {}).get("ref") or ""

        else:
            return jsonify({"message": "ok", "event": github_event}), 200

        if action:
            event["request_id"] = event["request_id"] or ("%s-%s" % (action.lower(), ts.replace(" ", "-").replace(":", "-")[:30]))
            try:
                mongo.db.events.insert_one(event)
            except Exception:
                pass
        return jsonify({"message": "Event stored", "event": event}), 200

    except Exception:
        # Catch-all: never send 400/500 back to GitHub
        return jsonify({"message": "ok"}), 200
