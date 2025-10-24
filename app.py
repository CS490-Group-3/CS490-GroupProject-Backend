from flask import Flask, jsonify
from flask_cors import CORS
from routes.salons.salon_routes import salon_bp 

app = Flask(__name__)
CORS(app)

app.register_blueprint(salon_bp, url_prefix="/salons")


@app.route("/test-db")
def test_db():
    from supabase_client import supabase
    try:
        response = supabase.table("salons").select("*").limit(1).execute()
        return jsonify({"connected": True, "sample": response.data})
    except Exception as e:
        return jsonify({"connected": False, "error": str(e)})


if __name__ == "__main__":
    app.run(debug=True)

