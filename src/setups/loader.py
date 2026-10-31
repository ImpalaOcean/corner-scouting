"""Load and join 360 data with corner events."""
import json
from pathlib import Path

def load_360_frames(filepath):
    """Read a StatsBomb 360 JSON file and index it by event_uuid."""
    path = Path(filepath)
    if not path.exists():
        return {}
    
    with path.open("r", encoding="utf-8-sig") as f:
        frames = json.load(f)
        
    # We only care about frames that actually have freeze_frame data
    indexed = {}
    for frame in frames:
        if "event_uuid" in frame and "freeze_frame" in frame:
            indexed[frame["event_uuid"]] = frame
            
    return indexed

def join_corners_and_360(corners_csv_path, raw_360_dir):
    """
    Read the corner summary CSV and attach the corresponding 360 frame.
    Returns a list of joined dictionaries.
    """
    import csv
    joined_data = []
    
    # We will build a cache of 360 files so we don't read the same file twice
    frame_cache = {}
    
    with open(corners_csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_id = str(row["match_id"])
            corner_id = row["corner_event_id"]
            
            # Load the 360 file for this match if we haven't already
            if match_id not in frame_cache:
                path = Path(raw_360_dir) / f"{match_id}.json"
                frame_cache[match_id] = load_360_frames(path)
                
            match_frames = frame_cache[match_id]
            
            # Attach the frame if it exists
            row["frame_360"] = match_frames.get(corner_id, None)
            joined_data.append(row)
            
    return joined_data