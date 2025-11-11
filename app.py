"""
Main Flask application for the Salon Booking Platform backend.
"""
from flask import Flask, jsonify
from flask_cors import CORS
from config import FLASK_DEBUG
import sys
from flasgger import Swagger
from utils.response import error_response

from routes import health_bp, auth_bp, appointments_bp, schedule_bp, salon_bp, upload_bp

def create_app():
    app = Flask(__name__)
    #swagger section
    swagger = Swagger(app, template_file="swagger_config.yml")    
    # Do not sort JSON response keys
    app.config['JSON_SORT_KEYS'] = False
    
    # Enable CORS
    CORS(app)

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(salon_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(upload_bp)

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """ Handle 404 errors. """
        return error_response(
            message="The requested endpoint does not exist",
            status_code=404,
            code="not_found"
        )

    @app.errorhandler(500)
    def internal_error(error):
        """ Handle 500 errors. """
        return error_response(
            message="An unexpected error occurred",
            status_code=500,
            code="internal_server_error"
        )
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    try:
        print("=" * 50)
        print("Starting Salon Booking Platform Backend...")
        print(f"Debug mode: {FLASK_DEBUG}")
        print("=" * 50)
        app.run(debug=FLASK_DEBUG, host='0.0.0.0', port=5001)
    except Exception as e:
        print(f"Failed to start application: {e}", file=sys.stderr)
        sys.exit(1)
