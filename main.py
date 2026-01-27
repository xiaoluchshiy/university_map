from flask import Flask, render_template, redirect, request
from data import db_session
from data.university import University
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from data.users import User
from forms.user import RegisterForm, LoginForm


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


@app.route("/")
def landing():
    return render_template("landing.html")


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


@app.route('/profile')
@login_required
def profile():
    db_sess = db_session.create_session()
    user = db_sess.get(User, current_user.id)

    favorite_count = len(user.favorite_universities)

    return render_template(
        "profile.html",
        user=user,
        favorite_count=favorite_count
    )


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


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
