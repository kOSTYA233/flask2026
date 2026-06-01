import hashlib
import json
import mimetypes
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, url_for)

BASE_DIR = Path(__file__).resolve().parent

DATA_FOLDER = BASE_DIR / "storage"
UPLOAD_FOLDER = BASE_DIR / "user_files"
DATABASE_FILE = DATA_FOLDER / "files_db.json"

DISALLOWED_EXTENSIONS = {'.exe', '.sh', '.php', '.js', '.bat', '.cmd', '.vbs'}

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-2024'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  


def init_storage():
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    if not DATABASE_FILE.exists():
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, indent=4, ensure_ascii=False)


def load_database():
    init_storage()
    with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_database(data):
    init_storage()
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def calculate_md5(file_storage) -> str:
    hash_md5 = hashlib.md5()
    file_storage.stream.seek(0)
    for chunk in iter(lambda: file_storage.stream.read(8192), b''):
        hash_md5.update(chunk)
    file_storage.stream.seek(0)
    return hash_md5.hexdigest()


def is_extension_blocked(filename: str) -> bool:
    ext = get_file_extension(filename)
    if ext in DISALLOWED_EXTENSIONS:
        return True
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and 'application/x-executable' in mime_type:
        return True
    return False


def build_file_path(file_uuid: str, extension: str):
    part1 = file_uuid[:2]
    part2 = file_uuid[2:4]
    relative_path = Path('user_files') / part1 / part2 / f"{file_uuid}{extension}"
    absolute_path = BASE_DIR / relative_path
    return relative_path, absolute_path


@app.route('/uploads/<path:filepath>')
def download_file(filepath):
    full_path = (BASE_DIR / filepath).resolve()
    uploads_root = UPLOAD_FOLDER.resolve()
    if not full_path.exists():
        abort(404)
    if uploads_root not in full_path.parents and full_path != uploads_root:
        abort(403)
    return send_from_directory(BASE_DIR, filepath)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        uploaded_file = request.files.get('file')
        

        if not uploaded_file or uploaded_file.filename == '':
            flash('Не выбран файл или файл не передан.', 'error')
            return redirect(url_for('index'))
        
        original_name = os.path.basename(uploaded_file.filename)
        file_ext = get_file_extension(original_name)
        

        if is_extension_blocked(original_name):
            flash(f'Запрещённый тип файла. Расширение "{file_ext or "без расширения"}" не разрешено.', 'error')
            return redirect(url_for('index'))
        

        file_md5 = calculate_md5(uploaded_file)
        database = load_database()
        
        duplicate_found = False
        for record in database.values():
            if record.get('md5_hash') == file_md5:
                duplicate_found = True
                break
        
        if duplicate_found:
            flash('Ошибка: файл с таким содержимым уже существует.', 'error')
            return redirect(url_for('index'))
        

        file_uuid = uuid.uuid4().hex
        rel_path, abs_path = build_file_path(file_uuid, file_ext)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        uploaded_file.save(abs_path)
        

        mime_type, _ = mimetypes.guess_type(original_name)
        

        database[file_uuid] = {
            'original_name': original_name,
            'stored_name': f"{file_uuid}{file_ext}",
            'server_path': rel_path.as_posix(),
            'upload_timestamp': datetime.now().isoformat(timespec='seconds'),
            'file_extension': file_ext if file_ext else '',
            'md5_hash': file_md5,
            'mime_info': mime_type or 'unknown'
        }
        save_database(database)
        
        flash('Файл успешно загружен!', 'success')
        return redirect(url_for('index'))
    

    db_content = load_database()
    file_list = sorted(db_content.values(), key=lambda x: x['upload_timestamp'], reverse=True)
    return render_template('file_list.html', files=file_list)


if __name__ == '__main__':
    init_storage()
    app.run(debug=True)