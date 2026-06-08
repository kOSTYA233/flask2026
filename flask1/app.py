import sys
import io
import contextlib
from itertools import cycle
import datetime
from flask import Flask, jsonify, request

status_lst = ["cancelled", "completed", "in_progress", "pending"]
priority_lst = ["high", "low", "medium"]

def get_task_list():
    f = io.StringIO()
    with contextlib.redirect_stdout(f):
        import this
    text = f.getvalue()
    status_cycle = cycle(status_lst)
    priority_cycle = cycle(priority_lst)
    tasks_lst = []
    num = 0
    for line in text.splitlines():
        if not line:
            continue
        num += 1
        tasks_lst.append({
            "id": num,
            "title": "Zen of Python",
            "description": line,
            "status": next(status_cycle),
            "priority": next(priority_cycle),
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "deleted_at": None,
        })
    return tasks_lst

tasks_lst = get_task_list()
status_lst = ["cancelled", "completed", "in_progress", "pending"]
priority_lst = ["high", "low", "medium"]
app = Flask(__name__)

def current_timestamp():
    return datetime.datetime.now().isoformat()

def locate_task_by_id(task_id):
    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return None
    for task in tasks_lst:
        if task["id"] == task_id:
            return task
    return None

ALLOWED_SORT_FIELDS = {
    "id", "title", "description", "status", "priority",
    "created_at", "updated_at", "deleted_at",
}

@app.route("/api/v1/tasks", methods=["GET"])
def get_tasks_lst():
    search_query = request.args.get("query")
    sort_field = request.args.get("order", "id")
    page_offset = request.args.get("offset", 0)

    try:
        page_offset = int(page_offset)
    except (TypeError, ValueError):
        page_offset = 0

    descending = False
    if sort_field.startswith("-"):
        descending = True
        sort_field = sort_field[1:]

    if sort_field not in ALLOWED_SORT_FIELDS:
        sort_field = "id"

    filtered_tasks = list(tasks_lst)

    if search_query:
        search_lower = search_query.lower()
        filtered_tasks = [
            t for t in filtered_tasks
            if search_lower in t["title"].lower()
            or search_lower in t["description"].lower()
        ]

    filtered_tasks.sort(
        key=lambda item: (item.get(sort_field) is None, item.get(sort_field)),
        reverse=descending,
    )

    paginated = filtered_tasks[page_offset:page_offset + 10]

    return jsonify({"tasks": paginated})

@app.route("/api/v1/tasks/<task_id>", methods=["GET"])
def get_tasks(task_id):
    task = locate_task_by_id(task_id)
    if task is None:
        return jsonify({"error": "Задача не найдена"}), 404
    return jsonify(task)

@app.route("/api/v1/tasks", methods=["POST"])
def post_tasks():
    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"error": "Отсутствуют данные JSON"}), 400

    task_title = payload.get("title")
    task_description = payload.get("description")
    task_status = payload.get("status", "pending")
    task_priority = payload.get("priority", "medium")

    if task_title is None:
        return jsonify({"error": "Пропущен обязательный параметр `title`"}), 400

    if task_description is None:
        return jsonify({"error": "Пропущен обязательный параметр `description`"}), 400

    if task_status not in status_lst:
        return jsonify({"error": "Поле `status` невалидно"}), 400

    if task_priority not in priority_lst:
        return jsonify({"error": "Поле `priority` невалидно"}), 400

    timestamp = current_timestamp()
    new_id = max((task["id"] for task in tasks_lst), default=0) + 1
    
    created_task = {
        "id": new_id,
        "title": task_title,
        "description": task_description,
        "status": task_status,
        "priority": task_priority,
        "created_at": timestamp,
        "updated_at": timestamp,
        "deleted_at": None,
    }

    tasks_lst.append(created_task)
    return jsonify(created_task)

@app.route("/api/v1/tasks/<task_id>", methods=["DELETE"])
def delete_tasks(task_id):
    task = locate_task_by_id(task_id)
    if task is None:
        return jsonify({"error": "Задача не найдена"}), 404

    deletion_time = current_timestamp()
    task["status"] = "cancelled"
    task["updated_at"] = deletion_time
    task["deleted_at"] = deletion_time

    return jsonify(task)

@app.route("/api/v1/tasks/<task_id>", methods=["PATCH"])
def patch_tasks(task_id):
    task = locate_task_by_id(task_id)
    if task is None:
        return jsonify({"error": "Задача не найдена"}), 404

    patch_data = request.get_json(silent=True)
    if not patch_data:
        return jsonify({"error": "Отсутствуют данные JSON"}), 400

    if "status" in patch_data and patch_data["status"] not in status_lst:
        return jsonify({"error": "Поле `status` невалидно"}), 400

    if "priority" in patch_data and patch_data["priority"] not in priority_lst:
        return jsonify({"error": "Поле `priority` невалидно"}), 400

    updatable_fields = ("title", "description", "status", "priority")
    for field in updatable_fields:
        if field in patch_data:
            task[field] = patch_data[field]

    task["updated_at"] = current_timestamp()

    return jsonify(task)