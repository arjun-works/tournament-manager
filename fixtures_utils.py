import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import re

# Database path
DB_PATH = "tournament.db"

def get_all_fixtures():
    """Get all fixtures from the database"""
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT f.*, 
           p1.name as player1_name, p1.emp_id as player1_emp_id,
           p2.name as player2_name, p2.emp_id as player2_emp_id,
           t1p1.name as team1_player1_name, t1p1.emp_id as team1_player1_emp_id,
           t1p2.name as team1_player2_name, t1p2.emp_id as team1_player2_emp_id,
           t2p1.name as team2_player1_name, t2p1.emp_id as team2_player1_emp_id,
           t2p2.name as team2_player2_name, t2p2.emp_id as team2_player2_emp_id
    FROM fixtures f
    LEFT JOIN participants p1 ON f.player1_id = p1.id
    LEFT JOIN participants p2 ON f.player2_id = p2.id
    LEFT JOIN participants t1p1 ON f.team1_player1_id = t1p1.id
    LEFT JOIN participants t1p2 ON f.team1_player2_id = t1p2.id
    LEFT JOIN participants t2p1 ON f.team2_player1_id = t2p1.id
    LEFT JOIN participants t2p2 ON f.team2_player2_id = t2p2.id
    ORDER BY start_time
    """
    fixtures_df = pd.read_sql_query(query, conn)
    conn.close()
    return fixtures_df

def get_fixtures_by_category(category):
    """Get fixtures for a specific category"""
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT f.*, 
           p1.name as player1_name, p1.emp_id as player1_emp_id,
           p2.name as player2_name, p2.emp_id as player2_emp_id,
           t1p1.name as team1_player1_name, t1p1.emp_id as team1_player1_emp_id,
           t1p2.name as team1_player2_name, t1p2.emp_id as team1_player2_emp_id,
           t2p1.name as team2_player1_name, t2p1.emp_id as team2_player1_emp_id,
           t2p2.name as team2_player2_name, t2p2.emp_id as team2_player2_emp_id
    FROM fixtures f
    LEFT JOIN participants p1 ON f.player1_id = p1.id
    LEFT JOIN participants p2 ON f.player2_id = p2.id
    LEFT JOIN participants t1p1 ON f.team1_player1_id = t1p1.id
    LEFT JOIN participants t1p2 ON f.team1_player2_id = t1p2.id
    LEFT JOIN participants t2p1 ON f.team2_player1_id = t2p1.id
    LEFT JOIN participants t2p2 ON f.team2_player2_id = t2p2.id
    WHERE f.category = ?
    ORDER BY start_time
    """
    fixtures_df = pd.read_sql_query(query, conn, params=(category,))
    conn.close()
    return fixtures_df

def parse_time_slot(time_slot_str):
    """Parse a time slot string (e.g., '11am-1pm') into start and end datetime objects"""
    # Extract start and end times using regex
    pattern = r'(\d+)(?::\d+)?([ap]m)-(\d+)(?::\d+)?([ap]m)'
    match = re.match(pattern, time_slot_str.lower().replace(' ', ''))
    
    if not match:
        st.error(f"Invalid time slot format: {time_slot_str}. Please use format like '11am-1pm'.")
        return None, None
    
    start_hour, start_ampm, end_hour, end_ampm = match.groups()
    
    # Convert to 24-hour format
    start_hour = int(start_hour)
    if start_ampm == 'pm' and start_hour < 12:
        start_hour += 12
    elif start_ampm == 'am' and start_hour == 12:
        start_hour = 0
        
    end_hour = int(end_hour)
    if end_ampm == 'pm' and end_hour < 12:
        end_hour += 12
    elif end_ampm == 'am' and end_hour == 12:
        end_hour = 0
    
    # Create datetime objects for today with the specified hours
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_time = today.replace(hour=start_hour)
    end_time = today.replace(hour=end_hour)
    
    # If end time is earlier than start time, assume it's the next day
    if end_time <= start_time:
        end_time += timedelta(days=1)
    
    return start_time, end_time

def generate_time_slots(start_time, end_time, interval_minutes, matches_per_slot):
    """Generate time slots based on start time, end time, interval, and matches per slot"""
    time_slots = []
    current_time = start_time
    
    while current_time < end_time:
        slot_end_time = current_time + timedelta(minutes=interval_minutes)
        if slot_end_time > end_time:
            slot_end_time = end_time
            
        # Create multiple slots at the same time based on matches_per_slot
        for _ in range(matches_per_slot):
            time_slots.append({
                'start_time': current_time,
                'end_time': slot_end_time,
                'time_slot': f"{current_time.strftime('%I:%M%p')}-{slot_end_time.strftime('%I:%M%p')}"
            })
            
        current_time = slot_end_time
    
    return time_slots

def assign_participants_to_slots(participants_df, time_slots, category, location):
    """Assign participants to time slots based on category"""
    fixtures = []
    
    # Filter participants by category
    category_participants = participants_df[participants_df['category'] == category].copy()
    
    if category_participants.empty:
        return []
    
    # Check if it's a singles or doubles category
    is_doubles = 'Doubles' in category
    
    if is_doubles:
        # For doubles, we need to pair participants
        # Group by partner_emp_id to get teams
        teams = []
        processed_ids = set()
        
        for _, player in category_participants.iterrows():
            if player['id'] in processed_ids:
                continue
                
            partner_emp_id = player['partner_emp_id']
            if not partner_emp_id or pd.isna(partner_emp_id):
                continue
                
            # Find the partner
            partner = category_participants[category_participants['emp_id'] == partner_emp_id]
            if not partner.empty:
                partner = partner.iloc[0]
                teams.append((player, partner))
                processed_ids.add(player['id'])
                processed_ids.add(partner['id'])
        
        # Create fixtures for doubles teams
        for i in range(0, len(teams), 2):
            if i + 1 < len(teams) and i < len(time_slots):
                team1 = teams[i]
                team2 = teams[i+1]
                
                fixtures.append({
                    'category': category,
                    'time_slot': time_slots[i//2]['time_slot'],
                    'start_time': time_slots[i//2]['start_time'],
                    'end_time': time_slots[i//2]['end_time'],
                    'location': location,
                    'court_number': (i//2) + 1,
                    'player1_id': None,
                    'player2_id': None,
                    'team1_player1_id': team1[0]['id'],
                    'team1_player2_id': team1[1]['id'],
                    'team2_player1_id': team2[0]['id'],
                    'team2_player2_id': team2[1]['id'],
                    'fixture_status': 'scheduled'
                })
    else:
        # For singles, pair individual participants
        players = category_participants.to_dict('records')
        
        for i in range(0, len(players), 2):
            if i + 1 < len(players) and i//2 < len(time_slots):
                player1 = players[i]
                player2 = players[i+1]
                
                fixtures.append({
                    'category': category,
                    'time_slot': time_slots[i//2]['time_slot'],
                    'start_time': time_slots[i//2]['start_time'],
                    'end_time': time_slots[i//2]['end_time'],
                    'location': location,
                    'court_number': (i//2) + 1,
                    'player1_id': player1['id'],
                    'player2_id': player2['id'],
                    'team1_player1_id': None,
                    'team1_player2_id': None,
                    'team2_player1_id': None,
                    'team2_player2_id': None,
                    'fixture_status': 'scheduled'
                })
    
    return fixtures

def save_fixtures(fixtures):
    """Save fixtures to the database"""
    if not fixtures:
        return 0
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Insert fixtures
    for fixture in fixtures:
        cursor.execute('''
            INSERT INTO fixtures (
                category, time_slot, start_time, end_time, location, court_number,
                player1_id, player2_id, team1_player1_id, team1_player2_id,
                team2_player1_id, team2_player2_id, fixture_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fixture['category'], fixture['time_slot'], 
            fixture['start_time'], fixture['end_time'], 
            fixture['location'], fixture['court_number'],
            fixture['player1_id'], fixture['player2_id'],
            fixture['team1_player1_id'], fixture['team1_player2_id'],
            fixture['team2_player1_id'], fixture['team2_player2_id'],
            fixture['fixture_status']
        ))
    
    conn.commit()
    count = len(fixtures)
    conn.close()
    
    return count

def delete_fixture(fixture_id):
    """Delete a fixture from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM fixtures WHERE id = ?", (fixture_id,))
    
    conn.commit()
    conn.close()
    
    return True

def get_fixture_emails(fixture_id):
    """Get email data for a fixture"""
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT f.*, 
           p1.name as player1_name, p1.emp_id as player1_emp_id, p1.email as player1_email,
           p2.name as player2_name, p2.emp_id as player2_emp_id, p2.email as player2_email,
           t1p1.name as team1_player1_name, t1p1.emp_id as team1_player1_emp_id, t1p1.email as team1_player1_email,
           t1p2.name as team1_player2_name, t1p2.emp_id as team1_player2_emp_id, t1p2.email as team1_player2_email,
           t2p1.name as team2_player1_name, t2p1.emp_id as team2_player1_emp_id, t2p1.email as team2_player1_email,
           t2p2.name as team2_player2_name, t2p2.emp_id as team2_player2_emp_id, t2p2.email as team2_player2_email
    FROM fixtures f
    LEFT JOIN participants p1 ON f.player1_id = p1.id
    LEFT JOIN participants p2 ON f.player2_id = p2.id
    LEFT JOIN participants t1p1 ON f.team1_player1_id = t1p1.id
    LEFT JOIN participants t1p2 ON f.team1_player2_id = t1p2.id
    LEFT JOIN participants t2p1 ON f.team2_player1_id = t2p1.id
    LEFT JOIN participants t2p2 ON f.team2_player2_id = t2p2.id
    WHERE f.id = ?
    """
    fixture_df = pd.read_sql_query(query, conn, params=(fixture_id,))
    conn.close()
    
    if fixture_df.empty:
        return None
        
    fixture = fixture_df.iloc[0]
    
    # Determine if it's singles or doubles
    is_doubles = fixture['player1_id'] is None or pd.isna(fixture['player1_id'])
    
    email_data = {
        'fixture_id': fixture_id,
        'category': fixture['category'],
        'time_slot': fixture['time_slot'],
        'location': fixture['location'],
        'court_number': fixture['court_number'],
        'emails': [],
        'names': [],
        'is_doubles': is_doubles
    }
    
    if is_doubles:
        # Doubles match
        if not pd.isna(fixture['team1_player1_email']):
            email_data['emails'].append(fixture['team1_player1_email'])
            email_data['names'].append(fixture['team1_player1_name'])
        
        if not pd.isna(fixture['team1_player2_email']):
            email_data['emails'].append(fixture['team1_player2_email'])
            email_data['names'].append(fixture['team1_player2_name'])
            
        if not pd.isna(fixture['team2_player1_email']):
            email_data['emails'].append(fixture['team2_player1_email'])
            email_data['names'].append(fixture['team2_player1_name'])
            
        if not pd.isna(fixture['team2_player2_email']):
            email_data['emails'].append(fixture['team2_player2_email'])
            email_data['names'].append(fixture['team2_player2_name'])
            
        # Team information
        email_data['team1'] = [
            {'name': fixture['team1_player1_name'], 'emp_id': fixture['team1_player1_emp_id']},
            {'name': fixture['team1_player2_name'], 'emp_id': fixture['team1_player2_emp_id']}
        ]
        email_data['team2'] = [
            {'name': fixture['team2_player1_name'], 'emp_id': fixture['team2_player1_emp_id']},
            {'name': fixture['team2_player2_name'], 'emp_id': fixture['team2_player2_emp_id']}
        ]
    else:
        # Singles match
        if not pd.isna(fixture['player1_email']):
            email_data['emails'].append(fixture['player1_email'])
            email_data['names'].append(fixture['player1_name'])
            
        if not pd.isna(fixture['player2_email']):
            email_data['emails'].append(fixture['player2_email'])
            email_data['names'].append(fixture['player2_name'])
            
        # Player information
        email_data['player1'] = {
            'name': fixture['player1_name'], 
            'emp_id': fixture['player1_emp_id']
        }
        email_data['player2'] = {
            'name': fixture['player2_name'], 
            'emp_id': fixture['player2_emp_id']
        }
    
    return email_data

def mark_emails_sent(fixture_id):
    """Mark emails as sent for a fixture"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE fixtures SET emails_sent = 1 WHERE id = ?", (fixture_id,))
    
    conn.commit()
    conn.close()
    
    return True

def update_fixture(fixture_id, **kwargs):
    """Update fixture details"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Build update query dynamically
    update_parts = []
    params = []
    
    for field, value in kwargs.items():
        if value is not None:
            update_parts.append(f"{field} = ?")
            params.append(value)
    
    if update_parts:
        query = f"UPDATE fixtures SET {', '.join(update_parts)} WHERE id = ?"
        params.append(fixture_id)
        
        cursor.execute(query, params)
        conn.commit()
        
    conn.close()
    return True

def get_fixture_by_id(fixture_id):
    """Get a single fixture by ID"""
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT f.*, 
           p1.name as player1_name, p1.emp_id as player1_emp_id,
           p2.name as player2_name, p2.emp_id as player2_emp_id,
           t1p1.name as team1_player1_name, t1p1.emp_id as team1_player1_emp_id,
           t1p2.name as team1_player2_name, t1p2.emp_id as team1_player2_emp_id,
           t2p1.name as team2_player1_name, t2p1.emp_id as team2_player1_emp_id,
           t2p2.name as team2_player2_name, t2p2.emp_id as team2_player2_emp_id
    FROM fixtures f
    LEFT JOIN participants p1 ON f.player1_id = p1.id
    LEFT JOIN participants p2 ON f.player2_id = p2.id
    LEFT JOIN participants t1p1 ON f.team1_player1_id = t1p1.id
    LEFT JOIN participants t1p2 ON f.team1_player2_id = t1p2.id
    LEFT JOIN participants t2p1 ON f.team2_player1_id = t2p1.id
    LEFT JOIN participants t2p2 ON f.team2_player2_id = t2p2.id
    WHERE f.id = ?
    """
    fixture_df = pd.read_sql_query(query, conn, params=(fixture_id,))
    conn.close()
    
    if fixture_df.empty:
        return None
    
    return fixture_df.iloc[0].to_dict()
