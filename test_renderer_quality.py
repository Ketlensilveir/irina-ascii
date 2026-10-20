"""Verifica a luz real das letras e a equivalência dos dois caminhos de desenho."""

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import unittest

import numpy as np
import pygame

from ascii_engine import Animation
from live_app import Renderer


class RendererQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((1280, 720))
        cls.animation = Animation()
        cls.renderer = Renderer(cls.animation)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_letters_reproduce_tones_without_random_brightness_noise(self):
        for hue in range(self.renderer.HUES):
            response = self.renderer.tonal_response[hue]
            target = np.linspace(0, response[-1].mean(), len(response))
            error = np.abs(response - target[:, None]) / target[-1]
            self.assertLess(error.mean(), 0.02)
            self.assertLess(error.max(), 0.05)

    def test_fast_portrait_matches_individual_letter_drawing(self):
        state = self.animation.state(5.5)
        self.renderer.surface.fill((0, 0, 0))
        self.renderer.surface.blits(
            self.renderer.glyph_blits(
                state.positions, state.brightness, state.glyphs, 0
            ),
            doreturn=False,
        )
        individual = pygame.surfarray.array3d(self.renderer.surface)
        levels = np.clip(
            state.brightness / 255 * (self.renderer.LEVELS - 1),
            0,
            self.renderer.LEVELS - 1,
        ).astype(int)
        tiles = self.renderer.grid_pixels[
            0,
            levels.reshape(self.animation.rows, self.animation.cols),
            (state.glyphs % 3).reshape(self.animation.rows, self.animation.cols),
        ]
        pixels = tiles.transpose(0, 2, 1, 3, 4).reshape(
            self.renderer.grid_surface.get_height(),
            self.renderer.grid_surface.get_width(),
            3,
        )
        pygame.surfarray.blit_array(
            self.renderer.grid_surface, pixels.transpose(1, 0, 2)
        )
        self.renderer.surface.fill((0, 0, 0))
        self.renderer.surface.blit(
            self.renderer.grid_surface, tuple(self.animation.grid_origin.astype(int))
        )
        fast = pygame.surfarray.array3d(self.renderer.surface)
        # Os tons quase pretos podem contribuir com menos de 2/255 na grade.
        difference = np.abs(individual.astype(int) - fast.astype(int))
        self.assertLess(difference.mean(), 0.1)


if __name__ == "__main__":
    unittest.main()
