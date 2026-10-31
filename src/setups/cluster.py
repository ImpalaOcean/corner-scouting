"""Cluster static corner setups into routine groups."""

def setup_to_vector(features):
    """
    Convert the zone occupancy dict into a flat list of numbers.
    We concatenate attackers and defenders for all 9 zones.
    Format: [att_zone1, def_zone1, att_zone2, def_zone2, ...]
    """
    vector = []
    for zone in range(1, 10):
        vector.append(features["zones"][zone]["att"])
        vector.append(features["zones"][zone]["def"])
    return vector

def cluster_setups(extracted_setups, n_clusters=2):
    """
    Takes a list of feature dicts and assigns a cluster ID to each.
    Uses a simple Euclidean distance-based K-Means (from scratch to avoid extra dependencies).
    """
    if not extracted_setups:
        return []

    # If we have fewer items than requested clusters, just make each its own cluster
    if len(extracted_setups) <= n_clusters:
        for i, setup in enumerate(extracted_setups):
            setup["cluster_id"] = i
        return extracted_setups

    vectors = [setup_to_vector(s) for s in extracted_setups]
    
    # Initialize centroids arbitrarily (first N items)
    centroids = [list(v) for v in vectors[:n_clusters]]
    
    assignments = [0] * len(vectors)
    
    # Run a few iterations of K-Means
    for _ in range(10):
        # Assign to nearest centroid
        for i, vec in enumerate(vectors):
            distances = []
            for c in centroids:
                # Euclidean distance
                dist = sum((a - b) ** 2 for a, b in zip(vec, c))
                distances.append(dist)
            assignments[i] = distances.index(min(distances))
            
        # Update centroids
        for c_idx in range(n_clusters):
            cluster_points = [vectors[i] for i, a in enumerate(assignments) if a == c_idx]
            if cluster_points:
                centroids[c_idx] = [
                    sum(p[i] for p in cluster_points) / len(cluster_points) 
                    for i in range(len(centroids[c_idx]))
                ]

    for i, setup in enumerate(extracted_setups):
        setup["cluster_id"] = assignments[i]
        
    return extracted_setups