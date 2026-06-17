import os
import uuid
import shutil
from datetime import datetime, timedelta
import json

from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, current_user, login_required
)
from sqlalchemy import and_, or_, func, text
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

database_uri = os.environ.get('DATABASE_URI') or os.environ.get('DATABASE_URL', 'sqlite:///app.db')
if database_uri.startswith('mysql://'):
    database_uri = database_uri.replace('mysql://', 'mysql+pymysql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads')
AVATAR_DIR = os.path.join(UPLOAD_DIR, 'avatars')
ANNOUNCEMENTS_DIR = os.path.join(UPLOAD_DIR, 'announcements')
BACKUPS_DIR = os.path.join(BASE_DIR, 'backups')

for d in (STATIC_DIR, UPLOAD_DIR, AVATAR_DIR, ANNOUNCEMENTS_DIR, BACKUPS_DIR):
    os.makedirs(d, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'index'

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(11), unique=True, nullable=False)
    username = db.Column(db.String(120))
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(20), default='user')
    is_blocked = db.Column(db.Boolean, default=False)
    blocked_reason = db.Column(db.Text)
    blocked_at = db.Column(db.DateTime)

    avatar = db.Column(db.String(255))
    age = db.Column(db.Integer)
    has_pets = db.Column(db.Boolean, default=False)
    bad_habits = db.Column(db.String(255))
    rental_type = db.Column(db.String(100))
    citizenship = db.Column(db.String(100))
    has_children = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_sms_code = db.Column(db.String(6))
    sms_code_expires_at = db.Column(db.DateTime)

    def set_password(self, password: str):
        if password:
            self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    announcements = db.relationship('Announcement', backref='owner', lazy=True)
    tenant_requests = db.relationship('TenantRequest', backref='owner', lazy=True)

class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(120))
    rooms = db.Column(db.String(60))
    equipment = db.Column(db.Text)
    cover_image = db.Column(db.String(255))
    
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)

    status = db.Column(db.String(40), default='active')
    moderation_reason = db.Column(db.Text)
    moderated_by = db.Column(db.Integer)
    moderated_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    images = db.relationship('AnnouncementImage', backref='announcement', cascade='all, delete-orphan', lazy=True)

def ensure_announcements_columns():
    if not is_sqlite():
        return

    columns = {
        'city': 'TEXT',
        'rooms': 'TEXT',
        'equipment': 'TEXT',
        'cover_image': 'VARCHAR(255)',
        'status': 'VARCHAR(40)',
        'moderation_reason': 'TEXT',
        'moderated_by': 'INTEGER',
        'moderated_at': 'DATETIME',
        'created_at': 'DATETIME',
        'updated_at': 'DATETIME',
        'lat': 'REAL',
        'lng': 'REAL'
    }
    existing = set()
    result = db.session.execute(text("PRAGMA table_info('announcements')")).mappings().all()
    for row in result:
        existing.add(row['name'])
    for name, column_type in columns.items():
        if name not in existing:
            db.session.execute(text(f"ALTER TABLE announcements ADD COLUMN {name} {column_type}"))
    db.session.commit()

class AnnouncementImage(db.Model):
    __tablename__ = 'announcement_images'
    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcements.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)

class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcements.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'announcement_id', name='uq_user_ann'),)

class TenantRequest(db.Model):
    __tablename__ = 'tenant_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    city = db.Column(db.String(120))
    rooms = db.Column(db.String(60))
    budget = db.Column(db.Integer)
    term = db.Column(db.String(120))
    description = db.Column(db.Text)
    has_children = db.Column(db.Boolean, default=False)
    has_pets = db.Column(db.Boolean, default=False)

    status = db.Column(db.String(40), default='active')
    moderation_reason = db.Column(db.Text)
    moderated_by = db.Column(db.Integer)
    moderated_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcements.id'), nullable=True)
    tenant_request_id = db.Column(db.Integer, db.ForeignKey('tenant_requests.id'), nullable=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(40), default='system')
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    payload_json = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ModerationAction(db.Model):
    __tablename__ = 'moderation_actions'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_type = db.Column(db.String(40))
    target_id = db.Column(db.Integer)
    action = db.Column(db.String(40))
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Backup(db.Model):
    __tablename__ = 'backups'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), default='db')
    location = db.Column(db.String(255))
    status = db.Column(db.String(20), default='success')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SavedSearch(db.Model):
    __tablename__ = 'saved_searches'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    params_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def is_admin():
    return current_user.is_authenticated and current_user.role == 'admin'

def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return False


def parse_int(value, default=None):
    if value is None or value == '':
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def is_sqlite():
    return db.engine.url.get_backend_name() == 'sqlite'


def create_admin_if_missing():
    admin_phone = os.environ.get('ADMIN_PHONE', '99999999999')  # новый телефон админа
    admin = User.query.filter_by(phone=admin_phone).first()
    if not admin:
        admin = User(phone=admin_phone, username='Админ', role='admin')
        db.session.add(admin)
        db.session.commit()
    # set SMS code if provided
    admin.last_sms_code = os.environ.get('ADMIN_SMS', '123456')
    admin.sms_code_expires_at = datetime.utcnow() + timedelta(minutes=30)
    # set password if provided in env (useful for stable admin login)
    env_pass = os.environ.get('ADMIN_PASSWORD')
    if env_pass and not admin.password_hash:
        admin.set_password(env_pass)
        # ensure role is admin
        admin.role = 'admin'
    db.session.commit()


def create_sample_data_if_missing():
    if Announcement.query.filter(Announcement.status == 'active').count() > 0:
        return

    user1 = User.query.filter_by(phone='80000000000').first()
    if not user1:
        user1 = User(phone='80000000000', username='Тестовый арендодатель')
        db.session.add(user1)

    user2 = User.query.filter_by(phone='80000000001').first()
    if not user2:
        user2 = User(phone='80000000001', username='Сергей Власов')
        db.session.add(user2)

    db.session.commit()

    samples = [
        {
            'user': user1,
            'title': 'Яркая студия рядом с метро',
            'description': 'Светлая студия с мебелью, стиральной машиной и быстрым интернетом. Отличный вариант для одного человека или пары.',
            'price': 42000,
            'location': 'Москва, Новослободская 23',
            'equipment': 'Кондиционер\nХолодильник\nПосудомоечная машина',
            'cover_image': 'img/apartment1.jpg'
        },
        {
            'user': user2,
            'title': 'Трёхкомнатная квартира с ремонтом',
            'description': 'Уютная квартира после ремонта в зеленом районе. Есть парковка и большой балкон.',
            'price': 68000,
            'location': 'Санкт-Петербург, Невский проспект 12',
            'equipment': 'Посудомоечная машина\nСтиральная машина\nКондиционер',
            'cover_image': 'img/apartment2.jpg'
        },
        {
            'user': user1,
            'title': 'Двухкомнатная квартира с видом на парк',
            'description': 'Просторная квартира с двумя окнами и видом на парк. Подходит для семьи с детьми.',
            'price': 52000,
            'location': 'Екатеринбург, Ленина 45',
            'equipment': 'Мебель\nИнтернет\nТелевизор',
            'cover_image': 'img/apartment1.jpg'
        }
    ]

    for sample in samples:
        ann = Announcement(
            user_id=sample['user'].id,
            title=sample['title'],
            description=sample['description'],
            price=sample['price'],
            location=sample['location'],
            equipment=sample['equipment'],
            cover_image=sample['cover_image'],
            status='active'
        )
        db.session.add(ann)
    db.session.commit()

@app.context_processor
def inject_unread_count():
    count = 0
    if current_user.is_authenticated:
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return {'unread_count': count}


@app.route('/unread_counts')
def unread_counts():
    if not current_user.is_authenticated:
        return jsonify({'success': True, 'notifications_unread': 0, 'messages_unread': 0})
    notifications_unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    messages_unread = Notification.query.filter_by(user_id=current_user.id, is_read=False, type='message').count()
    return jsonify({'success': True, 'notifications_unread': notifications_unread, 'messages_unread': messages_unread})


# Saved searches API
@app.route('/saved_searches')
@login_required
def get_saved_searches():
    searches = SavedSearch.query.filter_by(user_id=current_user.id).order_by(SavedSearch.created_at.desc()).all()
    return jsonify({'success': True, 'searches': [{'id': s.id, 'name': s.name, 'params': s.params_json, 'created_at': s.created_at.strftime('%Y-%m-%d %H:%M')} for s in searches]})

@app.route('/saved_searches/create', methods=['POST'])
@login_required
def create_saved_search():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    params = data.get('params') or {}
    if not name:
        return jsonify({'success': False, 'message': 'Введите имя для сохранения поиска.'}), 400
    ss = SavedSearch(user_id=current_user.id, name=name, params_json=json.dumps(params, ensure_ascii=False))
    db.session.add(ss)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Поиск сохранён.', 'id': ss.id})

with app.app_context():
    db.create_all()
    ensure_announcements_columns()
    create_admin_if_missing()
    create_sample_data_if_missing()

@app.route('/')
def index():
    items = Announcement.query.filter(Announcement.status == 'active').order_by(Announcement.created_at.desc()).limit(4).all()
    return render_template('index.html', items=items, active_page='index')

@app.route('/announcements')
def announcements():
    # rooms can be provided multiple times (checkboxes) -> getlist
    selected_rooms = request.args.getlist('rooms')
    selected_city = (request.args.get('city') or '').strip()
    price_min = parse_int(request.args.get('price_min'), None)
    price_max = parse_int(request.args.get('price_max'), None)

    query = Announcement.query.filter(Announcement.status == 'active')
    if selected_rooms:
        # filter announcements where rooms matches any of selected values
        query = query.filter(Announcement.rooms.in_(selected_rooms))
    if selected_city:
        query = query.filter(Announcement.city.ilike(f'%{selected_city}%'))
    if price_min is not None:
        query = query.filter(Announcement.price >= price_min)
    if price_max is not None:
        query = query.filter(Announcement.price <= price_max)

    items = query.order_by(Announcement.created_at.desc()).all()
    fav_ids = []
    if current_user.is_authenticated:
        fav_ids = [f.announcement_id for f in Favorite.query.filter_by(user_id=current_user.id).all()]
    # Собираем все уникальные города из активных объявлений для фильтра
    cities_q = db.session.query(Announcement.city).filter(Announcement.status == 'active', Announcement.city.isnot(None), Announcement.city != '').distinct().all()
    cities = sorted({c[0].strip() for c in cities_q if c[0] and c[0].strip()})

    return render_template('announcements.html', items=items, fav_ids=fav_ids, active_page='announcements', selected_rooms=selected_rooms, selected_city=selected_city, price_min=price_min, price_max=price_max, cities=cities)


@app.route('/cities.json')
def cities_json():
    cities_q = db.session.query(Announcement.city).filter(Announcement.status == 'active', Announcement.city.isnot(None), Announcement.city != '').distinct().all()
    cities = sorted({c[0].strip() for c in cities_q if c[0] and c[0].strip()})
    return jsonify({'success': True, 'cities': cities})


@app.route('/announcements/geo.json')
def announcements_geo():
    # Координаты крупных городов России
    city_coords = {
        'москва': (55.7558, 37.6173),
        'санкт-петербург': (59.9311, 30.3609),
        'екатеринбург': (56.8389, 60.6057),
        'новосибирск': (55.0415, 82.9346),
        'казань': (55.7887, 49.1221),
        'челябинск': (55.1644, 61.4368),
        'краснодар': (45.0355, 38.9757),
        'сочи': (43.5890, 39.7159),
        'самара': (53.1974, 50.1004),
        'ростов-на-дону': (47.2313, 39.7015),
        'уфа': (54.7355, 55.9573),
        'волгоград': (48.7086, 44.4793),
        'пермь': (58.0104, 56.2293),
        'воронеж': (51.6623, 39.1841),
        'тверь': (56.8615, 35.9311),
    }
    
    anns = Announcement.query.filter(Announcement.status == 'active', Announcement.city.isnot(None)).filter(Announcement.city != '').all()
    data = []
    for a in anns:
        lat = a.lat
        lng = a.lng
        
        # Если координат нет - используем город
        if lat is None or lng is None:
            city_lower = (a.city or '').lower().strip()
            if city_lower in city_coords:
                lat, lng = city_coords[city_lower]
            else:
                continue  # Пропускаем если не можем определить координаты
        
        img = a.cover_image or (a.images[0].image_path if a.images and len(a.images) > 0 else 'img/apartment1.jpg')
        data.append({'id': a.id, 'title': a.title, 'lat': lat, 'lng': lng, 'price': a.price, 'city': a.city, 'image': url_for('static', filename=img)})
    return jsonify({'success': True, 'items': data})

@app.route('/announcements/<int:announcement_id>')
def announcement_detail(announcement_id):
    item = Announcement.query.get_or_404(announcement_id)
    return render_template('announcement_detail.html', item=item, active_page='announcements')

@app.route('/favorites')
@login_required
def favorites():
    favs = Favorite.query.filter_by(user_id=current_user.id).all()
    ann_ids = [f.announcement_id for f in favs]
    items = Announcement.query.filter(Announcement.id.in_(ann_ids), Announcement.status == 'active').all()
    return render_template('favorites.html', items=items, active_page='favorites')

@app.route('/tenants')
def tenants():
    requests = TenantRequest.query.filter(TenantRequest.status == 'active').order_by(TenantRequest.created_at.desc()).all()
    return render_template('tenants.html', requests=requests, active_page='tenants')

@app.route('/about')
def about():
    return render_template('about.html', active_page='about')

@app.route('/profile')
@login_required
def profile():
    my_announcements = Announcement.query.filter_by(user_id=current_user.id).order_by(Announcement.created_at.desc()).all()
    my_request = TenantRequest.query.filter_by(user_id=current_user.id).order_by(TenantRequest.created_at.desc()).first()
    return render_template('profile.html', my_announcements=my_announcements, my_request=my_request, active_page='profile')

@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    if not name:
        return jsonify({'message': 'Пожалуйста, введите имя.'}), 400
    if len(phone) != 11 or not phone.isdigit():
        return jsonify({'message': 'Телефон должен состоять из 11 цифр.'}), 400
    user = User.query.filter_by(phone=phone).first()
    if not user:
        user = User(phone=phone, username=name)
        db.session.add(user)
    else:
        user.username = user.username or name
    user.last_sms_code = '123456'
    user.sms_code_expires_at = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    return jsonify({'message': 'Пользователь зарегистрирован. Введите код из СМС для входа.', 'redirect_url': url_for('index')})

@app.route('/login_user', methods=['POST'])
def login_user_route():
    data = request.get_json() or {}
    phone = (data.get('phone') or '').strip()
    sms_code = (data.get('smsCode') or '').strip()
    password = (data.get('password') or '').strip()
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({'message': 'Пользователь с таким телефоном не найден.'}), 404
    if user.is_blocked:
        return jsonify({'message': f'Аккаунт заблокирован: {user.blocked_reason or "без указания причины"}'}), 403
    # allow login by password if provided
    if password:
        if user.check_password(password):
            login_user(user)
            return jsonify({'message': 'Вход выполнен.', 'redirect_url': url_for('profile')})
        else:
            return jsonify({'message': 'Неверный пароль.'}), 400

    # otherwise, fallback to SMS code
    if not sms_code or sms_code != (user.last_sms_code or ''):
        return jsonify({'message': 'Неверный SMS-код.'}), 400
    # check expiry
    if user.sms_code_expires_at and datetime.utcnow() > user.sms_code_expires_at:
        return jsonify({'message': 'Срок действия SMS-кода истёк.'}), 400
    login_user(user)
    return jsonify({'message': 'Вход выполнен.', 'redirect_url': url_for('profile')})

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Вы вышли из аккаунта.', 'redirect_url': url_for('index')})

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    f = request.files.get('avatar')
    if not f:
        return jsonify({'success': False, 'message': 'Файл не прикреплён.'}), 400
    filename = secure_filename(f.filename) or f'avatar_{uuid.uuid4().hex}.jpg'
    ext = os.path.splitext(filename)[1].lower() or '.jpg'
    new_name = f'user_{current_user.id}_{uuid.uuid4().hex}{ext}'
    save_path = os.path.join(AVATAR_DIR, new_name)
    f.save(save_path)
    current_user.avatar = f'uploads/avatars/{new_name}'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Аватар обновлён!', 'avatar_url': url_for('static', filename=current_user.avatar)})

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json() or {}
    field_errors = {}
    username = (data.get('username') or '').strip()
    age = (data.get('age') or '').strip()
    if username and len(username) < 2:
        field_errors['username'] = 'Имя слишком короткое.'
    if age:
        try:
            age_val = int(age)
            if age_val < 0 or age_val > 120:
                field_errors['age'] = 'Возраст указан некорректно.'
        except ValueError:
            field_errors['age'] = 'Возраст должен быть числом.'
    if field_errors:
        return jsonify({'message': 'Проверьте поля.', 'field_errors': field_errors}), 400

    current_user.username = username or current_user.username
    current_user.age = int(age) if age else current_user.age
    current_user.has_pets = parse_bool(data.get('has_pets'))
    current_user.bad_habits = (data.get('bad_habits') or '').strip()
    current_user.rental_type = (data.get('rental_type') or '').strip()
    current_user.citizenship = (data.get('citizenship') or '').strip()
    current_user.has_children = parse_bool(data.get('has_children'))
    current_user.description = (data.get('description') or '').strip()
    db.session.commit()
    return jsonify({'message': 'Профиль обновлён.'})

@app.route('/announcements/create', methods=['POST'])
@login_required
def create_announcement():
    title = (request.form.get('title') or '').strip()
    description = (request.form.get('description') or '').strip()
    price = (request.form.get('price') or '0').strip()
    location = (request.form.get('location') or '').strip()
    city = (request.form.get('city') or '').strip()
    rooms = (request.form.get('rooms') or '').strip()
    equipment = (request.form.get('equipment') or '').strip()
    lat_str = (request.form.get('lat') or '').strip()
    lng_str = (request.form.get('lng') or '').strip()
    
    if not title or not description or not location or not city:
        return jsonify({'message': 'Заполните заголовок, описание, город и локацию.'}), 400
    try:
        price_val = int(price)
    except ValueError:
        return jsonify({'message': 'Цена должна быть числом.'}), 400
    
    lat = None
    lng = None
    try:
        if lat_str:
            lat = float(lat_str)
        if lng_str:
            lng = float(lng_str)
    except ValueError:
        pass

    ann = Announcement(
        user_id=current_user.id,
        title=title,
        description=description,
        price=price_val,
        location=location,
        city=city,
        rooms=rooms,
        equipment=equipment,
        lat=lat,
        lng=lng,
        status='active'
    )
    db.session.add(ann)
    db.session.commit()

    ann_dir = os.path.join(ANNOUNCEMENTS_DIR, str(ann.id))
    os.makedirs(ann_dir, exist_ok=True)

    cover = request.files.get('cover')
    if cover:
        c_name = secure_filename(cover.filename) or f'cover_{uuid.uuid4().hex}.jpg'
        c_ext = os.path.splitext(c_name)[1].lower() or '.jpg'
        new_cover = f'cover_{uuid.uuid4().hex}{c_ext}'
        cover.save(os.path.join(ann_dir, new_cover))
        ann.cover_image = f'uploads/announcements/{ann.id}/{new_cover}'

    gallery = request.files.getlist('gallery')
    for g in gallery:
        if not g:
            continue
        g_name = secure_filename(g.filename) or f'img_{uuid.uuid4().hex}.jpg'
        g_ext = os.path.splitext(g_name)[1].lower() or '.jpg'
        new_img = f'img_{uuid.uuid4().hex}{g_ext}'
        g.save(os.path.join(ann_dir, new_img))
        db.session.add(AnnouncementImage(announcement_id=ann.id, image_path=f'uploads/announcements/{ann.id}/{new_img}'))

    db.session.commit()

    db.session.add(Notification(user_id=current_user.id, type='system', title='Объявление создано', message=f'Ваше объявление "{ann.title}" опубликовано.'))
    db.session.commit()

    return jsonify({'message': 'Объявление создано!', 'redirect_url': url_for('announcements')})

@app.route('/messages/conversation/<int:target_user_id>')
@login_required
def message_conversation(target_user_id):
    if target_user_id == current_user.id:
        return jsonify({'success': False, 'message': 'Нельзя открыть диалог с самим собой.'}), 400
    target = User.query.get_or_404(target_user_id)
    msgs = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == target_user_id),
            and_(Message.sender_id == target_user_id, Message.receiver_id == current_user.id)
        )
    ).order_by(Message.created_at.asc()).all()
    return jsonify({
        'success': True,
        'user': {'id': target.id, 'name': target.username or target.phone},
        'messages': [
            {
                'id': m.id,
                'sender_id': m.sender_id,
                'receiver_id': m.receiver_id,
                'sender_name': m.sender.username or m.sender.phone,
                'text': m.text,
                'created_at': m.created_at.strftime('%Y-%m-%d %H:%M')
            } for m in msgs
        ]
    })

@app.route('/messages/send/<int:target_user_id>', methods=['POST'])
@login_required
def send_message(target_user_id):
    if target_user_id == current_user.id:
        return jsonify({'success': False, 'message': 'Нельзя отправить сообщение самому себе.'}), 400
    target = User.query.get_or_404(target_user_id)
    data = request.get_json() or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'success': False, 'message': 'Введите текст сообщения.'}), 400
    announcement_id = parse_int(data.get('announcement_id'), None)
    tenant_request_id = parse_int(data.get('tenant_request_id'), None)
    if announcement_id:
        ann = Announcement.query.get(announcement_id)
        if not ann or ann.user_id != target_user_id:
            return jsonify({'success': False, 'message': 'Неверное объявление.'}), 400
    if tenant_request_id:
        tr = TenantRequest.query.get(tenant_request_id)
        if not tr or tr.user_id != target_user_id:
            return jsonify({'success': False, 'message': 'Неверная анкета арендатора.'}), 400
    msg = Message(
        sender_id=current_user.id,
        receiver_id=target_user_id,
        announcement_id=announcement_id,
        tenant_request_id=tenant_request_id,
        text=text
    )
    db.session.add(msg)
    db.session.commit()
    db.session.add(Notification(
        user_id=target_user_id,
        type='message',
        title='Новое сообщение',
        message=f'Пользователь {current_user.username or current_user.phone} отправил вам сообщение.'
    ))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Сообщение отправлено.', 'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'), 'sender_id': msg.sender_id})

@app.route('/messages/conversations')
@login_required
def message_conversations():
    conversations = {}
    messages = Message.query.filter(
        or_(Message.sender_id == current_user.id, Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.desc()).all()
    for m in messages:
        if m.sender_id == current_user.id:
            partner = m.receiver
        else:
            partner = m.sender
        if not partner:
            continue
        if partner.id not in conversations:
            conversations[partner.id] = {
                'user_id': partner.id,
                'name': partner.username or partner.phone,
                'last_text': m.text,
                'last_date': m.created_at.strftime('%Y-%m-%d %H:%M')
            }
    return jsonify({'success': True, 'conversations': list(conversations.values())})

@app.route('/announcements/<int:announcement_id>/json')
@login_required
def announcement_json(announcement_id):
    ann = Announcement.query.get_or_404(announcement_id)
    if ann.user_id != current_user.id and not is_admin():
        return jsonify({'success': False, 'message': 'Нет доступа к объявлению.'}), 403
    imgs = [{'id': i.id, 'url': url_for('static', filename=i.image_path)} for i in ann.images]
    return jsonify({
        'success': True,
        'id': ann.id,
        'title': ann.title,
        'description': ann.description,
        'price': ann.price,
        'location': ann.location,
        'city': ann.city,
        'rooms': ann.rooms,
        'equipment': ann.equipment,
        'images': imgs
    })

@app.route('/announcements/<int:announcement_id>/images/<int:image_id>', methods=['DELETE'])
@login_required
def announcement_image_delete(announcement_id, image_id):
    ann = Announcement.query.get_or_404(announcement_id)
    img = AnnouncementImage.query.get_or_404(image_id)
    if img.announcement_id != ann.id:
        return jsonify({'success': False, 'message': 'Несоответствие объявления.'}), 400
    if ann.user_id != current_user.id and not is_admin():
        return jsonify({'success': False, 'message': 'Нет доступа.'}), 403
    file_path = os.path.join(STATIC_DIR, img.image_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
    db.session.delete(img)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Фото удалено.'})

@app.route('/announcements/<int:announcement_id>/edit', methods=['POST'])
@login_required
def announcement_edit(announcement_id):
    ann = Announcement.query.get_or_404(announcement_id)
    if ann.user_id != current_user.id and not is_admin():
        return jsonify({'message': 'Нет доступа.'}), 403
    title = (request.form.get('title') or '').strip()
    description = (request.form.get('description') or '').strip()
    price = (request.form.get('price') or '').strip()
    location = (request.form.get('location') or '').strip()
    city = (request.form.get('city') or '').strip()
    rooms = (request.form.get('rooms') or '').strip()
    equipment = (request.form.get('equipment') or '').strip()
    try:
        price_val = int(price) if price else ann.price
    except ValueError:
        return jsonify({'message': 'Цена должна быть числом.'}), 400

    ann.title = title or ann.title
    ann.description = description or ann.description
    ann.price = price_val
    ann.location = location or ann.location
    ann.city = city or ann.city
    ann.rooms = rooms or ann.rooms
    ann.equipment = equipment or ann.equipment
    ann.updated_at = datetime.utcnow()

    ann_dir = os.path.join(ANNOUNCEMENTS_DIR, str(ann.id))
    os.makedirs(ann_dir, exist_ok=True)

    cover = request.files.get('cover')
    if cover:
        c_name = secure_filename(cover.filename) or f'cover_{uuid.uuid4().hex}.jpg'
        c_ext = os.path.splitext(c_name)[1].lower() or '.jpg'
        new_cover = f'cover_{uuid.uuid4().hex}{c_ext}'
        cover.save(os.path.join(ann_dir, new_cover))
        ann.cover_image = f'uploads/announcements/{ann.id}/{new_cover}'

    gallery = request.files.getlist('gallery')
    for g in gallery:
        if not g:
            continue
        g_name = secure_filename(g.filename) or f'img_{uuid.uuid4().hex}.jpg'
        g_ext = os.path.splitext(g_name)[1].lower() or '.jpg'
        new_img = f'img_{uuid.uuid4().hex}{g_ext}'
        g.save(os.path.join(ann_dir, new_img))
        db.session.add(AnnouncementImage(announcement_id=ann.id, image_path=f'uploads/announcements/{ann.id}/{new_img}'))

    db.session.commit()
    return jsonify({'message': 'Изменения сохранены.'})

@app.route('/announcements/delete/<int:announcement_id>', methods=['DELETE'])
@login_required
def announcement_delete(announcement_id):
    ann = Announcement.query.get_or_404(announcement_id)
    if ann.user_id != current_user.id and not is_admin():
        return jsonify({'message': 'Нет доступа.'}), 403
    ann.status = 'removed_by_owner'
    db.session.commit()
    Favorite.query.filter_by(announcement_id=ann.id).delete()
    db.session.commit()
    return jsonify({'message': 'Объявление удалено.'})

@app.route('/favorites/toggle/<int:announcement_id>', methods=['POST'])
@login_required
def toggle_favorite(announcement_id):
    ann = Announcement.query.get_or_404(announcement_id)
    fav = Favorite.query.filter_by(user_id=current_user.id, announcement_id=announcement_id).first()
    active = True
    if fav:
        db.session.delete(fav)
        active = False
    else:
        db.session.add(Favorite(user_id=current_user.id, announcement_id=announcement_id))
    db.session.commit()
    return jsonify({'active': active})

@app.route('/tenants/create', methods=['POST'])
@login_required
def create_tenant_request():
    data = request.get_json() or {}
    tr = TenantRequest(
        user_id=current_user.id,
        city=(data.get('city') or '').strip(),
        rooms=(data.get('rooms') or '').strip(),
        budget=parse_int(data.get('budget'), 0) or 0,
        term=(data.get('term') or '').strip(),
        description=(data.get('description') or '').strip(),
        has_children=parse_bool(data.get('has_children')),
        has_pets=parse_bool(data.get('has_pets')),
        status='active'
    )
    db.session.add(tr)
    db.session.commit()
    db.session.add(Notification(user_id=current_user.id, type='system', title='Анкета опубликована', message='Ваша анкета арендатора опубликована.'))
    db.session.commit()
    return jsonify({'message': 'Анкета опубликована!', 'redirect_url': url_for('tenants')})

@app.route('/tenants/delete/<int:request_id>', methods=['DELETE'])
@login_required
def delete_tenant_request(request_id):
    tr = TenantRequest.query.get_or_404(request_id)
    if tr.user_id != current_user.id and not is_admin():
        return jsonify({'message': 'Нет доступа.'}), 403
    tr.status = 'removed_by_owner'
    db.session.commit()
    return jsonify({'message': 'Анкета удалена.'})

@app.route('/notifications')
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=items, active_page='notifications')

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    n = Notification.query.get_or_404(notification_id)
    if n.user_id != current_user.id:
        return jsonify({'message': 'Нет доступа.'}), 403
    n.is_read = True
    db.session.commit()
    return jsonify({'message': 'Уведомление прочитано.'})

@app.route('/admin')
@login_required
def admin_panel():
    if not is_admin():
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    anns = Announcement.query.order_by(Announcement.created_at.desc()).all()
    trs = TenantRequest.query.order_by(TenantRequest.created_at.desc()).all()
    backups = Backup.query.order_by(Backup.created_at.desc()).all()
    return render_template('admin.html', users=users, announcements=anns, tenant_requests=trs, backups=backups, active_page='admin')

@app.route('/admin/announcements/<int:announcement_id>/moderate', methods=['POST'])
@login_required
def moderate_announcement(announcement_id):
    if not is_admin():
        abort(403)
    ann = Announcement.query.get_or_404(announcement_id)
    data = request.get_json() or {}
    action = (data.get('action') or '').strip()
    reason = (data.get('reason') or '').strip()
    if action not in ('hide', 'remove', 'restore'):
        return jsonify({'message': 'Некорректное действие.'}), 400

    status_map = {'hide': 'hidden', 'remove': 'removed_by_moderator', 'restore': 'active'}
    ann.status = status_map[action]
    ann.moderation_reason = reason or None
    ann.moderated_by = current_user.id
    ann.moderated_at = datetime.utcnow()
    db.session.add(ModerationAction(admin_id=current_user.id, target_type='announcement', target_id=ann.id, action=action, reason=reason))
    db.session.commit()

    msg = {'hide': f'Ваше объявление "{ann.title}" скрыто модератором. Причина: {reason or "не указана"}.',
           'remove': f'Ваше объявление "{ann.title}" удалено модератором. Причина: {reason or "не указана"}.',
           'restore': f'Ваше объявление "{ann.title}" восстановлено модератором.'}[action]
    db.session.add(Notification(user_id=ann.user_id, type='moderation', title='Модерация объявления', message=msg))
    db.session.commit()

    if action in ('hide', 'remove'):
        Favorite.query.filter_by(announcement_id=ann.id).delete()
        db.session.commit()
    return jsonify({'message': 'Статус обновлён.'})

@app.route('/admin/tenants/<int:request_id>/moderate', methods=['POST'])
@login_required
def moderate_tenant_request(request_id):
    if not is_admin():
        abort(403)
    tr = TenantRequest.query.get_or_404(request_id)
    data = request.get_json() or {}
    action = (data.get('action') or '').strip()
    reason = (data.get('reason') or '').strip()
    if action not in ('hide', 'remove', 'restore'):
        return jsonify({'message': 'Некорректное действие.'}), 400
    status_map = {'hide': 'hidden', 'remove': 'removed_by_moderator', 'restore': 'active'}
    tr.status = status_map[action]
    tr.moderation_reason = reason or None
    tr.moderated_by = current_user.id
    tr.moderated_at = datetime.utcnow()
    db.session.add(ModerationAction(admin_id=current_user.id, target_type='tenant_request', target_id=tr.id, action=action, reason=reason))
    db.session.commit()

    msg = {'hide': 'Ваша анкета арендатора скрыта модератором. Причина: ' + (reason or 'не указана') + '.',
           'remove': 'Ваша анкета арендатора удалена модератором. Причина: ' + (reason or 'не указана') + '.',
           'restore': 'Ваша анкета арендатора восстановлена модератором.'}[action]
    db.session.add(Notification(user_id=tr.user_id, type='moderation', title='Модерация анкеты', message=msg))
    db.session.commit()
    return jsonify({'message': 'Статус обновлён.'})

@app.route('/admin/users/<int:user_id>/block', methods=['POST'])
@login_required
def block_user(user_id):
    if not is_admin():
        abort(403)
    u = User.query.get_or_404(user_id)
    data = request.get_json() or {}
    reason = (data.get('reason') or '').strip()
    u.is_blocked = True
    u.blocked_reason = reason or None
    u.blocked_at = datetime.utcnow()
    db.session.add(ModerationAction(admin_id=current_user.id, target_type='user', target_id=u.id, action='block', reason=reason))
    db.session.commit()
    db.session.add(Notification(user_id=u.id, type='security', title='Аккаунт заблокирован', message=f'Ваш аккаунт заблокирован. Причина: {reason or "не указана"}.'))
    db.session.commit()
    return jsonify({'message': 'Пользователь заблокирован.'})

@app.route('/admin/users/<int:user_id>/unblock', methods=['POST'])
@login_required
def unblock_user(user_id):
    if not is_admin():
        abort(403)
    u = User.query.get_or_404(user_id)
    u.is_blocked = False
    u.blocked_reason = None
    u.blocked_at = None
    db.session.add(ModerationAction(admin_id=current_user.id, target_type='user', target_id=u.id, action='unblock', reason=''))
    db.session.commit()
    db.session.add(Notification(user_id=u.id, type='security', title='Аккаунт разблокирован', message='Ваш аккаунт разблокирован.'))
    db.session.commit()
    return jsonify({'message': 'Пользователь разблокирован.'})

@app.route('/admin/backups/create', methods=['POST'])
@login_required
def create_backup():
    if not is_admin():
        abort(403)
    if is_sqlite():
        ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        db_file = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        db_path = os.path.join(BASE_DIR, db_file)
        if not os.path.exists(db_path):
            return jsonify({'message': 'Файл БД не найден.'}), 400
        backup_name = f'db_backup_{ts}.sqlite'
        backup_path = os.path.join(BACKUPS_DIR, backup_name)
        shutil.copyfile(db_path, backup_path)
        db.session.add(Backup(type='db', location=backup_path, status='success'))
        db.session.commit()
        return jsonify({'message': 'Бэкап создан.', 'file': backup_name})

    return jsonify({'message': 'Бэкап базы данных для MySQL нужно делать отдельно через mysqldump или хостинг.'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
