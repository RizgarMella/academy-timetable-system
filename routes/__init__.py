from routes.views import views_bp
from routes.api_data import api_data_bp
from routes.api_schedule import api_schedule_bp
from routes.api_solver import api_solver_bp


def register_blueprints(app):
    """Register all route blueprints with the Flask application."""
    app.register_blueprint(views_bp)
    app.register_blueprint(api_data_bp)
    app.register_blueprint(api_schedule_bp)
    app.register_blueprint(api_solver_bp)
