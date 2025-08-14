from flask import Blueprint, render_template
from ..models import Auction

spectator_bp = Blueprint("spectator", __name__)


@spectator_bp.route("/live")
def live_list():
	auctions = Auction.query.filter(Auction.status != "ended").order_by(Auction.scheduled_at.desc()).all()
	return render_template("spectator/live_list.html", auctions=auctions)