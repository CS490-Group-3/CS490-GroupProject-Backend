"""
Configuration file for the Flask application and Supabase connection.
"""
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Supabase configuration
SUPABASE_URL: str = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY")

# Flask configuration
FLASK_ENV: str = os.getenv("FLASK_ENV")
FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG").lower() == "true"

# Initialize and return a Supabase client instance.
def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Create a singleton Supabase client
supabase: Client = get_supabase_client()

