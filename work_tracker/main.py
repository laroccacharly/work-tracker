from typing import Literal
import argparse
import os
import sqlite3
import time
import sys
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime
from rich.console import Console
from rich.table import Table

class Event(BaseModel):
    message: str
    type: Literal["start", "stop", "marker"]
    time: int # unix timestamp

def get_db_path():
    db_path = os.environ.get("WORK_TRACKER_DB_PATH")
    if not db_path:
        print("WORK_TRACKER_DB_PATH environment variable not set.")
        print("Please add it to your .zshrc and reload.")
        sys.exit(1)
    return db_path

def init_db(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,
        type TEXT NOT NULL,
        time INTEGER NOT NULL
    )
    ''')
    
    conn.commit()
    conn.close()

def insert_event(event_type, message, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    current_time = int(time.time())
    
    cursor.execute(
        "INSERT INTO events (message, type, time) VALUES (?, ?, ?)",
        (message, event_type, current_time)
    )
    
    conn.commit()
    conn.close()
    
    return {"message": message, "type": event_type, "time": current_time}

def calculate_work_duration(events):
    """Calculate total work time from start/stop events."""
    total_seconds = 0
    current_start = None
    
    for event in events:
        message, event_type, timestamp = event
        
        if event_type == "start":
            current_start = timestamp
        elif event_type == "stop" and current_start is not None:
            duration = timestamp - current_start
            total_seconds += duration
            current_start = None
    
    # If there's an unclosed start event, count time until now
    if current_start is not None:
        current_time = int(time.time())
        duration = current_time - current_start
        total_seconds += duration
    
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return {
        "formatted": f"{hours}h {minutes}m {seconds}s"
    }

def list_events(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT message, type, time FROM events ORDER BY time")
    events = cursor.fetchall()
    
    conn.close()
    
    console = Console()
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Type")
    table.add_column("Time")
    table.add_column("Message")
    
    for event in events:
        message, event_type, timestamp = event
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        
        if event_type == "start":
            color = "green"
        elif event_type == "stop":
            color = "red"
        else:
            color = "yellow"
            
        table.add_row(
            f"[{color}]{event_type}[/{color}]",
            time_str,
            message
        )
    
    console.print(table)
    
    # Add summary of work time
    duration = calculate_work_duration(events)
    console.print(f"\n[bold]Total time worked:[/bold] {duration['formatted']}")
    
    # Show if there's ongoing work
    if events:
        last_event = events[-1]
        event_type = last_event[1]
        
        if event_type == "start":
            start_time = datetime.fromtimestamp(last_event[2])
            current_time = datetime.now()
            elapsed = current_time - start_time
            hours, remainder = divmod(elapsed.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            elapsed_str = f"{hours}h {minutes}m {seconds}s"
            console.print(f"[bold green]Current session:[/bold green] {elapsed_str} (since {start_time.strftime('%Y-%m-%d %H:%M:%S')})")

def main():
    parser = argparse.ArgumentParser(description="Work Tracker CLI")
    parser.add_argument("-m", "--message", type=str, help="Message for the event", default="")
    parser.add_argument("-s", "--stop", action="store_true", help="Create a stop event")
    parser.add_argument("list", nargs="?", help="List all events")
    
    args = parser.parse_args()
    
    db_path = get_db_path()
    init_db(db_path)
    
    if args.list == "list":
        list_events(db_path)
        return
    
    
    if args.stop:
        # Create a stop event
        event = insert_event("stop", args.message, db_path)
        print(f"Stopped work: {event['message']}")
    else:
        # Check if there's an active start event without a stop
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM events WHERE type = 'start' AND id > COALESCE(
                (SELECT MAX(id) FROM events WHERE type = 'stop'), 0
            ) LIMIT 1
        """)
        has_active_start = cursor.fetchone() is not None
        conn.close()
        
        if has_active_start:
            # If there's an active start event, create a marker
            event = insert_event("marker", args.message, db_path)
            print(f"Created marker: {event['message']}")
        else:
            # Otherwise create a start event
            event = insert_event("start", args.message, db_path)
            print(f"Started work: {event['message']}")

if __name__ == "__main__":
    main()
