import json
import os
import re
import secrets
import string
from datetime import datetime
from functools import wraps
from threading import Lock

from flask import Flask, flash, redirect, render_template, session, url_for
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret-development-key-2026"
app.config["WTF_CSRF_ENABLED"] = True

DATA_FILE = "users.json"
file_lock = Lock()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_data():
    with file_lock:
        if not os.path.exists(DATA_FILE):
            return {"users": []}
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data.get("users"), list) else {"users": []}
        except Exception:
            return {"users": []}


def save_data(data):
    with file_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def normalize_username(username):
    return username.strip().lower()


def get_user_by_username(username):
    norm = normalize_username(username)
    data = load_data()
    for user in data["users"]:
        if normalize_username(user["username"]) == norm:
            return user
    return None


def check_password_strength(password: str, username: str = "") -> list:
    errors = []
    if len(password) < 8:
        errors.append("Пароль должен быть не менее 8 символов.")
    if not re.search(r"[A-ZА-Я]", password):
        errors.append("Пароль должен содержать хотя бы одну заглавную букву.")
    if not re.search(r"[a-zа-я]", password):
        errors.append("Пароль должен содержать хотя бы одну строчную букву.")
    if not re.search(r"\d", password):
        errors.append("Пароль должен содержать хотя бы одну цифру.")
    if not re.search(r"[^\w\s]", password):
        errors.append("Пароль должен содержать хотя бы один специальный символ (!@#$ и т.д.).")
    if " " in password:
        errors.append("Пароль не должен содержать пробелы.")
    if username and normalize_username(username) in password.lower():
        errors.append("Пароль не должен содержать имя пользователя.")

    return errors


def generate_secure_default_password():
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "AdminStart1!" + "".join(secrets.choice(chars) for _ in range(12))


def init_first_admin():
    data = load_data()
    if data["users"]:
        return

    default_pwd = generate_secure_default_password()
    admin_user = {
        "username": "admin",
        "password_hash": generate_password_hash(default_pwd),
        "is_admin": True,
        "registered_at": now_str(),
        "last_login_at": None,
    }
    data["users"].append(admin_user)
    save_data(data)

    print("\n" + "="*70)
    print("ПЕРВЫЙ АДМИНИСТРАТОР УСПЕШНО СОЗДАН!")
    print(f"Логин:      admin")
    print(f"Пароль:     {default_pwd}")
    print("Сохраните эти данные! Они показываются только один раз.")
    print("="*70 + "\n")


def update_last_login(username):
    data = load_data()
    norm = normalize_username(username)
    for user in data["users"]:
        if normalize_username(user["username"]) == norm:
            user["last_login_at"] = now_str()
            break
    save_data(data)


def current_user():
    username = session.get("username")
    return get_user_by_username(username) if username else None


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Пожалуйста, войдите в систему.", "warning")
            return redirect(url_for("login"))
        if not user.get("is_admin"):
            flash("У вас недостаточно прав для доступа к этой странице.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


class LoginForm(FlaskForm):
    username = StringField("Имя пользователя", validators=[
        DataRequired("Введите имя пользователя"),
        Length(min=3, max=40)
    ])
    password = PasswordField("Пароль", validators=[DataRequired("Введите пароль")])
    submit = SubmitField("Войти")


class CreateUserForm(FlaskForm):
    username = StringField("Имя пользователя", validators=[
        DataRequired("Обязательное поле"),
        Length(min=3, max=40),
        Regexp(r"^[A-Za-z0-9_.-]+$", message="Разрешены только буквы, цифры, _, . и -")
    ])
    password = PasswordField("Пароль", validators=[DataRequired("Обязательное поле")])
    confirm_password = PasswordField("Повторите пароль", validators=[
        DataRequired(),
        EqualTo("password", message="Пароли не совпадают")
    ])
    is_admin = BooleanField("Назначить администратором")
    submit = SubmitField("Создать пользователя")




@app.route("/")
def index():
    if current_user() and current_user().get("is_admin"):
        return redirect(url_for("create_user"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = get_user_by_username(form.username.data)
        if user and check_password_hash(user["password_hash"], form.password.data):
            session.clear()
            session["username"] = user["username"]
            update_last_login(user["username"])
            flash("Вы успешно авторизовались!", "success")
            return redirect(url_for("create_user"))
        else:
            flash("Неверное имя пользователя или пароль.", "danger")

    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из аккаунта.", "success")
    return redirect(url_for("login"))


@app.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_user():
    form = CreateUserForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        if get_user_by_username(username):
            flash("Пользователь с таким именем уже существует.", "danger")
        else:
            pwd_errors = check_password_strength(password, username)
            if pwd_errors:
                for err in pwd_errors:
                    flash(err, "danger")
            else:
                data = load_data()
                new_user = {
                    "username": username,
                    "password_hash": generate_password_hash(password),
                    "is_admin": bool(form.is_admin.data),
                    "registered_at": now_str(),
                    "last_login_at": None,
                }
                data["users"].append(new_user)
                save_data(data)
                flash(f"Пользователь {username} успешно создан!", "success")
                return redirect(url_for("create_user"))

    data = load_data()
    all_users = sorted(data["users"], key=lambda x: x["username"].lower())

    return render_template(
        "create_user.html",
        form=form,
        users=all_users,
        current_user=current_user()
    )


if __name__ == "__main__":
    init_first_admin()
    app.run(debug=True)