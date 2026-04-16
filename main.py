from flask import Flask, render_template, redirect, request, Response, abort, send_file
from data import db_session
from data.university import University
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from data.users import User
from forms.user import RegisterForm, LoginForm
import io
import csv
import os
from functools import wraps


TYPE_ICONS = {
    'federal': '🏛️', 'technical': '🔧', 'medical': '⚕️', 'pedagogical': '👨‍🏫',
    'humanitarian': '📚', 'economic': '💼', 'architecture': '🏗️', 'linguistic': '🔤',
    'social': '👥', 'veterinary': '🐾', 'food_tech': '🍕', 'technology': '⚙️',
    'art': '🎨', 'culture': '🎭'
}

TYPE_NAMES = {
    'federal': 'Федеральный университет', 'technical': 'Технический вуз',
    'medical': 'Медицинский университет', 'pedagogical': 'Педагогический университет',
    'humanitarian': 'Гуманитарный университет', 'economic': 'Экономический университет',
    'architecture': 'Архитектурный институт', 'linguistic': 'Лингвистический университет',
    'social': 'Социальный университет', 'veterinary': 'Ветеринарная академия',
    'food_tech': 'Пищевой университет', 'technology': 'Технологический университет',
    'art': 'Художественная академия', 'culture': 'Институт культуры'
}

app = Flask(__name__)
app.config['SECRET_KEY'] = '65432456uijhgfdsxcvbn'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.get(User, int(user_id))


db_session.global_init("db/university.db")


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


@app.errorhandler(401)
def unauthorized(e):
    return render_template("401.html"), 401
    

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.admin:
            abort(403)
        return func(*args, **kwargs)

    return wrapper


def user_ban(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.ban:
            abort(403)
        return func(*args, **kwargs)

    return wrapper


@app.route("/")
def landing():
    return render_template("landing.html", current_user=current_user)


@app.route("/map")
def index():
    db_sess = db_session.create_session()

    uni_type = request.args.get("type")
    only_favorites = request.args.get("fav")

    query = db_sess.query(University)

    if uni_type and uni_type != "all":
        query = query.filter(University.type == uni_type)

    universities = query.all()

    favorite_ids = []
    if current_user.is_authenticated:
        user = db_sess.get(User, current_user.id)
        favorite_ids = [u.id for u in user.favorite_universities]

        if only_favorites:
            universities = [u for u in universities if u.id in favorite_ids]

    all_places = []

    for uni in universities:
        if uni.content and ',' in uni.content:
            try:
                lat, lon = map(float, uni.content.split(','))
            except ValueError:
                continue

            all_places.append({
                'id': uni.id,
                'title': uni.title,
                'lat': lat,
                'lon': lon,
                'type': uni.type,
                'description': uni.description,
                'website': uni.website,
                'is_favorite': uni.id in favorite_ids
            })

    return render_template(
        "index.html",
        places=all_places,
        selected_type=uni_type or "all",
        only_favorites=only_favorites or "off",
        current_user=current_user
    )


@app.route('/toggle_favorite/<int:university_id>', methods=['POST'])
@login_required
def toggle_favorite(university_id):
    db_sess = db_session.create_session()
    user = db_sess.get(User, current_user.id)
    university = db_sess.get(University, university_id)

    if not university:
        return redirect(request.referrer or "/map")

    if university in user.favorite_universities:
        user.favorite_universities.remove(university)
    else:
        user.favorite_universities.append(university)

    db_sess.commit()
    return redirect(request.referrer or "/map")


@app.route('/favorites')
@login_required
def favorites():
    db_sess = db_session.create_session()
    user = db_sess.get(User, current_user.id)

    favorite_universities = []

    for uni in user.favorite_universities:
        if uni.content and ',' in uni.content:
            try:
                lat, lon = map(float, uni.content.split(','))
            except ValueError:
                continue

            favorite_universities.append({
                'id': uni.id,
                'title': uni.title,
                'lat': lat,
                'lon': lon,
                'type': uni.type,
                'website': uni.website,
                'description': uni.description,
                'is_favorite': True,
                'type_icon': TYPE_ICONS.get(uni.type, '🎓'),
                'type_name': TYPE_NAMES.get(uni.type, 'Университет')
            })

    return render_template("favorites.html", favorites=favorite_universities)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db_sess = db_session.create_session()
    user = db_sess.get(User, current_user.id)

    favorite_count = len(user.favorite_universities)

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            abort(400, "Файл не выбран")
        file.filename = "universities.csv"
        os.makedirs(f"universities", exist_ok=True)
        file.save(os.path.join(f"universities", file.filename))
        with open('universities/universities.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=',')
            h = next(reader)
            for row in reader:
                universities = University(
                    title=row[1],
                    content=row[2],
                    type=row[3],
                    website=row[4],
                    description=row[5]
                )
                db_sess.add(universities)
                db_sess.commit()
        return redirect('/profile')

    return render_template(
        "profile.html",
        user=user,
        favorite_count=favorite_count
    )


@app.route('/admin/users', methods=["GET", "POST"])
@login_required
@admin_required
@user_ban
def admin_users():
    db_sess = db_session.create_session()
    users = db_sess.query(User)
    if request.method == "POST":
        for user in users:
            admin_value = request.form.get(f"admin_{user.id}")
            ban_value = request.form.get(f"ban_{user.id}")
            if admin_value == "admin":
                user.admin = 1
            if admin_value == "user":
                user.admin = 0
            if ban_value == "banned":
                user.ban = 1
            if ban_value == "unbanned":
                user.ban = 0
        db_sess.commit()
        return redirect('/admin/users')
    return render_template("admin_users.html", users=users)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template(
                'register.html',
                form=form,
                message="Пароли не совпадают"
            )

        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template(
                'register.html',
                form=form,
                message="Такой пользователь уже есть"
            )

        user = User(
            name=form.name.data,
            email=form.email.data,
            about=form.about.data
        )
        user.set_password(form.password.data)

        db_sess.add(user)
        db_sess.commit()

        return redirect('/login')

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/map")

        return render_template(
            'login.html',
            message="Неправильный логин или пароль",
            form=form
        )

    return render_template('login.html', form=form)


@app.route("/export")
@login_required
def export():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['ID', 'TITLE', 'CONTENT', 'TYPE', 'WEBSITE', 'DESCRIPTION'])

    db_sess = db_session.create_session()
    universities = db_sess.query(University).all()

    for university in universities:
        writer.writerow([
            university.id,
            university.title,
            university.content,
            university.type,
            university.website,
            university.description
        ])

    output.seek(0)

    return Response(output, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=universities.csv'})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/download-db')
def download_db():
    return send_file('db/university.db', as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)