from flask import Flask, render_template, request, redirect, url_for, session, abort, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from datetime import datetime
import re
from urllib.parse import urlparse, parse_qs
from typing import Optional

# =========================
# APP CONFIGURATION
# =========================
app = Flask(__name__)
app.config["SECRET_KEY"] = "CHANGE_THIS_TO_A_SECRET_KEY"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///gospeltube.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# =========================
# SETTINGS
# =========================
YT_API_KEY = "AIzaSyBY3d9mhvKYtuPa11H2Q4wYW8RVma_6994"
ADMIN_USERNAME = "fixgospel"
ADMIN_PASSWORD_HASH = generate_password_hash("Cris1994!!!!")

# =========================
# CONTEXT PROCESSOR
# =========================
@app.context_processor
def inject_globals():
    return dict(datetime=datetime)

# =========================
# DATABASE MODELS
# =========================
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    parent = db.relationship("Category", remote_side=[id], backref="children")
    videos = db.relationship("Video", backref="category", lazy=True)
class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    video_id = db.Column(db.String(50), nullable=False, unique=True)
    channel_id = db.Column(db.String(50))
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    translated_link = db.Column(db.String(500))
    download_link = db.Column(db.String(500))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# HELPERS
# =========================
def extract_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    url = url.strip()

    match = re.match(r"(https?://)?(www\.)?youtu\.be/([^?&/]+)", url)
    if match:
        return match.group(3)

    parsed_url = urlparse(url)
    if parsed_url.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        return parse_qs(parsed_url.query).get("v", [None])[0]

    return None


def fetch_video_details(video_id: str):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet", "id": video_id, "key": YT_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
        if data.get("items"):
            return data["items"][0]
    except Exception as e:
        print("YouTube API error:", e)
    return None


def admin_required():
    if not session.get("admin"):
        abort(403)


def get_related_videos(video, limit=6):
    if not video.category:
        return []

    category_ids = [video.category_id]

    if video.category.parent_id:
        siblings = Category.query.filter_by(parent_id=video.category.parent_id).all()
        category_ids = [c.id for c in siblings]
    else:
        children = Category.query.filter_by(parent_id=video.category_id).all()
        category_ids.extend([c.id for c in children])

    return (
        Video.query
        .filter(Video.category_id.in_(category_ids), Video.id != video.id)
        .order_by(Video.date_added.desc())
        .limit(limit)
        .all()
    )

# =========================
# FRONTEND ROUTES
# =========================
@app.route("/")
def index():
    categories = Category.query.filter_by(parent_id=None).all()
    homepage_data = []

    for cat in categories:
        parent_videos = Video.query.filter_by(category_id=cat.id).order_by(Video.date_added.desc()).limit(10).all()
        children_data = []

        for sub in cat.children:
            sub_videos = Video.query.filter_by(category_id=sub.id).order_by(Video.date_added.desc()).limit(10).all()
            if sub_videos:
                children_data.append({"category": sub, "videos": sub_videos})

        if parent_videos or children_data:
            homepage_data.append({
                "category": cat,
                "parent_videos": parent_videos,
                "children": children_data
            })

    return render_template("index.html", homepage_data=homepage_data)


@app.route("/videos")
def view_all_videos():
    videos = Video.query.order_by(Video.date_added.desc()).all()
    return render_template("view_all.html", videos=videos)


@app.route("/category/<int:category_id>")
def category_videos(category_id):
    category = Category.query.get_or_404(category_id)
    ids = [category.id] + [c.id for c in category.children]
    videos = Video.query.filter(Video.category_id.in_(ids)).all()
    return render_template("category.html", category=category, videos=videos)


@app.route("/video/<video_id>")
def video_page(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    related_videos = get_related_videos(video)
    return render_template("video.html", video=video, related_videos=related_videos)


@app.route("/search")
def search():
    q = request.args.get("q", "")
    videos = Video.query.filter(Video.title.ilike(f"%{q}%")).all() if q else []
    return render_template("search_results.html", videos=videos, query=q)

# =========================
# ADMIN AUTH
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if (
            request.form.get("username") == ADMIN_USERNAME
            and check_password_hash(ADMIN_PASSWORD_HASH, request.form.get("password"))
        ):
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid login", "danger")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin/dashboard")
def admin_dashboard():
    admin_required()
    return render_template(
        "admin_dashboard.html",
        videos=Video.query.order_by(Video.date_added.desc()).all(),
        categories=Category.query.all()
    )

# =========================
# CATEGORY MANAGEMENT
# =========================
@app.route("/admin/categories", methods=["GET", "POST"])
def manage_categories():
    admin_required()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        parent_id = request.form.get("parent_id") or None

        if name:
            db.session.add(Category(name=name, parent_id=parent_id))
            db.session.commit()
            flash("Category added successfully.", "success")

        return redirect(url_for("manage_categories"))

    return render_template("admin_categories.html", categories=Category.query.all())


@app.route("/admin/categories/edit/<int:id>", methods=["GET", "POST"])
def edit_category(id):
    admin_required()
    category = Category.query.get_or_404(id)

    if request.method == "POST":
        category.name = request.form.get("name", "").strip()
        category.parent_id = request.form.get("parent_id") or None
        db.session.commit()
        flash("Category updated successfully.", "success")
        return redirect(url_for("manage_categories"))

    categories = Category.query.filter(Category.id != id).all()
    return render_template("admin_edit_category.html", category=category, categories=categories)


@app.route("/admin/categories/delete/<int:id>", methods=["POST"])
def delete_category(id):
    admin_required()
    category = Category.query.get_or_404(id)

    if category.videos:
        flash("Cannot delete category with videos.", "danger")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Category deleted successfully.", "success")

    return redirect(url_for("manage_categories"))


@app.route("/admin/videos")
def manage_videos():
    videos = Video.query.all()
    return render_template("manage_videos.html", videos=videos)


@app.route("/admin/videos/edit/<int:video_id>", methods=["GET","POST"])
def edit_video(video_id):
    video = Video.query.get_or_404(video_id)
    categories = Category.query.all()

    if request.method == "POST":
        video.title = request.form["title"]
        video.category_id = request.form.get("category_id") or None
        video.translated_link = request.form.get("translated_link")
        video.download_link = request.form.get("download_link")
        db.session.commit()
        flash("Video updated successfully", "success")
        return redirect(url_for("manage_videos"))

    return render_template("edit_video.html", video=video, categories=categories)


@app.route("/admin/videos/delete/<int:video_id>")
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    db.session.delete(video)
    db.session.commit()
    flash("Video deleted", "success")
    return redirect(url_for("manage_videos"))
    
# =========================
# VIDEO MANAGEMENT
# =========================
@app.route("/admin/videos/add", methods=["GET", "POST"])
def add_video_view():
    admin_required()
    categories = Category.query.all()

    if request.method == "POST":
        youtube_url = request.form.get("youtube_url", "").strip()
        video_id = extract_video_id(youtube_url)

        if not video_id:
            flash("Invalid YouTube URL.", "danger")
            return redirect(url_for("add_video_view"))

        details = fetch_video_details(video_id)
        if not details:
            flash("Failed to fetch video details.", "danger")
            return redirect(url_for("add_video_view"))

        category_id = request.form.get("category_id") or None

        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            video = Video(video_id=video_id)
            db.session.add(video)

        video.title = details["snippet"]["title"]
        video.channel_id = details["snippet"]["channelId"]
        video.category_id = category_id
        video.translated_link = request.form.get("translated_link")
        video.download_link = request.form.get("download_link")

        db.session.commit()
        flash("Video saved successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_add_video.html", categories=categories)
# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
