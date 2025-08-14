from datetime import datetime
from typing import Optional
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db, login_manager


class User(UserMixin, db.Model):
	__tablename__ = "users"
	id = db.Column(db.Integer, primary_key=True)
	username = db.Column(db.String(80), unique=True, nullable=False)
	email = db.Column(db.String(120), unique=True, nullable=False)
	password_hash = db.Column(db.String(255), nullable=False)
	role = db.Column(db.String(20), nullable=False, default="spectator")  # admin, team, player, spectator
	created_at = db.Column(db.DateTime, default=datetime.utcnow)

	team = db.relationship("Team", back_populates="owner", uselist=False)
	player = db.relationship("Player", back_populates="user", uselist=False)

	def set_password(self, password: str) -> None:
		self.password_hash = generate_password_hash(password)

	def check_password(self, password: str) -> bool:
		return check_password_hash(self.password_hash, password)

	def __repr__(self) -> str:
		return f"<User {self.username} ({self.role})>"


@login_manager.user_loader
def load_user(user_id: str) -> Optional["User"]:
	return User.query.get(int(user_id))


class Team(db.Model):
	__tablename__ = "teams"
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(120), unique=True, nullable=False)
	logo_url = db.Column(db.String(255))
	strategy = db.Column(db.String(50), default="balanced")  # batting-heavy, bowling-heavy, balanced
	budget_total = db.Column(db.Integer, default=100000000)  # in rupees
	budget_remaining = db.Column(db.Integer, default=100000000)
	approved = db.Column(db.Boolean, default=False)

	owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
	owner = db.relationship("User", back_populates="team")

	bids = db.relationship("Bid", back_populates="team", cascade="all, delete-orphan")
	players = db.relationship("AuctionPlayer", back_populates="sold_to_team")

	def spend_budget(self, amount: int) -> None:
		self.budget_remaining = max(0, (self.budget_remaining or 0) - amount)

	def __repr__(self) -> str:
		return f"<Team {self.name} rem={self.budget_remaining}>"


class Player(db.Model):
	__tablename__ = "players"
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(120), nullable=False)
	role = db.Column(db.String(50), nullable=False)  # Batter, Bowler, All-Rounder, Wicketkeeper
	base_price = db.Column(db.Integer, default=1000000)
	stats_json = db.Column(db.JSON, default={})
	highlight_url = db.Column(db.String(255))
	ai_valuation = db.Column(db.Integer)
	approved = db.Column(db.Boolean, default=False)

	user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
	user = db.relationship("User", back_populates="player")

	auction_links = db.relationship("AuctionPlayer", back_populates="player", cascade="all, delete-orphan")

	def __repr__(self) -> str:
		return f"<Player {self.name} {self.role}>"


class Auction(db.Model):
	__tablename__ = "auctions"
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(120), nullable=False)
	scheduled_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
	budget_per_team = db.Column(db.Integer, default=100000000)
	status = db.Column(db.String(20), default="scheduled")  # scheduled, live, ended
	current_player_id = db.Column(db.Integer, db.ForeignKey("players.id"))
	created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

	players = db.relationship("AuctionPlayer", back_populates="auction", cascade="all, delete-orphan")
	bids = db.relationship("Bid", back_populates="auction", cascade="all, delete-orphan")

	def __repr__(self) -> str:
		return f"<Auction {self.name} {self.status}>"


class AuctionPlayer(db.Model):
	__tablename__ = "auction_players"
	id = db.Column(db.Integer, primary_key=True)
	auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=False)
	player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
	status = db.Column(db.String(20), default="available")  # available, sold, unsold
	sold_to_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
	final_price = db.Column(db.Integer)
	order_index = db.Column(db.Integer, default=0)

	auction = db.relationship("Auction", back_populates="players")
	player = db.relationship("Player", back_populates="auction_links")
	sold_to_team = db.relationship("Team", back_populates="players")

	def __repr__(self) -> str:
		return f"<AuctionPlayer auction={self.auction_id} player={self.player_id} {self.status}>"


class Bid(db.Model):
	__tablename__ = "bids"
	id = db.Column(db.Integer, primary_key=True)
	auction_id = db.Column(db.Integer, db.ForeignKey("auctions.id"), nullable=False)
	player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
	team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
	amount = db.Column(db.Integer, nullable=False)
	timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
	ip_address = db.Column(db.String(64))

	auction = db.relationship("Auction", back_populates="bids")
	team = db.relationship("Team", back_populates="bids")

	def __repr__(self) -> str:
		return f"<Bid {self.amount} team={self.team_id} player={self.player_id}>"