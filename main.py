from flask import Flask, render_template, redirect, jsonify, request
from data import db_session
from data.university import University
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from data.users import User
from forms.user import RegisterForm, LoginForm

app = Flask(__name__)
app.config['SECRET_KEY'] = '65432456uijhgfdsxcvbn'

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.get(User, user_id)


db_session.global_init("db/university.db")


@app.route("/")
def landing():
    """Главная страница-лендинг"""
    return render_template("landing.html")


@app.route("/map")
def index():
    """Основная карта с университетами"""
    try:
        db_sess = db_session.create_session()
        universities = db_sess.query(University).all()

        all_places = []
        favorite_ids = []

        # Получаем ID избранных университетов для текущего пользователя
        if current_user.is_authenticated:
            user = db_sess.get(User, current_user.id)
            favorite_ids = [uni.id for uni in user.favorite_universities]

        for uni in universities:
            if uni.content and ',' in uni.content:
                try:
                    coords = uni.content.split(',')
                    lat = float(coords[0].strip())
                    lon = float(coords[1].strip())

                    is_favorite = uni.id in favorite_ids

                    all_places.append({
                        'id': uni.id,
                        'title': uni.title,
                        'lat': lat,
                        'lon': lon,
                        'type': uni.type,
                        'is_favorite': is_favorite,  # Добавляем информацию об избранном
                        'website': uni.website,
                        'description': uni.description
                    })
                except (ValueError, IndexError) as e:
                    print(f"Ошибка обработки координат для {uni.title}: {e}")
                    continue

        print(f"✅ Загружено университетов из базы: {len(all_places)}")
        return render_template("index.html", places=all_places)

    except Exception as e:
        print(f"❌ Ошибка в функции index: {e}")
        temp_places = [
            {'id': 1, 'title': 'МГУ им. Ломоносова', 'lat': 55.703990, 'lon': 37.528268, 'type': 'federal',
             'user_name': 'Система', 'is_owner': False, 'is_favorite': False},
            {'id': 2, 'title': 'МФТИ', 'lat': 55.929592, 'lon': 37.517475, 'type': 'technical', 'user_name': 'Система',
             'is_owner': False, 'is_favorite': False},
        ]
        return render_template("index.html", places=temp_places)


@app.route('/favorites')
@login_required
def favorites():
    """Страница избранных университетов"""
    db_sess = db_session.create_session()
    user = db_sess.get(User, current_user.id)

    favorite_universities = []
    for uni in user.favorite_universities:
        if uni.content and ',' in uni.content:
            try:
                coords = uni.content.split(',')
                lat = float(coords[0].strip())
                lon = float(coords[1].strip())

                favorite_universities.append({
                    'id': uni.id,
                    'title': uni.title,
                    'lat': lat,
                    'lon': lon,
                    'type': uni.type,
                    'website': uni.website,
                    'description': uni.description
                })
            except (ValueError, IndexError) as e:
                continue

    return render_template("favorites.html", favorites=favorite_universities)


@app.route('/toggle_favorite/<int:university_id>', methods=['POST'])
@login_required
def toggle_favorite(university_id):
    """Добавить/удалить университет из избранного"""
    try:
        db_sess = db_session.create_session()
        user = db_sess.get(User, current_user.id)
        university = db_sess.get(University, university_id)

        if not university:
            return jsonify({'success': False, 'error': 'Университет не найден'})

        if university in user.favorite_universities:
            # Удаляем из избранного
            user.favorite_universities.remove(university)
            action = 'removed'
        else:
            # Добавляем в избранное
            user.favorite_universities.append(university)
            action = 'added'

        db_sess.commit()

        return jsonify({
            'success': True,
            'action': action,
            'is_favorite': action == 'added'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/profile')
@login_required
def profile():
    """Личный кабинет пользователя"""
    db_sess = db_session.create_session()
    user = db_sess.get(User, current_user.id)

    favorite_count = len(user.favorite_universities)

    return render_template("profile.html",
                           user=user,
                           favorite_count=favorite_count)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация пользователя"""
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form, message="Пароли не совпадают")

        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация',
                                   form=form, message="Такой пользователь уже есть")

        user = User(
            name=form.name.data,
            email=form.email.data,
            about=form.about.data
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()

        return redirect('/login')

    return render_template('register.html', title='Регистрация', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Авторизация пользователя"""
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/map")

        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)

    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    return redirect("/")


if __name__ == '__main__':
    app.run(port=8025, host='127.0.0.1')