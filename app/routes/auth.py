from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from ..models import db, User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
	if request.method == "POST":
		username = request.form.get("username")
		email = request.form.get("email")
		password = request.form.get("password")
		role = request.form.get("role", "spectator")
		if not username or not email or not password:
			flash("All fields are required", "error")
			return render_template("auth/register.html")
		if User.query.filter((User.username == username) | (User.email == email)).first():
			flash("User already exists", "error")
			return render_template("auth/register.html")

		user = User(username=username, email=email, role=role)
		user.set_password(password)
		db.session.add(user)
		db.session.commit()
		flash("Registration successful. Please login.", "success")
		return redirect(url_for("auth.login"))
	return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
	if request.method == "POST":
		username = request.form.get("username")
		password = request.form.get("password")
		user = User.query.filter_by(username=username).first()
		if not user or not user.check_password(password):
			flash("Invalid credentials", "error")
			return render_template("auth/login.html")
		login_user(user, remember=True)
		flash("Welcome back!", "success")
		if user.role == "admin":
			return redirect(url_for("admin.dashboard"))
		elif user.role == "team":
			return redirect(url_for("team.dashboard"))
		elif user.role == "player":
			return redirect(url_for("player.register_player"))
		return redirect(url_for("index"))
	return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
	logout_user()
	flash("Logged out.", "info")
	return redirect(url_for("index"))