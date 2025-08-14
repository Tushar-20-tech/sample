from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
	# Create DB tables on first run
	with app.app_context():
		from app.models import db
		db.create_all()
	# Run SocketIO server (eventlet)
	socketio.run(app, host="0.0.0.0", port=5000)