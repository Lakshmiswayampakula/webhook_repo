from flask import Blueprint, jsonify
from app.extensions import mongo

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Try to ping MongoDB
        mongo.db.command('ping')
        return jsonify({
            "status": "healthy",
            "mongodb": "connected"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "mongodb": "disconnected",
            "error": str(e)
        }), 503

@api.route('/events', methods=['GET'])
def get_events():
    """Get all webhook events from MongoDB. Always returns 200 with an array."""
    try:
        events = list(mongo.db.events.find().sort('timestamp', -1))
    except Exception:
        # Return 200 with empty array so dashboard shows "No events" instead of error
        return jsonify([]), 200

    formatted = []
    for e in events:
        author = e.get("author") or "Unknown"
        action = e.get("action") or ""
        from_branch = e.get("from_branch") or ""
        to_branch = e.get("to_branch") or ""
        timestamp = e.get("timestamp") or ""
        request_id = e.get("request_id") or ""

        if action == "PUSH":
            message = f'{author} pushed to {to_branch} on {timestamp}'
        elif action == "PULL_REQUEST":
            message = f'{author} submitted a pull request from {from_branch} to {to_branch} on {timestamp}'
        elif action == "MERGE":
            message = f'{author} merged branch {from_branch} to {to_branch} on {timestamp}'
        else:
            message = f'{author} performed {action or "action"} on {timestamp}'

        formatted.append({
            "message": message,
            "timestamp": timestamp,
            "action": action,
            "author": author,
            "request_id": request_id,
            "from_branch": from_branch,
            "to_branch": to_branch,
        })

    return jsonify(formatted)
