import unittest

import numpy as np

import render_video as video


class AnimationTests(unittest.TestCase):
    def test_default_delivery(self):
        a = video.parse_args([])
        self.assertEqual((a.width, a.height, a.fps), (1080, 1920, 30))

    def test_timeline_has_no_position_jumps(self):
        scene = video.Scene(270, 480, 42)
        for boundary in (3.0, 6.0, 8.0, 10.5, 14.5):
            p1, _, _ = scene.state(boundary - 0.0001)
            p2, _, _ = scene.state(boundary + 0.0001)
            self.assertLess(np.max(np.linalg.norm(p2 - p1, axis=1)), 0.5)

    def test_seek_is_deterministic(self):
        scene = video.Scene(270, 480, 42)
        a = scene.frame(9.1)
        scene.frame(2.0)
        self.assertTrue(np.array_equal(a, scene.frame(9.1)))

    def test_fine_ascii_grid_can_render(self):
        scene = video.Scene(270, 480, 42, cell=5)
        self.assertEqual(scene.frame(2.35).shape, (480, 270, 3))

    def test_missing_photo_is_clear(self):
        with self.assertRaises(FileNotFoundError):
            video.Scene(270, 480, 42, photo="missing.jpg")


if __name__ == "__main__":
    unittest.main()
