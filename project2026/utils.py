import os
import secrets
import string
from functools import wraps

from flask import flash, redirect, session, url_for, current_app
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from extensions import db


def active_user():
    from models import Account
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(Account, user_id)


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not active_user():
            flash("Сначала авторизуйтесь.", "warning")
            return redirect(url_for("routes.sign_in"))
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = active_user()
        if not user:
            flash("Сначала авторизуйтесь.", "warning")
            return redirect(url_for("routes.sign_in"))
        if not user.is_admin:
            flash("Доступ запрещён.", "danger")
            return redirect(url_for("routes.task_list"))
        return fn(*args, **kwargs)
    return wrapper


def save_file(file_storage):
    if not file_storage or file_storage.filename == "":
        return None, None
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    unique_name = f"{secrets.token_hex(16)}.{ext}" if ext else secrets.token_hex(16)
    file_storage.save(os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name))
    return unique_name, original


def make_default_password() -> str:
    alphabet = string.ascii_letters + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"Aa1!{suffix}"


def bootstrap_admin():
    from models import Account
    admin = Account.query.filter_by(username="admin").first()
    if admin:
        return
    pwd = make_default_password()
    root = Account(username="admin", password_hash=generate_password_hash(pwd), is_admin=True)
    db.session.add(root)
    db.session.commit()
    print("=" * 60)
    print("Создан стартовый администратор:")
    print("username: admin")
    print(f"password: {pwd}")
    print("=" * 60)


def build_task_query(user):
    """Return base query for tasks visible to the user."""
    from models import Task
    if user:
        q = Task.query.filter(
            db.or_(Task.is_private == False, Task.author_id == user.id)
        )
    else:
        q = Task.query.filter_by(is_private=False)
    return q
