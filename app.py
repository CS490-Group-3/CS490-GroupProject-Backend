"""
Main Flask application for the Salon Booking Platform backend.
"""
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from config import FLASK_DEBUG
import sys
from flasgger import Swagger

from routes import health_bp, auth_bp, appointments_bp, schedule_bp, salon_bp, upload_bp, services_bp, admin_bp, users_bp, reviews_bp, notifications_bp, products_bp, order_bp, payments_bp, payment_methods_bp, loyalty_bp, owner_bp
from services.error_logging_service import ErrorLoggingService

def create_app():
    app = Flask(__name__)
    #swagger section
    swagger = Swagger(app, template_file="swagger_config.yml")    
    # Do not sort JSON response keys
    app.config['JSON_SORT_KEYS'] = False
    
    # Enable CORS
    CORS(
        app,
        resources={r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "https://salonica.up.railway.app"
            ]
        }},
        supports_credentials=True
    )

    # Register blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(salon_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(schedule_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(payment_methods_bp)
    app.register_blueprint(loyalty_bp)
    app.register_blueprint(owner_bp)

    # Error handlers - safety net for routes without @auto_log_errors decorator
    @app.errorhandler(404)
    def not_found(error):
        """ Handle 404 errors. """
        # Don't log 404s - they're expected for invalid URLs
        return jsonify({
            "error": "Not Found",
            "message": "The requested endpoint does not exist"
        }), 404

    @app.errorhandler(500)
    @app.errorhandler(Exception)
    def handle_exception(e):
        """ Handle unhandled exceptions - safety net for routes without @auto_log_errors. """
        # Check if error was already logged by @auto_log_errors decorator
        if hasattr(g, 'error_logged') and g.error_logged:
            return jsonify({
                "error": "Internal Server Error",
                "message": "An unexpected error occurred"
            }), 500
        
        # Only log if not already logged (routes without @auto_log_errors)
        user_id = None
        try:
            if hasattr(g, 'user') and g.user:
                user_id = g.user.get('sub')
        except:
            pass
        
        ErrorLoggingService.log_exception(
            exception=e,
            user_id=user_id,
            endpoint=request.path if request else None,
            severity='high'
        )
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected error occurred"
        }), 500
    
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
