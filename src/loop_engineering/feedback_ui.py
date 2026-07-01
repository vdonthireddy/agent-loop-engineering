"""Lightweight Flask web UI for collecting external user feedback.

Runs on a separate port (default 5001) so it doesn't conflict with the
generated to-do app (port 5000).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template_string, request, redirect, url_for, flash

# ── HTML Template ───────────────────────────────────────────────

FEEDBACK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Loop Engineering — Feedback Portal</title>
    <style>
        :root {
            --bg-primary: #0f172a;
            --bg-card: #1e293b;
            --bg-input: #334155;
            --border: #475569;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #22c55e;
            --accent-orange: #f97316;
            --accent-red: #ef4444;
            --radius: 12px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.6;
        }

        .container {
            max-width: 720px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }

        /* ── Header ──────────────────────────── */
        header {
            text-align: center;
            margin-bottom: 2.5rem;
        }

        header h1 {
            font-size: 1.75rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-orange));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
        }

        header p {
            color: var(--text-secondary);
            font-size: 0.95rem;
        }

        .loop-badges {
            display: flex;
            justify-content: center;
            gap: 0.75rem;
            margin-top: 1rem;
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.3rem 0.75rem;
            border-radius: 999px;
            font-size: 0.8rem;
            font-weight: 500;
            border: 1px solid;
        }

        .badge--blue   { color: var(--accent-blue);   border-color: rgba(59,130,246,0.3);  background: rgba(59,130,246,0.1);  }
        .badge--green  { color: var(--accent-green);  border-color: rgba(34,197,94,0.3);   background: rgba(34,197,94,0.1);   }
        .badge--orange { color: var(--accent-orange); border-color: rgba(249,115,22,0.3);  background: rgba(249,115,22,0.1);  }

        /* ── Flash messages ──────────────────── */
        .flash {
            padding: 0.75rem 1rem;
            border-radius: var(--radius);
            margin-bottom: 1.5rem;
            font-size: 0.9rem;
            border: 1px solid rgba(34,197,94,0.3);
            background: rgba(34,197,94,0.1);
            color: var(--accent-green);
        }

        /* ── Form card ───────────────────────── */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1.5rem;
            margin-bottom: 2rem;
        }

        .card h2 {
            font-size: 1.15rem;
            font-weight: 600;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        label {
            display: block;
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 0.4rem;
            font-weight: 500;
        }

        select, input[type="text"], textarea {
            width: 100%;
            padding: 0.65rem 0.85rem;
            background: var(--bg-input);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 0.9rem;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s;
            margin-bottom: 1rem;
        }

        select:focus, input[type="text"]:focus, textarea:focus {
            border-color: var(--accent-blue);
        }

        textarea { resize: vertical; min-height: 100px; }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        button[type="submit"] {
            width: 100%;
            padding: 0.75rem;
            background: linear-gradient(135deg, var(--accent-blue), #6366f1);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s, transform 0.1s;
        }

        button[type="submit"]:hover { opacity: 0.9; }
        button[type="submit"]:active { transform: scale(0.98); }

        /* ── Feedback list ────────────────────── */
        .feedback-item {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1rem 1.25rem;
            margin-bottom: 0.75rem;
            transition: border-color 0.2s;
        }

        .feedback-item:hover {
            border-color: var(--accent-blue);
        }

        .feedback-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }

        .feedback-category {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }

        .cat-ux       { background: rgba(59,130,246,0.15);  color: var(--accent-blue);   }
        .cat-feature   { background: rgba(34,197,94,0.15);   color: var(--accent-green);  }
        .cat-bug       { background: rgba(239,68,68,0.15);   color: var(--accent-red);    }
        .cat-other     { background: rgba(148,163,184,0.15); color: var(--text-secondary);}

        .feedback-time {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .feedback-text {
            font-size: 0.9rem;
            color: var(--text-primary);
            line-height: 1.5;
        }

        .feedback-user {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 0.4rem;
            font-style: italic;
        }

        .empty-state {
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.95rem;
        }

        .empty-state span {
            font-size: 2rem;
            display: block;
            margin-bottom: 0.5rem;
        }

        /* ── Footer ──────────────────────────── */
        footer {
            text-align: center;
            padding: 2rem 0;
            color: var(--text-secondary);
            font-size: 0.8rem;
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }

        footer a {
            color: var(--accent-blue);
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔄 Loop Engineering — Feedback Portal</h1>
            <p>Submit feedback to drive the next product iteration</p>
            <div class="loop-badges">
                <span class="badge badge--blue">🔵 Agentic Loop</span>
                <span class="badge badge--green">🟢 Developer Loop</span>
                <span class="badge badge--orange">🟠 External Loop ← you are here</span>
            </div>
        </header>

        {% with messages = get_flashed_messages() %}
        {% if messages %}
        {% for msg in messages %}
        <div class="flash">✅ {{ msg }}</div>
        {% endfor %}
        {% endif %}
        {% endwith %}

        <!-- Submit Feedback Form -->
        <div class="card">
            <h2>💬 Submit Feedback</h2>
            <form method="POST" action="/submit">
                <div class="form-row">
                    <div>
                        <label for="user_name">Your Name</label>
                        <input type="text" id="user_name" name="user_name"
                               placeholder="e.g. Tester Alice" required>
                    </div>
                    <div>
                        <label for="category">Category</label>
                        <select id="category" name="category">
                            <option value="ux">UX / Design</option>
                            <option value="feature">Feature Request</option>
                            <option value="bug">Bug Report</option>
                            <option value="other">Other</option>
                        </select>
                    </div>
                </div>
                <label for="feedback">Feedback</label>
                <textarea id="feedback" name="feedback"
                          placeholder="Describe your experience, suggestion, or bug..." required></textarea>
                <button type="submit">Submit Feedback</button>
            </form>
        </div>

        <!-- Existing Feedback -->
        <div class="card">
            <h2>📋 Submitted Feedback ({{ feedback_items | length }})</h2>
            {% if feedback_items %}
                {% for item in feedback_items | reverse %}
                <div class="feedback-item">
                    <div class="feedback-meta">
                        <span class="feedback-category cat-{{ item.category }}">
                            {{ item.category | upper }}
                        </span>
                        <span class="feedback-time">{{ item.timestamp }}</span>
                    </div>
                    <div class="feedback-text">{{ item.feedback }}</div>
                    <div class="feedback-user">— {{ item.user_name }}</div>
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <span>📭</span>
                    No feedback submitted yet. Be the first!
                </div>
            {% endif %}
        </div>

        <footer>
            Concept from <a href="https://www.deeplearning.ai/the-batch/issue-359" target="_blank">The Batch Issue 359</a>
            &nbsp;·&nbsp; Loop Engineering Demo
        </footer>
    </div>
</body>
</html>
"""

# ── Flask App ───────────────────────────────────────────────────


def create_feedback_app(feedback_path: Path) -> Flask:
    """Create a Flask app that serves the feedback collection UI.

    Parameters
    ----------
    feedback_path : Path
        JSON file where feedback items are stored (created if missing).
    """
    app = Flask(__name__)
    app.secret_key = "loop-engineering-feedback-secret"

    def _load_feedback() -> list[dict]:
        if feedback_path.exists():
            try:
                data = json.loads(feedback_path.read_text())
                if isinstance(data, list):
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    def _save_feedback(items: list[dict]) -> None:
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        feedback_path.write_text(json.dumps(items, indent=2) + "\n")

    @app.route("/")
    def index():
        items = _load_feedback()
        return render_template_string(FEEDBACK_HTML, feedback_items=items)

    @app.route("/submit", methods=["POST"])
    def submit():
        user_name = request.form.get("user_name", "Anonymous").strip()
        category = request.form.get("category", "other").strip()
        feedback = request.form.get("feedback", "").strip()

        if not feedback:
            flash("Feedback cannot be empty.")
            return redirect(url_for("index"))

        items = _load_feedback()
        items.append({
            "user_name": user_name,
            "category": category,
            "feedback": feedback,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        })
        _save_feedback(items)

        flash(f"Thanks {user_name}! Your feedback has been recorded.")
        return redirect(url_for("index"))

    @app.route("/api/feedback")
    def api_feedback():
        """JSON endpoint for the external loop to consume."""
        items = _load_feedback()
        return {"feedback": items, "count": len(items)}

    @app.route("/api/clear", methods=["POST"])
    def api_clear():
        """Clear all feedback (called after external loop consumes it)."""
        _save_feedback([])
        return {"status": "cleared"}

    return app


def run_feedback_server(feedback_path: Path, port: int = 5001) -> None:
    """Start the feedback web UI."""
    app = create_feedback_app(feedback_path)
    app.run(host="0.0.0.0", port=port, debug=False)
