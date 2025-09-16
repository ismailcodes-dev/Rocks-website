import sqlite3
import requests
import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# --- SETUP ---
load_dotenv()

# --- CONFIGURATION ---
# --- FIX: Point to the database in the parent directory ---
DATABASE_PATH = '../economy.db' 
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_API_URL = 'https://discord.com/api/v9'

if not BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN not found in .env file. Please create it.")

# --- FLASK APP INITIALIZATION ---
app = Flask(__name__)
CORS(app)

# --- HELPER FUNCTIONS ---
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    # Check if the database file exists at the specified path
    if not os.path.exists(DATABASE_PATH):
        raise FileNotFoundError(f"Database not found at {os.path.abspath(DATABASE_PATH)}. Make sure the api.py is in a subfolder of your main bot directory.")
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_discord_user_info(user_id: int):
    """Fetches user details from the Discord API."""
    headers = {'Authorization': f'Bot {BOT_TOKEN}'}
    try:
        response = requests.get(f'{DISCORD_API_URL}/users/{user_id}', headers=headers)
        response.raise_for_status()
        user_data = response.json()
        
        avatar_hash = user_data.get('avatar')
        if avatar_hash:
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
        else:
            # Default avatar logic based on discriminator or new username system
            discriminator = user_data.get('discriminator')
            if discriminator and discriminator != '0':
                 # Old system with discriminator
                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{int(discriminator) % 5}.png"
            else:
                 # New system, use user ID
                avatar_url = f"https://cdn.discordapp.com/embed/avatars/{(user_id >> 22) % 6}.png"

        return {
            "name": user_data.get('global_name') or user_data.get('username'),
            "avatar": avatar_url
        }
    except requests.RequestException as e:
        print(f"Failed to fetch user {user_id} from Discord API: {e}")
        return {"name": f"Unknown User (ID: {user_id})", "avatar": "https://cdn.discordapp.com/embed/avatars/0.png"}


# --- API ENDPOINTS ---
@app.route('/leaderboard/<int:guild_id>', methods=['GET'])
def get_leaderboard(guild_id):
    """Fetches and returns the leaderboard for a specific guild."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, level, balance FROM users WHERE guild_id = ? ORDER BY level DESC, xp DESC LIMIT 10",
            (guild_id,)
        )
        db_users = cursor.fetchall()
        conn.close()

        leaderboard_data = []
        for index, row in enumerate(db_users):
            user_info = get_discord_user_info(row['user_id'])
            leaderboard_data.append({
                "rank": index + 1,
                "name": user_info['name'],
                "avatar": user_info['avatar'],
                "level": row['level'],
                "coins": row['balance']
            })
            
        return jsonify(leaderboard_data)
        
    except FileNotFoundError as e:
        print(f"DATABASE ERROR: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Error fetching leaderboard for guild {guild_id}: {e}")
        return jsonify({"error": "Failed to retrieve leaderboard data."}), 500

# --- RUN THE APP ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
