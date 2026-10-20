"""Testes da animação e dos controles, sem depender de uma janela."""

import unittest

import numpy as np

from ascii_engine import Animation, Playback


class LiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.animation = Animation(960, 540)

    def test_reveal_is_progressive(self):
        a = self.animation.state(0.2)
        b = self.animation.state(2.8)
        self.assertLess(
            np.count_nonzero(a.brightness > 30),
            np.count_nonzero(b.brightness > 30) * 0.4,
        )

    def test_letter_positions_continue_across_phases(self):
        for t in (4.5, 9, 11.5, 14, 19):
            a = self.animation.state(t - 0.00001)
            b = self.animation.state(t + 0.00001)
            self.assertLess(
                np.max(np.linalg.norm(a.positions - b.positions, axis=1)), 0.2
            )

    def test_replaying_same_time_is_exact(self):
        a = self.animation.state(15)
        self.animation.state(2)
        b = self.animation.state(15)
        np.testing.assert_array_equal(a.positions, b.positions)
        np.testing.assert_array_equal(a.brightness, b.brightness)
        np.testing.assert_array_equal(a.glyphs, b.glyphs)

    def test_eye_sampling_really_changes_with_blink(self):
        open_eye = self.animation.portrait(3.4)[0]
        closed_eye = self.animation.portrait(3.75)[0]
        self.assertGreater(np.abs(open_eye - closed_eye).sum(), 100)

    def test_highlights_keep_tonal_separation(self):
        a = Animation(960, 540)
        medians = []
        for value in (190, 215, 235, 250):
            a.luminance[:] = value
            a.silhouette[:] = 255
            brightness, _ = a.portrait(8.5)
            medians.append(float(np.median(brightness)))
        self.assertTrue(np.all(np.diff(medians) > 4), medians)

    def test_default_grid_has_enough_facial_detail(self):
        a = Animation()
        self.assertGreaterEqual(a.cols, 200)

    def test_hat_left_lobe_is_not_cut_away(self):
        mask = self.animation.silhouette
        for x, y in ((35, 490), (60, 530), (85, 555), (108, 558)):
            self.assertGreater(int(mask[y, x]), 230, (x, y))
        self.assertLess(int(mask[610, 45]), 10)

    def test_pause_restart_and_seek(self):
        p = Playback(22)
        p.update(2)
        p.paused = True
        p.update(4)
        self.assertEqual(p.time, 2)
        p.seek(30)
        self.assertEqual(p.time, 22)
        p.restart()
        self.assertEqual(p.time, 0)
        self.assertFalse(p.paused)
        p.speed = 0.5
        p.update(2)
        self.assertEqual(p.time, 1)


if __name__ == "__main__":
    unittest.main()
