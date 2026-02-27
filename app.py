from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, current_app
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re
from urllib.parse import urlparse, parse_qs
from typing import Optional
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import os

# Import models
from models import Category  # Ensure Category model is imported here
# =====================================================
# ENSURE INSTANCE FOLDER EXISTS (for SQLite)
# =====================================================
if not os.path.exists("instance"):
    os.makedirs("instance")
# =====================================================
# =====================================================
# APP CONFIGURATION
# =====================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

# Database configuration
database_url = os.environ.get("DATABASE_URL")

# Fix old-style postgres:// URLs
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///gospeltube.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ========================
# FLASK-MAIL CONFIGURATION
# ========================
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = ("GospelTube", "your_email@gmail.com")  # Sender name and email

mail = Mail(app)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# =====================================================
# SETTINGS
# =====================================================
ADMIN_USERNAME = "fixgospel"
ADMIN_PASSWORD_HASH = generate_password_hash("Cris1994!!!!")

# =====================================================
# CONTEXT PROCESSORS
# =====================================================
@app.context_processor
def inject_globals():
    """
    Provides global variables to all templates.
    Safe: No database access, so won't cause server errors.
    """
    return dict(datetime=datetime)

@app.context_processor
def inject_categories():
    from app import db
    from app import Category

    categories = []
    try:
        # Ensure app context is active
        from flask import current_app
        with current_app.app_context():
            categories = Category.query.order_by(Category.name).all()
    except Exception as e:
        print("Error loading categories:", e)
        categories = []

    return {"categories": categories}
# =====================================================
# HELPERS
# =====================================================
def extract_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = re.match(r"(https?://)?(www\.)?youtu\.be/([^?&/]+)", url)
    if match:
        return match.group(3)

    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        return parse_qs(parsed.query).get("v", [None])[0]
    return None

def slugify(name: str) -> str:
    return re.sub(r"\s+", "-", name.strip().lower())

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper

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

    return Video.query.filter(
        Video.category_id.in_(category_ids),
        Video.id != video.id
    ).order_by(Video.date_added.desc()).limit(limit).all()

def uploader_or_admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("role") not in ["admin", "uploader"]:
            flash("Login required.", "danger")
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper
    
def create_admin_user():
    """Create an admin user if it doesn't exist."""
    # Ensure tables exist first
    with app.app_context():
        db.create_all()  # Create tables if they don't exist

        # Fix categories without slugs
        for category in Category.query.filter(Category.slug == None).all():
            category.slug = re.sub(r"\s+", "-", category.name.strip().lower())
        db.session.commit()

        # Check if admin already exists
        admin = User.query.filter_by(username=ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=ADMIN_USERNAME,
                password=ADMIN_PASSWORD_HASH,  # make sure this is hashed
                role="admin"
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created successfully!")
        else:
            print("ℹ Admin user already exists.")
# =====================================================
# DATABASE MODELS
# =====================================================
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    parent = db.relationship("Category", remote_side=[id], backref="children")
    videos = db.relationship("Video", backref="category", lazy=True)

class Video(db.Model):
    __tablename__ = "videos"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    video_id = db.Column(db.String(50), nullable=False, unique=True)
    channel_id = db.Column(db.String(50))
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    translated_link = db.Column(db.String(500))
    download_link = db.Column(db.String(500))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))  # ✅ NEW
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0)
    last_watched = db.Column(db.DateTime)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_subscribed = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="uploader")  # admin | uploader
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Like(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    video_id = db.Column(
        db.Integer,
        db.ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False
    )
    __table_args__ = (
        db.UniqueConstraint("user_id", "video_id", name="unique_like"),
    )

# =====================================================
# FRONTEND ROUTES
# =====================================================
@app.route("/")
def index():
    categories = Category.query.filter_by(parent_id=None).order_by(Category.name.asc()).all()
    homepage_data = []

    for cat in categories:
        parent_videos = Video.query.filter_by(category_id=cat.id)\
                                   .order_by(Video.date_added.desc()).limit(10).all()
        children_data = []
        for sub in cat.children:
            sub_videos = Video.query.filter_by(category_id=sub.id)\
                                    .order_by(Video.date_added.desc()).limit(10).all()
            if sub_videos:
                children_data.append({"category": sub, "videos": sub_videos})
        if parent_videos or children_data:
            homepage_data.append({
                "category": cat,
                "parent_videos": parent_videos,
                "children": children_data
            })

    featured_videos = Video.query.order_by(Video.date_added.desc()).limit(5).all()
    popular_videos = Video.query.order_by(Video.views.desc()).limit(10).all()

    return render_template(
        "index.html",
        homepage_data=homepage_data,
        featured_videos=featured_videos,
        popular_videos=popular_videos,
        active_category="All"
    )

@app.route("/video/<video_id>")
def video_page(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    session_key = f"viewed_{video.id}"
    if not session.get(session_key):
        video.views += 1
        video.last_watched = datetime.utcnow()
        session[session_key] = True
        db.session.commit()

    return render_template(
        "video.html",
        video=video,
        related_videos=get_related_videos(video),
        popular_videos=Video.query.order_by(Video.views.desc()).limit(8).all()
    )

@app.route('/like_video/<video_id>', methods=['POST'])
def like_video(video_id):
    video = Video.query.filter_by(video_id=video_id).first_or_404()
    video.likes += 1
    db.session.commit()
    return jsonify({"likes": video.likes})

# ==============================
# SUBSCRIBE ROUTE (AJAX JSON)
# ==============================
@app.route("/subscribe", methods=["POST"])
def subscribe():
    try:
        data = request.get_json()
        if not data or "email" not in data:
            return jsonify({"status": "error", "message": "Email is required."}), 400

        email = data["email"].strip().lower()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({"status": "error", "message": "Invalid email address."}), 400

        # Check if already subscribed
        existing = Subscriber.query.filter_by(email=email).first()
        if existing:
            return jsonify({"status": "info", "message": "Email already subscribed."}), 200

        # Add subscriber
        new_sub = Subscriber(email=email)
        db.session.add(new_sub)
        db.session.commit()

        # Send Welcome Email
        try:
            msg = Message(
                subject="Welcome to GospelTube 🙌",
                recipients=[email],
                body=f"Hello!\n\nThank you for subscribing to GospelTube. Stay tuned for the latest videos and updates.\n\nBlessings,\nGospelTube Team"
            )
            mail.send(msg)
        except Exception as e:
            print("Welcome email failed:", e)

        return jsonify({"status": "success", "message": "Subscribed successfully 🙌"}), 200

    except Exception as e:
        print("Subscribe error:", e)
        return jsonify({"status": "error", "message": "Subscription failed. Try again."}), 500

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    videos = Video.query.filter(Video.title.ilike(f"%{q}%")).all() if q else []
    return render_template("search_results.html", videos=videos, query=q)

@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy.html")

# =====================================================
# CATEGORY PAGES
# =====================================================
@app.route("/category-page/<string:category_slug>")
def category_landing_page(category_slug):
    main_category = Category.query.filter_by(slug=category_slug).first_or_404()
    main_videos = Video.query.filter_by(category_id=main_category.id)\
                             .order_by(Video.date_added.desc()).limit(10).all()
    subcategory_blocks = []
    for sub in main_category.children:
        sub_videos = Video.query.filter_by(category_id=sub.id)\
                                .order_by(Video.date_added.desc()).limit(10).all()
        if sub_videos:
            subcategory_blocks.append({"category": sub, "videos": sub_videos})
    return render_template(
        "category_landing_page.html",
        main_category=main_category,
        main_videos=main_videos,
        subcategory_blocks=subcategory_blocks
    )

# =====================================================
# ADMIN ROUTES
# =====================================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role

            flash("Logged in successfully!", "success")

            if user.role == "admin":
                return redirect(url_for("manage_videos"))
            else:
                return redirect(url_for("uploader_dashboard"))

        flash("Invalid credentials.", "danger")

    return render_template("admin_login.html")

@app.route("/admin/create-user", methods=["POST"])
@admin_required
def create_user():
    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role", "uploader")

    if User.query.filter_by(username=username).first():
        flash("User already exists.", "warning")
        return redirect(url_for("manage_videos"))

    user = User(
        username=username,
        password=generate_password_hash(password),
        role=role
    )
    db.session.add(user)
    db.session.commit()

    flash("User created successfully.", "success")
    return redirect(url_for("manage_videos"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("admin_login"))

@app.route("/admin/videos")
@admin_required
def manage_videos():
    return render_template(
        "admin_videos.html",
        videos=Video.query.order_by(Video.date_added.desc()).all(),
        categories=Category.query.order_by(Category.name.asc()).all()
    )

@app.route("/admin/videos/add", methods=["GET", "POST"])
@uploader_or_admin_required
def add_video():
    if request.method == "POST":
        # ---- process video submission ----
        video_id = extract_video_id(request.form.get("youtube_link", ""))
        if not video_id:
            flash("Invalid YouTube link.", "danger")
            return redirect(url_for("manage_videos"))

        if Video.query.filter_by(video_id=video_id).first():
            flash("Video already exists.", "warning")
            return redirect(url_for("manage_videos"))

        video = Video(
            title=request.form.get("title"),
            description=request.form.get("description"),
            category_id=request.form.get("category_id") or None,
            video_id=video_id,
            translated_link=request.form.get("drive_link"),
            download_link=request.form.get("mediafire_link"),
            uploaded_by=session.get("user_id")
        )

        db.session.add(video)
        db.session.commit()
        flash("Video added successfully ✅", "success")
        return redirect(url_for("manage_videos"))

    # ---- GET request → show upload form ----
    categories = Category.query.order_by(Category.name.asc()).all()
    return render_template("upload_video.html", categories=categories)

@app.route("/create-uploader")
def create_uploader():
    from werkzeug.security import generate_password_hash
    user = User(username="john_uploader", password=generate_password_hash("Password123"), role="uploader")
    db.session.add(user)
    db.session.commit()
    return "Uploader Created ✅"

from datetime import datetime, timedelta

@app.route("/uploader/dashboard")
def uploader_dashboard():
    if session.get("role") != "uploader":
        return redirect(url_for("admin_login"))

    videos = Video.query.filter_by(
        uploaded_by=session.get("user_id")
    ).order_by(Video.date_added.desc()).all()

    now = datetime.utcnow()

    video_data = []
    for v in videos:
        editable = now <= v.date_added + timedelta(hours=48)
        video_data.append({
            "video": v,
            "editable": editable
        })

    return render_template(
        "uploader_dashboard.html",
        video_data=video_data
    )
    #======================#
    # Notify all subscribers
    # =========================
    subscribers = Subscriber.query.all()
    for sub in subscribers:
        try:
            msg = Message(
                subject=f"New Video Added: {video.title}",
                recipients=[sub.email],
                body=f"Hello!\n\nA new video '{video.title}' has been added to GospelTube.\nWatch it here: {url_for('video_page', video_id=video.video_id, _external=True)}\n\nBlessings,\nGospelTube Team"
            )
            mail.send(msg)
        except Exception as e:
            print(f"Notification email failed for {sub.email}:", e)

    flash("Video added successfully ✅", "success")
    return redirect(url_for("manage_videos"))

@app.route("/admin/videos/<int:video_id>/edit", methods=["GET", "POST"], endpoint="edit_video")
def edit_video(video_id):
    video = Video.query.get_or_404(video_id)

    # Admin can always edit
    if session.get("role") == "uploader":
        # Check if uploader owns this video
        if video.uploaded_by != session.get("user_id"):
            flash("You cannot edit this video.", "danger")
            return redirect(url_for("uploader_dashboard"))

        # Check if within 48 hours
        if datetime.utcnow() > video.date_added + timedelta(hours=48):
            flash("You can no longer edit this video (48 hours passed).", "warning")
            return redirect(url_for("uploader_dashboard"))

    categories = Category.query.order_by(Category.name.asc()).all()

    if request.method == "POST":
        video.title = request.form.get("title", video.title)
        video.description = request.form.get("description", video.description)
        video.category_id = request.form.get("category_id") or None
        video.translated_link = request.form.get("drive_link")
        video.download_link = request.form.get("mediafire_link")
        db.session.commit()
        flash("Video updated successfully ✅", "success")

        # Redirect depending on role
        if session.get("role") == "admin":
            return redirect(url_for("manage_videos"))
        return redirect(url_for("uploader_dashboard"))

    return render_template("admin_edit_video.html", video=video, categories=categories)

@app.route("/admin/videos/<int:video_id>/delete", methods=["POST"], endpoint="delete_video")
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)

    if session.get("role") == "uploader":
        if video.uploaded_by != session.get("user_id"):
            flash("You cannot delete this video.", "danger")
            return redirect(url_for("uploader_dashboard"))

        if datetime.utcnow() > video.date_added + timedelta(hours=48):
            flash("You can no longer delete this video (48 hours passed).", "warning")
            return redirect(url_for("uploader_dashboard"))

    db.session.delete(video)
    db.session.commit()
    flash("Video deleted successfully ✅", "success")

    if session.get("role") == "admin":
        return redirect(url_for("manage_videos"))
    return redirect(url_for("uploader_dashboard"))

# =====================================================
# ADMIN CATEGORY ROUTES
# =====================================================
@app.route("/admin/categories", methods=["GET", "POST"])
@admin_required
def manage_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        parent_id = request.form.get("parent_id") or None
        if not name:
            flash("Category name required.", "danger")
            return redirect(url_for("manage_categories"))
        if Category.query.filter_by(name=name).first():
            flash("Category already exists.", "warning")
            return redirect(url_for("manage_categories"))
        slug = slugify(name)
        counter = 1
        base_slug = slug
        while Category.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        db.session.add(Category(name=name, parent_id=parent_id, slug=slug))
        db.session.commit()
        flash("Category added successfully.", "success")
    return render_template("admin_categories.html", categories=Category.query.order_by(Category.name.asc()).all())

@app.route("/admin/categories/<int:category_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    categories = Category.query.filter(Category.id != category.id).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        parent_id = request.form.get("parent_id") or None
        if not name:
            flash("Category name is required.", "danger")
            return redirect(url_for("edit_category", category_id=category.id))
        category.name = name
        new_slug = slugify(name)
        if new_slug != category.slug:
            counter = 1
            base_slug = new_slug
            while Category.query.filter(Category.slug == new_slug, Category.id != category.id).first():
                new_slug = f"{base_slug}-{counter}"
                counter += 1
            category.slug = new_slug
        category.parent_id = parent_id
        db.session.commit()
        flash("Category updated successfully ✅", "success")
        return redirect(url_for("manage_categories"))
    return render_template("admin_edit_category.html", category=category, categories=categories)

@app.route("/admin/categories/<int:category_id>/delete", methods=["POST"], endpoint="delete_category")
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.videos:
        flash("Cannot delete category with videos. Remove videos first.", "danger")
        return redirect(url_for("manage_categories"))
    if category.children:
        flash("Cannot delete category with subcategories.", "warning")
        return redirect(url_for("manage_categories"))
    db.session.delete(category)
    db.session.commit()
    flash("Category deleted successfully ✅", "success")
    return redirect(url_for("manage_categories"))

# =====================================================
# VIEW ALL VIDEOS
# =====================================================
@app.route("/videos")
def view_all_videos():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    videos_pagination = Video.query.order_by(Video.date_added.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return render_template("view_all.html", videos=videos_pagination.items, pagination=videos_pagination)

# =====================================================
# RUN APP (Render-ready)
# =====================================================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        for category in Category.query.filter(Category.slug == None).all():
            category.slug = re.sub(r"\s+", "-", category.name.strip().lower())
        # Create admin user if not exists
        create_admin_user()

    # Render requires host 0.0.0.0 and PORT from env
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))