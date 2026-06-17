from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint
from datetime import datetime

# Инициализируем db как заглушку
# Привязывается в app.py через db.init_app(app)
db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=False, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    age = db.Column(db.Integer, nullable=True)
    has_pets = db.Column(db.Boolean, default=False)
    bad_habits = db.Column(db.String(100), nullable=True)
    rental_type = db.Column(db.String(50), nullable=True)
    citizenship = db.Column(db.String(50), nullable=True)
    has_children = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, nullable=True)

    # Путь к файлу аватара в static: "uploads/avatars/<filename>.jpg"
    avatar = db.Column(db.String(255), nullable=True)

    # Связи
    announcements = relationship('Announcement', backref='owner', lazy=True, cascade="all, delete-orphan")
    tenant_requests = relationship('TenantRequest', backref='owner', lazy=True, cascade="all, delete-orphan")
    favorites = relationship('Favorite', backref='user', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"User('{self.username}', '{self.phone}')"

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100), nullable=False)

    # Владение и медиа
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    cover_image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Оснащение квартиры (список через запятую/строки)
    equipment = db.Column(db.Text, nullable=True)

    # Много фотографий для галереи
    images = relationship('AnnouncementImage', backref='announcement', lazy=True, cascade="all, delete-orphan")

    # Избранное
    favorites_rel = relationship('Favorite', backref='announcement', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"Announcement('{self.title}', '{self.location}')"

class AnnouncementImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcement.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"AnnouncementImage(ann_id={self.announcement_id}, path='{self.image_path}')"

class TenantRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    city = db.Column(db.String(100), nullable=False)
    rooms = db.Column(db.String(20), nullable=True)  # студия/1/2/3...
    budget = db.Column(db.Integer, nullable=True)   # руб/мес
    term = db.Column(db.String(50), nullable=True)  # срок аренды
    has_children = db.Column(db.Boolean, default=False)
    has_pets = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), default='published')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"TenantRequest(user_id={self.user_id}, city='{self.city}', budget={self.budget})"

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcement.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'announcement_id', name='uq_user_announcement_favorite'),
    )

    def __repr__(self):
        return f"Favorite(user_id={self.user_id}, ann_id={self.announcement_id})"
