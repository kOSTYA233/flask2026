from datetime import datetime, timezone
from functools import wraps
import secrets
import string

from flask import (
    Flask, flash, redirect, render_template, 
    session, url_for, abort, request
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import (
    BooleanField, PasswordField, StringField, 
    SubmitField, TextAreaField
)
from wtforms.validators import DataRequired, EqualTo, Length, Regexp


app = Flask(__name__)
app.config.update(
    SECRET_KEY=secrets.token_hex(32),
    SQLALCHEMY_DATABASE_URI="sqlite:///blog.db",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    WTF_CSRF_ENABLED=True
)

db = SQLAlchemy(app)


class Account(db.Model):
    __tablename__ = "users"
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
    
    entries = db.relationship("Entry", backref="author", lazy=True)


class Entry(db.Model):
    __tablename__ = "posts"
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_private = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)


class SignInForm(FlaskForm):
    username = StringField(
        "Логин",
        validators=[
            DataRequired(message="Введите логин."),
            Length(min=3, max=50, message="Логин должен быть длиной от 3 до 50 символов."),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[DataRequired(message="Введите пароль.")],
    )
    submit = SubmitField("Войти")


class ArticleForm(FlaskForm):
    title = StringField(
        "Заголовок",
        validators=[
            DataRequired(message="Введите заголовок поста."),
            Length(min=3, max=200, message="Заголовок должен быть длиной от 3 до 200 символов."),
        ],
    )
    content = TextAreaField(
        "Текст поста",
        validators=[
            DataRequired(message="Введите текст поста."),
            Length(min=5, message="Текст поста должен содержать минимум 5 символов."),
        ],
    )
    is_private = BooleanField("Приватный пост (скрыт от анонимных пользователей)")
    submit = SubmitField("Сохранить")


class NewAccountForm(FlaskForm):
    username = StringField(
        "Логин нового пользователя",
        validators=[
            DataRequired(message="Введите username."),
            Length(min=3, max=50, message="Логин должен быть длиной от 3 до 50 символов."),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message="Логин может содержать только буквы, цифры, _, . и -",
            ),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(message="Введите пароль."),
            Length(min=6, message="Пароль должен содержать минимум 6 символов."),
        ],
    )
    confirm_password = PasswordField(
        "Подтверждение пароля",
        validators=[
            DataRequired(message="Подтвердите пароль."),
            EqualTo("password", message="Пароли не совпадают."),
        ],
    )
    is_admin = BooleanField("Выдать права администратора")
    submit = SubmitField("Создать пользователя")


def active_user():
    """Возвращает текущего авторизованного пользователя или None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(Account, user_id)


def require_login(fn):
    """Декоратор для маршрутов, требующих авторизации."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = active_user()
        if not user:
            flash("Сначала авторизуйтесь.", "warning")
            return redirect(url_for("sign_in"))
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    """Декоратор для маршрутов, доступных только администраторам."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = active_user()
        if not user:
            flash("Сначала авторизуйтесь.", "warning")
            return redirect(url_for("sign_in"))
        if not user.is_admin:
            flash("Доступ запрещён. Нужны права администратора.", "danger")
            return redirect(url_for("articles"))
        return fn(*args, **kwargs)
    return wrapper


def make_default_password() -> str:
    """Генерирует случайный пароль для администратора."""
    alphabet = string.ascii_letters + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"Aa1!{suffix}"


def bootstrap_admin():
    """Создаёт учётную запись администратора при первом запуске."""
    admin = Account.query.filter_by(username="admin").first()
    if admin:
        return

    init_pwd = make_default_password()
    root = Account(
        username="admin",
        password_hash=generate_password_hash(init_pwd),
        is_admin=True,
    )
    db.session.add(root)
    db.session.commit()

    print("=" * 60)
    print("Создан стартовый администратор:")
    print("username: admin")
    print(f"password: {init_pwd}")
    print("Сохрани этот пароль и затем войди в систему.")
    print("=" * 60)


@app.route("/")
def home():
    return redirect(url_for("articles"))


@app.route("/login", methods=["GET", "POST"])
def sign_in():
    if active_user():
        return redirect(url_for("articles"))

    form = SignInForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        user = Account.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Неверный логин или пароль.", "danger")
        else:
            session.clear()
            session["user_id"] = user.id
            flash("Вы успешно вошли в систему.", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("articles"))

    return render_template("login.html", form=form, current_user=active_user())


@app.route("/logout")
def sign_out():
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("articles"))


@app.route("/posts")
def articles():
    user = active_user()

    if user:
        entry_list = Entry.query.order_by(Entry.created_at.desc()).all()
    else:
        entry_list = (
            Entry.query
            .filter_by(is_private=False)
            .order_by(Entry.created_at.desc())
            .all()
        )

    return render_template("posts.html", posts=entry_list, current_user=user)


@app.route("/posts/create", methods=["GET", "POST"])
@require_login
def new_article():
    form = ArticleForm()
    user = active_user()

    if form.validate_on_submit():
        entry = Entry(
            title=form.title.data.strip(),
            content=form.content.data.strip(),
            is_private=bool(form.is_private.data),
            author_id=user.id,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Пост успешно создан.", "success")
        return redirect(url_for("articles"))

    return render_template(
        "post_form.html",
        form=form,
        form_title="Создание поста",
        current_user=user,
    )


@app.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@require_login
def modify_article(post_id):
    user = active_user()
    entry = db.session.get(Entry, post_id)

    if not entry:
        abort(404)

    if entry.author_id != user.id:
        flash("Вы можете редактировать только свои записи.", "danger")
        return redirect(url_for("articles"))

    form = ArticleForm(obj=entry)

    if form.validate_on_submit():
        entry.title = form.title.data.strip()
        entry.content = form.content.data.strip()
        entry.is_private = bool(form.is_private.data)
        db.session.commit()
        flash("Пост успешно обновлён.", "success")
        return redirect(url_for("articles"))

    return render_template(
        "post_form.html",
        form=form,
        form_title="Редактирование поста",
        current_user=user,
    )


@app.route("/users/create", methods=["GET", "POST"])
@require_admin
def register_account():
    form = NewAccountForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        is_admin = bool(form.is_admin.data)

        existing = Account.query.filter_by(username=username).first()
        if existing:
            flash("Пользователь с таким username уже существует.", "danger")
        else:
            user = Account(
                username=username,
                password_hash=generate_password_hash(password),
                is_admin=is_admin,
            )
            db.session.add(user)
            db.session.commit()
            flash(f"Пользователь '{username}' успешно создан.", "success")
            return redirect(url_for("register_account"))

    users = Account.query.order_by(Account.username.asc()).all()

    return render_template(
        "create_user.html",
        form=form,
        users=users,
        current_user=active_user(),
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        bootstrap_admin()

    app.run(debug=True)