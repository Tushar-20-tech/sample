import os
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO

# Extensions

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO(async_mode="eventlet", cors_allowed_origins="*")


def create_app() -> Flask:
	app = Flask(__name__, template_folder="../templates", static_folder="../static")
	app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
	app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:////workspace/auction.db")
	app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
	app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=7)

	# Init extensions
	db.init_app(app)
	login_manager.init_app(app)
	socketio.init_app(app)

	login_manager.login_view = "auth.login"

	# Register blueprints
	from .routes.auth import auth_bp
	from .routes.admin import admin_bp
	from .routes.team import team_bp
	from .routes.player import player_bp
	from .routes.spectator import spectator_bp
	from .routes.auction import auction_bp

	app.register_blueprint(auth_bp)
	app.register_blueprint(admin_bp, url_prefix="/admin")
	app.register_blueprint(team_bp, url_prefix="/team")
	app.register_blueprint(player_bp, url_prefix="/player")
	app.register_blueprint(spectator_bp, url_prefix="/spectator")
	app.register_blueprint(auction_bp, url_prefix="/auction")

	# Import socket handlers to bind events
	from . import sockets  # noqa: F401

	# Root route
	from flask import render_template, redirect, url_for

	@app.route("/")
	def index():
		return render_template("index.html")

	return app