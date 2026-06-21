from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random
import string

app = Flask(__name__)
app.secret_key = 'verander-dit-naar-iets-geheims'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flowr.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ─────────────────────────────────────────
# DATABASE MODELLEN (= tabellen)
# ─────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    duration = db.Column(db.Integer)           # in seconden
    description = db.Column(db.Text)
    rating = db.Column(db.Float)
    genre = db.Column(db.String(100))
    director = db.Column(db.String(100))
    release_year = db.Column(db.Integer)
    thumbnail_url = db.Column(db.String(300))


class Room(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    room_code = db.Column(db.String(8), unique=True, nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'))
    playback_position = db.Column(db.Integer, default=0)  # in seconden
    is_playing = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    host = db.relationship('User', backref='hosted_rooms')
    movie = db.relationship('Movie', backref='rooms')


class RoomMember(db.Model):
    __tablename__ = 'room_members'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    room = db.relationship('Room', backref='members')
    user = db.relationship('User', backref='room_memberships')


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='messages')
    room = db.relationship('Room', backref='messages')


class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    rating = db.Column(db.Integer)   # 1 t/m 10
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='reviews')
    movie = db.relationship('Movie', backref='reviews')


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────
# HULPFUNCTIES
# ─────────────────────────────────────────

def generate_room_code():
    """Genereert een unieke 6-letterige kamercode, bijv. 'XK92BT'"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Room.query.filter_by(room_code=code).first():
            return code

def logged_in_user():
    """Geeft het User-object terug van de ingelogde gebruiker, of None"""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route('/')
def index():
    movies = Movie.query.all()
    user = logged_in_user()
    return render_template('index.html', movies=movies, user=user)


# --- Authenticatie ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check of gebruiker al bestaat
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='E-mail al in gebruik')

        hashed = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed)
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        return render_template('login.html', error='Verkeerde gegevens')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


# --- Films ---

@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    reviews = Review.query.filter_by(movie_id=movie_id).all()
    user = logged_in_user()
    return render_template('movie_detail.html', movie=movie, reviews=reviews, user=user)


@app.route('/movie/<int:movie_id>/review', methods=['POST'])
def add_review(movie_id):
    user = logged_in_user()
    if not user:
        return redirect(url_for('login'))

    rating = int(request.form['rating'])
    body = request.form['body']
    review = Review(user_id=user.id, movie_id=movie_id, rating=rating, body=body)
    db.session.add(review)
    db.session.commit()
    return redirect(url_for('movie_detail', movie_id=movie_id))


# --- Kamers ---

@app.route('/rooms/create', methods=['GET', 'POST'])
def create_room():
    user = logged_in_user()
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        movie_id = request.form.get('movie_id')
        code = generate_room_code()
        room = Room(name=name, room_code=code, host_id=user.id, movie_id=movie_id)
        db.session.add(room)
        db.session.commit()

        # Voeg de host ook toe als lid
        member = RoomMember(room_id=room.id, user_id=user.id)
        db.session.add(member)
        db.session.commit()

        return redirect(url_for('room', room_code=code))

    movies = Movie.query.all()
    return render_template('create_room.html', movies=movies, user=user)


@app.route('/rooms/join', methods=['GET', 'POST'])
def join_room():
    user = logged_in_user()
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form['room_code'].upper()
        room = Room.query.filter_by(room_code=code).first()
        if not room:
            return render_template('join_room.html', error='Kamer niet gevonden', user=user)

        # Voeg toe als lid als nog niet lid
        already_member = RoomMember.query.filter_by(room_id=room.id, user_id=user.id).first()
        if not already_member:
            member = RoomMember(room_id=room.id, user_id=user.id)
            db.session.add(member)
            db.session.commit()

        return redirect(url_for('room', room_code=code))

    return render_template('join_room.html', user=user)


@app.route('/room/<room_code>')
def room(room_code):
    user = logged_in_user()
    if not user:
        return redirect(url_for('login'))

    room = Room.query.filter_by(room_code=room_code).first_or_404()
    messages = Message.query.filter_by(room_id=room.id).order_by(Message.sent_at).all()
    is_host = (room.host_id == user.id)

    return render_template('room.html', room=room, messages=messages, user=user, is_host=is_host)


# --- Chat (via polling) ---

@app.route('/room/<room_code>/send', methods=['POST'])
def send_message(room_code):
    user = logged_in_user()
    if not user:
        return jsonify({'error': 'Niet ingelogd'}), 401

    room = Room.query.filter_by(room_code=room_code).first_or_404()
    content = request.json.get('content', '').strip()
    if content:
        msg = Message(room_id=room.id, user_id=user.id, content=content)
        db.session.add(msg)
        db.session.commit()

    return jsonify({'status': 'ok'})


@app.route('/room/<room_code>/messages')
def get_messages(room_code):
    """JavaScript vraagt dit elke paar seconden op (polling)"""
    room = Room.query.filter_by(room_code=room_code).first_or_404()
    messages = Message.query.filter_by(room_id=room.id).order_by(Message.sent_at).all()
    return jsonify([{
        'username': m.user.username,
        'content': m.content,
        'sent_at': m.sent_at.strftime('%H:%M')
    } for m in messages])


# --- Afspeelsynchronisatie ---

@app.route('/room/<room_code>/playback', methods=['POST'])
def update_playback(room_code):
    """Alleen de host mag dit aanroepen"""
    user = logged_in_user()
    room = Room.query.filter_by(room_code=room_code).first_or_404()
    if room.host_id != user.id:
        return jsonify({'error': 'Geen toegang'}), 403

    data = request.json
    room.playback_position = data.get('position', room.playback_position)
    room.is_playing = data.get('is_playing', room.is_playing)
    db.session.commit()
    return jsonify({'status': 'ok'})


@app.route('/room/<room_code>/playback')
def get_playback(room_code):
    """Alle kijkers vragen dit op om gesynchroniseerd te blijven"""
    room = Room.query.filter_by(room_code=room_code).first_or_404()
    return jsonify({
        'position': room.playback_position,
        'is_playing': room.is_playing
    })


# --- Contact ---

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    user = logged_in_user()
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        contact_msg = ContactMessage(name=name, email=email, message=message)
        db.session.add(contact_msg)
        db.session.commit()
        return render_template('contact.html', success=True, user=user)

    return render_template('contact.html', user=user)


# ─────────────────────────────────────────
# DATABASE AANMAKEN + APP STARTEN
# ─────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()   # Maakt alle tabellen aan als ze nog niet bestaan
    app.run(debug=True)
