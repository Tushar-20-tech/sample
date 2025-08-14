from flask import Blueprint, render_template, request
from flask_login import current_user
from ..models import Auction, AuctionPlayer, Team, Player, Bid

auction_bp = Blueprint("auction", __name__)


@auction_bp.route("/live/<int:auction_id>")
def live(auction_id):
	auction = Auction.query.get_or_404(auction_id)
	teams = Team.query.filter_by(approved=True).all()
	aps = AuctionPlayer.query.filter_by(auction_id=auction_id).order_by(AuctionPlayer.order_index.asc()).all()
	players_json = []
	for ap in aps:
		players_json.append({
			"id": ap.id,
			"player_id": ap.player_id,
			"status": ap.status,
			"order_index": ap.order_index,
			"player": {
				"id": ap.player.id if ap.player else None,
				"name": ap.player.name if ap.player else None,
				"role": ap.player.role if ap.player else None,
				"base_price": ap.player.base_price if ap.player else 0,
				"highlight_url": ap.player.highlight_url if ap.player else None,
			}
		})
	teams_json = [{
		"id": t.id,
		"name": t.name,
		"budget_total": t.budget_total,
		"budget_remaining": t.budget_remaining
	} for t in teams]
	return render_template("auction/live.html", auction=auction, teams=teams, players_json=players_json, teams_json=teams_json, user=current_user if current_user.is_authenticated else None)


@auction_bp.route("/replay/<int:auction_id>")
def replay(auction_id):
	auction = Auction.query.get_or_404(auction_id)
	bids = Bid.query.filter_by(auction_id=auction_id).order_by(Bid.timestamp.asc()).all()
	return render_template("auction/replay.html", auction=auction, bids=bids)