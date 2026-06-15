from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint, abort, flash, redirect, render_template,
    request, session, url_for, send_from_directory, current_app,
)
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from forms import SignInForm, NewAccountForm, TaskForm, StatusForm, CommentForm
from models import Account, Task, Comment
from utils import active_user, require_login, require_admin, save_file, build_task_query

bp = Blueprint("routes", __name__)


@bp.route("/")
def home():
    return redirect(url_for("routes.task_list"))


@bp.route("/login", methods=["GET", "POST"])
def sign_in():
    if active_user():
        return redirect(url_for("routes.task_list"))
    form = SignInForm()
    if form.validate_on_submit():
        user = Account.query.filter_by(username=form.username.data.strip()).first()
        if not user or not check_password_hash(user.password_hash, form.password.data):
            flash("Неверный логин или пароль.", "danger")
        else:
            session.clear()
            session["user_id"] = user.id
            flash("Добро пожаловать!", "success")
            return redirect(request.args.get("next") or url_for("routes.task_list"))
    return render_template("login.html", form=form, current_user=active_user())


@bp.route("/logout")
def sign_out():
    session.clear()
    flash("Вы вышли из системы.", "success")
    return redirect(url_for("routes.task_list"))


#Task list

@bp.route("/tasks")
def task_list():
    user = active_user()
    q = build_task_query(user)

    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    search = request.args.get("search", "").strip()
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    sort = request.args.get("sort", "created_desc")

    if status_filter:
        q = q.filter(Task.status == status_filter)
    if priority_filter:
        q = q.filter(Task.priority == priority_filter)
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(Task.title.ilike(like), Task.description.ilike(like)))
    if date_from:
        try:
            q = q.filter(Task.deadline >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(Task.deadline <= datetime.strptime(date_to, "%Y-%m-%d"))
        except ValueError:
            pass

    if sort == "created_asc":
        q = q.order_by(Task.created_at.asc())
    elif sort == "deadline_asc":
        q = q.order_by(Task.deadline.asc().nullslast())
    elif sort == "deadline_desc":
        q = q.order_by(Task.deadline.desc().nullslast())
    elif sort == "priority":
        priority_order = db.case({"high": 0, "medium": 1, "low": 2}, value=Task.priority)
        q = q.order_by(priority_order)
    elif sort == "status":
        status_order = db.case({"new": 0, "in_progress": 1, "done": 2, "archived": 3}, value=Task.status)
        q = q.order_by(status_order)
    else:
        q = q.order_by(Task.created_at.desc())

    tasks = q.all()
    return render_template(
        "tasks.html",
        tasks=tasks,
        current_user=user,
        status_filter=status_filter,
        priority_filter=priority_filter,
        search=search,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
    )


#My tasks

@bp.route("/my-tasks")
@require_login
def my_tasks():
    user = active_user()
    q = Task.query.filter_by(author_id=user.id)

    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")
    search = request.args.get("search", "").strip()
    sort = request.args.get("sort", "created_desc")

    if status_filter:
        q = q.filter(Task.status == status_filter)
    if priority_filter:
        q = q.filter(Task.priority == priority_filter)
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(Task.title.ilike(like), Task.description.ilike(like)))

    if sort == "created_asc":
        q = q.order_by(Task.created_at.asc())
    elif sort == "deadline_asc":
        q = q.order_by(Task.deadline.asc().nullslast())
    elif sort == "deadline_desc":
        q = q.order_by(Task.deadline.desc().nullslast())
    elif sort == "priority":
        priority_order = db.case({"high": 0, "medium": 1, "low": 2}, value=Task.priority)
        q = q.order_by(priority_order)
    elif sort == "status":
        status_order = db.case({"new": 0, "in_progress": 1, "done": 2, "archived": 3}, value=Task.status)
        q = q.order_by(status_order)
    else:
        q = q.order_by(Task.created_at.desc())

    tasks = q.all()
    return render_template(
        "my_tasks.html",
        tasks=tasks,
        current_user=user,
        status_filter=status_filter,
        priority_filter=priority_filter,
        search=search,
        sort=sort,
    )


#Task detail
@bp.route("/tasks/<int:task_id>", methods=["GET", "POST"])
def task_detail(task_id):
    user = active_user()
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)
    if task.is_private and (not user or user.id != task.author_id):
        abort(403)

    comment_form = CommentForm()
    status_form = StatusForm(obj=task)

    if comment_form.validate_on_submit() and comment_form.text.data and user:
        fname, orig = save_file(request.files.get("attachment"))
        comment = Comment(
            text=comment_form.text.data.strip(),
            filename=fname,
            original_filename=orig,
            author_id=user.id,
            task_id=task.id,
        )
        db.session.add(comment)
        db.session.commit()
        flash("Комментарий добавлен.", "success")
        return redirect(url_for("routes.task_detail", task_id=task.id))

    return render_template(
        "task_detail.html",
        task=task,
        comment_form=comment_form,
        status_form=status_form,
        current_user=user,
    )


#Change status

@bp.route("/tasks/<int:task_id>/status", methods=["POST"])
@require_login
def change_status(task_id):
    user = active_user()
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)
    if task.is_private and user.id != task.author_id:
        abort(403)

    new_status = request.form.get("status")
    allowed = {"new", "in_progress", "done", "archived"}
    if new_status not in allowed:
        flash("Недопустимый статус.", "danger")
        return redirect(url_for("routes.task_detail", task_id=task_id))

    if new_status == "archived" and user.id != task.author_id:
        flash("Только автор может отправить задачу в архив.", "danger")
        return redirect(url_for("routes.task_detail", task_id=task_id))

    task.status = new_status
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f"Статус изменён: {task.status_label}", "success")
    return redirect(url_for("routes.task_detail", task_id=task_id))


#Create task

@bp.route("/tasks/create", methods=["GET", "POST"])
@require_login
def create_task():
    user = active_user()
    form = TaskForm()
    if form.validate_on_submit():
        fname, orig = save_file(request.files.get("attachment"))
        deadline = None
        if form.deadline.data:
            deadline = datetime.combine(form.deadline.data, datetime.min.time())
        task = Task(
            title=form.title.data.strip(),
            description=form.description.data.strip(),
            priority=form.priority.data,
            is_private=bool(form.is_private.data),
            deadline=deadline,
            filename=fname,
            original_filename=orig,
            author_id=user.id,
        )
        db.session.add(task)
        db.session.commit()
        flash("Задача создана.", "success")
        return redirect(url_for("routes.task_detail", task_id=task.id))
    return render_template("task_form.html", form=form, form_title="Новая задача", current_user=user)


#Edit task

@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@require_login
def edit_task(task_id):
    user = active_user()
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)
    if task.author_id != user.id:
        flash("Вы можете редактировать только свои задачи.", "danger")
        return redirect(url_for("routes.task_list"))

    form = TaskForm(obj=task)
    if form.validate_on_submit():
        task.title = form.title.data.strip()
        task.description = form.description.data.strip()
        task.priority = form.priority.data
        task.is_private = bool(form.is_private.data)
        if form.deadline.data:
            task.deadline = datetime.combine(form.deadline.data, datetime.min.time())
        else:
            task.deadline = None
        new_file, new_orig = save_file(request.files.get("attachment"))
        if new_file:
            task.filename = new_file
            task.original_filename = new_orig
        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Задача обновлена.", "success")
        return redirect(url_for("routes.task_detail", task_id=task.id))

    if task.deadline and not form.deadline.data:
        form.deadline.data = task.deadline.date()

    return render_template(
        "task_form.html", form=form, form_title="Редактирование задачи",
        current_user=user, task=task,
    )


#Download

@bp.route("/uploads/<path:filename>")
def download_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


#Statistics 

@bp.route("/stats")
@require_login
def statistics():
    user = active_user()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    base = Task.query if user.is_admin else Task.query.filter_by(author_id=user.id)

    done_week = base.filter(Task.status == "done", Task.updated_at >= week_ago).count()
    done_month = base.filter(Task.status == "done", Task.updated_at >= month_ago).count()
    total = base.count()
    by_status = {s: base.filter(Task.status == s).count() for s in ["new", "in_progress", "done", "archived"]}
    by_priority = {p: base.filter(Task.priority == p).count() for p in ["high", "medium", "low"]}

    return render_template(
        "statistics.html",
        current_user=user,
        done_week=done_week,
        done_month=done_month,
        total=total,
        by_status=by_status,
        by_priority=by_priority,
    )


#Admin: users

@bp.route("/users/create", methods=["GET", "POST"])
@require_admin
def register_account():
    form = NewAccountForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if Account.query.filter_by(username=username).first():
            flash("Пользователь с таким именем уже существует.", "danger")
        else:
            u = Account(
                username=username,
                password_hash=generate_password_hash(form.password.data),
                is_admin=bool(form.is_admin.data),
            )
            db.session.add(u)
            db.session.commit()
            flash(f"Пользователь «{username}» создан.", "success")
            return redirect(url_for("routes.register_account"))
    users = Account.query.order_by(Account.username.asc()).all()
    return render_template("create_user.html", form=form, users=users, current_user=active_user())
