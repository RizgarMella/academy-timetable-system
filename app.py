import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from config import DATABASE_URI
from models import init_db, get_session
from routes import register_blueprints
from seed_data import seed_all, check_if_seeded


def create_app():
    app = Flask(__name__)
    app.config['DATABASE_URI'] = DATABASE_URI

    init_db(DATABASE_URI)

    register_blueprints(app)

    # Seed data on first run
    session = get_session()
    try:
        if not check_if_seeded(session):
            print("First run detected. Seeding database with sample data...")
            print("This includes running the optimizer (may take up to 60 seconds)...")
            seed_all(session)
            print("Seeding complete!")
        else:
            print("Database already seeded.")
    except Exception as e:
        print(f"Warning during seeding: {e}")
        session.rollback()
    finally:
        session.close()

    return app


if __name__ == '__main__':
    app = create_app()
    print("\n=== Training Academy Timetable System ===")
    print("Open http://localhost:5000 in your browser")
    print("==========================================\n")
    app.run(debug=True, port=5000, use_reloader=False)
