from flask import Flask, request, jsonify, redirect, session, render_template, send_from_directory, Response
import requests
import time
import datetime
import json
import os

app = Flask(__name__, template_folder="templates")
app.secret_key = "secret123"

# Browser headers (still used for the new API)
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://ffemote.com",          # may not be needed, but kept
    "Referer": "https://ffemote.com/"
}

# ---------- BLOCKED UID ----------
blocked_uids = set()

# ---------- LOG STORAGE ----------
logs = []

def add_log(team, uid, response_text):
    current_time = time.time()
    timestamp = datetime.datetime.fromtimestamp(current_time).strftime('%H:%M:%S')
    log_entry = f"[{timestamp}] TEAM: {team} | UID: {uid} | {response_text}"
    logs.append((current_time, log_entry))
    # Keep last 200 logs
    if len(logs) > 200:
        logs.pop(0)

# ---------- HOME ----------
@app.route("/")
def home():
    return render_template("index.html")

# ---------- ADMIN ----------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == "pak112233":
            session["admin"] = True
            return redirect("/admin")
        else:
            return "Wrong Password"

    if not session.get("admin"):
        return '''
        <form method="POST">
            <input name="password" placeholder="Enter Password">
            <button>Login</button>
        </form>
        '''

    return render_template("admin.html", uids=list(blocked_uids))

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/admin")

# ---------- LOG PAGE ----------
@app.route("/logs")
def view_logs():
    if not session.get("admin"):
        return redirect("/admin")
    return render_template("logs.html")

# ---------- LOG DATA (RAW TEXT, NO AUTO-REFRESH) ----------
@app.route("/logs-data")
def logs_data():
    if not session.get("admin"):
        return "Unauthorized"

    output = []
    for t, msg in reversed(logs):  # newest first
        output.append(msg)
    return "\n".join(output)

# ---------- BLOCK ----------
@app.route("/block", methods=["POST"])
def block():
    if not session.get("admin"):
        return redirect("/admin")

    uid = request.form.get("uid")
    if uid:
        blocked_uids.add(uid)
        add_log("SYSTEM", uid, "BLOCKED")

    return redirect("/admin")

# ---------- UNBLOCK ----------
@app.route("/unblock", methods=["POST"])
def unblock():
    if not session.get("admin"):
        return redirect("/admin")

    uid = request.form.get("uid")
    if uid in blocked_uids:
        blocked_uids.remove(uid)
        add_log("SYSTEM", uid, "UNBLOCKED")

    return redirect("/admin")

# ---------- SEND (UPDATED API) ----------
@app.route("/send", methods=["POST"])
def send():
    uid = request.form.get("uid")
    team = request.form.get("team")
    emote = str(request.form.get("emote")).strip()
    # no_bot is ignored – new API doesn't support it
    # no_bot = request.form.get("no_bot", "false").lower() == "true"

    if uid in blocked_uids:
        add_log(team, uid, "BLOCKED")
        return jsonify({"status": "blocked"})

    try:
        # New API: GET request with query parameters
        params = {
            "tc": team,            # team code
            "uid1": uid,           # single UID (uid2..uid6 omitted)
            "emote_id": emote
        }

        r = requests.get(
            "https://emoteapi-5lobbyapi.stargmr.pro/api/public/join",
            params=params,
            headers=BROWSER_HEADERS,
            timeout=10
        )

        response_text = r.text.strip()

        # Consider success if status 200 and response contains "success" (adjust as needed)
        if r.status_code == 200 and "success" in r.text.lower():
            add_log(team, uid, f"SUCCESS - {response_text}")
            return jsonify({"status": "success"})
        else:
            add_log(team, uid, f"FAIL - {response_text}")
            return jsonify({"status": "fail"})

    except Exception as e:
        add_log(team, uid, f"ERROR - {str(e)}")
        return jsonify({"status": "error"})

# ---------- CONTENT PAGES (added for AdSense compliance) ----------

def load_blog_posts():
    path = os.path.join(app.root_path, "static", "blog_posts.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.route("/privacy")
def privacy_policy():
    return render_template("privacy.html")

@app.route("/about")
def about_us():
    return render_template("about.html")

@app.route("/contact")
def contact_us():
    return render_template("contact.html")

@app.route("/blog")
def blog_index():
    posts = load_blog_posts()
    posts_sorted = sorted(posts, key=lambda p: p["date"], reverse=True)
    return render_template("blog.html", posts=posts_sorted)

@app.route("/blog/<slug>")
def blog_post(slug):
    posts = load_blog_posts()
    post = next((p for p in posts if p["slug"] == slug), None)
    if not post:
        return redirect("/blog")
    return render_template("blog_post.html", post=post)

@app.route("/robots.txt")
def robots_txt():
    return send_from_directory(os.path.join(app.root_path, "static"), "robots.txt")

@app.route("/sitemap.xml")
def sitemap_xml():
    posts = load_blog_posts()
    pages = ["/", "/blog", "/about", "/contact", "/privacy"]
    pages += [f"/blog/{p['slug']}" for p in posts]

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        xml_parts.append(f"<url><loc>{page}</loc></url>")
    xml_parts.append("</urlset>")

    return Response("".join(xml_parts), mimetype="application/xml")

# ---------- RUN ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
