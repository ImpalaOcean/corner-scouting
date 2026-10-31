"""Extract static setup features from 360 freeze frames."""

def normalize_coordinates(x, y, is_left_corner):
    """
    Normalize coordinates so all corners are viewed as if taken from the right.
    StatsBomb coordinates: X goes 0 to 120 (left to right), Y goes 0 to 80 (bottom to top).
    Right corner is at X=120, Y=80. Left corner is at X=120, Y=0.
    """
    if is_left_corner:
        return x, 80.0 - y
    return x, y

def assign_zone(x, y):
    """
    Divide the attacking third/penalty box area into 9 zones based on X and Y.
    X ranges from 102 to 120 (the 18-yard box starts at 102). We'll use 100 to 120.
    Y ranges from 0 to 80.
    Returns a zone number from 1 to 9.
    """
    if x < 102:
        return 0 # Outside the box
        
    # X columns: Near (114-120), Central (108-114), Far (102-108)
    if x >= 114:
        col = 0
    elif x >= 108:
        col = 1
    else:
        col = 2
        
    # Y rows: Bottom (0-26.6), Middle (26.6-53.3), Top (53.3-80)
    if y < 26.66:
        row = 0
    elif y < 53.33:
        row = 1
    else:
        row = 2
        
    return (col * 3) + row + 1

def extract_frame_features(frame, corner_side):
    """
    Process a single 360 frame and return counts and zone occupancy.
    corner_side: 'left' or 'right' based on the corner location.
    """
    if not frame or "freeze_frame" not in frame:
        return None
        
    is_left = (corner_side == "left")
    
    att_count = 0
    def_count = 0
    keeper_count = 0
    zone_occupancy = {i: {"att": 0, "def": 0} for i in range(1, 10)}
    
    for player in frame["freeze_frame"]:
        x, y = player["location"]
        is_teammate = player["teammate"]
        is_keeper = player["keeper"]
        
        # Normalize coordinates
        norm_x, norm_y = normalize_coordinates(x, y, is_left)
        
        if is_keeper:
            keeper_count += 1
            
        if is_teammate:
            att_count += 1
        else:
            def_count += 1
            
        # Assign to zone (ignore zones outside the box for now)
        zone = assign_zone(norm_x, norm_y)
        if zone > 0:
            if is_teammate:
                zone_occupancy[zone]["att"] += 1
            else:
                zone_occupancy[zone]["def"] += 1
                
    return {
        "total_visible": att_count + def_count,
        "attackers": att_count,
        "defenders": def_count,
        "keepers": keeper_count,
        "zones": zone_occupancy
    }