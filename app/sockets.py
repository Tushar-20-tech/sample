from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional
from flask import request
from . import socketio
from .models import db, Auction, AuctionPlayer, Bid, Team, Player


@dataclass
class AuctionState:
	auction_id: int
	current_ap_id: Optional[int] = None
	highest_bid_amount: int = 0
	highest_bid_team_id: Optional[int] = None
	bid_history: list = field(default_factory=list)
	end_time: Optional[datetime] = None
	min_increment: int = 100000  # 1 lakh default
	auto_bids: Dict[int, int] = field(default_factory=dict)  # team_id -> max_limit
	timer_running: bool = False


_state_by_auction: Dict[int, AuctionState] = {}


def get_state(auction_id: int) -> AuctionState:
	if auction_id not in _state_by_auction:
		_state_by_auction[auction_id] = AuctionState(auction_id=auction_id)
	return _state_by_auction[auction_id]


@socketio.on("connect")
def on_connect():
	return True


@socketio.on("join_auction")
def on_join_auction(data):
	from flask_socketio import join_room
	auction_id = int(data.get("auction_id"))
	join_room(f"auction:{auction_id}")
	state = get_state(auction_id)
	# Send current snapshot
	socketio.emit(
		"snapshot",
		{
			"current_ap_id": state.current_ap_id,
			"highest_bid_amount": state.highest_bid_amount,
			"highest_bid_team_id": state.highest_bid_team_id,
			"end_time": state.end_time.isoformat() if state.end_time else None,
			"bid_history": state.bid_history[-30:],
		},
		room=request.sid,
	)


@socketio.on("start_player")
def on_start_player(data):
	auction_id = int(data.get("auction_id"))
	ap_id = int(data.get("auction_player_id"))
	duration_sec = int(data.get("duration", 30))
	min_increment = int(data.get("min_increment", 100000))

	state = get_state(auction_id)
	state.current_ap_id = ap_id
	state.highest_bid_amount = 0
	state.highest_bid_team_id = None
	state.bid_history = []
	state.min_increment = min_increment
	state.end_time = datetime.utcnow() + timedelta(seconds=duration_sec)
	state.timer_running = True
	state.auto_bids = {}

	socketio.emit("player_start", {"auction_player_id": ap_id, "end_time": state.end_time.isoformat()}, room=f"auction:{auction_id}")

	def countdown_loop():
		while state.timer_running and state.end_time:
			remaining = (state.end_time - datetime.utcnow()).total_seconds()
			if remaining <= 0:
				break
			# push countdown ticks every second
			socketio.emit("tick", {"remaining": int(remaining)}, room=f"auction:{auction_id}")
			from eventlet import sleep  # local import to avoid hard dependency when testing
			sleep(1)
		finalize_sale(auction_id)

	from . import socketio as _s
	_s.start_background_task(countdown_loop)


@socketio.on("place_bid")
def on_place_bid(data):
	auction_id = int(data.get("auction_id"))
	team_id = int(data.get("team_id"))
	amount = int(data.get("amount"))
	player_id = int(data.get("player_id"))

	state = get_state(auction_id)
	if not state.end_time or not state.timer_running:
		return
	if amount < max(state.highest_bid_amount + state.min_increment, 0):
		return

	team: Team = Team.query.get(team_id)
	if not team or not team.approved:
		return
	if team.budget_remaining is None or team.budget_remaining < amount:
		return

	# Basic fraud detection: rapid-fire bids or repeated IPs
	last_events = state.bid_history[-5:]
	if last_events:
		last_ts = datetime.fromisoformat(last_events[-1]["ts"])
		if (datetime.utcnow() - last_ts).total_seconds() < 0.5:
			socketio.emit("commentary", {"text": "Fraud alert: rapid bids detected"}, room=f"auction:{auction_id}")
		last_ips = [e.get("ip") for e in last_events if e.get("ip")]
		if request.remote_addr in last_ips:
			socketio.emit("commentary", {"text": "Fraud alert: repeated IP bids"}, room=f"auction:{auction_id}")

	# Persist bid
	bid = Bid(
		auction_id=auction_id,
		player_id=player_id,
		team_id=team_id,
		amount=amount,
		ip_address=request.remote_addr,
	)
	db.session.add(bid)
	db.session.commit()

	state.highest_bid_amount = amount
	state.highest_bid_team_id = team_id
	state.bid_history.append({"team_id": team_id, "amount": amount, "ts": datetime.utcnow().isoformat(), "ip": request.remote_addr})

	# Extend timer slightly on last moments (anti-sniping)
	remaining = (state.end_time - datetime.utcnow()).total_seconds() if state.end_time else 0
	if remaining is not None and remaining < 5:
		state.end_time = datetime.utcnow() + timedelta(seconds=5)

	socketio.emit(
		"bid_update",
		{"team_id": team_id, "amount": amount, "remaining": int((state.end_time - datetime.utcnow()).total_seconds()) if state.end_time else 0},
		room=f"auction:{auction_id}",
	)

	# Auto-bid check
	for auto_team_id, max_limit in list(state.auto_bids.items()):
		if auto_team_id == state.highest_bid_team_id:
			continue
		if max_limit >= state.highest_bid_amount + state.min_increment:
			_auto_amount = min(max_limit, state.highest_bid_amount + state.min_increment)
			socketio.emit("commentary", {"text": f"Auto-bid placed by Team {auto_team_id} for ₹{_auto_amount:,}"}, room=f"auction:{auction_id}")
			on_place_bid({
				"auction_id": auction_id,
				"team_id": auto_team_id,
				"amount": _auto_amount,
				"player_id": player_id,
			})


@socketio.on("set_auto_bid")
def on_set_auto_bid(data):
	auction_id = int(data.get("auction_id"))
	team_id = int(data.get("team_id"))
	max_limit = int(data.get("max_limit"))
	state = get_state(auction_id)
	state.auto_bids[team_id] = max_limit
	socketio.emit("commentary", {"text": f"Team {team_id} enabled auto-bid up to ₹{max_limit:,}"}, room=f"auction:{auction_id}")


def finalize_sale(auction_id: int) -> None:
	state = get_state(auction_id)
	if not state.current_ap_id:
		return
	state.timer_running = False

	ap: AuctionPlayer = AuctionPlayer.query.get(state.current_ap_id)
	if not ap:
		return

	if state.highest_bid_team_id is None:
		ap.status = "unsold"
	else:
		ap.status = "sold"
		ap.sold_to_team_id = state.highest_bid_team_id
		ap.final_price = state.highest_bid_amount
		# deduct budget
		team = Team.query.get(state.highest_bid_team_id)
		if team:
			team.spend_budget(state.highest_bid_amount)

	db.session.commit()

	# Broadcast
	socketio.emit(
		"player_sold",
		{
			"auction_player_id": ap.id,
			"sold_to_team_id": ap.sold_to_team_id,
			"final_price": ap.final_price,
			"status": ap.status,
		},
		room=f"auction:{auction_id}",
	)

	# Reset
	state.current_ap_id = None
	state.end_time = None
	state.highest_bid_amount = 0
	state.highest_bid_team_id = None
	state.bid_history = []