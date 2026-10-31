import unittest
from src.setups.features import normalize_coordinates, assign_zone, extract_frame_features
from src.setups.cluster import cluster_setups

class TestSetups(unittest.TestCase):
    
    def test_coordinate_normalization(self):
        # Right corner stays the same
        self.assertEqual(normalize_coordinates(110, 20, is_left_corner=False), (110, 20))
        # Left corner flips Y
        self.assertEqual(normalize_coordinates(110, 20, is_left_corner=True), (110, 60))

    def test_zone_assignment(self):
        # Outside the box
        self.assertEqual(assign_zone(90, 40), 0)
        # Zone 2 (Near post, middle Y)
        self.assertEqual(assign_zone(115, 40), 2)
        # Zone 5 (Central, middle Y)
        self.assertEqual(assign_zone(110, 40), 5)

    def test_extract_frame_features(self):
        mock_frame = {
            "freeze_frame": [
                {"teammate": True, "keeper": False, "location": [110, 40]},
                {"teammate": False, "keeper": False, "location": [115, 40]},
                {"teammate": False, "keeper": True, "location": [118, 40]}
            ]
        }
        features = extract_frame_features(mock_frame, "right")
        self.assertEqual(features["total_visible"], 3)
        self.assertEqual(features["attackers"], 1)
        self.assertEqual(features["defenders"], 2)
        self.assertEqual(features["keepers"], 1)
        self.assertEqual(features["zones"][5]["att"], 1)

    def test_clustering(self):
        # Create two distinct setup patterns
        setup_a = {"zones": {i: {"att": 1 if i < 5 else 0, "def": 0} for i in range(1, 10)}}
        setup_b = {"zones": {i: {"att": 0, "def": 1 if i >= 5 else 0} for i in range(1, 10)}}
        
        extracted = [setup_a, setup_b, setup_a.copy(), setup_b.copy()]
        clustered = cluster_setups(extracted, n_clusters=2)
        
        self.assertEqual(len(clustered), 4)
        # The two 'setup_a' instances should be in the same cluster
        self.assertEqual(clustered[0]["cluster_id"], clustered[2]["cluster_id"])
        # The two 'setup_b' instances should be in the same cluster
        self.assertEqual(clustered[1]["cluster_id"], clustered[3]["cluster_id"])
        # 'setup_a' and 'setup_b' should be different
        self.assertNotEqual(clustered[0]["cluster_id"], clustered[1]["cluster_id"])

if __name__ == "__main__":
    unittest.main()