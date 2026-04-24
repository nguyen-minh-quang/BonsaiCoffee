from datetime import timedelta, timezone as tz

import cloudinary
import cloudinary.uploader
from flask import Flask, jsonify, request as flask_request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required

VN_TZ = tz(timedelta(hours=7))

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)
    login_manager.init_app(app)

    # Cloudinary config
    cloudinary.config(
        cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=app.config["CLOUDINARY_API_KEY"],
        api_secret=app.config["CLOUDINARY_API_SECRET"],
    )

    @app.route("/api/upload", methods=["POST"])
    @login_required
    def api_upload():
        file = flask_request.files.get("file")
        if not file:
            return jsonify({"success": False, "message": "Không có file"}), 400
        try:
            result = cloudinary.uploader.upload(
                file, folder="brewmanager", transformation=[
                    {"width": 800, "height": 800, "crop": "limit", "quality": "auto"}
                ]
            )
            return jsonify({"success": True, "url": result["secure_url"]})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.cashier.routes import cashier_bp
    from app.waiter.routes import waiter_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(cashier_bp, url_prefix="/cashier")
    app.register_blueprint(waiter_bp, url_prefix="/waiter")

    @app.template_filter("vntime")
    def vntime_filter(dt, fmt="%H:%M %d/%m/%Y"):
        if dt is None:
            return ""
        # SQLite tra ve datetime naive -> coi nhu UTC roi convert sang gio VN
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz.utc)
        return dt.astimezone(VN_TZ).strftime(fmt)

    with app.app_context():
        db.create_all()

    return app
