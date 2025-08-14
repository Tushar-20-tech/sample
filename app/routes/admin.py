from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import db, User, Team, Player, Auction, AuctionPlayer
from .. import socketio

admin_bp = Blueprint("admin", __name__)


def require_admin():
	return current_user.is_authenticated and current_user.role == "admin"


@admin_bp.before_request
def check_admin():
	# Allow viewing login page redirection
	if request.endpoint == "auth.login":
		return
	if not require_admin():
		return redirect(url_for("auth.login"))


@admin_bp.route("/dashboard", methods=["GET"]) 
@login_required
def dashboard():
	auctions = Auction.query.order_by(Auction.scheduled_at.desc()).all()
	pending_teams = Team.query.filter_by(approved=False).all()
	pending_players = Player.query.filter_by(approved=False).all()
	return render_template("admin/dashboard.html", auctions=auctions, pending_teams=pending_teams, pending_players=pending_players)


@admin_bp.route("/create_auction", methods=["POST"]) 
@login_required
def create_auction():
	name = request.form.get("name")
	scheduled_at_str = request.form.get("scheduled_at")
	budget = int(request.form.get("budget", 100000000))
	if not name or not scheduled_at_str:
		flash("Name and schedule are required", "error")
		return redirect(url_for("admin.dashboard"))
	scheduled_at = datetime.fromisoformat(scheduled_at_str)
	auction = Auction(name=name, scheduled_at=scheduled_at, budget_per_team=budget, status="scheduled", created_by_id=current_user.id)
	db.session.add(auction)
	db.session.commit()
	flash("Auction created", "success")
	return redirect(url_for("admin.dashboard"))


@admin_bp.route("/approve_team/<int:team_id>", methods=["POST"]) 
@login_required
def approve_team(team_id):
	team = Team.query.get_or_404(team_id)
	team.approved = True
	team.budget_remaining = team.budget_total
	db.session.commit()
	flash("Team approved", "success")
	return redirect(url_for("admin.dashboard"))


@admin_bp.route("/approve_player/<int:player_id>", methods=["POST"]) 
@login_required
def approve_player(player_id):
	player = Player.query.get_or_404(player_id)
	player.approved = True
	db.session.commit()
	flash("Player approved", "success")
	return redirect(url_for("admin.dashboard"))


@admin_bp.route("/add_player_to_auction", methods=["POST"]) 
@login_required
def add_player_to_auction():
	auction_id = int(request.form.get("auction_id"))
	player_id = int(request.form.get("player_id"))
	order_index = int(request.form.get("order_index", 0))
	ap = AuctionPlayer(auction_id=auction_id, player_id=player_id, order_index=order_index)
	db.session.add(ap)
	db.session.commit()
	flash("Player added to auction", "success")
	return redirect(url_for("admin.dashboard"))


@admin_bp.route("/start_player", methods=["POST"]) 
@login_required
def start_player():
	from ..sockets import on_start_player
	auction_id = int(request.form.get("auction_id"))
	ap_id = int(request.form.get("auction_player_id"))
	duration = int(request.form.get("duration", 30))
	min_inc = int(request.form.get("min_increment", 100000))

	# Start via server-side handler to set timers & state
	on_start_player({"auction_id": auction_id, "auction_player_id": ap_id, "duration": duration, "min_increment": min_inc})
	return redirect(url_for("admin.dashboard"))


@admin_bp.route("/export/teams/<int:auction_id>.csv")
@login_required
def export_teams_csv(auction_id):
	import csv
	from io import StringIO
	aps = AuctionPlayer.query.filter_by(auction_id=auction_id, status='sold').all()
	buf = StringIO()
	writer = csv.writer(buf)
	writer.writerow(["Team", "Player", "Role", "Final Price"])
	for ap in aps:
		team = ap.sold_to_team
		player = ap.player
		writer.writerow([
			team.name if team else '',
			player.name if player else '',
			player.role if player else '',
			ap.final_price or 0,
		])
	buf.seek(0)
	from flask import Response
	return Response(buf.read(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=auction_{auction_id}_teams.csv'})