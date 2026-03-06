# models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()  # ✅ Only defined once

# =====================================================
# USER MODEL
# =====================================================
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="uploader")  # admin | uploader
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    videos = db.relationship("Video", backref="uploader", lazy="dynamic", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="author", lazy="dynamic", cascade="all, delete-orphan")
    likes = db.relationship("Like", backref="user", lazy="dynamic", cascade="all, delete-orphan")


# =====================================================
# CATEGORY MODEL (SELF-REFERENCING)
# =====================================================
class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)

    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    parent = db.relationship(
        "Category",
        remote_side=[id],
        backref=db.backref("children", lazy="dynamic")
    )

    videos = db.relationship("Video", backref="category", lazy="dynamic", cascade="all, delete-orphan")


# =====================================================
# VIDEO MODEL
# =====================================================
class Video(db.Model):
    __tablename__ = "videos"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    video_id = db.Column(db.String(50), nullable=False, unique=True)
    channel_id = db.Column(db.String(50), nullable=True)
    filename = db.Column(db.String(200), nullable=True)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    translated_link = db.Column(db.String(500), nullable=True)
    download_link = db.Column(db.String(500), nullable=True)

    views = db.Column(db.Integer, default=0)
    likes_count = db.Column(db.Integer, default=0)
    last_watched = db.Column(db.DateTime, nullable=True)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    comments = db.relationship("Comment", backref="video", lazy="dynamic", cascade="all, delete-orphan")
    likes = db.relationship("Like", backref="video", lazy="dynamic", cascade="all, delete-orphan")


# =====================================================
# COMMENT MODEL
# =====================================================
class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)


# =====================================================
# LIKE MODEL
# =====================================================
class Like(db.Model):
    __tablename__ = "likes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "video_id", name="unique_like"),
    )


# =====================================================
# SUBSCRIBER MODEL
# =====================================================
class Subscriber(db.Model):
    __tablename__ = "subscribers"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_subscribed = db.Column(db.DateTime, default=datetime.utcnow)