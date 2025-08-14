from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import db, Team, Auction

team_bp = Blueprint("team", __name__)


@team_bp.route("/dashboard", methods=["GET", "POST"]) 
@login_required
def dashboard():
	if current_user.role != "team":
		return redirect(url_for("auth.login"))
	team = Team.query.filter_by(owner_user_id=current_user.id).first()
	if request.method == "POST":
		name = request.form.get("name")
		logo_url = request.form.get("logo_url")
		strategy = request.form.get("strategy", "balanced")
		budget = int(request.form.get("budget", 100000000))
		if team is None:
			team = Team(name=name, logo_url=logo_url, strategy=strategy, budget_total=budget, budget_remaining=budget, owner_user_id=current_user.id)
			db.session.add(team)
		else:
			team.name = name
			team.logo_url = logo_url
			team.strategy = strategy
			team.budget_total = budget
			db.session.add(team)
		db.session.commit()
		flash("Team profile saved", "success")
	auctions = Auction.query.order_by(Auction.scheduled_at.desc()).all()
	return render_template("team/dashboard.html", team=team, auctions=auctions)