# models.py
from app import db

# ==========================
# Category Model
# ==========================
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    # Relationship: One category can have many videos
    videos = db.relationship("Video", backref="category", lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"


# ==========================
# Video Model
# ==========================
class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)
    # Optional fields for future use
    url = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f"<Video {self.title}>"