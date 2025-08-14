import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import sqlite3
from io import BytesIO
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# Windows-specific imports (for Outlook integration)
# These will only work on Windows systems
try:
    import win32com.client
    import pythoncom
    OUTLOOK_AVAILABLE = True
except ImportError:
    OUTLOOK_AVAILABLE = False
from fixtures_utils import (get_all_fixtures, get_fixtures_by_category, parse_time_slot, 
                           generate_time_slots, assign_participants_to_slots, save_fixtures, 
                           delete_fixture, get_fixture_emails, mark_emails_sent)

# Function to generate sample participants for testing
def generate_sample_participants(game, category, count=30, slot_type="Morning"):
    """
    Generate sample participants for testing purposes.
    
    Args:
        game: The game name (e.g., 'Carrom')
        category: The category (e.g., 'Men's Singles', 'Women's Doubles')
        count: Number of participants to generate (default: 30)
        slot_type: The slot type (Morning/Afternoon/Evening)
        
    Returns:
        int: Number of participants generated
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Generate unique IDs starting from a high number to avoid conflicts
        cursor.execute("SELECT MAX(id) FROM participants")
        max_id = cursor.fetchone()[0] or 0
        start_id = max_id + 1
        
        # Generate unique employee IDs
        cursor.execute("SELECT MAX(CAST(emp_id AS INTEGER)) FROM participants WHERE emp_id GLOB '[0-9]*'")
        result = cursor.fetchone()[0]
        max_emp_id = int(result) if result else 10000
        start_emp_id = max_emp_id + 1
        
        participants_added = 0
        
        # For doubles categories, we need to create pairs
        if 'Doubles' in category:
            # Generate pairs (need even number of participants)
            pairs_count = count // 2
            for i in range(pairs_count):
                # Create first player of the pair
                player1_id = start_id + (i * 2)
                player1_emp_id = str(start_emp_id + (i * 2))
                player1_name = f"Player {player1_emp_id}"
                
                # Create second player of the pair
                player2_id = start_id + (i * 2) + 1
                player2_emp_id = str(start_emp_id + (i * 2) + 1)
                player2_name = f"Player {player2_emp_id}"
                
                # Insert first player with reference to second player
                # Current timestamp for registration and creation time
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute("""
                    INSERT INTO participants 
                    (id, emp_id, name, email, category, game, partner_emp_id, registered_at_desk, slot, registered_timestamp, created_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player1_id, player1_emp_id, player1_name, 
                    f"player{player1_emp_id}@example.com", 
                    category, game, player2_emp_id, 0, slot_type, current_time, current_time
                ))
                
                # Insert second player with reference to first player
                cursor.execute("""
                    INSERT INTO participants 
                    (id, emp_id, name, email, category, game, partner_emp_id, registered_at_desk, slot, registered_timestamp, created_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player2_id, player2_emp_id, player2_name, 
                    f"player{player2_emp_id}@example.com", 
                    category, game, player1_emp_id, 0, slot_type, current_time, current_time
                ))
                
                participants_added += 2
        else:
            # For singles, just create individual participants
            for i in range(count):
                player_id = start_id + i
                player_emp_id = str(start_emp_id + i)
                player_name = f"Player {player_emp_id}"
                
                # Current timestamp for registration and creation time
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute("""
                    INSERT INTO participants 
                    (id, emp_id, name, email, category, game, registered_at_desk, slot, registered_timestamp, created_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, player_emp_id, player_name, 
                    f"player{player_emp_id}@example.com", 
                    category, game, 0, slot_type, current_time, current_time
                ))
                
                participants_added += 1
        
        conn.commit()
        conn.close()
        return participants_added
    
    except Exception as e:
        st.error(f"Error generating sample participants: {str(e)}")
        return 0

# Set page configuration
st.set_page_config(
    page_title="Carrom Tournament Manager",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Enhanced colorful CSS styling
st.markdown("""
<style>
    /* Colorful background and styling */
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4efe9 100%);
    }
    
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 1200px;
        background-color: rgba(255, 255, 255, 0.8);
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    /* Header styling */
    h1, h2, h3 {
        color: #3a506b;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        border-bottom: 2px solid #5bc0be;
        padding-bottom: 0.3rem;
        margin-bottom: 1rem;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        border: none;
        padding: 10px 16px;
        color: #3a506b;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #5bc0be !important;
        color: white !important;
        font-weight: bold;
    }
    
    /* Button styling with gradient */
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #ff6b35 0%, #f7882f 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        font-weight: bold;
        box-shadow: 0 2px 5px rgba(0,0,0,0.15);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(90deg, #f7882f 0%, #ff6b35 100%);
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Sidebar styling */
    .css-1d391kg, .css-12oz5g7 {
        background: linear-gradient(180deg, #3a506b 0%, #1c2541 100%);
        color: white;
    }
    
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #3a506b 0%, #1c2541 100%);
    }
    
    /* Metric styling */
    [data-testid="stMetricValue"] {
        background: linear-gradient(90deg, #5bc0be 0%, #3a506b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: bold;
        font-size: 2rem;
    }
    
    /* Dataframe styling */
    .dataframe {
        border-collapse: collapse;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .dataframe thead th {
        background-color: #5bc0be;
        color: white;
        text-align: left;
        padding: 12px;
    }
    
    .dataframe tbody tr:nth-child(even) {
        background-color: #f0f2f6;
    }
    
    .dataframe tbody tr:hover {
        background-color: #e4efe9;
    }
    
    /* Enhanced colorful category table styling */
    .category-table {
        border-collapse: collapse;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        margin-bottom: 20px;
    }
    
    .category-table thead th {
        background: linear-gradient(90deg, #3a506b 0%, #5bc0be 100%);
        color: white;
        text-align: center;
        padding: 15px;
        font-weight: bold;
        font-size: 1.1em;
    }
    
    .category-table tbody tr:nth-child(odd) {
        background: linear-gradient(90deg, #f5f7fa 0%, #e4efe9 100%);
    }
    
    .category-table tbody tr:nth-child(even) {
        background: linear-gradient(90deg, #e4efe9 0%, #d4e4ef 100%);
    }
    
    .category-table tbody tr:hover {
        background: linear-gradient(90deg, #cce5ff 0%, #b8daff 100%);
        transform: scale(1.01);
        transition: transform 0.2s ease;
    }
    
    .category-table td {
        padding: 12px 15px;
        text-align: center;
        font-size: 1.05em;
    }
    
    /* Success and error messages */
    .stSuccess {
        border-radius: 8px;
        padding: 0.8rem;
        background: linear-gradient(90deg, #d4edda 0%, #c3e6cb 100%);
        border: 1px solid #c3e6cb;
        color: #155724;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    .stError {
        border-radius: 8px;
        padding: 0.8rem;
        background: linear-gradient(90deg, #f8d7da 0%, #f5c6cb 100%);
        border: 1px solid #f5c6cb;
        color: #721c24;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Info message styling */
    .stInfo {
        border-radius: 8px;
        padding: 0.8rem;
        background: linear-gradient(90deg, #cce5ff 0%, #b8daff 100%);
        border: 1px solid #b8daff;
        color: #004085;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
</style>
""", unsafe_allow_html=True)

# Database path
DB_PATH = 'tournament.db'

def init_database():
    """Initialize the SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if participants table exists and get its structure
    cursor.execute("PRAGMA table_info(participants)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Migrate old database if needed
    if columns and 'emp_id' not in columns:
        print("Migrating database to new schema...")
        
        # Create new table with correct schema
        cursor.execute('''
            CREATE TABLE participants_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,  
                email TEXT,
                location TEXT,
                sub_location TEXT,
                game TEXT,
                category TEXT NOT NULL,
                slot TEXT,
                partner_emp_id TEXT,
                gender TEXT,
                partner_gender TEXT,
                registered_at_desk INTEGER DEFAULT 0,
                registered_timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migrate existing data if any
        cursor.execute("SELECT COUNT(*) FROM participants")
        if cursor.fetchone()[0] > 0:
            # Generate unique emp_ids for existing participants
            if 'team_partner' in columns:
                cursor.execute('''
                    INSERT INTO participants_new (emp_id, name, email, category, partner_emp_id, registered_at_desk, created_at)
                    SELECT 
                        'EMP' || SUBSTR('0000' || id, -4) AS emp_id,
                        name,
                        email,
                        category,
                        CASE WHEN team_partner IS NOT NULL AND team_partner != '' THEN team_partner ELSE NULL END,
                        COALESCE(registered_at_desk, 0),
                        COALESCE(created_at, CURRENT_TIMESTAMP)
                    FROM participants
                ''')
            else:
                cursor.execute('''
                    INSERT INTO participants_new (emp_id, name, email, category, registered_at_desk, created_at)
                    SELECT 
                        'EMP' || SUBSTR('0000' || id, -4) AS emp_id,
                        name,
                        email,
                        category,
                        COALESCE(registered_at_desk, 0),
                        COALESCE(created_at, CURRENT_TIMESTAMP)
                    FROM participants
                ''')
        
        # Replace old table
        cursor.execute("DROP TABLE participants")
        cursor.execute("ALTER TABLE participants_new RENAME TO participants")
        print("Database migration completed.")
    
    # Check if registered_timestamp column exists, if not add it
    elif columns and 'registered_timestamp' not in columns:
        print("Adding registered_timestamp column...")
        cursor.execute("ALTER TABLE participants ADD COLUMN registered_timestamp TIMESTAMP")
    
    # Check if created_at column exists, if not add it
    if columns and 'created_at' not in columns:
        print("Adding created_at column to participants table...")
        cursor.execute("ALTER TABLE participants ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        print("created_at column added to participants table.")
    
    # Check and add missing columns to matches table
    cursor.execute("PRAGMA table_info(matches)")
    matches_columns = [column[1] for column in cursor.fetchall()]
    
    if matches_columns and 'winner_team' not in matches_columns:
        print("Adding winner_team column to matches table...")
        try:
            cursor.execute("ALTER TABLE matches ADD COLUMN winner_team INTEGER")
            print("winner_team column added to matches table.")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    if matches_columns and 'completed_at' not in matches_columns:
        print("Adding completed_at column to matches table...")
        try:
            cursor.execute("ALTER TABLE matches ADD COLUMN completed_at TIMESTAMP")
            print("completed_at column added to matches table.")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    if matches_columns and 'updated_at' not in matches_columns:
        print("Adding updated_at column to matches table...")
        try:
            cursor.execute("ALTER TABLE matches ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("updated_at column added to matches table.")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    if matches_columns and 'created_at' not in matches_columns:
        print("Adding created_at column to matches table...")
        try:
            cursor.execute("ALTER TABLE matches ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("created_at column added to matches table.")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Create participants table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_id TEXT UNIQUE,
            name TEXT,
            email TEXT,
            category TEXT,
            partner_emp_id TEXT,
            registered_at_desk INTEGER DEFAULT 0,
            registered_timestamp TIMESTAMP,
            location TEXT,
            sub_location TEXT,
            game TEXT,
            slot TEXT,
            gender TEXT,
            partner_gender TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create matches table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_number INTEGER,
            round_number INTEGER,
            category TEXT,
            player1_id INTEGER,
            player2_id INTEGER,
            team1_player1_id INTEGER,
            team1_player2_id INTEGER,
            team2_player1_id INTEGER,
            team2_player2_id INTEGER,
            winner_id INTEGER,
            winner_team_id INTEGER,
            winner_team INTEGER,
            match_status TEXT DEFAULT 'pending',
            match_date TIMESTAMP,
            score TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player1_id) REFERENCES participants (id),
            FOREIGN KEY (player2_id) REFERENCES participants (id),
            FOREIGN KEY (team1_player1_id) REFERENCES participants (id),
            FOREIGN KEY (team1_player2_id) REFERENCES participants (id),
            FOREIGN KEY (team2_player1_id) REFERENCES participants (id),
            FOREIGN KEY (team2_player2_id) REFERENCES participants (id)
        )
    ''')
    
    # Create fixtures table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fixtures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            time_slot TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            location TEXT,
            court_number INTEGER,
            player1_id INTEGER,
            player2_id INTEGER,
            team1_player1_id INTEGER,
            team1_player2_id INTEGER,
            team2_player1_id INTEGER,
            team2_player2_id INTEGER,
            fixture_status TEXT DEFAULT 'scheduled',
            emails_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player1_id) REFERENCES participants (id),
            FOREIGN KEY (player2_id) REFERENCES participants (id),
            FOREIGN KEY (team1_player1_id) REFERENCES participants (id),
            FOREIGN KEY (team1_player2_id) REFERENCES participants (id),
            FOREIGN KEY (team2_player1_id) REFERENCES participants (id),
            FOREIGN KEY (team2_player2_id) REFERENCES participants (id)
        )
    ''')
    
    # Check if match_code column exists in matches table, if not add it
    cursor.execute("PRAGMA table_info(matches)")
    match_columns = [column[1] for column in cursor.fetchall()]
    
    if 'match_code' not in match_columns:
        print("Adding match_code column to matches table...")
        cursor.execute("ALTER TABLE matches ADD COLUMN match_code TEXT")
        print("match_code column added.")
    
    if 'advancement_type' not in match_columns:
        print("Adding advancement_type column to matches table...")
        cursor.execute("ALTER TABLE matches ADD COLUMN advancement_type TEXT DEFAULT 'normal'")
        print("advancement_type column added.")
    
    # Check if slot and round_number columns exist in fixtures table, if not add them
    cursor.execute("PRAGMA table_info(fixtures)")
    fixtures_columns = [column[1] for column in cursor.fetchall()]
    
    if 'slot' not in fixtures_columns:
        print("Adding slot column to fixtures table...")
        cursor.execute("ALTER TABLE fixtures ADD COLUMN slot TEXT")
        print("slot column added to fixtures table.")
    
    if 'round_number' not in fixtures_columns:
        print("Adding round_number column to fixtures table...")
        cursor.execute("ALTER TABLE fixtures ADD COLUMN round_number INTEGER")
        print("round_number column added to fixtures table.")
    
    if 'game' not in fixtures_columns:
        print("Adding game column to fixtures table...")
        cursor.execute("ALTER TABLE fixtures ADD COLUMN game TEXT")
        print("game column added to fixtures table.")
    
    conn.commit()
    conn.close()

def get_participants():
    """Get all participants from database, excluding auto-generated placeholder partners"""
    conn = sqlite3.connect(DB_PATH)
    # Filter out placeholder partners (those with names starting with "Player-")
    df = pd.read_sql_query('''
        SELECT * FROM participants 
        WHERE name NOT LIKE 'Player-%' 
        ORDER BY created_at DESC
    ''', conn)
    conn.close()
    return df

def get_matches():
    """Get all matches from database"""
    conn = sqlite3.connect(DB_PATH)
    
    # Check if created_at column exists in matches table
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(matches)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Use appropriate ordering based on available columns
    if 'created_at' in columns:
        order_by = 'ORDER BY m.created_at DESC'
    elif 'updated_at' in columns:
        order_by = 'ORDER BY m.updated_at DESC'
    else:
        order_by = 'ORDER BY m.id DESC'
    
    df = pd.read_sql_query(f'''
        SELECT m.*, 
               p1.name as player1_name, p2.name as player2_name,
               t1p1.name as team1_player1_name, t1p2.name as team1_player2_name,
               t2p1.name as team2_player1_name, t2p2.name as team2_player2_name,
               w.name as winner_name
        FROM matches m
        LEFT JOIN participants p1 ON m.player1_id = p1.id
        LEFT JOIN participants p2 ON m.player2_id = p2.id
        LEFT JOIN participants t1p1 ON m.team1_player1_id = t1p1.id
        LEFT JOIN participants t1p2 ON m.team1_player2_id = t1p2.id
        LEFT JOIN participants t2p1 ON m.team2_player1_id = t2p1.id
        LEFT JOIN participants t2p2 ON m.team2_player2_id = t2p2.id
        LEFT JOIN participants w ON m.winner_id = w.id
        {order_by}
    ''', conn)
    conn.close()
    return df

def add_participant(emp_id, name, email, category, partner_emp_id=None):
    """Add a new participant to the database (legacy function)"""
    return add_participant_extended(emp_id, name, email, None, None, "Carrom", category, None, partner_emp_id, None, None)

def add_participant_extended(emp_id, name, email, location=None, sub_location=None, game="Carrom", 
                           category=None, slot=None, partner_emp_id=None, gender=None, partner_gender=None):
    """Add a new participant to the database with extended fields"""
    try:
        # Print debug info
        print(f"Adding participant: {emp_id}, {name}, {email}, {location}, {sub_location}, {game}, {category}, {slot}, {partner_emp_id}, {gender}, {partner_gender}")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current timestamp for created_at
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Check if the participant already exists
        cursor.execute('SELECT COUNT(*) FROM participants WHERE emp_id = ?', (emp_id,))
        if cursor.fetchone()[0] > 0:
            print(f"Participant with emp_id {emp_id} already exists!")
            conn.close()
            raise sqlite3.IntegrityError(f"UNIQUE constraint failed: participants.emp_id ({emp_id})")
        
        # Insert the new participant with all fields
        cursor.execute('''
            INSERT INTO participants (emp_id, name, email, location, sub_location, game, category, slot, 
                                    partner_emp_id, gender, partner_gender, registered_at_desk, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (emp_id, name, email, location, sub_location, game, category, slot, 
              partner_emp_id, gender, partner_gender, 0, current_time))
        
        # Verify the insert worked
        cursor.execute('SELECT * FROM participants WHERE emp_id = ?', (emp_id,))
        result = cursor.fetchone()
        print(f"Insert result: {result}")
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error in add_participant_extended: {str(e)}")
        # Re-raise the exception to be caught by the caller
        raise e

def ensure_partner_exists(partner_emp_id, category, game="Carrom", slot=None, gender=None):
    """Ensure that a partner exists in the database, create a placeholder if not"""
    if not partner_emp_id:
        return False
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if partner exists
    cursor.execute('SELECT COUNT(*) FROM participants WHERE emp_id = ?', (partner_emp_id,))
    exists = cursor.fetchone()[0] > 0
    
    if not exists:
        # Create a placeholder partner entry
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        partner_name = f"Player-{partner_emp_id}"
        partner_email = f"player{partner_emp_id}@example.com"
        
        # Insert with all the new fields
        cursor.execute('''
            INSERT INTO participants (emp_id, name, email, game, category, slot, gender, registered_at_desk, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (partner_emp_id, partner_name, partner_email, game, category, slot, gender, 0, current_time))
        
        conn.commit()
        print(f"Created placeholder partner with ID {partner_emp_id}")
        result = True
    else:
        print(f"Partner with ID {partner_emp_id} already exists")
        result = False
        
    conn.close()
    return result

def update_registration_status(participant_id, status):
    """Update participant registration status with timestamp"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if status == 1:
        # Mark as reported with current timestamp
        cursor.execute('''
            UPDATE participants 
            SET registered_at_desk = ?, registered_timestamp = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, participant_id))
    else:
        # Unmark - clear both status and timestamp
        cursor.execute('''
            UPDATE participants 
            SET registered_at_desk = ?, registered_timestamp = NULL
            WHERE id = ?
        ''', (status, participant_id))
    
    conn.commit()
    conn.close()

def generate_match_id(match_id, category, round_number):
    """Generate a readable match ID"""
    category_code = ''.join([word[0].upper() for word in category.split()])
    return f"{category_code}-R{round_number}-{match_id:03d}"

def create_match(category, round_number, player1_id=None, player2_id=None, 
                team1_player1_id=None, team1_player2_id=None,
                team2_player1_id=None, team2_player2_id=None):
    """Create a new match"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Check if created_at column exists
    cursor.execute("PRAGMA table_info(matches)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'created_at' in columns:
        cursor.execute(''' 
            INSERT INTO matches (category, round_number, player1_id, player2_id, 
                                team1_player1_id, team1_player2_id, 
                                team2_player1_id, team2_player2_id, 
                                match_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (category, round_number, player1_id, player2_id, 
              team1_player1_id, team1_player2_id, 
              team2_player1_id, team2_player2_id, 
              'scheduled', current_time))
    else:
        cursor.execute(''' 
            INSERT INTO matches (category, round_number, player1_id, player2_id, 
                                team1_player1_id, team1_player2_id, 
                                team2_player1_id, team2_player2_id, 
                                match_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (category, round_number, player1_id, player2_id, 
              team1_player1_id, team1_player2_id, 
              team2_player1_id, team2_player2_id, 
              'scheduled'))
    
    match_id = cursor.lastrowid
    
    # Generate a readable match ID
    readable_id = generate_match_id(match_id, category, round_number)
    
    # Update the match with the readable ID
    cursor.execute(''' 
        UPDATE matches SET match_code = ? WHERE id = ?
    ''', (readable_id, match_id))
    
    conn.commit()
    conn.close()
    return match_id

def update_match_result(match_id, winner_id=None, winner_team=None, advancement_type='normal'):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Update match status and winner
        if winner_id is not None:  # Singles match
            cursor.execute('''
                UPDATE matches 
                SET match_status = 'completed', winner_id = ?, completed_at = ?, advancement_type = ? 
                WHERE id = ?
            ''', (winner_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), advancement_type, match_id))
        elif winner_team is not None:  # Doubles match
            cursor.execute('''
                UPDATE matches 
                SET match_status = 'completed', winner_team = ?, completed_at = ?, advancement_type = ? 
                WHERE id = ?
            ''', (winner_team, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), advancement_type, match_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating match result: {str(e)}")
        return False

def update_match_tracker_details(match_id, round_number=None, match_status=None, winner_id=None, advancement_type=None):
    """Update match details including round, status, winner and advancement type"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Build the update query dynamically based on provided parameters
        update_parts = []
        params = []
        
        if round_number is not None:
            update_parts.append("round_number = ?")
            params.append(round_number)
        
        if match_status is not None:
            update_parts.append("match_status = ?")
            params.append(match_status)
            
            # If status is completed, add timestamp
            if match_status == 'completed':
                update_parts.append("completed_at = ?")
                params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            elif match_status == 'scheduled':
                # Reset completed_at if match is rescheduled
                update_parts.append("completed_at = NULL")
        
        if winner_id is not None:
            update_parts.append("winner_id = ?")
            params.append(winner_id)
        
        if advancement_type is not None:
            update_parts.append("advancement_type = ?")
            params.append(advancement_type)
        
        # Only proceed if we have something to update
        if update_parts:
            query = f"UPDATE matches SET {', '.join(update_parts)} WHERE id = ?"
            params.append(match_id)
            
            cursor.execute(query, params)
            conn.commit()
            
            print(f"Updated match {match_id} with {', '.join(update_parts)}")
            result = True
        else:
            print(f"No updates provided for match {match_id}")
            result = False
            
        conn.close()
        return result
    except Exception as e:
        print(f"Error updating match details: {str(e)}")
        return False

def update_match_details(match_id, player1_id=None, player2_id=None, team1_player1_id=None, team1_player2_id=None, team2_player1_id=None, team2_player2_id=None, match_status=None, round_number=None):
    """Update match details"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Build the update query dynamically
    update_parts = []
    params = []
    
    if player1_id is not None:
        update_parts.append("player1_id = ?")
        params.append(player1_id)
    
    if player2_id is not None:
        update_parts.append("player2_id = ?")
        params.append(player2_id)
    
    if team1_player1_id is not None:
        update_parts.append("team1_player1_id = ?")
        params.append(team1_player1_id)
    
    if team1_player2_id is not None:
        update_parts.append("team1_player2_id = ?")
        params.append(team1_player2_id)
    
    if team2_player1_id is not None:
        update_parts.append("team2_player1_id = ?")
        params.append(team2_player1_id)
    
    if team2_player2_id is not None:
        update_parts.append("team2_player2_id = ?")
        params.append(team2_player2_id)
    
    if match_status is not None:
        update_parts.append("match_status = ?")
        params.append(match_status)
    
    if round_number is not None:
        update_parts.append("round_number = ?")
        params.append(round_number)
    
    # Only proceed if we have something to update
    if update_parts:
        query = f"UPDATE matches SET {', '.join(update_parts)} WHERE id = ?"
        params.append(match_id)
        
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

def search_participants(search_term, participants_df):
    # Search participants by emp_id, name, email, or category
    if participants_df.empty:
        return pd.DataFrame()
        
    search_term = str(search_term).lower()
    
    # Search in multiple columns
    mask = (
        participants_df['emp_id'].astype(str).str.lower().str.contains(search_term) |
        participants_df['name'].astype(str).str.lower().str.contains(search_term) |
        participants_df['email'].astype(str).str.lower().str.contains(search_term) |
        participants_df['category'].astype(str).str.lower().str.contains(search_term)
    )
    
    return participants_df[mask]


def get_match_details(match_id):
    """
    Get detailed information about a specific match, including participant emails.
    
    Args:
        match_id (int): ID of the match to retrieve details for
        
    Returns:
        dict: Dictionary containing match details with participant information
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get basic match information
        cursor.execute("""
            SELECT * FROM matches WHERE id = ?
        """, (match_id,))
        match = cursor.fetchone()
        
        if not match:
            return None
            
        # Convert to dictionary
        columns = [desc[0] for desc in cursor.description]
        match_dict = {columns[i]: match[i] for i in range(len(columns))}
        
        # Get participant details based on match type (singles or doubles)
        if match_dict['category'] in ['Mens Singles', 'Womens Singles']:
            # Singles match - get player details
            if match_dict['player1_id']:
                cursor.execute("""
                    SELECT name, email, emp_id FROM participants WHERE id = ?
                """, (match_dict['player1_id'],))
                player1 = cursor.fetchone()
                if player1:
                    match_dict['player1_name'] = player1[0]
                    match_dict['player1_email'] = player1[1]
                    match_dict['player1_emp_id'] = player1[2]
            
            if match_dict['player2_id']:
                cursor.execute("""
                    SELECT name, email, emp_id FROM participants WHERE id = ?
                """, (match_dict['player2_id'],))
                player2 = cursor.fetchone()
                if player2:
                    match_dict['player2_name'] = player2[0]
                    match_dict['player2_email'] = player2[1]
                    match_dict['player2_emp_id'] = player2[2]
        else:
            # Doubles match - get team details
            if match_dict['team1_player1_id']:
                cursor.execute("""
                    SELECT name, email, emp_id FROM participants WHERE id = ?
                """, (match_dict['team1_player1_id'],))
                team1_player1 = cursor.fetchone()
                if team1_player1:
                    match_dict['team1_player1_name'] = team1_player1[0]
                    match_dict['team1_player1_email'] = team1_player1[1]
                    match_dict['team1_player1_emp_id'] = team1_player1[2]
            
            if match_dict['team1_player2_id']:
                cursor.execute("""
                    SELECT name, email, emp_id FROM participants WHERE id = ?
                """, (match_dict['team1_player2_id'],))
                team1_player2 = cursor.fetchone()
                if team1_player2:
                    match_dict['team1_player2_name'] = team1_player2[0]
                    match_dict['team1_player2_email'] = team1_player2[1]
                    match_dict['team1_player2_emp_id'] = team1_player2[2]
            
            if match_dict['team2_player1_id']:
                cursor.execute("""
                    SELECT name, email, emp_id FROM participants WHERE id = ?
                """, (match_dict['team2_player1_id'],))
                team2_player1 = cursor.fetchone()
                if team2_player1:
                    match_dict['team2_player1_name'] = team2_player1[0]
                    match_dict['team2_player1_email'] = team2_player1[1]
                    match_dict['team2_player1_emp_id'] = team2_player1[2]
            
            if match_dict['team2_player2_id']:
                cursor.execute("""
                    SELECT name, email, emp_id FROM participants WHERE id = ?
                """, (match_dict['team2_player2_id'],))
                team2_player2 = cursor.fetchone()
                if team2_player2:
                    match_dict['team2_player2_name'] = team2_player2[0]
                    match_dict['team2_player2_email'] = team2_player2[1]
                    match_dict['team2_player2_emp_id'] = team2_player2[2]
        
        conn.close()
        return match_dict
    except Exception as e:
        st.error(f"Error retrieving match details: {str(e)}")
        return None

def get_upcoming_matches(limit=50):
    """
    Get upcoming (scheduled) matches with participant details.
    
    Args:
        limit (int): Maximum number of matches to retrieve
        
    Returns:
        DataFrame: DataFrame containing upcoming match information
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get matches that are scheduled (not completed)
        matches_df = pd.read_sql_query("""
            SELECT * FROM matches 
            WHERE match_status = 'scheduled' 
            ORDER BY round_number ASC, id ASC
            LIMIT ?
        """, conn, params=(limit,))
        
        if matches_df.empty:
            conn.close()
            return pd.DataFrame()
        
        # Get participants data for additional details
        participants_df = pd.read_sql_query("SELECT * FROM participants", conn)
        conn.close()
        
        # Add player/team names to matches
        for idx, match in matches_df.iterrows():
            if match['category'] in ['Mens Singles', 'Womens Singles']:
                # Singles match
                player1 = participants_df[participants_df['id'] == match['player1_id']]
                player2 = participants_df[participants_df['id'] == match['player2_id']]
                
                matches_df.at[idx, 'player1_name'] = player1['name'].iloc[0] if not player1.empty else "TBD"
                matches_df.at[idx, 'player2_name'] = player2['name'].iloc[0] if not player2.empty else "TBD"
                matches_df.at[idx, 'player1_email'] = player1['email'].iloc[0] if not player1.empty else ""
                matches_df.at[idx, 'player2_email'] = player2['email'].iloc[0] if not player2.empty else ""
            else:
                # Doubles match
                team1_player1 = participants_df[participants_df['id'] == match['team1_player1_id']]
                team1_player2 = participants_df[participants_df['id'] == match['team1_player2_id']]
                team2_player1 = participants_df[participants_df['id'] == match['team2_player1_id']]
                team2_player2 = participants_df[participants_df['id'] == match['team2_player2_id']]
                
                team1_player1_name = team1_player1['name'].iloc[0] if not team1_player1.empty else "TBD"
                team1_player2_name = team1_player2['name'].iloc[0] if not team1_player2.empty else "TBD"
                team2_player1_name = team2_player1['name'].iloc[0] if not team2_player1.empty else "TBD"
                team2_player2_name = team2_player2['name'].iloc[0] if not team2_player2.empty else "TBD"
                
                matches_df.at[idx, 'team1_player1_name'] = team1_player1_name
                matches_df.at[idx, 'team1_player2_name'] = team1_player2_name
                matches_df.at[idx, 'team2_player1_name'] = team2_player1_name
                matches_df.at[idx, 'team2_player2_name'] = team2_player2_name
                
                matches_df.at[idx, 'team1_names'] = f"{team1_player1_name} & {team1_player2_name}"
                matches_df.at[idx, 'team2_names'] = f"{team2_player1_name} & {team2_player2_name}"
        
        return matches_df
    except Exception as e:
        st.error(f"Error retrieving upcoming matches: {str(e)}")
        return pd.DataFrame()

def get_recent_winners(limit=20):
    """
    Get recently completed matches with winner details.
    
    Args:
        limit (int): Maximum number of matches to retrieve
        
    Returns:
        DataFrame: DataFrame containing completed matches with winner information
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get completed matches with winners
        matches_df = pd.read_sql_query("""
            SELECT * FROM matches 
            WHERE match_status = 'completed' 
            ORDER BY completed_at DESC
            LIMIT ?
        """, conn, params=(limit,))
        
        if matches_df.empty:
            conn.close()
            return pd.DataFrame()
        
        # Get participants data for additional details
        participants_df = pd.read_sql_query("SELECT * FROM participants", conn)
        conn.close()
        
        # Add winner details to matches
        for idx, match in matches_df.iterrows():
            if match['category'] in ['Mens Singles', 'Womens Singles']:
                # Singles match
                winner = participants_df[participants_df['id'] == match['winner_id']]
                player1 = participants_df[participants_df['id'] == match['player1_id']]
                player2 = participants_df[participants_df['id'] == match['player2_id']]
                
                matches_df.at[idx, 'winner_name'] = winner['name'].iloc[0] if not winner.empty else "Unknown"
                matches_df.at[idx, 'winner_email'] = winner['email'].iloc[0] if not winner.empty else ""
                matches_df.at[idx, 'player1_name'] = player1['name'].iloc[0] if not player1.empty else "Unknown"
                matches_df.at[idx, 'player2_name'] = player2['name'].iloc[0] if not player2.empty else "Unknown"
            else:
                # Doubles match
                team1_player1 = participants_df[participants_df['id'] == match['team1_player1_id']]
                team1_player2 = participants_df[participants_df['id'] == match['team1_player2_id']]
                team2_player1 = participants_df[participants_df['id'] == match['team2_player1_id']]
                team2_player2 = participants_df[participants_df['id'] == match['team2_player2_id']]
                
                team1_player1_name = team1_player1['name'].iloc[0] if not team1_player1.empty else "Unknown"
                team1_player2_name = team1_player2['name'].iloc[0] if not team1_player2.empty else "Unknown"
                team2_player1_name = team2_player1['name'].iloc[0] if not team2_player1.empty else "Unknown"
                team2_player2_name = team2_player2['name'].iloc[0] if not team2_player2.empty else "Unknown"
                
                # Determine winning team
                if match['winner_team'] == 1:
                    winner_team_names = f"{team1_player1_name} & {team1_player2_name}"
                else:
                    winner_team_names = f"{team2_player1_name} & {team2_player2_name}"
                
                matches_df.at[idx, 'winner_team_names'] = winner_team_names
                matches_df.at[idx, 'team1_names'] = f"{team1_player1_name} & {team1_player2_name}"
                matches_df.at[idx, 'team2_names'] = f"{team2_player1_name} & {team2_player2_name}"
        
        return matches_df
    except Exception as e:
        st.error(f"Error retrieving recent winners: {str(e)}")
        return pd.DataFrame()

def send_outlook_email(recipients, subject, body, html_body=None, save_copy=True, draft_only=False, open_outlook=False):
    """
    Send an email using the Outlook desktop application.
    
    Args:
        recipients (str or list): Email recipient(s)
        subject (str): Email subject
        body (str): Email body text
        html_body (str, optional): HTML formatted email body
        save_copy (bool): Whether to save a copy in the Sent Items folder
        draft_only (bool): If True, save as draft instead of sending
        open_outlook (bool): If True, attempt to open Outlook after creating drafts
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    if not OUTLOOK_AVAILABLE:
        st.warning("⚠️ Email functionality is not available on this platform. This feature requires Microsoft Outlook on Windows.")
        return False
        
    try:
        # Initialize COM for this thread (required for multithreaded applications)
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        mail = outlook.CreateItem(0)  # olMailItem
        
        # Set recipients
        if isinstance(recipients, list):
            mail.To = "; ".join(recipients)
        else:
            mail.To = recipients
            
        # Set subject and body
        mail.Subject = subject
        if html_body:
            mail.HTMLBody = html_body
        else:
            mail.Body = body
        
        # Try to save to sent items folder for both old and new Outlook
        if save_copy:
            try:
                # Method for older Outlook versions
                mail.SaveSentMessageFolder = namespace.GetDefaultFolder(5)  # 5 = olFolderSentMail
            except Exception as save_error:
                # For newer Outlook versions, this property might be handled differently
                # The default behavior should save to sent items anyway
                pass
        
        # If draft_only is True, save as draft instead of sending
        if draft_only:
            mail.Save()  # Save as draft
            
            # Try to open Outlook if requested
            if open_outlook:
                try:
                    # Try to make Outlook visible
                    outlook_app = outlook.Application
                    outlook_app.ActiveExplorer().Activate()
                except:
                    # If that fails, try to launch Outlook via shell
                    try:
                        import os
                        os.system('start outlook.exe')
                    except:
                        pass
            
            pythoncom.CoUninitialize()
            return True
        else:
            # Send the email
            mail.Send()
            pythoncom.CoUninitialize()
            return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        try:
            pythoncom.CoUninitialize()
        except:
            pass
        return False


def get_match_details(match_id):
    """
    Get detailed information about a match including participant names and emails.
    
    Args:
        match_id (int): ID of the match
        
    Returns:
        dict: Dictionary containing match details
    """
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # Get match information
        match_query = """
        SELECT * FROM matches WHERE id = ?
        """
        match_df = pd.read_sql_query(match_query, conn, params=(match_id,))
        
        if match_df.empty:
            conn.close()
            return None
            
        match_data = match_df.iloc[0].to_dict()
        
        # Get participant information based on category
        if 'Singles' in match_data['category']:
            # Singles match
            player1_query = "SELECT * FROM participants WHERE id = ?"
            player2_query = "SELECT * FROM participants WHERE id = ?"
            
            player1_df = pd.read_sql_query(player1_query, conn, params=(match_data['player1_id'],))
            player2_df = pd.read_sql_query(player2_query, conn, params=(match_data['player2_id'],))
            
            if not player1_df.empty:
                match_data['player1_name'] = player1_df.iloc[0]['name']
                match_data['player1_email'] = player1_df.iloc[0]['email']
                match_data['player1_emp_id'] = player1_df.iloc[0]['emp_id']
            
            if not player2_df.empty:
                match_data['player2_name'] = player2_df.iloc[0]['name']
                match_data['player2_email'] = player2_df.iloc[0]['email']
                match_data['player2_emp_id'] = player2_df.iloc[0]['emp_id']
                
        else:
            # Doubles match
            team1_player1_query = "SELECT * FROM participants WHERE id = ?"
            team1_player2_query = "SELECT * FROM participants WHERE id = ?"
            team2_player1_query = "SELECT * FROM participants WHERE id = ?"
            team2_player2_query = "SELECT * FROM participants WHERE id = ?"
            
            team1_player1_df = pd.read_sql_query(team1_player1_query, conn, params=(match_data['team1_player1_id'],))
            team1_player2_df = pd.read_sql_query(team1_player2_query, conn, params=(match_data['team1_player2_id'],))
            team2_player1_df = pd.read_sql_query(team2_player1_query, conn, params=(match_data['team2_player1_id'],))
            team2_player2_df = pd.read_sql_query(team2_player2_query, conn, params=(match_data['team2_player2_id'],))
            
            if not team1_player1_df.empty:
                match_data['team1_player1_name'] = team1_player1_df.iloc[0]['name']
                match_data['team1_player1_email'] = team1_player1_df.iloc[0]['email']
                match_data['team1_player1_emp_id'] = team1_player1_df.iloc[0]['emp_id']
                
            if not team1_player2_df.empty:
                match_data['team1_player2_name'] = team1_player2_df.iloc[0]['name']
                match_data['team1_player2_email'] = team1_player2_df.iloc[0]['email']
                match_data['team1_player2_emp_id'] = team1_player2_df.iloc[0]['emp_id']
                
            if not team2_player1_df.empty:
                match_data['team2_player1_name'] = team2_player1_df.iloc[0]['name']
                match_data['team2_player1_email'] = team2_player1_df.iloc[0]['email']
                match_data['team2_player1_emp_id'] = team2_player1_df.iloc[0]['emp_id']
                
            if not team2_player2_df.empty:
                match_data['team2_player2_name'] = team2_player2_df.iloc[0]['name']
                match_data['team2_player2_email'] = team2_player2_df.iloc[0]['email']
                match_data['team2_player2_emp_id'] = team2_player2_df.iloc[0]['emp_id']
        
        conn.close()
        return match_data
    except Exception as e:
        st.error(f"Error retrieving match details: {str(e)}")
        conn.close()
        return None


def get_upcoming_matches():
    """
    Get all upcoming matches (scheduled but not completed)
    
    Returns:
        DataFrame: DataFrame containing upcoming match details
    """
    conn = sqlite3.connect(DB_PATH)
    
    try:
        query = """
        SELECT * FROM matches 
        WHERE match_status = 'scheduled' 
        ORDER BY round_number, category
        """
        
        matches_df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Enhance with participant names
        if not matches_df.empty:
            # Create columns for participant names
            matches_df['player1_name'] = ''
            matches_df['player2_name'] = ''
            matches_df['team1_names'] = ''
            matches_df['team2_names'] = ''
            
            # Get all participants
            participants_df = get_participants()
            
            # Map IDs to names
            for idx, match in matches_df.iterrows():
                if 'Singles' in match['category']:
                    # Singles match
                    if match['player1_id']:
                        player1 = participants_df[participants_df['id'] == match['player1_id']]
                        if not player1.empty:
                            matches_df.at[idx, 'player1_name'] = player1.iloc[0]['name']
                    
                    if match['player2_id']:
                        player2 = participants_df[participants_df['id'] == match['player2_id']]
                        if not player2.empty:
                            matches_df.at[idx, 'player2_name'] = player2.iloc[0]['name']
                else:
                    # Doubles match
                    team1_names = []
                    team2_names = []
                    
                    if match['team1_player1_id']:
                        player = participants_df[participants_df['id'] == match['team1_player1_id']]
                        if not player.empty:
                            team1_names.append(player.iloc[0]['name'])
                    
                    if match['team1_player2_id']:
                        player = participants_df[participants_df['id'] == match['team1_player2_id']]
                        if not player.empty:
                            team1_names.append(player.iloc[0]['name'])
                    
                    if match['team2_player1_id']:
                        player = participants_df[participants_df['id'] == match['team2_player1_id']]
                        if not player.empty:
                            team2_names.append(player.iloc[0]['name'])
                    
                    if match['team2_player2_id']:
                        player = participants_df[participants_df['id'] == match['team2_player2_id']]
                        if not player.empty:
                            team2_names.append(player.iloc[0]['name'])
                    
                    matches_df.at[idx, 'team1_names'] = ' & '.join(team1_names)
                    matches_df.at[idx, 'team2_names'] = ' & '.join(team2_names)
        
        return matches_df
    except Exception as e:
        st.error(f"Error retrieving upcoming matches: {str(e)}")
        conn.close()
        return pd.DataFrame()


def get_recent_winners(limit=10):
    """
    Get recent match winners
    
    Args:
        limit (int): Maximum number of recent winners to retrieve
        
    Returns:
        DataFrame: DataFrame containing recent winners
    """
    conn = sqlite3.connect(DB_PATH)
    
    try:
        query = """
        SELECT * FROM matches 
        WHERE match_status = 'completed' 
        ORDER BY updated_at DESC
        LIMIT ?
        """
        
        matches_df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()
        
        # Get all participants
        participants_df = get_participants()
        
        # Add winner information
        if not matches_df.empty:
            # Create columns for winner names
            matches_df['winner_name'] = ''
            matches_df['winner_team_names'] = ''
            
            # Map IDs to names
            for idx, match in matches_df.iterrows():
                if 'Singles' in match['category']:
                    # Singles match
                    if match['winner_id']:
                        winner = participants_df[participants_df['id'] == match['winner_id']]
                        if not winner.empty:
                            matches_df.at[idx, 'winner_name'] = winner.iloc[0]['name']
                else:
                    # Doubles match - winner is a team
                    if match['winner_team'] == 'team1':
                        team_names = []
                        
                        if match['team1_player1_id']:
                            player = participants_df[participants_df['id'] == match['team1_player1_id']]
                            if not player.empty:
                                team_names.append(player.iloc[0]['name'])
                        
                        if match['team1_player2_id']:
                            player = participants_df[participants_df['id'] == match['team1_player2_id']]
                            if not player.empty:
                                team_names.append(player.iloc[0]['name'])
                                 
                        matches_df.at[idx, 'winner_team_names'] = ' & '.join(team_names)
                    
                    elif match['winner_team'] == 'team2':
                        team_names = []
                        
                        if match['team2_player1_id']:
                            player = participants_df[participants_df['id'] == match['team2_player1_id']]
                            if not player.empty:
                                team_names.append(player.iloc[0]['name'])
                        
                        if match['team2_player2_id']:
                            player = participants_df[participants_df['id'] == match['team2_player2_id']]
                            if not player.empty:
                                team_names.append(player.iloc[0]['name'])
                                 
                        matches_df.at[idx, 'winner_team_names'] = ' & '.join(team_names)
        
        return matches_df
    except Exception as e:
        st.error(f"Error retrieving recent winners: {str(e)}")
        conn.close()
        return pd.DataFrame()

# Initialize database
init_database()

# Main application with tabs
st.title("🏆 Tournament Manager")
st.markdown("<div style='background: linear-gradient(90deg, #5bc0be 0%, #3a506b 100%); padding: 10px; border-radius: 10px; margin-bottom: 20px;'><h3 style='color: white; margin:0; text-align:center; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);'>Welcome to the Tournament Management System</h3></div>", unsafe_allow_html=True)

# Global Game Selection
st.sidebar.markdown("### 🎮 Game Selection")
selected_game = st.sidebar.selectbox(
    "Choose Game:",
    ["Carrom", "Chess", "Badminton", "Table Tennis"],
    index=0,
    help="Select the game type for this tournament session"
)
st.sidebar.markdown(f"**Current Game:** {selected_game}")
st.sidebar.divider()

# Store selected game in session state
if 'selected_game' not in st.session_state:
    st.session_state.selected_game = selected_game
else:
    st.session_state.selected_game = selected_game

# Create tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "📊 Dashboard", 
    "📥 Import Participants", 
    "📝 Registration Desk", 
    "📅 Fixtures", 
    "🏟️ Matches", 
    "🏆 Tournament Bracket", 
    "👑 Winners", 
    "📊 Reports & Export",
    "📋 Tournament Tracker",
    "📧 Email Notifications"
])

with tab1:
    # Dashboard content
    st.subheader("📊 Tournament Overview")
    
    # Get current statistics
    participants_df = get_participants()
    matches_df = get_matches()
    
    # Simple statistics section
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Participants", len(participants_df))
    
    with col2:
        reported_count = len(participants_df[participants_df['registered_at_desk'] == 1]) if not participants_df.empty else 0
        st.metric("Reported at Desk", reported_count)
    
    with col3:
        st.metric("Total Matches", len(matches_df))
    
    with col4:
        completed_count = len(matches_df[matches_df['match_status'] == 'completed']) if not matches_df.empty else 0
        st.metric("Completed Matches", completed_count)
    
    # Recent activity
    if not matches_df.empty:
        st.subheader("📋 Recent Activity")
        recent_matches = matches_df.head(5)
        st.dataframe(recent_matches[['category', 'player1_name', 'player2_name', 'match_status']], use_container_width=True)
    else:
        st.info("No matches found. Create some matches to see recent activity.")
    
    # Help section
    st.subheader("💡 Getting Started")
    st.info("""
    1. **Import Participants**: Upload an Excel file with participant data
    2. **Registration Desk**: Mark participants as reported when they arrive
    3. **Create Matches**: Set up matches between reported participants
    4. **Record Results**: Update match results and determine winners
    5. **View Bracket**: Monitor tournament progress
    6. **Generate Reports**: Export data and create summaries
    """)

with tab2:
    # Import Participants
    st.subheader("📥 Import Participants")
    
    # Initialize form key for resetting the form
    if 'form_key' not in st.session_state:
        st.session_state.form_key = 0
    
    # Function to reset form by incrementing the key
    def reset_form():
        st.session_state.form_key += 1
    
    # Manual Entry Form
    st.subheader("✏️ Manual Entry")
    with st.form(key=f"manual_participant_entry_{st.session_state.form_key}"):
        col1, col2, col3 = st.columns(3)
        with col1:
            emp_id = st.text_input("Employee ID*")
            name = st.text_input("Name*")
            email = st.text_input("Email*")
            location = st.text_input("Location")
            sub_location = st.text_input("Sub Location")
        with col2:
            game = st.text_input("Game", value=st.session_state.selected_game, disabled=True)
            category = st.selectbox("Category*", ["Mens Singles", "Womens Singles", "Mens Doubles", "Womens Doubles", "Mixed Doubles"])
            slot = st.selectbox("Slot", ["Morning", "Afternoon", "Evening", ""], index=3)
            round_number = st.selectbox("Round Number", [1, 2, 3, 4, 5, 6], index=0)
            gender = st.selectbox("Gender", ["Male", "Female", ""], index=2)
        with col3:
            partner_emp_id = st.text_input("Partner Employee ID (for doubles/mixed)")
            partner_gender = st.selectbox("Partner Gender", ["Male", "Female", ""], index=2)
            
            # Help text for doubles categories
            if 'Doubles' in category:
                st.info("ℹ️ For doubles categories, please provide partner information.")
        
        if st.form_submit_button("Add Participant"):
            # Debug info
            st.write(f"Form submitted with: {emp_id}, {name}, {email}, {category}, {partner_emp_id}")
            
            if emp_id and name and email and category:
                try:
                    # Check if this is a doubles category
                    is_doubles = 'Doubles' in category
                    
                    # For doubles categories, make sure partner_emp_id is provided
                    if is_doubles and not partner_emp_id:
                        st.warning("⚠️ This is a doubles category. Please provide a Partner Employee ID.")
                    else:
                        # Add the participant with all fields
                        add_participant_extended(
                            emp_id=emp_id, 
                            name=name, 
                            email=email, 
                            location=location,
                            sub_location=sub_location,
                            game=game,
                            category=category, 
                            slot=slot,
                            partner_emp_id=partner_emp_id if partner_emp_id else None,
                            gender=gender,
                            partner_gender=partner_gender
                        )
                        
                        # If this is a doubles category, automatically create the partner if they don't exist
                        if is_doubles and partner_emp_id:
                            partner_created = ensure_partner_exists(partner_emp_id, category)
                            if partner_created:
                                st.info(f"💡 Created placeholder entry for partner with ID {partner_emp_id}. You can update their details later.")
                        
                        # Success message
                        st.success(f"✅ Successfully added {name} ({emp_id})")
                        
                        # Reset form by incrementing the form key
                        reset_form()
                        
                        # Rerun the app to show the cleared form
                        st.rerun()
                except sqlite3.IntegrityError as ie:
                    if "UNIQUE constraint failed" in str(ie):
                        st.error(f"❌ Employee ID '{emp_id}' already exists. Please use a different Employee ID.")
                    else:
                        st.error(f"❌ Database error: {str(ie)}")
                except Exception as e:
                    st.error(f"❌ Error adding participant: {str(e)}")
                    st.error(f"Detailed error: {type(e).__name__}: {str(e)}")
            else:
                st.error("❌ Please fill all required fields (marked with *)")
                # Show which fields are missing
                missing = []
                if not emp_id: missing.append("Employee ID")
                if not name: missing.append("Name")
                if not email: missing.append("Email")
                if not category: missing.append("Category")
                st.error(f"Missing fields: {', '.join(missing)}")

    
    st.divider()
    
    # Excel Upload
    st.subheader("📊 Excel Import")
    uploaded_file = st.file_uploader("Upload Excel file with participant data", type=['xlsx', 'xls'])
    
    # Check if import was just completed (hide preview after import)
    if 'import_completed' not in st.session_state:
        st.session_state.import_completed = False
        
    # Initialize column mapping in session state if not exists
    if 'column_mapping' not in st.session_state:
        st.session_state.column_mapping = {
            'emp_id': 'emp_id',
            'name': 'name',
            'email': 'email',
            'location': 'location',
            'sub_location': 'sub_location',
            'game': 'game',
            'category': 'category',
            'slot': 'slot',
            'partner_emp_id': 'partner_emp_id',
            'gender': 'gender',
            'partner_gender': 'partner_gender'
        }
    
    if uploaded_file is not None and not st.session_state.import_completed:
        try:
            df = pd.read_excel(uploaded_file)
            
            st.success(f"✅ File uploaded successfully! Found {len(df)} rows of data.")
            
            # Show file info
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"📊 **File Info:**\n- Filename: {uploaded_file.name}\n- Rows: {len(df)}\n- Columns: {len(df.columns)}")
            with col2:
                st.info(f"📋 **Columns Found:**\n" + "\n".join([f"- {col}" for col in df.columns.tolist()]))
            
            st.subheader("📖 Data Preview")
            st.write("First 10 rows of your data:")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Show column mapping UI
            st.subheader("🔄 Column Mapping")
            st.write("Map your Excel columns to the required fields. This allows flexibility in your Excel format.")
            
            # Create column mapping UI
            with st.expander("📋 Edit Column Mapping", expanded=True):
                col1, col2 = st.columns(2)
                
                # Required fields
                with col1:
                    st.markdown("**Required Fields**")
                    st.session_state.column_mapping['emp_id'] = st.selectbox(
                        "Employee ID*", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['emp_id']) + 1 if st.session_state.column_mapping['emp_id'] in df.columns else 0
                    )
                    st.session_state.column_mapping['name'] = st.selectbox(
                        "Name*", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['name']) + 1 if st.session_state.column_mapping['name'] in df.columns else 0
                    )
                    st.session_state.column_mapping['email'] = st.selectbox(
                        "Email*", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['email']) + 1 if st.session_state.column_mapping['email'] in df.columns else 0
                    )
                    st.session_state.column_mapping['category'] = st.selectbox(
                        "Category*", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['category']) + 1 if st.session_state.column_mapping['category'] in df.columns else 0
                    )
                
                # Optional fields
                with col2:
                    st.markdown("**Optional Fields**")
                    st.session_state.column_mapping['location'] = st.selectbox(
                        "Location", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['location']) + 1 if st.session_state.column_mapping['location'] in df.columns else 0
                    )
                    st.session_state.column_mapping['sub_location'] = st.selectbox(
                        "Sub Location", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['sub_location']) + 1 if st.session_state.column_mapping['sub_location'] in df.columns else 0
                    )
                    st.session_state.column_mapping['game'] = st.selectbox(
                        "Game", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['game']) + 1 if st.session_state.column_mapping['game'] in df.columns else 0
                    )
                    st.session_state.column_mapping['slot'] = st.selectbox(
                        "Slot", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['slot']) + 1 if st.session_state.column_mapping['slot'] in df.columns else 0
                    )
                    st.session_state.column_mapping['partner_emp_id'] = st.selectbox(
                        "Partner Employee ID", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['partner_emp_id']) + 1 if st.session_state.column_mapping['partner_emp_id'] in df.columns else 0
                    )
                    st.session_state.column_mapping['gender'] = st.selectbox(
                        "Gender", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['gender']) + 1 if st.session_state.column_mapping['gender'] in df.columns else 0
                    )
                    st.session_state.column_mapping['partner_gender'] = st.selectbox(
                        "Partner Gender", 
                        options=[''] + df.columns.tolist(),
                        index=df.columns.tolist().index(st.session_state.column_mapping['partner_gender']) + 1 if st.session_state.column_mapping['partner_gender'] in df.columns else 0
                    )
            
            # Validate required columns based on mapping
            required_fields = ['emp_id', 'name', 'email', 'category']
            missing_fields = [field for field in required_fields if not st.session_state.column_mapping[field]]
            
            if missing_fields:
                st.error(f"❌ **Missing Required Field Mappings:** {', '.join(missing_fields)}")
                st.info("📝 **Required Fields:** You must map Employee ID, Name, Email, and Category to columns in your Excel file.")
                
                st.subheader("📋 Expected Format")
                st.write("Your Excel file should have columns that can be mapped to these fields:")
                expected_format = pd.DataFrame({
                    'emp_id': ['EMP001', 'EMP002', '...'],
                    'name': ['John Doe', 'Jane Smith', '...'],
                    'email': ['john@company.com', 'jane@company.com', '...'],
                    'category': ['Mens Singles', 'Womens Singles', '...'],
                    'location': ['Bangalore', 'Chennai', '...'],
                    'sub_location': ['East Campus', 'Main Building', '...'],
                    'game': ['Carrom', 'Carrom', '...'],
                    'slot': ['Morning', 'Afternoon', '...'],
                    'partner_emp_id': ['', 'EMP003', '...'],
                    'gender': ['Male', 'Female', '...'],
                    'partner_gender': ['', 'Male', '...']
                })
                st.dataframe(expected_format)
            else:
                st.success("✅ **Column Mapping Successful!** All required fields are mapped.")
                
                # Create a clean dataframe with mapped columns
                df_clean = pd.DataFrame()
                
                # Map the required columns
                for field in ['emp_id', 'name', 'email', 'category']:
                    if st.session_state.column_mapping[field]:
                        df_clean[field] = df[st.session_state.column_mapping[field]].copy()
                    else:
                        st.error(f"Missing required field mapping: {field}")
                        break
                
                # Map optional columns if they exist in the mapping
                for field in ['location', 'sub_location', 'game', 'slot', 'partner_emp_id', 'gender', 'partner_gender']:
                    if st.session_state.column_mapping[field]:
                        df_clean[field] = df[st.session_state.column_mapping[field]].copy()
                    else:
                        # Add empty column for optional fields
                        df_clean[field] = ''
                        if field == 'game':
                            df_clean[field] = 'Carrom'  # Default value for game
                
                # Add registered_at_desk column with default value
                df_clean['registered_at_desk'] = 0
                
                # Data validation summary
                st.subheader("🔍 Data Validation Summary")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    unique_empids = df_clean['emp_id'].nunique()
                    total_empids = len(df_clean)
                    if unique_empids == total_empids:
                        st.success(f"✅ All Employee IDs unique ({unique_empids})")
                    else:
                        st.warning(f"⚠️ Duplicate Employee IDs found ({total_empids - unique_empids} duplicates)")
                
                with col2:
                    categories = df_clean['category'].value_counts()
                    st.info(f"📊 Categories found:\n" + "\n".join([f"• {cat}: {count}" for cat, count in categories.items()]))
                
                with col3:
                    partners = len(df_clean[df_clean['partner_emp_id'] != ''])
                    st.info(f"👥 Participants with partners: {partners}")
                
                st.write(f"📥 **Ready to import {len(df_clean)} participants**")
                
                if st.button("Import Data", type="primary"):
                    # Show progress
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        
                        imported_count = 0
                        skipped_count = 0
                        errors = []
                        total_rows = len(df_clean)
                        
                        status_text.text("Starting import...")
                        
                        for idx, row in df_clean.iterrows():
                            # Update progress
                            progress = (idx + 1) / total_rows
                            progress_bar.progress(progress)
                            status_text.text(f"Processing participant {idx + 1} of {total_rows}: {row['name']}")
                            
                            try:
                                cursor.execute('''
                                    INSERT INTO participants (emp_id, name, email, location, sub_location, game, category, slot, 
                                                          partner_emp_id, gender, partner_gender, registered_at_desk)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    row['emp_id'], 
                                    row['name'], 
                                    row['email'],
                                    row['location'] if 'location' in row and row['location'] else None,
                                    row['sub_location'] if 'sub_location' in row and row['sub_location'] else None,
                                    row['game'] if 'game' in row and row['game'] else 'Carrom',
                                    row['category'], 
                                    row['slot'] if 'slot' in row and row['slot'] else None,
                                    row['partner_emp_id'] if 'partner_emp_id' in row and row['partner_emp_id'] else None,
                                    row['gender'] if 'gender' in row and row['gender'] else None,
                                    row['partner_gender'] if 'partner_gender' in row and row['partner_gender'] else None,
                                    row['registered_at_desk']
                                ))
                                imported_count += 1
                            except sqlite3.IntegrityError as ie:
                                if "UNIQUE constraint failed" in str(ie):
                                    skipped_count += 1
                                    errors.append(f"Skipped {row['emp_id']} - {row['name']} (Employee ID already exists)")
                                else:
                                    errors.append(f"Error with {row['emp_id']} - {row['name']}: {str(ie)}")
                            except Exception as e:
                                errors.append(f"Unexpected error with {row['emp_id']} - {row['name']}: {str(e)}")
                        
                        conn.commit()
                        conn.close()
                        
                        # Clear progress indicators
                        progress_bar.empty()
                        status_text.empty()
                        
                        # Show detailed results
                        st.success("✅ Import completed!")
                        
                        # Results summary
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("✅ Successfully Imported", imported_count)
                        with col2:
                            st.metric("⚠️ Skipped (Duplicates)", skipped_count)
                        with col3:
                            st.metric("❌ Errors", len(errors) - skipped_count if len(errors) > skipped_count else 0)
                        
                        # Show specific messages
                        if imported_count > 0:
                            st.success(f"🎉 Successfully imported {imported_count} new participants!")
                        
                        if skipped_count > 0:
                            st.warning(f"⚠️ Skipped {skipped_count} participants because their Employee IDs already exist in the database.")
                        
                        if errors:
                            with st.expander(f"📋 View Details ({len(errors)} issues found)", expanded=False):
                                for i, error in enumerate(errors[:10], 1):  # Show first 10 errors
                                    st.write(f"{i}. {error}")
                                if len(errors) > 10:
                                    st.write(f"... and {len(errors) - 10} more issues")
                        
                        # Auto-refresh if data was imported
                        if imported_count > 0:
                            st.balloons()  # Celebration animation
                            st.info("🔄 Refreshing page to show updated participant list...")
                            # Set flag to hide the preview after import
                            st.session_state.import_completed = True
                            st.rerun()
                            
                    except Exception as import_error:
                        progress_bar.empty()
                        status_text.empty()
                        st.error(f"❌ Import failed: {str(import_error)}")
                        st.error("Please check your Excel file format and try again.")
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")

    elif uploaded_file is not None and st.session_state.import_completed:
        # Show brief success message after import completion
        st.success("✅ Data import completed successfully!")
        st.info("📋 File preview hidden. Upload a new file to see preview again.")
        
        # Reset the flag when a new file is uploaded
        if st.button("Upload New File"):
            st.session_state.import_completed = False
            st.rerun()
    
    # Show sample template
    st.subheader("📋 Sample Template")
    sample_data = {
        'emp_id': [
            # Mens Singles
            'EMP001', 'EMP002', 'EMP003', 'EMP004', 'EMP005', 'EMP006',
            # Womens Singles  
            'EMP007', 'EMP008', 'EMP009', 'EMP010', 'EMP011', 'EMP012',
            # Mens Doubles
            'EMP013', 'EMP014', 'EMP015', 'EMP016', 'EMP017', 'EMP018', 'EMP019', 'EMP020',
            # Womens Doubles
            'EMP021', 'EMP022', 'EMP023', 'EMP024', 'EMP025', 'EMP026', 'EMP027', 'EMP028',
            # Mixed Doubles
            'EMP029', 'EMP030', 'EMP031', 'EMP032', 'EMP033', 'EMP034', 'EMP035', 'EMP036'
        ],
        'name': [
            # Mens Singles
            'John Doe', 'Michael Smith', 'David Johnson', 'Robert Brown', 'James Wilson', 'Christopher Davis',
            # Womens Singles
            'Sarah Miller', 'Jessica Garcia', 'Ashley Rodriguez', 'Amanda Martinez', 'Jennifer Lopez', 'Lisa Anderson',
            # Mens Doubles
            'Mark Thompson', 'Steven White', 'Kevin Harris', 'Brian Clark', 'Daniel Lewis', 'Ryan Walker', 'Jason Hall', 'Andrew Young',
            # Womens Doubles  
            'Emily King', 'Michelle Wright', 'Stephanie Green', 'Nicole Adams', 'Rachel Baker', 'Lauren Nelson', 'Samantha Hill', 'Christina Scott',
            # Mixed Doubles
            'Alex Turner', 'Maria Gonzalez', 'Thomas Campbell', 'Diana Parker', 'Jonathan Evans', 'Natalie Collins', 'Matthew Stewart', 'Isabella Morris'
        ],
        'email': [
            # Mens Singles
            'john.doe@company.com', 'michael.smith@company.com', 'david.johnson@company.com', 'robert.brown@company.com', 'james.wilson@company.com', 'christopher.davis@company.com',
            # Womens Singles
            'sarah.miller@company.com', 'jessica.garcia@company.com', 'ashley.rodriguez@company.com', 'amanda.martinez@company.com', 'jennifer.lopez@company.com', 'lisa.anderson@company.com',
            # Mens Doubles
            'mark.thompson@company.com', 'steven.white@company.com', 'kevin.harris@company.com', 'brian.clark@company.com', 'daniel.lewis@company.com', 'ryan.walker@company.com', 'jason.hall@company.com', 'andrew.young@company.com',
            # Womens Doubles
            'emily.king@company.com', 'michelle.wright@company.com', 'stephanie.green@company.com', 'nicole.adams@company.com', 'rachel.baker@company.com', 'lauren.nelson@company.com', 'samantha.hill@company.com', 'christina.scott@company.com',
            # Mixed Doubles
            'alex.turner@company.com', 'maria.gonzalez@company.com', 'thomas.campbell@company.com', 'diana.parker@company.com', 'jonathan.evans@company.com', 'natalie.collins@company.com', 'matthew.stewart@company.com', 'isabella.morris@company.com'
        ],
        'location': [
            # All participants
            'Bangalore', 'Chennai', 'Hyderabad', 'Pune', 'Mumbai', 'Delhi',
            'Bangalore', 'Chennai', 'Hyderabad', 'Pune', 'Mumbai', 'Delhi',
            'Bangalore', 'Bangalore', 'Chennai', 'Chennai', 'Hyderabad', 'Hyderabad', 'Pune', 'Pune',
            'Mumbai', 'Mumbai', 'Delhi', 'Delhi', 'Bangalore', 'Bangalore', 'Chennai', 'Chennai',
            'Hyderabad', 'Hyderabad', 'Pune', 'Pune', 'Mumbai', 'Mumbai', 'Delhi', 'Delhi'
        ],
        'sub_location': [
            # All participants
            'Main Campus', 'East Wing', 'Tech Park', 'Downtown', 'Central', 'North Block',
            'Main Campus', 'East Wing', 'Tech Park', 'Downtown', 'Central', 'North Block',
            'Main Campus', 'Main Campus', 'East Wing', 'East Wing', 'Tech Park', 'Tech Park', 'Downtown', 'Downtown',
            'Central', 'Central', 'North Block', 'North Block', 'Main Campus', 'Main Campus', 'East Wing', 'East Wing',
            'Tech Park', 'Tech Park', 'Downtown', 'Downtown', 'Central', 'Central', 'North Block', 'North Block'
        ],
        'game': ['Carrom'] * 36,  # All participants playing Carrom
        'category': [
            # Mens Singles (6 participants)
            'Mens Singles', 'Mens Singles', 'Mens Singles', 'Mens Singles', 'Mens Singles', 'Mens Singles',
            # Womens Singles (6 participants)
            'Womens Singles', 'Womens Singles', 'Womens Singles', 'Womens Singles', 'Womens Singles', 'Womens Singles',
            # Mens Doubles (8 participants - 4 pairs)
            'Mens Doubles', 'Mens Doubles', 'Mens Doubles', 'Mens Doubles', 'Mens Doubles', 'Mens Doubles', 'Mens Doubles', 'Mens Doubles',
            # Womens Doubles (8 participants - 4 pairs)
            'Womens Doubles', 'Womens Doubles', 'Womens Doubles', 'Womens Doubles', 'Womens Doubles', 'Womens Doubles', 'Womens Doubles', 'Womens Doubles',
            # Mixed Doubles (8 participants - 4 pairs)
            'Mixed Doubles', 'Mixed Doubles', 'Mixed Doubles', 'Mixed Doubles', 'Mixed Doubles', 'Mixed Doubles', 'Mixed Doubles', 'Mixed Doubles'
        ],
        'slot': [
            # Alternating Morning/Afternoon for all participants
            'Morning', 'Afternoon', 'Morning', 'Afternoon', 'Morning', 'Afternoon',
            'Morning', 'Afternoon', 'Morning', 'Afternoon', 'Morning', 'Afternoon',
            'Morning', 'Morning', 'Afternoon', 'Afternoon', 'Morning', 'Morning', 'Afternoon', 'Afternoon',
            'Morning', 'Morning', 'Afternoon', 'Afternoon', 'Morning', 'Morning', 'Afternoon', 'Afternoon',
            'Morning', 'Morning', 'Afternoon', 'Afternoon', 'Morning', 'Morning', 'Afternoon', 'Afternoon'
        ],
        'partner_emp_id': [
            # Mens Singles (no partners)
            '', '', '', '', '', '',
            # Womens Singles (no partners)
            '', '', '', '', '', '',
            # Mens Doubles (paired)
            'EMP014', 'EMP013', 'EMP016', 'EMP015', 'EMP018', 'EMP017', 'EMP020', 'EMP019',
            # Womens Doubles (paired)
            'EMP022', 'EMP021', 'EMP024', 'EMP023', 'EMP026', 'EMP025', 'EMP028', 'EMP027',
            # Mixed Doubles (paired)
            'EMP030', 'EMP029', 'EMP032', 'EMP031', 'EMP034', 'EMP033', 'EMP036', 'EMP035'
        ],
        'gender': [
            # Mens Singles and Doubles
            'Male', 'Male', 'Male', 'Male', 'Male', 'Male',
            # Womens Singles and Doubles
            'Female', 'Female', 'Female', 'Female', 'Female', 'Female',
            # Mens Doubles
            'Male', 'Male', 'Male', 'Male', 'Male', 'Male', 'Male', 'Male',
            # Womens Doubles
            'Female', 'Female', 'Female', 'Female', 'Female', 'Female', 'Female', 'Female',
            # Mixed Doubles (alternating Male/Female)
            'Male', 'Female', 'Male', 'Female', 'Male', 'Female', 'Male', 'Female'
        ],
        'partner_gender': [
            # Singles (no partners)
            '', '', '', '', '', '',
            '', '', '', '', '', '',
            # Mens Doubles (all Male partners)
            'Male', 'Male', 'Male', 'Male', 'Male', 'Male', 'Male', 'Male',
            # Womens Doubles (all Female partners)
            'Female', 'Female', 'Female', 'Female', 'Female', 'Female', 'Female', 'Female',
            # Mixed Doubles (alternating Female/Male)
            'Female', 'Male', 'Female', 'Male', 'Female', 'Male', 'Female', 'Male'
        ],
        'registered_at_desk': [0] * 36  # All participants start as not registered
    }
    sample_df = pd.DataFrame(sample_data)
    st.dataframe(sample_df)
    
    # Download template as Excel
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        sample_df.to_excel(writer, sheet_name='Participants', index=False)
    
    st.download_button(
        label="📥 Download Excel Template",
        data=buffer.getvalue(),
        file_name="participant_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with tab3:
    # Registration Desk
    st.subheader("📝 Registration Desk")
    
    # Add reset option 
    with st.expander("⚙️ Admin Options"):
        st.warning("⚠️ Danger Zone - These actions cannot be undone!")
        
        # Side by side layout for admin options
        col1, col2 = st.columns(2, gap="large")
        
        with col1:
            st.markdown("### 👥 Reset Participants Only")
            st.write("Delete all participant data but keep match history.")
            st.markdown("**What gets deleted:**")
            st.markdown("- All participant records")
            st.markdown("- Registration status")
            st.markdown("**What stays:**")
            st.markdown("- Match history and results")
            
            if st.button("🗑️ Reset All Participants", type="secondary", use_container_width=True):
                # Show confirmation dialog
                if "confirm_reset_participants" not in st.session_state:
                    st.session_state.confirm_reset_participants = True
                    st.rerun()
            
            # Check for confirmation state
            if st.session_state.get("confirm_reset_participants", False):
                st.error("⚠️ **CONFIRM DELETION**")
                st.warning("This will permanently delete ALL participant data!")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("�️ Yes, Delete All Participants", key="confirm_reset_participants_yes", type="primary"):
                        with st.spinner("�🔄 Resetting participants data..."):
                            try:
                                conn = sqlite3.connect(DB_PATH)
                                cursor = conn.cursor()
                                # Get count before deletion
                                cursor.execute("SELECT COUNT(*) FROM participants")
                                participant_count = cursor.fetchone()[0]
                                
                                if participant_count > 0:
                                    cursor.execute("DELETE FROM participants")
                                    conn.commit()
                                    conn.close()
                                    
                                    # Show success animation
                                    st.success(f"✅ Successfully deleted {participant_count} participants from the database!")
                                    st.balloons()  # Success animation
                                    st.info("🔄 Page will refresh to show updated data...")
                                    del st.session_state.confirm_reset_participants
                                    st.rerun()
                                else:
                                    conn.close()
                                    st.info("ℹ️ No participants found to delete.")
                                    del st.session_state.confirm_reset_participants
                            except Exception as e:
                                st.error(f"❌ Error resetting participants: {str(e)}")
                                del st.session_state.confirm_reset_participants
                with col_no:
                    if st.button("❌ Cancel", key="confirm_reset_participants_no", type="secondary"):
                        del st.session_state.confirm_reset_participants
                        st.rerun()
        
        with col2:
            st.markdown("### 🗂️ Reset All Tournament Data")
            st.write("Delete ALL data including participants and matches.")
            st.markdown("**What gets deleted:**")
            st.markdown("- All participant records")
            st.markdown("- All match records and results")
            st.markdown("- Complete tournament history")
            st.markdown("**⚠️ This action is irreversible!**")
            
            if st.button("🗑️ Reset All Data", type="secondary", use_container_width=True):
                # Show confirmation dialog
                if "confirm_reset_all_data" not in st.session_state:
                    st.session_state.confirm_reset_all_data = True
                    st.rerun()
            
            # Check for confirmation state
            if st.session_state.get("confirm_reset_all_data", False):
                st.error("⚠️ **CONFIRM COMPLETE RESET**")
                st.warning("This will permanently delete ALL tournament data including participants and matches!")
                st.markdown("**⚠️ THIS ACTION CANNOT BE UNDONE!**")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("🗑️ Yes, Delete Everything", key="confirm_reset_all_data_yes", type="primary"):
                        with st.spinner("🔄 Resetting all tournament data..."):
                            try:
                                conn = sqlite3.connect(DB_PATH)
                                cursor = conn.cursor()
                                
                                # Get counts before deletion
                                cursor.execute("SELECT COUNT(*) FROM participants")
                                participant_count = cursor.fetchone()[0]
                                cursor.execute("SELECT COUNT(*) FROM matches")
                                match_count = cursor.fetchone()[0]
                                
                                if participant_count > 0 or match_count > 0:
                                    cursor.execute("DELETE FROM participants")
                                    cursor.execute("DELETE FROM matches") 
                                    conn.commit()
                                    conn.close()
                                    
                                    # Show success animation
                                    st.success(f"✅ Successfully reset all tournament data!")
                                    st.info(f"📊 Deleted: {participant_count} participants and {match_count} matches")
                                    st.snow()  # Different animation for complete reset
                                    st.info("🔄 Page will refresh to show clean slate...")
                                    del st.session_state.confirm_reset_all_data
                                    st.rerun()
                                else:
                                    conn.close()
                                    st.info("ℹ️ No data found to delete.")
                                    del st.session_state.confirm_reset_all_data
                            except Exception as e:
                                st.error(f"❌ Error resetting data: {str(e)}")
                                del st.session_state.confirm_reset_all_data
                with col_no:
                    if st.button("❌ Cancel", key="confirm_reset_all_data_no", type="secondary"):
                        del st.session_state.confirm_reset_all_data
                        st.rerun()
    
    participants_df = get_participants()
    
    if participants_df.empty:
        st.info("No participants found. Please import participants first.")
    else:
        # Statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Participants", len(participants_df))
        with col2:
            reported_count = len(participants_df[participants_df['registered_at_desk'] == 1])
            st.metric("Reported", reported_count)
        with col3:
            pending_count = len(participants_df[participants_df['registered_at_desk'] == 0])
            st.metric("Pending", pending_count)
        
        st.divider()
        
        # Search and filters  
        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
        with col1:
            search_term = st.text_input("🔍 Search participants", placeholder="Search by Employee ID, name, email, category, or partner ID...")
        with col2:
            status_filter = st.selectbox("Status Filter", ["All", "Reported", "Not Reported"])
        with col3:
            # Filter categories by selected game
            game_participants = participants_df[participants_df['game'] == st.session_state.selected_game]
            categories = ["All"] + sorted(game_participants['category'].unique()) if not game_participants.empty else ["All"]
            category_filter = st.selectbox("Category Filter", categories)
        with col4:
            round_filter = st.selectbox("Round Filter", ["All", "Round 1", "Round 2", "Round 3", "Round 4", "Round 5", "Round 6"])
        with col5:
            # Game is already selected globally, show for reference
            st.write(f"**Game:** {st.session_state.selected_game}")
            game_filter = st.session_state.selected_game
        
        # Get participants who have completed matches
        conn = sqlite3.connect(DB_PATH)
        
        # For singles matches
        completed_singles_query = '''
        SELECT player1_id, player2_id FROM matches 
        WHERE match_status = 'completed' AND (player1_id IS NOT NULL OR player2_id IS NOT NULL)
        '''
        completed_singles = pd.read_sql_query(completed_singles_query, conn)
        
        # For doubles matches
        completed_doubles_query = '''
        SELECT team1_player1_id, team1_player2_id, team2_player1_id, team2_player2_id 
        FROM matches 
        WHERE match_status = 'completed' AND 
        (team1_player1_id IS NOT NULL OR team1_player2_id IS NOT NULL OR 
         team2_player1_id IS NOT NULL OR team2_player2_id IS NOT NULL)
        '''
        completed_doubles = pd.read_sql_query(completed_doubles_query, conn)
        conn.close()
        
        # Create a set of all participant IDs who have completed matches
        completed_participant_ids = set()
        
        # Add singles participants
        if not completed_singles.empty:
            completed_participant_ids.update(completed_singles['player1_id'].dropna().astype(int).tolist())
            completed_participant_ids.update(completed_singles['player2_id'].dropna().astype(int).tolist())
        
        # Add doubles participants
        if not completed_doubles.empty:
            completed_participant_ids.update(completed_doubles['team1_player1_id'].dropna().astype(int).tolist())
            completed_participant_ids.update(completed_doubles['team1_player2_id'].dropna().astype(int).tolist())
            completed_participant_ids.update(completed_doubles['team2_player1_id'].dropna().astype(int).tolist())
            completed_participant_ids.update(completed_doubles['team2_player2_id'].dropna().astype(int).tolist())
        
        # Apply search
        filtered_df = search_participants(search_term, participants_df)
        
        # Apply game filter (always filter by selected game)
        filtered_df = filtered_df[filtered_df['game'] == game_filter]
        
        # Remove participants who have completed matches
        filtered_df = filtered_df[~filtered_df['id'].isin(completed_participant_ids)]
        
        # Apply status filter
        if status_filter == "Reported":
            filtered_df = filtered_df[filtered_df['registered_at_desk'] == 1]
        elif status_filter == "Not Reported":
            filtered_df = filtered_df[filtered_df['registered_at_desk'] == 0]
        
        # Apply category filter
        if category_filter != "All":
            filtered_df = filtered_df[filtered_df['category'] == category_filter]
        
        if len(filtered_df) == 0 and (search_term or status_filter != "All" or category_filter != "All"):
            st.warning("No participants found matching your criteria.")
        else:
            st.write(f"Showing {len(filtered_df)} participants")
            
            # Table header
            header_cols = st.columns([1, 2, 2, 1.5, 2, 1.2, 1.2, 1.2, 1.2])
            with header_cols[0]:
                st.write("**Emp ID**")
            with header_cols[1]:
                st.write("**Name**")
            with header_cols[2]:
                st.write("**Email**")
            with header_cols[3]:
                st.write("**Category**")
            with header_cols[4]:
                st.write("**Partner**")
            with header_cols[5]:
                st.write("**Slot**")
            with header_cols[6]:
                st.write("**Round**")
            with header_cols[7]:
                st.write("**Status**")
            with header_cols[8]:
                st.write("**Action**")
            st.divider()
            
            # Create interactive table with status toggle
            if not filtered_df.empty:
                for idx, participant in filtered_df.iterrows():
                    # Get partner name if exists
                    partner_info = "None"
                    if participant['partner_emp_id']:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute('SELECT name FROM participants WHERE emp_id = ?', (participant['partner_emp_id'],))
                        partner_result = cursor.fetchone()
                        conn.close()
                        if partner_result:
                            partner_info = f"{partner_result[0]} ({participant['partner_emp_id']})"
                        else:
                            partner_info = participant['partner_emp_id']
                    
                    # Get match information for this participant
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    
                    # Check for singles matches
                    cursor.execute('''
                        SELECT round_number, match_date, match_number 
                        FROM matches 
                        WHERE (player1_id = ? OR player2_id = ?) AND match_status = 'scheduled'
                        ORDER BY round_number ASC
                        LIMIT 1
                    ''', (participant['id'], participant['id']))
                    singles_match = cursor.fetchone()
                    
                    # Check for doubles matches
                    cursor.execute('''
                        SELECT round_number, match_date, match_number 
                        FROM matches 
                        WHERE (team1_player1_id = ? OR team1_player2_id = ? OR 
                               team2_player1_id = ? OR team2_player2_id = ?) AND match_status = 'scheduled'
                        ORDER BY round_number ASC
                        LIMIT 1
                    ''', (participant['id'], participant['id'], participant['id'], participant['id']))
                    doubles_match = cursor.fetchone()
                    
                    conn.close()
                    
                    # Determine slot and round info
                    slot_info = participant.get('slot', 'Not Assigned')
                    round_info = "Not Assigned"
                    
                    # Use singles or doubles match info
                    current_match = singles_match or doubles_match
                    if current_match:
                        round_info = f"Round {current_match[0]}"
                        if current_match[1]:  # match_date contains time slot
                            slot_info = current_match[1]
                    
                    # Apply round filter
                    if round_filter != "All":
                        expected_round = int(round_filter.split()[1])
                        if current_match and current_match[0] != expected_round:
                            continue
                        elif not current_match and round_filter != "All":
                            continue
                    
                    # Display row
                    cols = st.columns([1, 2, 2, 1.5, 2, 1.2, 1.2, 1.2, 1.2])
                    
                    with cols[0]:
                        st.write(participant['emp_id'])
                    with cols[1]:
                        st.write(participant['name'])
                    with cols[2]:
                        st.write(participant['email'])
                    with cols[3]:
                        st.write(participant['category'])
                    with cols[4]:
                        st.write(partner_info)
                    with cols[5]:
                        st.write(slot_info if slot_info != 'Not Assigned' else "Not Set")
                    with cols[6]:
                        st.write(round_info)
                    with cols[7]:
                        if participant['registered_at_desk']:
                            # Format timestamp for display
                            timestamp_display = ""
                            if participant.get('registered_timestamp'):
                                try:
                                    timestamp = datetime.strptime(participant['registered_timestamp'], '%Y-%m-%d %H:%M:%S')
                                    timestamp_display = f"\n({timestamp.strftime('%I:%M %p')})"
                                except:
                                    timestamp_display = ""
                            st.success(f"✅ Reported{timestamp_display}")
                        else:
                            st.error("❌ Not Reported")
                    with cols[8]:
                        # Action button with confirmation
                        if participant['registered_at_desk']:
                            if st.button("Unmark", key=f"unmark_{participant['id']}", type="secondary"):
                                # Show confirmation dialog
                                if f"confirm_unmark_{participant['id']}" not in st.session_state:
                                    st.session_state[f"confirm_unmark_{participant['id']}"] = True
                                    st.rerun()
                            
                            # Check for confirmation state
                            if st.session_state.get(f"confirm_unmark_{participant['id']}", False):
                                st.error("🚨 Confirm?")
                                # Use single row with smaller buttons
                                confirm_col1, confirm_col2 = st.columns([1, 1])
                                with confirm_col1:
                                    if st.button("✅", key=f"confirm_yes_{participant['id']}", type="primary", help="Yes, unmark this participant"):
                                        update_registration_status(participant['id'], 0)
                                        del st.session_state[f"confirm_unmark_{participant['id']}"]
                                        st.rerun()
                                with confirm_col2:
                                    if st.button("❌", key=f"confirm_no_{participant['id']}", type="secondary", help="No, cancel"):
                                        del st.session_state[f"confirm_unmark_{participant['id']}"]
                                        st.rerun()
                        else:
                            if st.button("Report", key=f"mark_{participant['id']}", type="primary"):
                                update_registration_status(participant['id'], 1)
                                st.rerun()
                
                st.divider()
                
                # Bulk actions
                st.subheader("🔧 Bulk Actions")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Mark All Filtered as Reported", type="primary"):
                        # Show confirmation dialog
                        if "confirm_mark_all" not in st.session_state:
                            st.session_state.confirm_mark_all = True
                            st.rerun()
                    
                    # Check for confirmation state
                    if st.session_state.get("confirm_mark_all", False):
                        st.warning(f"⚠️ Mark {len(filtered_df)} participants as reported?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("Yes, Mark All", key="confirm_mark_all_yes", type="primary"):
                                try:
                                    conn = sqlite3.connect(DB_PATH)
                                    cursor = conn.cursor()
                                    participant_ids = filtered_df['id'].tolist()
                                    cursor.executemany("UPDATE participants SET registered_at_desk = 1, registered_timestamp = CURRENT_TIMESTAMP WHERE id = ?", [(pid,) for pid in participant_ids])
                                    conn.commit()
                                    conn.close()
                                    st.success(f"Marked {len(participant_ids)} participants as reported!")
                                    del st.session_state.confirm_mark_all
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error in bulk update: {str(e)}")
                        with col_no:
                            if st.button("Cancel", key="confirm_mark_all_no", type="secondary"):
                                del st.session_state.confirm_mark_all
                                st.rerun()
                
                with col2:
                    if st.button("Unmark All Filtered", type="secondary"):
                        # Show confirmation dialog
                        if "confirm_unmark_all" not in st.session_state:
                            st.session_state.confirm_unmark_all = True
                            st.rerun()
                    
                    # Check for confirmation state
                    if st.session_state.get("confirm_unmark_all", False):
                        st.warning(f"⚠️ Unmark {len(filtered_df)} participants?")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("Yes, Unmark All", key="confirm_unmark_all_yes", type="primary"):
                                try:
                                    conn = sqlite3.connect(DB_PATH)
                                    cursor = conn.cursor()
                                    participant_ids = filtered_df['id'].tolist()
                                    cursor.executemany("UPDATE participants SET registered_at_desk = 0, registered_timestamp = NULL WHERE id = ?", [(pid,) for pid in participant_ids])
                                    conn.commit()
                                    conn.close()
                                    st.success(f"Unmarked {len(participant_ids)} participants!")
                                    del st.session_state.confirm_unmark_all
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error in bulk update: {str(e)}")
                        with col_no:
                            if st.button("No, Cancel", key="confirm_unmark_all_no"):
                                del st.session_state.confirm_unmark_all
                                st.rerun()
                        
                        with col2:
                            # Delete fixture
                            st.subheader("🗑️ Delete Fixture")
                            delete_fixture_id = st.number_input(f"Fixture ID to Delete for {category}", min_value=1, key=f"delete_fixture_id_{category}")
                            
                            if st.button("Delete Fixture", key=f"delete_fixture_{category}"):
                                # Confirm deletion
                                if "confirm_delete_fixture" not in st.session_state:
                                    st.session_state.confirm_delete_fixture = True
                                    st.session_state.fixture_to_delete = delete_fixture_id
                                    st.warning(f"⚠️ Are you sure you want to delete fixture #{delete_fixture_id}?")
                                    st.rerun()
                            
                            # Handle confirmation
                            if st.session_state.get("confirm_delete_fixture", False):
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button("Yes, Delete", key=f"confirm_delete_yes_{category}"):
                                        success = delete_fixture(st.session_state.fixture_to_delete)
                                        if success:
                                            st.success(f"✅ Fixture #{st.session_state.fixture_to_delete} deleted successfully.")
                                            del st.session_state.confirm_delete_fixture
                                            del st.session_state.fixture_to_delete
                                            st.rerun()
                                        else:
                                            st.error("❌ Failed to delete fixture.")
                                with col_no:
                                    if st.button("Cancel", key=f"confirm_delete_no_{category}"):
                                        del st.session_state.confirm_delete_fixture
                                        del st.session_state.fixture_to_delete
                                        st.rerun()

with tab4:
    # Fixtures tab
    st.subheader("📅 Fixtures Management")
    
    participants_df = get_participants()
    
    if participants_df.empty:
        st.info("No participants found. Please import participants first.")
    else:
        # Create tabs for fixture creation and viewing
        fixture_tab1, fixture_tab2 = st.tabs(["Create Fixtures", "View Fixtures"])
        
        with fixture_tab1:
            st.subheader("⏱️ Create Time Slots and Generate Matches")
            
            # Sample data generator section
            with st.expander("🧪 Generate Sample Data for Testing", expanded=False):
                st.write("Generate 30 sample participants for testing purposes.")
                
                sample_game = st.session_state.selected_game
                sample_categories = ["Men's Singles", "Women's Singles", "Men's Doubles", "Women's Doubles", "Mixed Doubles"]
                sample_slot_types = ["Morning", "Afternoon", "Evening"]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    sample_category = st.selectbox(
                        "Select Category for Sample Data", 
                        sample_categories,
                        key="sample_category_selector"
                    )
                
                with col2:
                    sample_slot_type = st.selectbox(
                        "Select Slot Type",
                        sample_slot_types,
                        key="sample_slot_type_selector"
                    )
                
                if st.button("Generate 30 Sample Participants", key="generate_sample_data"):
                    with st.spinner(f"Generating 30 sample participants for {sample_game} - {sample_category} ({sample_slot_type} slot)..."):
                        count = generate_sample_participants(sample_game, sample_category, 30, sample_slot_type)
                        st.success(f"✅ Generated {count} sample participants for {sample_game} - {sample_category} ({sample_slot_type} slot)")
                        # Set flag to rerun the app to refresh data
                        st.session_state.rerun_app = True
                        st.rerun()
            
            # Form for creating fixtures
            with st.form("create_fixtures_form"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Select category based on game
                    game_participants = participants_df[participants_df['game'] == st.session_state.selected_game]
                    categories = sorted(game_participants['category'].unique()) if not game_participants.empty else []
                    
                    if not categories:
                        st.warning(f"No participants found for {st.session_state.selected_game}. Please add participants first.")
                        selected_category = None
                    else:
                        selected_category = st.selectbox("Select Category", categories)
                    
                    # Select round number
                    round_number = st.selectbox("Round Number", [1, 2, 3, 4, 5, 6], index=0)
                
                with col2:
                    # Select slot
                    slot_option = st.selectbox("Select Slot", ["Morning", "Afternoon", "Evening"])
                    
                    # Pre-defined timings
                    if slot_option == "Morning":
                        default_timing = "11:00-13:00"
                    elif slot_option == "Afternoon":
                        default_timing = "13:00-19:00"
                    else:  # Evening
                        default_timing = "19:00-21:00"
                    
                    # Allow manual override
                    custom_timing = st.text_input("Custom Time Range (HH:MM-HH:MM)", value=default_timing, 
                                                help="Override default timing if needed. Format: HH:MM-HH:MM")
                
                with col3:
                    # Match configuration
                    interval_minutes = st.number_input("Interval Between Matches (minutes)", 
                                                     min_value=10, max_value=60, value=20, step=5)
                    
                    # Get participant count for this category and game
                    if selected_category:
                        category_participants = participants_df[
                            (participants_df['category'] == selected_category) & 
                            (participants_df['game'] == st.session_state.selected_game)
                        ]
                        max_participants = len(category_participants)
                        
                        # Show participant count and list for selected filters
                        st.info(f"📊 **Participants Found:** {max_participants} in {st.session_state.selected_game} - {selected_category}")
                        
                        # Display participants in a table with slot and round info
                        with st.expander(f"👥 View All {max_participants} Participants", expanded=True):
                            if 'Doubles' in selected_category:
                                # For doubles, show teams with partners
                                teams_data = []
                                processed_ids = set()
                                team_count = 0
                                
                                for _, participant in category_participants.iterrows():
                                    if participant['id'] not in processed_ids and participant['partner_emp_id']:
                                        partner = category_participants[category_participants['emp_id'] == participant['partner_emp_id']]
                                        if not partner.empty:
                                            team_count += 1
                                            teams_data.append({
                                                'Team #': team_count,
                                                'Player 1': f"{participant['name']} ({participant['emp_id']})",
                                                'Player 2': f"{partner.iloc[0]['name']} ({partner.iloc[0]['emp_id']})",
                                                'Slot': participant.get('slot', 'Not Assigned'),
                                                'Round': participant.get('round', 'Not Assigned')
                                            })
                                            processed_ids.add(participant['id'])
                                            processed_ids.add(partner.iloc[0]['id'])
                                
                                if teams_data:
                                    st.dataframe(pd.DataFrame(teams_data), use_container_width=True)
                                    st.info(f"👥 **Teams Available:** {team_count} complete teams")
                                    max_matches = team_count // 2  # Each match needs 2 teams
                                else:
                                    st.warning("No complete teams found. Please ensure participants have valid partners.")
                                    max_matches = 0
                            else:
                                # For singles, show individual participants
                                singles_data = []
                                for i, (_, participant) in enumerate(category_participants.iterrows()):
                                    singles_data.append({
                                        'Player #': i+1,
                                        'Name': participant['name'],
                                        'ID': participant['emp_id'],
                                        'Slot': participant.get('slot', 'Not Assigned'),
                                        'Round': participant.get('round', 'Not Assigned')
                                    })
                                
                                if singles_data:
                                    st.dataframe(pd.DataFrame(singles_data), use_container_width=True)
                                    max_matches = max_participants // 2  # Each match needs 2 players
                                else:
                                    st.warning("No participants found.")
                                    max_matches = 0
                            
                        st.info(f"🏆 **Maximum Possible Matches:** {max_matches}")
                        
                        # Note about slot filtering
                        st.info(f"ℹ️ **Selected Slot:** {slot_option} - Only matches for this time slot will be created.")
                    else:
                        max_participants = 0
                        max_matches = 0
                    
                    no_of_matches = st.number_input("Number of Matches per Time Slot", 
                                                  min_value=1, max_value=max(1, 4), 
                                                  value=min(4, max(1, 4)), step=1,
                                                  help=f"How many matches to schedule in each time slot (1-4 matches per slot)")
                    
                    st.info(f"💡 **Logic:** Each time slot will have {no_of_matches} matches running simultaneously.\n"
                           f"All {max_participants} participants will be distributed across time slots until 1 PM or all are scheduled.\n"
                           f"Example: 20 participants, 4 matches per slot = 5 time slots needed.")
                
                location = st.text_input("Location", "Main Sports Hall")
                
                # Submit button
                submitted = st.form_submit_button("🎯 Generate Fixtures and Matches")
                
                if submitted:
                    try:
                        # Parse time range
                        start_time_str, end_time_str = custom_timing.split("-")
                        start_hour, start_minute = map(int, start_time_str.strip().split(":"))
                        end_hour, end_minute = map(int, end_time_str.strip().split(":"))
                        
                        # Calculate total available minutes
                        start_total_minutes = start_hour * 60 + start_minute
                        end_total_minutes = end_hour * 60 + end_minute
                        total_available_minutes = end_total_minutes - start_total_minutes
                        
                        # Calculate required time for matches
                        required_minutes = no_of_matches * interval_minutes
                        
                        if required_minutes > total_available_minutes:
                            st.error(f"❌ Not enough time! Need {required_minutes} minutes but only {total_available_minutes} minutes available.")
                            excess_matches = (required_minutes - total_available_minutes) // interval_minutes
                            st.warning(f"⚠️ Consider reducing matches by {excess_matches} or increasing interval time.")
                        else:
                            # Generate time slots based on matches per slot
                            time_slots = []
                            
                            # Get participants for the selected category and game
                            filtered_participants = participants_df[
                                (participants_df['category'] == selected_category) & 
                                (participants_df['game'] == st.session_state.selected_game)
                            ]
                                                        # Store the time range for display
                            st.session_state.time_range = f"{start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d}"
                            
                            if len(filtered_participants) == 0:
                                st.error("❌ No participants found for the selected category and game.")
                            else:
                                st.info(f"📊 Found {len(filtered_participants)} participants to schedule for {slot_option} slot")
                                
                                # Apply slot filtering based on selected slot option
                                # Update participants with slot information
                                for index, participant in filtered_participants.iterrows():
                                    # Update the slot in the database
                                    conn = sqlite3.connect(DB_PATH)
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        "UPDATE participants SET slot = ? WHERE id = ?",
                                        (slot_option, participant['id'])
                                    )
                                    conn.commit()
                                    conn.close()
                                    
                                    # Also update in the dataframe
                                    filtered_participants.at[index, 'slot'] = slot_option
                                
                                # For doubles, group into teams first
                                if 'Doubles' in selected_category:
                                    teams = []
                                    processed_ids = set()
                                    
                                    for _, player in filtered_participants.iterrows():
                                        if player['id'] in processed_ids:
                                            continue
                                            
                                        partner_emp_id = player['partner_emp_id']
                                        if not partner_emp_id or pd.isna(partner_emp_id):
                                            continue
                                            
                                        # Find the partner
                                        partner = filtered_participants[filtered_participants['emp_id'] == partner_emp_id]
                                        if not partner.empty:
                                            teams.append({
                                                'team_id': len(teams) + 1,
                                                'player1': player,
                                                'player2': partner.iloc[0]
                                            })
                                            processed_ids.add(player['id'])
                                            processed_ids.add(partner.iloc[0]['id'])
                                    
                                    total_entities = teams
                                    entity_type = "teams"
                                    st.info(f"👥 Created {len(teams)} complete teams from participants")
                                else:
                                    total_entities = filtered_participants.to_dict('records')
                                    entity_type = "players"
                                
                                # Calculate time slots needed for individual entity scheduling
                                total_entities_count = len(total_entities)
                                
                                # For individual fixture allocation, each entity gets its own slot
                                # The no_of_matches parameter becomes matches per time slot
                                matches_per_time_slot = no_of_matches
                                
                                # Calculate how many entities we need to schedule
                                # For singles: each match needs 2 players
                                # For doubles: each match needs 2 teams (4 players)
                                if 'Singles' in selected_category:
                                    # For singles, we need pairs of players for each match
                                    total_matches_needed = total_entities_count // 2
                                    if total_entities_count % 2 != 0:
                                        st.warning(f"⚠️ Odd number of players ({total_entities_count}). One player will not be scheduled.")
                                else:
                                    # For doubles, we need pairs of teams for each match
                                    total_matches_needed = total_entities_count // 2
                                    if total_entities_count % 2 != 0:
                                        st.warning(f"⚠️ Odd number of teams ({total_entities_count}). One team will not be scheduled.")
                                
                                # Calculate how many time slots we need
                                time_slots_needed = (total_matches_needed + matches_per_time_slot - 1) // matches_per_time_slot
                                
                                st.info(f"🕐 Need {time_slots_needed} time slots to schedule {total_matches_needed} matches ({matches_per_time_slot} matches per time slot)")
                                
                                # Generate time slots
                                current_minutes = start_total_minutes
                                match_counter = 0
                                fixture_number = 1
                                entity_index = 0
                                
                                for slot_index in range(time_slots_needed):
                                    # Check if we've reached the end time
                                    if current_minutes >= end_total_minutes:
                                        st.warning(f"⚠️ Time limit reached! Only scheduled {slot_index} time slots.")
                                        break
                                    
                                    # Calculate start and end time for this slot
                                    slot_start_hour = current_minutes // 60
                                    slot_start_minute = current_minutes % 60
                                    slot_end_minutes = current_minutes + interval_minutes
                                    slot_end_hour = slot_end_minutes // 60
                                    slot_end_minute = slot_end_minutes % 60
                                    
                                    slot_str = f"{slot_start_hour:02d}:{slot_start_minute:02d}-{slot_end_hour:02d}:{slot_end_minute:02d}"
                                    
                                    # Schedule matches for this time slot
                                    matches_in_this_slot = min(matches_per_time_slot, total_matches_needed - match_counter)
                                    
                                    for match_in_slot in range(matches_in_this_slot):
                                        # Assign fixture number (1 for first 2 matches, 2 for next 2, etc.)
                                        current_fixture_number = (match_counter // 2) + 1
                                        
                                        # Create fixtures for this match
                                        if entity_index < total_entities_count - 1:  # Ensure we have at least 2 entities
                                            # For singles: create two fixtures (one for each player)
                                            # For doubles: create two fixtures (one for each team)
                                            
                                            # First entity in the match
                                            time_slots.append({
                                                'time_slot': slot_str,
                                                'match_fixture_number': current_fixture_number,
                                                'court_number': (match_in_slot % 4) + 1,  # Cycle through courts 1-4
                                                'slot_index': slot_index + 1,
                                                'entity_in_slot': match_in_slot * 2 + 1,
                                                'entity': total_entities[entity_index],
                                                'match_position': 'first'
                                            })
                                            
                                            # Second entity in the match
                                            time_slots.append({
                                                'time_slot': slot_str,
                                                'match_fixture_number': current_fixture_number,
                                                'court_number': (match_in_slot % 4) + 1,  # Same court as first entity
                                                'slot_index': slot_index + 1,
                                                'entity_in_slot': match_in_slot * 2 + 2,
                                                'entity': total_entities[entity_index + 1],
                                                'match_position': 'second'
                                            })
                                            
                                            entity_index += 2  # Move to next pair of entities
                                            match_counter += 1
                                    
                                    # Move to next time slot
                                    current_minutes = slot_end_minutes
                                    
                                    current_minutes += interval_minutes
                                
                                if not time_slots:
                                    st.error("❌ No matches could be scheduled. Check your time settings and participant count.")
                                else:
                                    # Show generated time slots
                                    st.success(f"✅ Generated {len(time_slots)} fixture slots for {selected_category} - Round {round_number}")
                                    
                                    # Show generated time slots
                                    time_slots_df = pd.DataFrame(time_slots)
                                    
                                    # For display purposes, create a more readable format
                                    slots_df = pd.DataFrame()
                                    
                                    # Process each time slot and add to the dataframe
                                    for i, slot_info in enumerate(time_slots):
                                        slot_data = {
                                            'Time Slot': slot_info['time_slot'],
                                            'Court': slot_info['court_number'],
                                            'Fixture #': slot_info['match_fixture_number'],
                                            'Slot Type': slot_option,  # Add the slot type (Morning/Afternoon/Evening)
                                            'Round': round_number,  # Add the round number
                                            'Category': selected_category,
                                            'Location': location,
                                            'Game': st.session_state.selected_game
                                        }
                                        
                                        # Add participant/team information for individual fixtures
                                        if 'Doubles' in selected_category:
                                            # For doubles fixtures - each fixture is for one team
                                            if slot_info['entity']:
                                                team = slot_info['entity']
                                                slot_data['Team_Player1'] = team['player1']['name']
                                                slot_data['Team_Player1_ID'] = team['player1']['emp_id']
                                                slot_data['Team_Player2'] = team['player2']['name']
                                                slot_data['Team_Player2_ID'] = team['player2']['emp_id']
                                                slot_data['Team_DB_IDs'] = [team['player1']['id'], team['player2']['id']]
                                            else:
                                                slot_data['Team_Player1'] = 'TBD'
                                                slot_data['Team_Player1_ID'] = 'TBD'
                                                slot_data['Team_Player2'] = 'TBD'
                                                slot_data['Team_Player2_ID'] = 'TBD'
                                                slot_data['Team_DB_IDs'] = [None, None]
                                        else:
                                            # For singles fixtures - each fixture is for one player
                                            if slot_info['entity']:
                                                slot_data['Player_Name'] = slot_info['entity']['name']
                                                slot_data['Player_ID'] = slot_info['entity']['emp_id']
                                                slot_data['Player_DB_ID'] = slot_info['entity']['id']
                                            else:
                                                slot_data['Player_Name'] = 'TBD'
                                                slot_data['Player_ID'] = 'TBD'
                                                slot_data['Player_DB_ID'] = None
                                        
                                        slots_df = pd.concat([slots_df, pd.DataFrame([slot_data])], ignore_index=True)
                                    
                                    st.subheader(f"📋 Generated Fixture Schedule - {slot_option} Slot, Round {round_number}")
                                    
                                    # Display appropriate columns based on match type
                                    if 'Doubles' in selected_category:
                                        display_cols = ['Time Slot', 'Slot Type', 'Round', 'Court', 'Fixture #', 'Team_Player1', 'Team_Player1_ID', 'Team_Player2', 'Team_Player2_ID']
                                    else:
                                        display_cols = ['Time Slot', 'Slot Type', 'Round', 'Court', 'Fixture #', 'Player_Name', 'Player_ID']
                                    
                                    # Create a styled dataframe
                                    st.markdown("### Match Schedule")
                                    st.dataframe(slots_df[display_cols], use_container_width=True)
                                    
                                    # Show a summary of the time allocation
                                    st.markdown("### Time Allocation Summary")
                                    unique_times = slots_df['time_slot'].unique()
                                    unique_fixture_numbers = slots_df['match_fixture_number'].unique()
                                    
                                    st.info(f"Time Range: {st.session_state.time_range}")
                                    st.info(f"Total Time Slots: {len(unique_times)}")
                                    st.info(f"Total Match Fixtures: {len(unique_fixture_numbers)}")
                                    
                                    # Show time allocation details
                                    time_allocation = []
                                    for time_slot in sorted(unique_times):
                                        matches_in_slot = slots_df[slots_df['time_slot'] == time_slot]['match_fixture_number'].unique()
                                        time_allocation.append({
                                            'Time Slot': time_slot,
                                            'Match Fixtures': ", ".join([str(m) for m in sorted(matches_in_slot)]),
                                            'Count': len(matches_in_slot)
                                        })
                                    
                                    st.dataframe(pd.DataFrame(time_allocation), use_container_width=True)
                                    
                                    # Save to database with proper connection handling
                                    if st.button("💾 Save Fixtures to Database", type="primary"):
                                        fixtures_created = 0
                                        errors = []
                                        
                                        for i, slot_info in enumerate(time_slots):
                                            try:
                                                # Use a separate connection for each operation to avoid locking
                                                conn = sqlite3.connect(DB_PATH, timeout=10.0)
                                                cursor = conn.cursor()
                                                
                                                # Create fixture entry for individual entity
                                                if 'Doubles' in selected_category:
                                                    # Get team IDs for individual team fixture
                                                    team_ids = slots_df.iloc[i]['Team_DB_IDs'] if not pd.isna(slots_df.iloc[i].get('Team_DB_IDs')) else [None, None]
                                                    
                                                    cursor.execute('''
                                                        INSERT INTO fixtures (category, time_slot, location, court_number, 
                                                                            team1_player1_id, team1_player2_id, 
                                                                            fixture_status, created_at, slot, round_number, game)
                                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                                    ''', (selected_category, slot_info['time_slot'], location, 
                                                          slot_info['court_number'], 
                                                          team_ids[0], team_ids[1],
                                                          'scheduled', datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                          slot_option, round_number, st.session_state.selected_game))
                                                    
                                                    # Create corresponding match entry (placeholder for future pairing)
                                                    match_id = create_match(
                                                        category=selected_category,
                                                        round_number=round_number,
                                                        team1_player1_id=team_ids[0],
                                                        team1_player2_id=team_ids[1],
                                                        team2_player1_id=None,  # To be assigned later
                                                        team2_player2_id=None   # To be assigned later
                                                    )
                                                else:
                                                    # Singles fixture for individual player
                                                    player_id = slots_df.iloc[i]['Player_DB_ID'] if not pd.isna(slots_df.iloc[i].get('Player_DB_ID')) else None
                                                    
                                                    cursor.execute('''
                                                        INSERT INTO fixtures (category, time_slot, location, court_number, 
                                                                            player1_id, fixture_status, created_at, slot, round_number, game)
                                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                                    ''', (selected_category, slot_info['time_slot'], location, 
                                                          slot_info['court_number'], player_id,
                                                          'scheduled', datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                          slot_option, round_number, st.session_state.selected_game))
                                                    
                                                    # Create corresponding match entry (placeholder for future pairing)
                                                    match_id = create_match(
                                                        category=selected_category,
                                                        round_number=round_number,
                                                        player1_id=player_id,
                                                        player2_id=None  # To be assigned later
                                                    )
                                                
                                                fixture_id = cursor.lastrowid
                                                fixtures_created += 1
                                                
                                                if match_id:
                                                    # Update match with fixture information
                                                    cursor.execute('''
                                                        UPDATE matches 
                                                        SET match_number = ?, match_date = ? 
                                                        WHERE id = ?
                                                    ''', (slot_info['match_fixture_number'], slot_info['time_slot'], match_id))
                                                
                                                conn.commit()
                                                conn.close()
                                                
                                            except Exception as e:
                                                errors.append(f"Fixture {i+1}: {str(e)}")
                                                try:
                                                    conn.close()
                                                except Exception:
                                                    pass
                                        
                                        if errors:
                                            st.error(f"❌ {len(errors)} errors occurred:")
                                            for error in errors[:5]:  # Show first 5 errors
                                                st.error(error)
                                        
                                        if fixtures_created > 0:
                                            st.success(f"🎯 Successfully created {fixtures_created} fixtures!")
                                            
                                            # Show summary
                                            unique_slots = len(set([slot['time_slot'] for slot in time_slots]))
                                            participants_scheduled = len(total_entities)
                                            st.info(f"📊 **Summary:**\n"
                                                   f"- Time Slots Used: {unique_slots}\n"
                                                   f"- Fixtures Created: {fixtures_created}\n"
                                                   f"- Participants Scheduled: {participants_scheduled}\n")
                                            
                                            # Set flag to rerun the app to refresh data
                                            st.session_state.rerun_app = True
                                            st.rerun()
                            
                    except ValueError:
                        st.error("❌ Invalid time format! Please use HH:MM-HH:MM format (e.g., 11:00-13:00)")
                    except Exception as e:
                        st.error(f"❌ Error creating fixtures: {str(e)}")
        
        with fixture_tab2:
            st.subheader("📋 View and Manage Fixtures")
            
            # Get all fixtures
            fixtures_df = get_all_fixtures()
            
            if fixtures_df.empty:
                st.info("No fixtures found. Please create fixtures first.")
            else:
                # Filter options
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    categories = ["All Categories"] + sorted(fixtures_df['category'].unique().tolist())
                    # Default to Women's Singles if available in the categories
                    default_index = 0
                    if "Women's Singles" in categories:
                        default_index = categories.index("Women's Singles")
                    selected_filter_category = st.selectbox("Filter by Category", categories, index=default_index, key="filter_fixtures_category")
                
                with col2:
                    # Add slot type filter (Morning/Afternoon/Evening)
                    slot_types = ["All Slots"] + sorted(fixtures_df['slot'].dropna().unique().tolist())
                    selected_slot_type = st.selectbox("Filter by Slot Type", slot_types, key="filter_slot_type")
                    
                    # Keep the time slot filter too
                    time_slots = ["All Time Slots"] + sorted(fixtures_df['time_slot'].unique().tolist())
                    selected_time_slot = st.selectbox("Filter by Time", time_slots, key="filter_time_slot")
                
                with col3:
                    round_numbers = ["All Rounds"] + sorted(fixtures_df['round_number'].unique().tolist())
                    selected_round = st.selectbox("Filter by Round", round_numbers, key="filter_round_number")
                
                # Apply filters
                filtered_fixtures = fixtures_df.copy()
                
                if selected_filter_category != "All Categories":
                    filtered_fixtures = filtered_fixtures[filtered_fixtures['category'] == selected_filter_category]
                
                # Apply slot type filter (Morning/Afternoon/Evening)
                if selected_slot_type != "All Slots":
                    filtered_fixtures = filtered_fixtures[filtered_fixtures['slot'] == selected_slot_type]
                
                if selected_time_slot != "All Time Slots":
                    filtered_fixtures = filtered_fixtures[filtered_fixtures['time_slot'] == selected_time_slot]
                
                if selected_round != "All Rounds":
                    filtered_fixtures = filtered_fixtures[filtered_fixtures['round_number'] == selected_round]
                
                if filtered_fixtures.empty:
                    st.info("No fixtures found with the selected filters.")
                else:
                    st.success(f"Found {len(filtered_fixtures)} fixtures matching your filters")
                    
                    # Display fixtures in a clean format (similar to create fixtures preview)
                    for category in sorted(filtered_fixtures['category'].unique()):
                        st.subheader(f"🏆 {category}")
                        category_fixtures = filtered_fixtures[filtered_fixtures['category'] == category]
                        
                        # Check if it's singles or doubles
                        is_singles = 'Singles' in category
                        
                        # Create a clean display dataframe similar to create fixtures
                        display_data = []
                        
                        for _, fixture in category_fixtures.iterrows():
                            # Use the slot field from the database if available, otherwise determine from time
                            slot_type = fixture['slot'] if pd.notna(fixture['slot']) else "Unknown"
                            
                            # Fallback to determining slot type based on time if slot is not available
                            if slot_type == "Unknown":
                                time_str = fixture['time_slot']
                                if time_str:
                                    try:
                                        start_time = time_str.split('-')[0]
                                        hour = int(start_time.split(':')[0])
                                        if hour < 12:
                                            slot_type = "Morning"
                                        elif hour < 17:
                                            slot_type = "Afternoon"
                                        else:
                                            slot_type = "Evening"
                                    except:
                                        pass
                            
                            row_data = {
                                'Fixture_ID': fixture['id'],
                                'Time_Slot': fixture['time_slot'],
                                'Slot_Type': slot_type,
                                'Round': fixture['round_number'] if pd.notna(fixture['round_number']) else "N/A",
                                'Court': fixture['court_number'],
                                'Location': fixture['location'],
                                'Status': fixture['fixture_status'],
                                'Emails_Sent': "Yes" if fixture['emails_sent'] == 1 else "No"
                            }
                            
                            if is_singles:
                                # For singles matches - show player details clearly
                                row_data['Player_1'] = f"{fixture['player1_name']} ({fixture['player1_emp_id']})" if fixture['player1_name'] else "TBD"
                                row_data['Player_2'] = f"{fixture['player2_name']} ({fixture['player2_emp_id']})" if fixture['player2_name'] else "TBD"
                            else:
                                # For doubles matches - show team details clearly
                                team1_str = "TBD"
                                team2_str = "TBD"
                                
                                if fixture['team1_player1_name'] and fixture['team1_player2_name']:
                                    team1_str = f"{fixture['team1_player1_name']} & {fixture['team1_player2_name']}"
                                
                                if fixture['team2_player1_name'] and fixture['team2_player2_name']:
                                    team2_str = f"{fixture['team2_player1_name']} & {fixture['team2_player2_name']}"
                                
                                row_data['Team_1'] = team1_str
                                row_data['Team_2'] = team2_str
                            
                            display_data.append(row_data)
                        
                        # Create and display the dataframe
                        display_df = pd.DataFrame(display_data)
                        
                        if is_singles:
                            column_order = ['Fixture_ID', 'Time_Slot', 'Slot_Type', 'Round', 'Court', 'Player_1', 'Player_2', 'Location', 'Status', 'Emails_Sent']
                        else:
                            column_order = ['Fixture_ID', 'Time_Slot', 'Slot_Type', 'Round', 'Court', 'Team_1', 'Team_2', 'Location', 'Status', 'Emails_Sent']
                        
                        st.dataframe(display_df[column_order], use_container_width=True)
                        
                        # Action buttons for this category
                        st.subheader(f"⚙️ Actions for {category}")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown("**📧 Individual Email**")
                            fixture_id = st.number_input(f"Fixture ID", min_value=1, key=f"email_fixture_id_{category}")
                            
                            if st.button("Send Email", key=f"send_individual_email_{category}"):
                                # Get fixture data for emails
                                email_data = get_fixture_emails(fixture_id)
                                
                                if email_data:
                                    # Create email content
                                    subject = f"Tournament: Your {email_data['category']} Match Details"
                                    
                                    # Simple email body
                                    body = f"""Dear Participant,

Your {email_data['category']} match has been scheduled.

Match Details:
- Time Slot: {email_data['time_slot']}
- Location: {email_data['location']}  
- Court Number: {email_data['court_number']}

Please arrive 10 minutes before your scheduled time.

Good luck!
Tournament Committee"""
                                    
                                    # Send email
                                    success = send_outlook_email(
                                        recipients=email_data['emails'],
                                        subject=subject,
                                        body=body,
                                        draft_only=True,
                                        open_outlook=True
                                    )
                                    
                                    if success:
                                        mark_emails_sent(fixture_id)
                                        st.success("✅ Email draft created in Outlook")
                                    else:
                                        st.error("❌ Failed to create email")
                                else:
                                    st.error(f"❌ Fixture #{fixture_id} not found")
                        
                        with col2:
                            st.markdown("**📮 Bulk Email**")
                            
                            # Show all fixtures in this category that haven't had emails sent yet
                            unsent_fixtures = category_fixtures[category_fixtures['emails_sent'] == 0]
                            if not unsent_fixtures.empty:
                                st.info(f"📧 {len(unsent_fixtures)} fixtures in {category} need email notifications")
                                
                                # Create a selection for fixtures
                                fixture_options = []
                                for _, fixture in unsent_fixtures.iterrows():
                                    if 'Singles' in category:
                                        player1 = fixture['player1_name'] if fixture['player1_name'] else "TBD"
                                        player2 = fixture['player2_name'] if fixture['player2_name'] else "TBD"
                                        desc = f"Time: {fixture['time_slot']} - {player1} vs {player2}"
                                    else:
                                        team1 = "TBD"
                                        team2 = "TBD"
                                        if fixture['team1_player1_name'] and fixture['team1_player2_name']:
                                            team1 = f"{fixture['team1_player1_name']} & {fixture['team1_player2_name']}"
                                        if fixture['team2_player1_name'] and fixture['team2_player2_name']:
                                            team2 = f"{fixture['team2_player1_name']} & {fixture['team2_player2_name']}"
                                        desc = f"Time: {fixture['time_slot']} - {team1} vs {team2}"
                                    
                                    fixture_options.append({"id": fixture['id'], "description": desc})
                                
                                selected_fixtures = st.multiselect(
                                    "Select fixtures to send notifications for:",
                                    options=[f["id"] for f in fixture_options],
                                    format_func=lambda x: next((f["description"] for f in fixture_options if f["id"] == x), ""),
                                    key=f"bulk_fixtures_{category}"
                                )
                                
                                if selected_fixtures:
                                    if st.button("Send Selected Emails", key=f"send_selected_emails_{category}"):
                                        success_count = 0
                                        error_count = 0
                                        
                                        for fixture_id in selected_fixtures:
                                            try:
                                                email_data = get_fixture_emails(fixture_id)
                                                if email_data and email_data['emails']:
                                                    subject = f"Tournament: Your {email_data['category']} Match Details"
                                                    
                                                    # Personalized email body for each participant
                                                    for i, email in enumerate(email_data['emails']):
                                                        participant_name = email_data['names'][i] if i < len(email_data['names']) else "Participant"
                                                        
                                                        body = f"""Dear {participant_name},

Your {email_data['category']} match has been scheduled.

Match Details:
- Time Slot: {email_data['time_slot']}
- Venue: {email_data['location']}
- Court Number: {email_data['court_number']}

Please arrive 10 minutes before your scheduled time.

Good luck!
Tournament Committee"""
                                                        
                                                        # Send individual email
                                                        success = send_outlook_email(
                                                            recipients=[email],
                                                            subject=subject,
                                                            body=body,
                                                            draft_only=True
                                                        )
                                                        
                                                        if success:
                                                            success_count += 1
                                                        else:
                                                            error_count += 1
                                                    
                                                    # Mark emails as sent
                                                    mark_emails_sent(fixture_id)
                                            except Exception as e:
                                                error_count += 1
                                                st.error(f"Error with fixture {fixture_id}: {str(e)}")
                                        
                                        if success_count > 0:
                                            st.success(f"✅ Created {success_count} email drafts in Outlook")
                                        if error_count > 0:
                                            st.warning(f"⚠️ {error_count} emails failed to create")
                                else:
                                    st.info("Please select fixtures to send notifications for")
                            else:
                                st.success(f"✅ All fixtures in {category} have been notified")
                                
                            # Add option to send all emails at once
                            if st.button("Send All Emails", key=f"send_bulk_emails_{category}"):
                                success_count = 0
                                error_count = 0
                                
                                for _, fixture in category_fixtures.iterrows():
                                    try:
                                        email_data = get_fixture_emails(fixture['id'])
                                        if email_data and email_data['emails']:
                                            subject = f"Tournament: Your {email_data['category']} Match Details"
                                            
                                            # Personalized email body for each participant
                                            for i, email in enumerate(email_data['emails']):
                                                participant_name = email_data['names'][i] if i < len(email_data['names']) else "Participant"
                                                
                                                body = f"""Dear {participant_name},

Your {email_data['category']} match has been scheduled.

Match Details:
- Time Slot: {email_data['time_slot']}
- Venue: {email_data['location']}
- Court Number: {email_data['court_number']}

Please arrive 10 minutes before your scheduled time.

Good luck!
Tournament Committee"""
                                                
                                                # Send individual email
                                                success = send_outlook_email(
                                                    recipients=[email],
                                                    subject=subject,
                                                    body=body,
                                                    draft_only=True
                                                )
                                                
                                                if success:
                                                    success_count += 1
                                                else:
                                                    error_count += 1
                                            
                                            # Mark emails as sent
                                            mark_emails_sent(fixture['id'])
                                    except Exception as e:
                                        error_count += 1
                                        st.error(f"Error with fixture {fixture['id']}: {str(e)}")
                                
                                if success_count > 0:
                                    st.success(f"✅ Created {success_count} email drafts in Outlook")
                                if error_count > 0:
                                    st.warning(f"⚠️ {error_count} emails failed to create")
                        
                        with col3:
                            st.markdown("**🗑️ Delete Fixture**")
                            delete_fixture_id = st.number_input(f"Fixture ID", min_value=1, key=f"delete_fixture_id_{category}")
                            
                            if st.button("Delete Fixture", key=f"delete_fixture_{category}", type="secondary"):
                                try:
                                    delete_fixture(delete_fixture_id)
                                    st.success(f"✅ Deleted fixture #{delete_fixture_id}")
                                except Exception as e:
                                    st.error(f"❌ Error deleting fixture: {str(e)}")
                        
                        st.divider()

with tab5:
    # Match Management
    st.subheader("⚔️ Match Management")
    
    participants_df = get_participants()
    reported_participants = participants_df[participants_df['registered_at_desk'] == 1]
    matches_df = get_matches()
    
    if reported_participants.empty:
        st.info("No reported participants found. Please mark participants as reported first.")
    else:
        # ... (rest of the code remains the same)
        # Get participants who are already in matches
        participants_in_matches = set()
        if not matches_df.empty:
            # Add singles participants
            participants_in_matches.update(matches_df['player1_id'].dropna().astype(int).tolist())
            participants_in_matches.update(matches_df['player2_id'].dropna().astype(int).tolist())
            # Add doubles participants
            participants_in_matches.update(matches_df['team1_player1_id'].dropna().astype(int).tolist())
            participants_in_matches.update(matches_df['team1_player2_id'].dropna().astype(int).tolist())
            participants_in_matches.update(matches_df['team2_player1_id'].dropna().astype(int).tolist())
            participants_in_matches.update(matches_df['team2_player2_id'].dropna().astype(int).tolist())
        
        # Filter out participants who are already in matches
        available_participants = reported_participants[~reported_participants['id'].isin(participants_in_matches)]
        
        # Create new match
        st.subheader("🆕 Create New Match")
        
        categories = ['Mens Singles', 'Womens Singles', 'Mens Doubles', 'Womens Doubles', 'Mixed Doubles']
        
        # Initialize session state for category tracking
        if 'match_category_index' not in st.session_state:
            st.session_state.match_category_index = 0
        
        # Use index-based selection to avoid caching issues
        selected_category_index = st.selectbox(
            "Select Category:", 
            range(len(categories)),
            format_func=lambda x: categories[x],
            index=st.session_state.match_category_index,
            key="match_category_selector"
        )
        
        # Update session state and get actual category
        st.session_state.match_category_index = selected_category_index
        selected_category = categories[selected_category_index]
        
        round_number = st.number_input("Round Number:", min_value=1, value=1)
        
        # Filter participants by the correctly selected category
        category_participants = available_participants[available_participants['category'] == selected_category].copy()
        
        st.write(f"**Available participants in {selected_category}:** {len(category_participants)}")
        
        if len(category_participants) < 2:
            st.warning(f"Need at least 2 available participants in {selected_category} category (not already in matches).")
            if len(reported_participants[reported_participants['category'] == selected_category]) >= 2:
                st.info(f"💡 There are reported participants in {selected_category}, but they are already assigned to matches.")
        else:
            if selected_category in ['Mens Singles', 'Womens Singles']:
                # Singles match
                player1 = st.selectbox(
                    "Player 1:", 
                    options=category_participants['id'].values,
                    format_func=lambda x: f"{category_participants[category_participants['id'] == x]['name'].iloc[0]} ({category_participants[category_participants['id'] == x]['emp_id'].iloc[0]})"
                )
                
                available_players = category_participants[category_participants['id'] != player1]
                if len(available_players) > 0:
                    player2 = st.selectbox(
                        "Player 2:",
                        options=available_players['id'].values,
                        format_func=lambda x: f"{category_participants[category_participants['id'] == x]['name'].iloc[0]} ({category_participants[category_participants['id'] == x]['emp_id'].iloc[0]})"
                    )
                    
                    if st.button("Create Match", key="create_singles_match"):
                        create_match(selected_category, round_number, player1, player2)
                        st.success("Match created successfully!")
                        st.rerun()
                else:
                    st.warning("Only one available participant remaining for this category.")
            
            else:
                # Doubles match - treat like singles (individual players compete)
                st.write("**Player Selection:**")
                st.info("💡 Select 2 individual players from the doubles category. Partners are for reference only.")
                
                player1 = st.selectbox(
                    "Player 1:", 
                    options=category_participants['id'].values,
                    format_func=lambda x: f"{category_participants[category_participants['id'] == x]['name'].iloc[0]} ({category_participants[category_participants['id'] == x]['emp_id'].iloc[0]}) - Partner: {category_participants[category_participants['id'] == x]['partner_emp_id'].iloc[0] if category_participants[category_participants['id'] == x]['partner_emp_id'].iloc[0] else 'None'}"
                )
                
                available_players = category_participants[category_participants['id'] != player1]
                if len(available_players) > 0:
                    player2 = st.selectbox(
                        "Player 2:",
                        options=available_players['id'].values,
                        format_func=lambda x: f"{category_participants[category_participants['id'] == x]['name'].iloc[0]} ({category_participants[category_participants['id'] == x]['emp_id'].iloc[0]}) - Partner: {category_participants[category_participants['id'] == x]['partner_emp_id'].iloc[0] if category_participants[category_participants['id'] == x]['partner_emp_id'].iloc[0] else 'None'}"
                    )
                    
                    if st.button("Create Match", key="create_doubles_match"):
                        # For doubles, we still use player1_id and player2_id (same as singles)
                        create_match(selected_category, round_number, player1, player2)
                        st.success("Match created successfully!")
                        st.rerun()
                else:
                    st.warning("Only one available participant remaining for this category.")

    # Show existing matches with enhanced UI
    st.subheader("📋 Existing Matches")
    matches_df = get_matches()
    
    if not matches_df.empty:
        # Filter matches by status
        col1, col2 = st.columns([3, 1])
        with col2:
            match_filter = st.selectbox("Filter by Status:", ["All Matches", "Scheduled", "Completed"])
        
        # Apply filter
        if match_filter == "Scheduled":
            display_matches = matches_df[matches_df['match_status'] == 'scheduled']
        elif match_filter == "Completed":
            display_matches = matches_df[matches_df['match_status'] == 'completed']
        else:
            display_matches = matches_df
        
        if display_matches.empty:
            st.info(f"No {match_filter.lower()} found.")
        else:
            # Group matches by category
            categories = display_matches['category'].unique()
            
            for category in categories:
                with st.expander(f"🏆 {category} ({len(display_matches[display_matches['category'] == category])} matches)", expanded=True):
                    category_matches = display_matches[display_matches['category'] == category].sort_values(['round_number', 'created_at'])
                    
                    for _, match in category_matches.iterrows():
                        # Create a card-like layout for each match
                        match_container = st.container()
                        with match_container:
                            # Match header with ID and status
                            col1, col2, col3 = st.columns([2, 2, 1])
                            with col1:
                                st.markdown(f"**🆔 Match #{match['id']} - Round {match['round_number']}**")
                            with col2:
                                if match['match_status'] == 'completed':
                                    st.success("✅ Completed")
                                else:
                                    st.warning("⏳ Scheduled")
                            with col3:
                                match_date = pd.to_datetime(match['created_at']).strftime('%m/%d %H:%M')
                                st.caption(f"📅 {match_date}")
                            
                            # Match details
                            if category in ['Mens Singles', 'Womens Singles']:
                                # Singles match display
                                col1, col2, col3 = st.columns([2, 1, 2])
                                with col1:
                                    st.markdown(f"**🏃‍♂️ Player 1:**\n{match['player1_name'] or 'TBD'}")
                                with col2:
                                    st.markdown("**VS**")
                                with col3:
                                    st.markdown(f"**🏃‍♂️ Player 2:**\n{match['player2_name'] or 'TBD'}")
                                
                                # Winner or result buttons
                                if match['match_status'] == 'completed':
                                    st.success(f"🏆 **Winner:** {match['winner_name']}")
                                else:
                                    st.write("**Declare Winner:**")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        if st.button(f"🏆 {match['player1_name']}", key=f"win1_{match['id']}", use_container_width=True):
                                            update_match_result(match['id'], winner_id=match['player1_id'])
                                            st.success(f"{match['player1_name']} wins!")
                                            st.rerun()
                                    with col2:
                                        if st.button(f"🏆 {match['player2_name']}", key=f"win2_{match['id']}", use_container_width=True):
                                            update_match_result(match['id'], winner_id=match['player2_id'])
                                            st.success(f"{match['player2_name']} wins!")
                                            st.rerun()
                            
                            else:
                                # Doubles match display
                                col1, col2, col3 = st.columns([2, 1, 2])
                                with col1:
                                    st.markdown(f"**� Team 1:**")
                                    st.write(f"• {match['team1_player1_name'] or 'TBD'}")
                                    st.write(f"• {match['team1_player2_name'] or 'TBD'}")
                                with col2:
                                    st.markdown("**VS**")
                                with col3:
                                    st.markdown(f"**👥 Team 2:**")
                                    st.write(f"• {match['team2_player1_name'] or 'TBD'}")
                                    st.write(f"• {match['team2_player2_name'] or 'TBD'}")
                                
                                # Winner or result buttons for doubles
                                if match['match_status'] == 'completed':
                                    if match['winner_team'] == 1:
                                        team1 = f"{match['team1_player1_name']} & {match['team1_player2_name']}"
                                        st.success(f"🏆 **Winner:** Team 1 ({team1})")
                                    elif match['winner_team'] == 2:
                                        team2 = f"{match['team2_player1_name']} & {match['team2_player2_name']}"
                                        st.success(f"🏆 **Winner:** Team 2 ({team2})")
                                else:
                                    st.write("**Declare Winner:**")
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        team1 = f"{match['team1_player1_name']} & {match['team1_player2_name']}"
                                        if st.button(f"🏆 Team 1", key=f"team1_win_{match['id']}", use_container_width=True):
                                            update_match_result(match['id'], winner_team=1)
                                            st.success(f"Team 1 wins!")
                                            st.rerun()
                                    with col2:
                                        team2 = f"{match['team2_player1_name']} & {match['team2_player2_name']}"
                                        if st.button(f"🏆 Team 2", key=f"team2_win_{match['id']}", use_container_width=True):
                                            update_match_result(match['id'], winner_team=2)
                                            st.success(f"Team 2 wins!")
                                            st.rerun()
                            
                            st.divider()
    else:
        st.info("No matches found. Create some matches to see them here.")

with tab5:
    # Tournament Bracket
    st.subheader("🏆 Tournament Bracket")
    st.info("Tournament bracket view coming soon!")
    # Winners Tab
    st.subheader("👑 Tournament Winners")
    
    matches_df = get_matches()
    completed_matches = matches_df[matches_df['match_status'] == 'completed']
    
    if completed_matches.empty:
        st.info("No completed matches found. Complete some matches to see winners here.")
    else:
        # Get participants data for additional details
        participants_df = get_participants()
        
        # Winners summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Completed Matches", len(completed_matches))
        with col2:
            categories_with_winners = completed_matches['category'].nunique()
            st.metric("Categories with Winners", categories_with_winners)
        with col3:
            if not completed_matches.empty:
                latest_match = completed_matches.iloc[0]
                latest_date = pd.to_datetime(latest_match['completed_at']).strftime('%m/%d %H:%M')
                st.metric("Latest Match", latest_date)
        
        st.divider()
        
        # Group winners by category
        categories = completed_matches['category'].unique()
        
        for category in sorted(categories):
            with st.expander(f"🏆 {category} Winners", expanded=True):
                category_matches = completed_matches[completed_matches['category'] == category].sort_values('completed_at', ascending=False)
                
                for _, match in category_matches.iterrows():
                    # Create winner card
                    winner_container = st.container()
                    with winner_container:
                        # Winner header
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            st.markdown(f"**🆔 Match #{match['id']} - Round {match['round_number']}**")
                        with col2:
                            completed_date = pd.to_datetime(match['completed_at']).strftime('%B %d, %Y at %I:%M %p')
                            st.caption(f"🕒 Completed: {completed_date}")
                        
                        if category in ['Mens Singles', 'Womens Singles']:
                            # Singles winner display
                            winner_id = match['winner_id']
                            winner_name = match['winner_name']
                            
                            # Get winner details
                            winner_details = participants_df[participants_df['id'] == winner_id].iloc[0] if not participants_df[participants_df['id'] == winner_id].empty else None
                            
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.success(f"🏆 **Winner:** {winner_name}")
                            with col2:
                                if winner_details is not None:
                                    st.info(f"**Details:**\n- Employee ID: {winner_details['emp_id']}\n- Email: {winner_details['email']}")
                            
                            # Opponent details
                            opponent_name = match['player2_name'] if match['player1_name'] == winner_name else match['player1_name']
                            opponent_id = match['player2_id'] if match['player1_id'] == winner_id else match['player1_id']
                            opponent_details = participants_df[participants_df['id'] == opponent_id].iloc[0] if not participants_df[participants_df['id'] == opponent_id].empty else None
                            
                            st.markdown(f"**🥈 Defeated:** {opponent_name}")
                            if opponent_details is not None:
                                st.caption(f"Employee ID: {opponent_details['emp_id']} | Email: {opponent_details['email']}")
                        
                        else:
                            # Doubles winner display
                            winner_team = match['winner_team']
                            
                            if winner_team == 1:
                                winner_player1_name = match['team1_player1_name']
                                winner_player2_name = match['team1_player2_name']
                                winner_player1_id = match['team1_player1_id']
                                winner_player2_id = match['team1_player2_id']
                                loser_player1_name = match['team2_player1_name']
                                loser_player2_name = match['team2_player2_name']
                                loser_player1_id = match['team2_player1_id']
                                loser_player2_id = match['team2_player2_id']
                            else:
                                winner_player1_name = match['team2_player1_name']
                                winner_player2_name = match['team2_player2_name']
                                winner_player1_id = match['team2_player1_id']
                                winner_player2_id = match['team2_player2_id']
                                loser_player1_name = match['team1_player1_name']
                                loser_player2_name = match['team1_player2_name']
                                loser_player1_id = match['team1_player1_id']
                                loser_player2_id = match['team1_player2_id']
                            
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.success(f"🏆 **Winning Team:**\n• {winner_player1_name}\n• {winner_player2_name}")
                            with col2:
                                # Get winner details
                                winner1_details = participants_df[participants_df['id'] == winner_player1_id].iloc[0] if not participants_df[participants_df['id'] == winner_player1_id].empty else None
                                winner2_details = participants_df[participants_df['id'] == winner_player2_id].iloc[0] if not participants_df[participants_df['id'] == winner_player2_id].empty else None
                                
                                details_text = "**Winners Details:**\n"
                                if winner1_details is not None:
                                    details_text += f"• {winner1_details['emp_id']} - {winner1_details['email']}\n"
                                if winner2_details is not None:
                                    details_text += f"• {winner2_details['emp_id']} - {winner2_details['email']}"
                                st.info(details_text)
                            
                            # Opponent team details
                            st.markdown(f"**🥈 Defeated Team:**\n• {loser_player1_name}\n• {loser_player2_name}")
                            
                            # Get loser details
                            loser1_details = participants_df[participants_df['id'] == loser_player1_id].iloc[0] if not participants_df[participants_df['id'] == loser_player1_id].empty else None
                            loser2_details = participants_df[participants_df['id'] == loser_player2_id].iloc[0] if not participants_df[participants_df['id'] == loser_player2_id].empty else None
                            
                            loser_details_text = ""
                            if loser1_details is not None:
                                loser_details_text += f"• {loser1_details['emp_id']} - {loser1_details['email']}\n"
                            if loser2_details is not None:
                                loser_details_text += f"• {loser2_details['emp_id']} - {loser2_details['email']}"
                            st.caption(loser_details_text)
                        
                        st.divider()

with tab7:
    # Winners tab content - simplified to only show recent winners
    st.subheader("👑 Recent Winners")
    
    matches_df = get_matches()
    completed_matches = matches_df[matches_df['match_status'] == 'completed']
    
    if completed_matches.empty:
        st.info("No completed matches found. Complete some matches to see winners here.")
    else:
        # Get participants data for additional details
        participants_df = get_participants()
        
        # Winners summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Completed Matches", len(completed_matches))
        with col2:
            categories_with_winners = completed_matches['category'].nunique()
            st.metric("Categories with Winners", categories_with_winners)
        with col3:
            if not completed_matches.empty:
                latest_match = completed_matches.iloc[0]
                latest_date = pd.to_datetime(latest_match['completed_at']).strftime('%m/%d %H:%M')
                st.metric("Latest Match", latest_date)
        
        st.divider()
        
        # Group winners by category
        categories = completed_matches['category'].unique()
        
        for category in sorted(categories):
            with st.expander(f"🏆 {category} Winners", expanded=True):
                category_matches = completed_matches[completed_matches['category'] == category].sort_values('completed_at', ascending=False)
                
                for _, match in category_matches.iterrows():
                    # Create winner card
                    winner_container = st.container()
                    with winner_container:
                        # Winner header
                        col1, col2, col3 = st.columns([2, 2, 1])
                        with col1:
                            st.markdown(f"**🆔 Match #{match['id']} - Round {match['round_number']}**")
                        with col2:
                            completed_date = pd.to_datetime(match['completed_at']).strftime('%B %d, %Y at %I:%M %p')
                            st.caption(f"🕒 Completed: {completed_date}")
                        
                        if category in ['Mens Singles', 'Womens Singles']:
                            # Singles winner display
                            winner_id = match['winner_id']
                            winner_name = match['winner_name']
                            
                            # Get winner details
                            winner_details = participants_df[participants_df['id'] == winner_id].iloc[0] if not participants_df[participants_df['id'] == winner_id].empty else None
                            
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.success(f"🏆 **Winner:** {winner_name}")
                            with col2:
                                if winner_details is not None:
                                    st.info(f"**Details:**\n- Employee ID: {winner_details['emp_id']}\n- Email: {winner_details['email']}")
                            
                            # Opponent details
                            opponent_name = match['player2_name'] if match['player1_name'] == winner_name else match['player1_name']
                            opponent_id = match['player2_id'] if match['player1_id'] == winner_id else match['player1_id']
                            opponent_details = participants_df[participants_df['id'] == opponent_id].iloc[0] if not participants_df[participants_df['id'] == opponent_id].empty else None
                            
                            st.markdown(f"**🥈 Defeated:** {opponent_name}")
                            if opponent_details is not None:
                                st.caption(f"Employee ID: {opponent_details['emp_id']} | Email: {opponent_details['email']}")
                        
                        else:
                            # Doubles winner display
                            winner_team = match['winner_team']
                            
                            if winner_team == 1:
                                winner_player1_name = match['team1_player1_name']
                                winner_player2_name = match['team1_player2_name']
                                winner_player1_id = match['team1_player1_id']
                                winner_player2_id = match['team1_player2_id']
                                loser_player1_name = match['team2_player1_name']
                                loser_player2_name = match['team2_player2_name']
                                loser_player1_id = match['team2_player1_id']
                                loser_player2_id = match['team2_player2_id']
                            else:
                                winner_player1_name = match['team2_player1_name']
                                winner_player2_name = match['team2_player2_name']
                                winner_player1_id = match['team2_player1_id']
                                winner_player2_id = match['team2_player2_id']
                                loser_player1_name = match['team1_player1_name']
                                loser_player2_name = match['team1_player2_name']
                                loser_player1_id = match['team1_player1_id']
                                loser_player2_id = match['team1_player2_id']
                            
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.success(f"🏆 **Winning Team:**\n• {winner_player1_name}\n• {winner_player2_name}")
                            with col2:
                                # Get winner details
                                winner1_details = participants_df[participants_df['id'] == winner_player1_id].iloc[0] if not participants_df[participants_df['id'] == winner_player1_id].empty else None
                                winner2_details = participants_df[participants_df['id'] == winner_player2_id].iloc[0] if not participants_df[participants_df['id'] == winner_player2_id].empty else None
                                
                                details_text = "**Winners Details:**\n"
                                if winner1_details is not None:
                                    details_text += f"• {winner1_details['emp_id']} - {winner1_details['email']}\n"
                                if winner2_details is not None:
                                    details_text += f"• {winner2_details['emp_id']} - {winner2_details['email']}"
                                st.info(details_text)
                            
                            # Opponent team details
                            st.markdown(f"**🥈 Defeated Team:**\n• {loser_player1_name}\n• {loser_player2_name}")
                            
                            # Get loser details
                            loser1_details = participants_df[participants_df['id'] == loser_player1_id].iloc[0] if not participants_df[participants_df['id'] == loser_player1_id].empty else None
                            loser2_details = participants_df[participants_df['id'] == loser_player2_id].iloc[0] if not participants_df[participants_df['id'] == loser_player2_id].empty else None
                            
                            loser_details_text = ""
                            if loser1_details is not None:
                                loser_details_text += f"• {loser1_details['emp_id']} - {loser1_details['email']}\n"
                            if loser2_details is not None:
                                loser_details_text += f"• {loser2_details['emp_id']} - {loser2_details['email']}"
                            st.caption(loser_details_text)
                        
                        st.divider()

with tab5:
    # Tournament Bracket
    st.subheader("🏆 Tournament Bracket")
    
    matches_df = get_matches()
    
    if matches_df.empty:
        st.info("No matches found. Create some matches to view the tournament bracket.")
    else:
        # Category selection for bracket view
        categories = matches_df['category'].unique()
        selected_category = st.selectbox("Select category to view bracket:", categories, key="bracket_view_category_tab1")
        
        category_matches = matches_df[matches_df['category'] == selected_category]
        
        if not category_matches.empty:
            # Group by rounds
            rounds = sorted(category_matches['round_number'].unique())
            
            for round_num in rounds:
                st.subheader(f"Round {round_num}")
                round_matches = category_matches[category_matches['round_number'] == round_num]
                
                for _, match in round_matches.iterrows():
                    if match['category'] in ['Mens Singles', 'Womens Singles']:
                        match_display = f"{match['player1_name']} vs {match['player2_name']}"
                    else:
                        team1 = f"{match['team1_player1_name']} & {match['team1_player2_name']}"
                        team2 = f"{match['team2_player1_name']} & {match['team2_player2_name']}"
                        match_display = f"{team1} vs {team2}"
                    
                    status_emoji = "✅" if match['match_status'] == 'completed' else "⏳"
                    winner_info = f" - Winner: {match['winner_name']}" if match['match_status'] == 'completed' and match['winner_name'] else ""
                    
                    st.write(f"{status_emoji} {match_display}{winner_info}")

with tab6:
    # Tournament Bracket
    st.subheader("🏆 Tournament Bracket")
    
    matches_df = get_matches()
    
    if matches_df.empty:
        st.info("No matches found. Create some matches to view the tournament bracket.")
    else:
        # Category selection for bracket view
        categories = matches_df['category'].unique()
        selected_category = st.selectbox("Select category to view bracket:", categories, key="bracket_view_category_tab2")
        
        category_matches = matches_df[matches_df['category'] == selected_category]
        
        if not category_matches.empty:
            # Group by rounds
            rounds = sorted(category_matches['round_number'].unique())
            
            for round_num in rounds:
                st.subheader(f"Round {round_num}")
                round_matches = category_matches[category_matches['round_number'] == round_num]
                
                for _, match in round_matches.iterrows():
                    if match['category'] in ['Mens Singles', 'Womens Singles']:
                        match_display = f"{match['player1_name']} vs {match['player2_name']}"
                    else:
                        team1 = f"{match['team1_player1_name']} & {match['team1_player2_name']}"
                        team2 = f"{match['team2_player1_name']} & {match['team2_player2_name']}"
                        match_display = f"{team1} vs {team2}"
                    
                    status_emoji = "✅" if match['match_status'] == 'completed' else "⏳"
                    winner_info = f" - Winner: {match['winner_name']}" if match['match_status'] == 'completed' and match['winner_name'] else ""
                    
                    st.write(f"{status_emoji} {match_display}{winner_info}")
    
    # Detailed reports
    if not participants_df.empty:
        st.subheader("📋 Detailed Participant List")
        
        # Search and filter options
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("Filter by status:", ["All", "Reported", "Not Reported"])
        with col2:
            category_filter = st.selectbox("Filter by category:", ["All"] + list(participants_df['category'].unique()))
        
        # Apply filters
        filtered_participants = participants_df.copy()
        
        if status_filter == "Reported":
            filtered_participants = filtered_participants[filtered_participants['registered_at_desk'] == 1]
        elif status_filter == "Not Reported":
            filtered_participants = filtered_participants[filtered_participants['registered_at_desk'] == 0]
        
        if category_filter != "All":
            filtered_participants = filtered_participants[filtered_participants['category'] == category_filter]
        
        st.write(f"Showing {len(filtered_participants)} participants")
        
        # Display with pagination for large lists
        if len(filtered_participants) > 500:
            st.info("Large dataset detected. Use search and filters to narrow down results.")
            
            search_term = st.text_input("🔍 Search participants:")
            if search_term:
                filtered_participants = search_participants(search_term, filtered_participants)
                st.write(f"Search results: {len(filtered_participants)} participants")
        
        # Show results with pagination
        if len(filtered_participants) > 100:
            page_size = 100
            total_pages = (len(filtered_participants) - 1) // page_size + 1
            page = st.selectbox("Select page:", range(1, total_pages + 1))
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            display_df = filtered_participants.iloc[start_idx:end_idx]
        else:
            display_df = filtered_participants
        
        # Format display
        display_df = display_df.copy()
        display_df['Status'] = display_df['registered_at_desk'].apply(lambda x: 'Reported' if x else 'Not Reported')
        
        # Add partner name lookup for display
        display_df['Partner'] = display_df['partner_emp_id'].apply(lambda x: x if x else 'None')
        
        st.dataframe(display_df[['emp_id', 'name', 'email', 'category', 'Partner', 'Status']], use_container_width=True)

with tab8:
    # Reports & Export tab content
    st.subheader("📊 Reports & Export")
    
    participants_df = get_participants()
    matches_df = get_matches()
    
    # Summary statistics
    st.subheader("📈 Tournament Summary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total Participants", len(participants_df))
        st.metric("Reported Participants", len(participants_df[participants_df['registered_at_desk'] == 1]) if not participants_df.empty else 0)
    
    with col2:
        st.metric("Total Matches", len(matches_df))
        st.metric("Completed Matches", len(matches_df[matches_df['match_status'] == 'completed']) if not matches_df.empty else 0)
    
    # Reports section
    st.subheader("📊 Tournament Reports")
    
    # Participants by Category report
    if st.button("📋 Generate Participants by Category Report"):
        if not participants_df.empty:
            # Category-wise breakdown with enhanced styling
            st.subheader("📊 Category-wise Participants")
            category_counts = participants_df['category'].value_counts().reset_index()
            category_counts.columns = ['Category', 'Count']
            
            # Display bar chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=category_counts['Category'],
                y=category_counts['Count'],
                marker_color=['#5bc0be', '#3a506b', '#ff6b35', '#f7882f', '#6b818c'],
                text=category_counts['Count'],
                textposition='auto',
            ))
            fig.update_layout(
                title="Participants by Category",
                xaxis_title="Category",
                yaxis_title="Number of Participants",
                template="plotly_white",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Apply custom CSS to the dataframe
            st.markdown("""
            <style>
            .category-table-container {
                margin: 20px 0;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Display styled table
            st.markdown("<div class='category-table-container'>", unsafe_allow_html=True)
            st.markdown("""
            <style>
                .category-table th {
                    background: linear-gradient(90deg, #3a506b 0%, #5bc0be 100%);
                    color: white;
                    text-align: center;
                    padding: 15px;
                    font-weight: bold;
                    font-size: 1.1em;
                }
                .category-table tr:nth-child(odd) {
                    background: linear-gradient(90deg, #f5f7fa 0%, #e4efe9 100%);
                }
                .category-table tr:nth-child(even) {
                    background: linear-gradient(90deg, #e4efe9 0%, #d4e4ef 100%);
                }
            </style>
            """, unsafe_allow_html=True)
            st.table(category_counts.set_index('Category'))
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Detailed breakdown by category
            st.subheader("📋 Detailed Breakdown by Category")
            
            for category in sorted(participants_df['category'].unique()):
                with st.expander(f"{category} - {len(participants_df[participants_df['category'] == category])} participants"):
                    category_data = participants_df[participants_df['category'] == category]
                    
                    # Show registration status breakdown
                    reported = len(category_data[category_data['registered_at_desk'] == 1])
                    not_reported = len(category_data[category_data['registered_at_desk'] == 0])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Reported", reported)
                    with col2:
                        st.metric("Not Reported", not_reported)
                    
                    # Show participant list
                    st.dataframe(category_data[['emp_id', 'name', 'email', 'registered_at_desk']], use_container_width=True)
            
            # Export participants
    
    # Create email notification tabs
    email_tab1, email_tab2, email_tab3 = st.tabs(["📅 Match Fixtures", "🏆 Winner Notifications", "📝 Custom Email"])
    
    with email_tab1:
            st.subheader("📅 Send Match Fixture Notifications")
            st.write("Notify participants about their upcoming matches.")
        
            # Get upcoming matches
            upcoming_matches = get_upcoming_matches()
            
            if upcoming_matches.empty:
                st.info("No upcoming matches found. Create some matches first.")
            else:
                # Filter options
                col1, col2 = st.columns(2)
                with col1:
                    category_filter = st.selectbox(
                        "Filter by category:", 
                        ["All"] + list(upcoming_matches['category'].unique()),
                        key="fixture_category_filter"
                    )
                with col2:
                    round_filter = st.selectbox(
                        "Filter by round:", 
                        ["All"] + list(map(str, sorted(upcoming_matches['round_number'].unique()))),
                        key="fixture_round_filter"
                    )
                
                # Apply filters
                filtered_matches = upcoming_matches.copy()
                if category_filter != "All":
                    filtered_matches = filtered_matches[filtered_matches['category'] == category_filter]
                if round_filter != "All":
                    filtered_matches = filtered_matches[filtered_matches['round_number'] == int(round_filter)]
                
                # Display matches
                st.write(f"Showing {len(filtered_matches)} upcoming matches")
            
                if not filtered_matches.empty:
                    # Create a selection grid for matches
                    match_options = []
                    for idx, match in filtered_matches.iterrows():
                        if 'Singles' in match['category']:
                            match_desc = f"{match['category']} - Round {match['round_number']}: {match['player1_name']} vs {match['player2_name']}"
                        else:
                            match_desc = f"{match['category']} - Round {match['round_number']}: {match['team1_names']} vs {match['team2_names']}"
                        match_options.append({"id": match['id'], "description": match_desc})
                    
                    selected_matches = st.multiselect(
                        "Select matches to send notifications for:",
                        options=[m["id"] for m in match_options],
                        format_func=lambda x: next((m["description"] for m in match_options if m["id"] == x), ""),
                        key="fixture_match_select"
                    )
                    
                    if selected_matches:
                        # Email customization
                        st.subheader("Email Content")
                    
                        email_subject = st.text_input(
                            "Email Subject:", 
                            value="Carrom Tournament - Your Upcoming Match Details",
                            key="fixture_email_subject"
                        )
                        
                        email_intro = st.text_area(
                            "Email Introduction:",
                            value="Hello,\n\nYou have an upcoming match in the Carrom Tournament. Please find the details below:",
                            height=100,
                            key="fixture_email_intro"
                        )
                        
                        email_footer = st.text_area(
                            "Email Footer:",
                            value="\nBest regards,\nTournament Organizers",
                            height=100,
                            key="fixture_email_footer"
                        )
                    
                        # Preview section
                        with st.expander("📝 Preview Email", expanded=False):
                            st.subheader("Email Preview")
                            st.write(f"**Subject:** {email_subject}")
                            st.write("**Body:**")
                            
                            # Show preview for first selected match
                            if selected_matches:
                                preview_match = filtered_matches[filtered_matches['id'] == selected_matches[0]].iloc[0]
                                match_details = get_match_details(selected_matches[0])
                                
                                if match_details:
                                    preview_body = email_intro + "\n\n"
                                    
                                    if 'Singles' in preview_match['category']:
                                        preview_body += f"Category: {preview_match['category']}\n"
                                        preview_body += f"Round: {preview_match['round_number']}\n"
                                        preview_body += f"Match: {preview_match['player1_name']} vs {preview_match['player2_name']}\n"
                                    else:
                                        preview_body += f"Category: {preview_match['category']}\n"
                                        preview_body += f"Round: {preview_match['round_number']}\n"
                                        preview_body += f"Match: {preview_match['team1_names']} vs {preview_match['team2_names']}\n"
                                    
                                    preview_body += email_footer
                                    st.text(preview_body)
                        
                        # Initialize session state for review if not exists
                        if 'fixture_emails_to_review' not in st.session_state:
                            st.session_state.fixture_emails_to_review = []
                        if 'show_fixture_review' not in st.session_state:
                            st.session_state.show_fixture_review = False
                        
                        # Preview button
                        if st.button("📝 Review Emails Before Sending", key="review_fixture_emails"):
                            with st.spinner("Preparing emails for review..."):
                                emails_to_review = []
                                
                                for match_id in selected_matches:
                                    match_details = get_match_details(match_id)
                                
                                    if match_details:
                                        # Prepare email content
                                        email_body = email_intro + "\n\n"
                                        
                                        if 'Singles' in match_details['category']:
                                            email_body += f"Category: {match_details['category']}\n"
                                            email_body += f"Round: {match_details['round_number']}\n"
                                            email_body += f"Match: {match_details['player1_name']} vs {match_details['player2_name']}\n"
                                            
                                            # Get player emails
                                            recipients = []
                                            if 'player1_email' in match_details and match_details['player1_email']:
                                                recipients.append(match_details['player1_email'])
                                            if 'player2_email' in match_details and match_details['player2_email']:
                                                recipients.append(match_details['player2_email'])
                                                
                                            match_description = f"{match_details['player1_name']} vs {match_details['player2_name']}"
                                        else:
                                            email_body += f"Category: {match_details['category']}\n"
                                            email_body += f"Round: {match_details['round_number']}\n"
                                            team1_names = []
                                            if 'team1_player1_name' in match_details:
                                                team1_names.append(match_details['team1_player1_name'])
                                            if 'team1_player2_name' in match_details:
                                                team1_names.append(match_details['team1_player2_name'])
                                                
                                            team2_names = []
                                            if 'team2_player1_name' in match_details:
                                                team2_names.append(match_details['team2_player1_name'])
                                            if 'team2_player2_name' in match_details:
                                                team2_names.append(match_details['team2_player2_name'])
                                                
                                            email_body += f"Match: {' & '.join(team1_names)} vs {' & '.join(team2_names)}\n"
                                            
                                            # Get team member emails
                                            recipients = []
                                            if 'team1_player1_email' in match_details and match_details['team1_player1_email']:
                                                recipients.append(match_details['team1_player1_email'])
                                            if 'team1_player2_email' in match_details and match_details['team1_player2_email']:
                                                recipients.append(match_details['team1_player2_email'])
                                            if 'team2_player1_email' in match_details and match_details['team2_player1_email']:
                                                recipients.append(match_details['team2_player1_email'])
                                            if 'team2_player2_email' in match_details and match_details['team2_player2_email']:
                                                recipients.append(match_details['team2_player2_email'])
                                                
                                            match_description = f"{' & '.join(team1_names)} vs {' & '.join(team2_names)}"
                                        
                                        email_body += email_footer
                                        
                                        # Add to review list
                                        if recipients:
                                            emails_to_review.append({
                                                'match_id': match_id,
                                                'recipients': recipients,
                                                'subject': email_subject,
                                                'body': email_body,
                                                'match_description': match_description
                                            })
                            
                                # Store in session state
                                st.session_state.fixture_emails_to_review = emails_to_review
                                st.session_state.show_fixture_review = True
                        
                        # Show review interface if needed
                        if st.session_state.show_fixture_review and st.session_state.fixture_emails_to_review:
                            st.subheader("📋 Email Review")                        
                            
                            # Show a sample email
                            sample = st.session_state.fixture_emails_to_review[0]
                            st.markdown("**Sample Email Preview:**")
                            st.markdown(f"**To:** {', '.join(sample['recipients'])}")
                            st.markdown(f"**Subject:** {sample['subject']}")
                            st.text_area("Email Body", sample['body'], height=200, key="fixture_preview_body", disabled=True)
                            
                            # Show summary
                            total_emails = len(st.session_state.fixture_emails_to_review)
                            total_recipients = sum(len(email['recipients']) for email in st.session_state.fixture_emails_to_review)
                            st.markdown(f"**Total emails to be sent:** {total_emails} (to {total_recipients} recipients)")
                            
                            # List all matches
                            with st.expander("View all matches", expanded=False):
                                for email in st.session_state.fixture_emails_to_review:
                                    st.markdown(f"- **{email['match_description']}** (To: {', '.join(email['recipients'])})")
                            
                            # Confirmation buttons
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                if st.button("📤 Confirm and Send Emails", key="confirm_fixture_emails"):
                                    with st.spinner("Sending emails..."):
                                        success_count = 0
                                        fail_count = 0
                                        
                                        for email_data in st.session_state.fixture_emails_to_review:
                                            try:
                                                if send_outlook_email(email_data['recipients'], email_data['subject'], email_data['body']):
                                                    success_count += 1
                                                else:
                                                    fail_count += 1
                                            except Exception as e:
                                                st.error(f"Error sending email for match {email_data['match_id']}: {str(e)}")
                                                fail_count += 1
                                    
                                    # Show results
                                    if success_count > 0:
                                        st.success(f"✅ Successfully sent {success_count} match fixture notifications")
                                    if fail_count > 0:
                                        st.error(f"❌ Failed to send {fail_count} match fixture notifications")
                                    
                                    # Clear review state
                                    st.session_state.show_fixture_review = False
                                    st.session_state.fixture_emails_to_review = []
                        
                        with col2:
                            # Add options for draft saving
                            draft_options = st.radio(
                                "Draft Options:",
                                ["Save as individual drafts", "Save as batch drafts (5 per batch)", "Save as batch drafts (10 per batch)"],
                                key="fixture_draft_options",
                                horizontal=True
                            )
                            
                            open_outlook = st.checkbox("Open Outlook after creating drafts", value=True, key="fixture_open_outlook")
                            
                            if st.button("📝 Save as Drafts in Outlook", key="save_fixture_drafts"):
                                with st.spinner("Saving emails as drafts..."):
                                    success_count = 0
                                    fail_count = 0
                                    
                                    # Determine batch size
                                    batch_size = 1  # Default: individual emails
                                    if draft_options == "Save as batch drafts (5 per batch)":
                                        batch_size = 5
                                    elif draft_options == "Save as batch drafts (10 per batch)":
                                        batch_size = 10
                                    
                                    # Process emails in batches if needed
                                    if batch_size > 1:
                                        # Group emails into batches
                                        email_batches = []
                                        current_batch = []
                                        current_recipients = []
                                        
                                        for i, email_data in enumerate(st.session_state.fixture_emails_to_review):
                                            current_batch.append(email_data)
                                            current_recipients.extend(email_data['recipients'])
                                            
                                            # When batch is full or this is the last email
                                            if len(current_batch) >= batch_size or i == len(st.session_state.fixture_emails_to_review) - 1:
                                                if current_batch:  # Make sure batch isn't empty
                                                    # Create a batch summary
                                                    batch_subject = f"Carrom Tournament - Match Fixture Notifications (Batch of {len(current_batch)})"
                                                    batch_body = "Hello Tournament Organizer,\n\nBelow are the match fixture emails ready to be sent. Please review and send them individually.\n\n=== EMAILS IN THIS BATCH ==="
                                                    
                                                    # Add each email to the batch body
                                                    for idx, email in enumerate(current_batch):
                                                        batch_body += "\n\n--- EMAIL " + str(idx+1) + " ---\n"
                                                        batch_body += "To: " + ', '.join(email['recipients']) + "\n"
                                                        batch_body += "Subject: " + email['subject'] + "\n"
                                                        batch_body += "Body:\n" + email['body'] + "\n"
                                                        batch_body += "\n--- END OF EMAIL ---"
                                                    
                                                    # Add the batch to our list
                                                    email_batches.append({
                                                        'subject': batch_subject,
                                                        'body': batch_body,
                                                        'recipients': ['tournament.organizer@example.com']  # Placeholder recipient
                                                    })
                                                    
                                                    # Reset for next batch
                                                    current_batch = []
                                                    current_recipients = []
                                        
                                        # Save each batch as a draft
                                        for batch in email_batches:
                                            try:
                                                if send_outlook_email(
                                                    batch['recipients'][0],  # Send to organizer
                                                    batch['subject'], 
                                                    batch['body'], 
                                                    draft_only=True,
                                                    open_outlook=open_outlook and success_count == 0  # Only open on first success
                                                ):
                                                    success_count += 1
                                                else:
                                                    fail_count += 1
                                            except Exception as e:
                                                st.error(f"Error saving batch draft: {str(e)}")
                                                fail_count += 1
                                    else:
                                        # Save individual drafts (original behavior)
                                        for i, email_data in enumerate(st.session_state.fixture_emails_to_review):
                                            try:
                                                if send_outlook_email(
                                                    email_data['recipients'], 
                                                    email_data['subject'], 
                                                    email_data['body'], 
                                                    draft_only=True,
                                                    open_outlook=open_outlook and i == 0  # Only open on first email
                                                ):
                                                    success_count += 1
                                                else:
                                                    fail_count += 1
                                            except Exception as e:
                                                st.error(f"Error saving draft for match {email_data['match_id']}: {str(e)}")
                                                fail_count += 1
                                    
                                    # Show results
                                    if batch_size > 1 and success_count > 0:
                                        st.success(f"✅ Successfully saved {success_count} batch drafts in Outlook")
                                        st.info("Each draft contains multiple emails that you can review and send individually.")
                                    elif success_count > 0:
                                        st.success(f"✅ Successfully saved {success_count} emails as drafts in Outlook")
                                        st.info("Please review and send the draft emails in Outlook.")
                                        
                                    if fail_count > 0:
                                        st.error(f"❌ Failed to save {fail_count} drafts")
                                    
                                    # Clear review state
                                    st.session_state.show_fixture_review = False
                                    st.session_state.fixture_emails_to_review = []
                        
                        with col3:
                            if st.button("❌ Cancel", key="cancel_fixture_emails"):
                                st.session_state.show_fixture_review = False
                                st.session_state.fixture_emails_to_review = []
                                st.info("Email sending cancelled.")
                                st.rerun()
                else:
                    st.info("Please select at least one match to send notifications.")
    
    with email_tab2:
        st.subheader("🏆 Send Winner Notifications")
        st.write("Notify participants about match results and winners.")
        
        # Get completed matches with winners
        completed_matches = get_recent_winners(limit=50)  # Get up to 50 recent winners
        
        if completed_matches.empty:
            st.info("No completed matches with winners found.")
        else:
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                category_filter = st.selectbox(
                    "Filter by category:", 
                    ["All"] + list(completed_matches['category'].unique()),
                    key="winner_category_filter"
                )
            with col2:
                round_filter = st.selectbox(
                    "Filter by round:", 
                    ["All"] + list(map(str, sorted(completed_matches['round_number'].unique()))),
                    key="winner_round_filter"
                )
            
            # Apply filters
            filtered_matches = completed_matches.copy()
            if category_filter != "All":
                filtered_matches = filtered_matches[filtered_matches['category'] == category_filter]
            if round_filter != "All":
                filtered_matches = filtered_matches[filtered_matches['round_number'] == int(round_filter)]
            
            # Display matches
            st.write(f"Showing {len(filtered_matches)} completed matches with winners")
            
            if not filtered_matches.empty:
                # Create a selection grid for matches
                match_options = []
                for idx, match in filtered_matches.iterrows():
                    if 'Singles' in match['category']:
                        match_desc = f"{match['category']} - Round {match['round_number']}: Winner - {match['winner_name']}"
                    else:
                        match_desc = f"{match['category']} - Round {match['round_number']}: Winners - {match['winner_team_names']}"
                    match_options.append({"id": match['id'], "description": match_desc})
                
                selected_matches = st.multiselect(
                    "Select matches to send winner notifications for:",
                    options=[m["id"] for m in match_options],
                    format_func=lambda x: next((m["description"] for m in match_options if m["id"] == x), ""),
                    key="winner_match_select"
                )
                
                if selected_matches:
                    # Email customization
                    st.subheader("Email Content")
                    
                    email_subject = st.text_input(
                        "Email Subject:", 
                        value="Carrom Tournament - Match Results",
                        key="winner_email_subject"
                    )
                    
                    email_intro = st.text_area(
                        "Email Introduction:",
                        value="Hello,\n\nWe are pleased to announce the results of your recent match in the Carrom Tournament:",
                        height=100,
                        key="winner_email_intro"
                    )
                    
                    email_footer = st.text_area(
                        "Email Footer:",
                        value="\nCongratulations to the winners! Thank you all for participating.\n\nBest regards,\nTournament Organizers",
                        height=100,
                        key="winner_email_footer"
                    )
                    
                    # Preview section
                    with st.expander("📝 Preview Email", expanded=False):
                        st.subheader("Email Preview")
                        st.write(f"**Subject:** {email_subject}")
                        st.write("**Body:**")
                        
                        # Show preview for first selected match
                        if selected_matches:
                            preview_match = filtered_matches[filtered_matches['id'] == selected_matches[0]].iloc[0]
                            match_details = get_match_details(selected_matches[0])
                            
                            if match_details:
                                preview_body = email_intro + "\n\n"
                                
                                if 'Singles' in preview_match['category']:
                                    preview_body += f"Category: {preview_match['category']}\n"
                                    preview_body += f"Round: {preview_match['round_number']}\n"
                                    
                                    # Use match_details for player names if available, otherwise use safe fallbacks
                                    player1 = match_details.get('player1_name', 'Player 1')
                                    player2 = match_details.get('player2_name', 'Player 2')
                                    preview_body += f"Match: {player1} vs {player2}\n"
                                    preview_body += f"Winner: {preview_match['winner_name']}\n"
                                else:
                                    preview_body += f"Category: {preview_match['category']}\n"
                                    preview_body += f"Round: {preview_match['round_number']}\n"
                                    team1_names = []
                                    if 'team1_player1_name' in match_details:
                                        team1_names.append(match_details['team1_player1_name'])
                                    if 'team1_player2_name' in match_details:
                                        team1_names.append(match_details['team1_player2_name'])
                                        
                                    team2_names = []
                                    if 'team2_player1_name' in match_details:
                                        team2_names.append(match_details['team2_player1_name'])
                                    if 'team2_player2_name' in match_details:
                                        team2_names.append(match_details['team2_player2_name'])
                                        
                                    preview_body += f"Match: {' & '.join(team1_names)} vs {' & '.join(team2_names)}\n"
                                    preview_body += f"Winners: {preview_match['winner_team_names']}\n"
                                
                                preview_body += email_footer
                                st.text(preview_body)
                    
                    # Initialize session state for review if not exists
                    if 'winner_emails_to_review' not in st.session_state:
                        st.session_state.winner_emails_to_review = []
                    if 'show_winner_review' not in st.session_state:
                        st.session_state.show_winner_review = False
                    
                    # Preview button
                    if st.button("📝 Review Emails Before Sending", key="review_winner_emails"):
                        with st.spinner("Preparing emails for review..."):
                            emails_to_review = []
                            
                            for match_id in selected_matches:
                                match_details = get_match_details(match_id)
                                
                                if match_details:
                                    # Prepare email content
                                    email_body = email_intro + "\n\n"
                                    
                                    if 'Singles' in match_details['category']:
                                        email_body += f"Category: {match_details['category']}\n"
                                        email_body += f"Round: {match_details['round_number']}\n"
                                        email_body += f"Match: {match_details['player1_name']} vs {match_details['player2_name']}\n"
                                        
                                        # Get winner name
                                        if match_details['winner_id'] == match_details['player1_id']:
                                            winner_name = match_details['player1_name']
                                        else:
                                            winner_name = match_details['player2_name']
                                            
                                        email_body += f"Winner: {winner_name}\n"
                                        match_description = f"{match_details['player1_name']} vs {match_details['player2_name']} (Winner: {winner_name})"
                                        
                                        # Send to both players
                                        recipients = []
                                        if 'player1_email' in match_details and match_details['player1_email']:
                                            recipients.append(match_details['player1_email'])
                                        if 'player2_email' in match_details and match_details['player2_email']:
                                            recipients.append(match_details['player2_email'])
                                    else:
                                        email_body += f"Category: {match_details['category']}\n"
                                        email_body += f"Round: {match_details['round_number']}\n"
                                        
                                        team1_names = []
                                        if 'team1_player1_name' in match_details:
                                            team1_names.append(match_details['team1_player1_name'])
                                        if 'team1_player2_name' in match_details:
                                            team1_names.append(match_details['team1_player2_name'])
                                            
                                        team2_names = []
                                        if 'team2_player1_name' in match_details:
                                            team2_names.append(match_details['team2_player1_name'])
                                        if 'team2_player2_name' in match_details:
                                            team2_names.append(match_details['team2_player2_name'])
                                            
                                        email_body += f"Match: {' & '.join(team1_names)} vs {' & '.join(team2_names)}\n"
                                        
                                        # Get winner team names
                                        winner_team_names = []
                                        if match_details['winner_team'] == 'team1':
                                            winner_team_names = team1_names
                                            email_body += f"Winners: {' & '.join(team1_names)}\n"
                                        else:
                                            winner_team_names = team2_names
                                            email_body += f"Winners: {' & '.join(team2_names)}\n"
                                        
                                        match_description = f"{' & '.join(team1_names)} vs {' & '.join(team2_names)} (Winners: {' & '.join(winner_team_names)})"
                                        
                                        # Send to all team members
                                        recipients = []
                                        if 'team1_player1_email' in match_details and match_details['team1_player1_email']:
                                            recipients.append(match_details['team1_player1_email'])
                                        if 'team1_player2_email' in match_details and match_details['team1_player2_email']:
                                            recipients.append(match_details['team1_player2_email'])
                                        if 'team2_player1_email' in match_details and match_details['team2_player1_email']:
                                            recipients.append(match_details['team2_player1_email'])
                                        if 'team2_player2_email' in match_details and match_details['team2_player2_email']:
                                            recipients.append(match_details['team2_player2_email'])
                                    
                                    email_body += email_footer
                                    
                                    # Add to review list
                                    if recipients:
                                        emails_to_review.append({
                                            'match_id': match_id,
                                            'recipients': recipients,
                                            'subject': email_subject,
                                            'body': email_body,
                                            'match_description': match_description
                                        })
                            
                            # Store in session state
                            st.session_state.winner_emails_to_review = emails_to_review
                            st.session_state.show_winner_review = True
                    
                    # Show review interface if needed
                    if st.session_state.show_winner_review and st.session_state.winner_emails_to_review:
                        st.subheader("📋 Email Review")                        
                        
                        # Show a sample email
                        sample = st.session_state.winner_emails_to_review[0]
                        st.markdown("**Sample Email Preview:**")
                        st.markdown(f"**To:** {', '.join(sample['recipients'])}")
                        st.markdown(f"**Subject:** {sample['subject']}")
                        st.text_area("Email Body", sample['body'], height=200, key="winner_preview_body", disabled=True)
                        
                        # Show summary
                        total_emails = len(st.session_state.winner_emails_to_review)
                        total_recipients = sum(len(email['recipients']) for email in st.session_state.winner_emails_to_review)
                        st.markdown(f"**Total emails to be sent:** {total_emails} (to {total_recipients} recipients)")
                        
                        # List all matches
                        with st.expander("View all matches", expanded=False):
                            for email in st.session_state.winner_emails_to_review:
                                st.markdown(f"- **{email['match_description']}** (To: {', '.join(email['recipients'])})")
                        
                        # Confirmation buttons
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("📤 Confirm and Send Emails", key="confirm_winner_emails"):
                                with st.spinner("Sending emails..."):
                                    success_count = 0
                                    fail_count = 0
                                    
                                    for email_data in st.session_state.winner_emails_to_review:
                                        try:
                                            if send_outlook_email(email_data['recipients'], email_data['subject'], email_data['body']):
                                                success_count += 1
                                            else:
                                                fail_count += 1
                                        except Exception as e:
                                            st.error(f"Error sending email for match {email_data['match_id']}: {str(e)}")
                                            fail_count += 1
                                    
                                    # Show results
                                    if success_count > 0:
                                        st.success(f"✅ Successfully sent {success_count} winner notification emails")
                                    if fail_count > 0:
                                        st.error(f"❌ Failed to send {fail_count} winner notification emails")
                                    
                                    # Clear review state
                                    st.session_state.show_winner_review = False
                                    st.session_state.winner_emails_to_review = []
                        
                        with col2:
                            # Add options for draft saving
                            draft_options = st.radio(
                                "Draft Options:",
                                ["Save as individual drafts", "Save as batch drafts (5 per batch)", "Save as batch drafts (10 per batch)"],
                                key="winner_draft_options",
                                horizontal=True
                            )
                            
                            open_outlook = st.checkbox("Open Outlook after creating drafts", value=True, key="winner_open_outlook")
                            
                            if st.button("📝 Save as Drafts in Outlook", key="save_winner_drafts"):
                                with st.spinner("Saving emails as drafts..."):
                                    success_count = 0
                                    fail_count = 0
                                    
                                    # Determine batch size
                                    batch_size = 1  # Default: individual emails
                                    if draft_options == "Save as batch drafts (5 per batch)":
                                        batch_size = 5
                                    elif draft_options == "Save as batch drafts (10 per batch)":
                                        batch_size = 10
                                    
                                    # Process emails in batches if needed
                                    if batch_size > 1:
                                        # Group emails into batches
                                        email_batches = []
                                        current_batch = []
                                        current_recipients = []
                                        
                                        for i, email_data in enumerate(st.session_state.winner_emails_to_review):
                                            current_batch.append(email_data)
                                            current_recipients.extend(email_data['recipients'])
                                            
                                            # When batch is full or this is the last email
                                            if len(current_batch) >= batch_size or i == len(st.session_state.winner_emails_to_review) - 1:
                                                if current_batch:  # Make sure batch isn't empty
                                                    # Create a batch summary
                                                    batch_subject = f"Carrom Tournament - Winner Notifications (Batch of {len(current_batch)})"
                                                    batch_body = "Hello Tournament Organizer,\n\nBelow are the winner notification emails ready to be sent. Please review and send them individually.\n\n=== EMAILS IN THIS BATCH ==="
                                                    
                                                    # Add each email to the batch body
                                                    for idx, email in enumerate(current_batch):
                                                        batch_body += f"\n\n--- EMAIL {idx+1} ---\n"
                                                        batch_body += f"To: {', '.join(email['recipients'])}\n"
                                                        batch_body += f"Subject: {email['subject']}\n"
                                                        batch_body += f"Body:\n{email['body']}\n"
                                                        batch_body += "\n--- END OF EMAIL ---"
                                                    
                                                    # Add the batch to our list
                                                    email_batches.append({
                                                        'subject': batch_subject,
                                                        'body': batch_body,
                                                        'recipients': ['tournament.organizer@example.com']  # Placeholder recipient
                                                    })
                                                    
                                                    # Reset for next batch
                                                    current_batch = []
                                                    current_recipients = []
                                        
                                        # Save each batch as a draft
                                        for batch in email_batches:
                                            try:
                                                if send_outlook_email(
                                                    batch['recipients'][0],  # Send to organizer
                                                    batch['subject'], 
                                                    batch['body'], 
                                                    draft_only=True,
                                                    open_outlook=open_outlook and success_count == 0  # Only open on first success
                                                ):
                                                    success_count += 1
                                                else:
                                                    fail_count += 1
                                            except Exception as e:
                                                st.error(f"Error saving batch draft: {str(e)}")
                                                fail_count += 1
                                    else:
                                        # Save individual drafts (original behavior)
                                        for i, email_data in enumerate(st.session_state.winner_emails_to_review):
                                            try:
                                                if send_outlook_email(
                                                    email_data['recipients'], 
                                                    email_data['subject'], 
                                                    email_data['body'], 
                                                    draft_only=True,
                                                    open_outlook=open_outlook and i == 0  # Only open on first email
                                                ):
                                                    success_count += 1
                                                else:
                                                    fail_count += 1
                                            except Exception as e:
                                                st.error(f"Error saving draft for match {email_data['match_id']}: {str(e)}")
                                                fail_count += 1
                                    
                                    # Show results
                                    if batch_size > 1 and success_count > 0:
                                        st.success(f"✅ Successfully saved {success_count} batch drafts in Outlook")
                                        st.info("Each draft contains multiple emails that you can review and send individually.")
                                    elif success_count > 0:
                                        st.success(f"✅ Successfully saved {success_count} emails as drafts in Outlook")
                                        st.info("Please review and send the draft emails in Outlook.")
                                        
                                    if fail_count > 0:
                                        st.error(f"❌ Failed to save {fail_count} drafts")
                                    
                                    # Clear review state
                                    st.session_state.show_winner_review = False
                                    st.session_state.winner_emails_to_review = []
                        
                        with col3:
                            if st.button("❌ Cancel", key="cancel_winner_emails"):
                                st.session_state.show_winner_review = False
                                st.session_state.winner_emails_to_review = []
                                st.info("Email sending cancelled.")
                                st.rerun()
                else:
                    st.info("Please select at least one match to send notifications.")
    
    with email_tab3:
        st.subheader("📝 Custom Email")
        st.write("Send a custom email to selected participants.")
        
        # Get participants
        participants_df = get_participants()
        
        if participants_df.empty:
            st.info("No participants found. Add participants first.")
        else:
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                category_filter = st.selectbox(
                    "Filter by category:", 
                    ["All"] + list(participants_df['category'].unique()),
                    key="custom_category_filter"
                )
            with col2:
                status_filter = st.selectbox(
                    "Filter by registration status:", 
                    ["All", "Reported", "Not Reported"],
                    key="custom_status_filter"
                )
            
            # Apply filters
            filtered_participants = participants_df.copy()
            if category_filter != "All":
                filtered_participants = filtered_participants[filtered_participants['category'] == category_filter]
            if status_filter == "Reported":
                filtered_participants = filtered_participants[filtered_participants['registered_at_desk'] == 1]
            elif status_filter == "Not Reported":
                filtered_participants = filtered_participants[filtered_participants['registered_at_desk'] == 0]
            
            # Search option
            search_term = st.text_input("🔍 Search participants:", key="custom_search_term")
            if search_term:
                filtered_participants = search_participants(search_term, filtered_participants)
            
            # Display participants
            st.write(f"Showing {len(filtered_participants)} participants")
            
            if not filtered_participants.empty:
                # Create a selection grid for participants
                selected_participants = st.multiselect(
                    "Select participants to email:",
                    options=filtered_participants['id'].tolist(),
                    format_func=lambda x: f"{filtered_participants[filtered_participants['id'] == x].iloc[0]['name']} ({filtered_participants[filtered_participants['id'] == x].iloc[0]['emp_id']})",
                    key="custom_participant_select"
                )
                
                # Select all option
                if st.button("Select All Displayed Participants"):
                    st.session_state.custom_participant_select = filtered_participants['id'].tolist()
                    st.rerun()
                
                if selected_participants:
                    # Email customization
                    st.subheader("Email Content")
                    
                    email_subject = st.text_input(
                        "Email Subject:", 
                        value="Carrom Tournament - Important Information",
                        key="custom_email_subject"
                    )
                    
                    email_body = st.text_area(
                        "Email Body:",
                        value="Hello,\n\nThis is an important announcement regarding the Carrom Tournament.\n\n[Your message here]\n\nBest regards,\nTournament Organizers",
                        height=200,
                        key="custom_email_body"
                    )
                    
                    # Preview section
                    with st.expander("📝 Preview Email", expanded=False):
                        st.subheader("Email Preview")
                        st.write(f"**Subject:** {email_subject}")
                        st.write("**Body:**")
                        st.text(email_body)
                        
                        # Show recipients
                        selected_emails = filtered_participants[filtered_participants['id'].isin(selected_participants)]['email'].tolist()
                        st.write(f"**Recipients:** {len(selected_emails)} participants")
                        if len(selected_emails) <= 10:
                            st.write(", ".join(selected_emails))
                        else:
                            st.write(", ".join(selected_emails[:10]) + f" and {len(selected_emails) - 10} more...")
                    
                    # Initialize session state for review if not exists
                    if 'custom_email_to_review' not in st.session_state:
                        st.session_state.custom_email_to_review = None
                    if 'show_custom_review' not in st.session_state:
                        st.session_state.show_custom_review = False
                    
                    # Preview button
                    if st.button("📝 Review Email Before Sending", key="review_custom_email"):
                        with st.spinner("Preparing email for review..."):
                            # Get recipient emails
                            selected_emails = filtered_participants[filtered_participants['id'].isin(selected_participants)]['email'].tolist()
                            selected_names = filtered_participants[filtered_participants['id'].isin(selected_participants)]['name'].tolist()
                            
                            # Filter out empty emails
                            valid_emails = [email for email in selected_emails if email and isinstance(email, str)]
                            
                            if valid_emails:
                                # Store in session state
                                st.session_state.custom_email_to_review = {
                                    'recipients': valid_emails,
                                    'subject': email_subject,
                                    'body': email_body,
                                    'recipient_names': selected_names
                                }
                                st.session_state.show_custom_review = True
                            else:
                                st.error("No valid email addresses found for selected participants")
                    
                    # Show review interface if needed
                    if st.session_state.show_custom_review and st.session_state.custom_email_to_review:
                        st.subheader("📋 Email Review")
                        
                        email_data = st.session_state.custom_email_to_review
                        
                        # Show email preview
                        st.markdown("**Email Preview:**")
                        st.markdown(f"**To:** {', '.join(email_data['recipients'][:5])}{'...' if len(email_data['recipients']) > 5 else ''}")
                        st.markdown(f"**Subject:** {email_data['subject']}")
                        st.text_area("Email Body", email_data['body'], height=200, key="custom_preview_body", disabled=True)
                        
                        # Show summary
                        st.markdown(f"**Total recipients:** {len(email_data['recipients'])}")
                        
                        # List recipients
                        with st.expander("View all recipients", expanded=False):
                            for i, (name, email) in enumerate(zip(email_data['recipient_names'], email_data['recipients'])):
                                if i < 50:  # Limit to 50 to avoid UI overload
                                    st.markdown(f"- {name}: {email}")
                                else:
                                    st.markdown(f"...and {len(email_data['recipients']) - 50} more")
                                    break
                        
                        # Confirmation buttons
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("📤 Confirm and Send Email", key="confirm_custom_email"):
                                with st.spinner("Sending emails..."):
                                    try:
                                        if send_outlook_email(email_data['recipients'], email_data['subject'], email_data['body']):
                                            st.success(f"✅ Successfully sent emails to {len(email_data['recipients'])} participants")
                                        else:
                                            st.error("❌ Failed to send emails")
                                    except Exception as e:
                                        st.error(f"Error sending emails: {str(e)}")
                                    
                                    # Clear review state
                                    st.session_state.show_custom_review = False
                                    st.session_state.custom_email_to_review = None
                        
                        with col2:
                            # Add options for draft saving
                            if len(email_data['recipients']) > 10:  # Only show batch options if there are many recipients
                                draft_options = st.radio(
                                    "Draft Options:",
                                    ["Save as single draft with all recipients", "Split into batches of 50 recipients", "Split into batches of 100 recipients"],
                                    key="custom_draft_options",
                                    horizontal=True
                                )
                            else:
                                draft_options = "Save as single draft with all recipients"
                                
                            open_outlook = st.checkbox("Open Outlook after creating drafts", value=True, key="custom_open_outlook")
                            
                            if st.button("📝 Save as Draft in Outlook", key="save_custom_draft"):
                                with st.spinner("Saving email as draft..."):
                                    success_count = 0
                                    fail_count = 0
                                    
                                    # Determine if we need to split into batches
                                    if draft_options == "Split into batches of 50 recipients":
                                        batch_size = 50
                                    elif draft_options == "Split into batches of 100 recipients":
                                        batch_size = 100
                                    else:
                                        batch_size = 0  # No batching
                                    
                                    if batch_size > 0 and len(email_data['recipients']) > batch_size:
                                        # Split recipients into batches
                                        recipient_batches = [email_data['recipients'][i:i+batch_size] 
                                                            for i in range(0, len(email_data['recipients']), batch_size)]
                                        
                                        # Create a draft for each batch
                                        for i, batch in enumerate(recipient_batches):
                                            try:
                                                if send_outlook_email(
                                                    batch, 
                                                    f"{email_data['subject']} (Batch {i+1} of {len(recipient_batches)})", 
                                                    email_data['body'], 
                                                    draft_only=True,
                                                    open_outlook=open_outlook and i == 0  # Only open on first batch
                                                ):
                                                    success_count += 1
                                                else:
                                                    fail_count += 1
                                            except Exception as e:
                                                st.error(f"Error saving draft for batch {i+1}: {str(e)}")
                                                fail_count += 1
                                    else:
                                        # Save as a single draft with all recipients
                                        try:
                                            if send_outlook_email(
                                                email_data['recipients'], 
                                                email_data['subject'], 
                                                email_data['body'], 
                                                draft_only=True,
                                                open_outlook=open_outlook
                                            ):
                                                success_count += 1
                                            else:
                                                fail_count += 1
                                        except Exception as e:
                                            st.error(f"Error saving draft: {str(e)}")
                                            fail_count += 1
                                    
                                    # Show results
                                    if batch_size > 0 and success_count > 0:
                                        st.success(f"✅ Successfully saved {success_count} email drafts in Outlook")
                                        st.info(f"Recipients were split into {success_count} batches for easier management.")
                                    elif success_count > 0:
                                        st.success(f"✅ Successfully saved email as draft in Outlook")
                                        st.info("Please open Outlook to review and send the draft email.")
                                        
                                    if fail_count > 0:
                                        st.error(f"❌ Failed to save {fail_count} drafts")
                                    
                                    # Clear review state
                                    st.session_state.show_custom_review = False
                                    st.session_state.custom_email_to_review = None
                        
                        with col3:
                            if st.button("❌ Cancel", key="cancel_custom_email"):
                                st.session_state.show_custom_review = False
                                st.session_state.custom_email_to_review = None
                                st.info("Email sending cancelled.")
                                st.rerun()
                else:
                    st.info("Please select at least one participant to email.")

with tab10:
    # Email Notifications tab
    st.subheader("📧 Email Notifications")
    st.write("This tab allows you to send custom email notifications to tournament participants.")
    
    # Add your email notification functionality here
    st.info("Use this tab to send custom email notifications to participants.")

# Main execution
if __name__ == "__main__":
    # Initialize database
    init_database()
    
    # Set page config must be first command
    st.set_page_config(
        page_title="Tennis Tournament Manager",
        page_icon="🎾",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
