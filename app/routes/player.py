from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models import db, Player

player_bp = Blueprint("player", __name__)


@player_bp.route("/register", methods=["GET", "POST"]) 
@login_required
def register_player():
	if current_user.role not in ("player", "admin"):
		return redirect(url_for("auth.login"))
	player = Player.query.filter_by(user_id=current_user.id).first()
	if request.method == "POST":
		name = request.form.get("name")
		role = request.form.get("role")
		base_price = int(request.form.get("base_price", 1000000))
		highlight_url = request.form.get("highlight_url")
		stats = {
			"matches": int(request.form.get("matches", 0)),
			"runs": int(request.form.get("runs", 0)),
			"wickets": int(request.form.get("wickets", 0)),
			"strike_rate": float(request.form.get("strike_rate", 0) or 0),
			"economy": float(request.form.get("economy", 0) or 0),
		}
		# Simple AI valuation heuristic (placeholder):
		def estimate_valuation(stats):
			matches = stats.get("matches", 0)
			runs = stats.get("runs", 0)
			wickets = stats.get("wickets", 0)
			strike = stats.get("strike_rate", 0.0)
			economy = stats.get("economy", 0.0)
			bat_score = runs * (strike/100.0)
			bowl_score = wickets * (6.0 / max(1.0, economy))
			score = bat_score * 5000 + bowl_score * 15000 + matches * 10000
			return int(max(base_price, min(score, base_price * 50)))

		ai_val = estimate_valuation(stats)

		if player is None:
			player = Player(user_id=current_user.id, name=name, role=role, base_price=base_price, highlight_url=highlight_url, stats_json=stats, ai_valuation=ai_val)
			db.session.add(player)
		else:
			player.name = name
			player.role = role
			player.base_price = base_price
			player.highlight_url = highlight_url
			player.stats_json = stats
			player.ai_valuation = ai_val
		db.session.commit()
		flash("Player details submitted. Estimated value: ₹{} (awaiting approval).".format(ai_val), "success")
	return render_template("player/register.html", player=player)