import os
import secrets

from flask import Flask

from extensions import db
from utils import bootstrap_admin

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=secrets.token_hex(32),
    SQLALCHEMY_DATABASE_URI="sqlite:///tracker.db",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    WTF_CSRF_ENABLED=True,
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
)

db.init_app(app)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

from routes import bp
app.register_blueprint(bp)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        bootstrap_admin()
    app.run(debug=True)
