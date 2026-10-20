"""Janela, controles e desenho das letras da animação ao vivo."""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from ascii_engine import CHARS, DURATION, ROOT, Animation, Playback, ease


def font_path():
    for path in (
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ):
        if Path(path).exists():
            return path
    return None


class Renderer:
    """Desenha somente caracteres; a foto nunca é colada por baixo das letras."""

    LEVELS = 64
    HUES = 8

    def __init__(self, animation):
        self.animation = animation
        self.surface = pygame.Surface((animation.width, animation.height)).convert()
        self.font = pygame.font.Font(font_path(), round(animation.cell * 1.5))
        self.tile_size = (animation.cell, round(animation.cell * 1.3))
        self.small_font = pygame.font.Font(None, 20)
        self._build_palettes()
        templates = self._build_glyph_templates()
        self._build_atlas(templates)
        self._calibrate_tones()
        self._build_grid_cache(animation)
        self._build_title(animation)

    def _build_palettes(self):
        """Cria a passagem de cobre e creme até o azul do Kali."""
        self.palette = []
        warm_keys = np.array(
            [
                [0, 0, 0],
                [55, 9, 3],
                [165, 48, 18],
                [245, 116, 62],
                [255, 182, 130],
                [255, 233, 211],
            ]
        )
        cool_keys = np.array(
            [
                [0, 0, 0],
                [5, 17, 24],
                [12, 55, 79],
                [36, 132, 188],
                [107, 211, 255],
                [232, 248, 255],
            ]
        )
        x = np.linspace(0, 5, self.LEVELS)
        for hue in range(self.HUES):
            p = hue / (self.HUES - 1)
            keys = warm_keys * (1 - p) + cool_keys * p
            self.palette.append(
                np.column_stack(
                    [np.interp(x, np.arange(6), keys[:, i]) for i in range(3)]
                ).astype(np.uint8)
            )

    def _build_glyph_templates(self):
        """Encaixa cada letra na célula e mede sua área iluminada."""
        whites = []
        for char in CHARS:
            raw = self.font.render(char, True, (255, 255, 255)).convert_alpha()
            bounds = raw.get_bounding_rect(min_alpha=1)
            cropped = raw.subsurface(bounds).copy()
            ratio = min(
                1.0,
                self.tile_size[0] / max(1, bounds.width),
                self.tile_size[1] / max(1, bounds.height),
            )
            if ratio < 1:
                cropped = pygame.transform.smoothscale(
                    cropped,
                    (
                        max(1, round(bounds.width * ratio)),
                        max(1, round(bounds.height * ratio)),
                    ),
                )
            tile = pygame.Surface(self.tile_size, pygame.SRCALPHA)
            tile.blit(
                cropped,
                (
                    (self.tile_size[0] - cropped.get_width()) // 2,
                    (self.tile_size[1] - cropped.get_height()) // 2,
                ),
            )
            whites.append(tile)
        self.coverage = np.array(
            [pygame.surfarray.array_alpha(tile).mean() / 255 for tile in whites]
        )
        return whites

    def _build_atlas(self, whites):
        """Guarda as letras coloridas para não renderizar fontes a cada quadro."""
        self.atlas = []
        for palette in self.palette:
            shades = []
            for color in palette:
                glyphs = []
                for original in whites:
                    tile = original.copy()
                    tile.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    opaque = pygame.Surface(self.tile_size).convert()
                    opaque.fill((0, 0, 0))
                    opaque.blit(tile, (0, 0))
                    opaque.set_colorkey((0, 0, 0), pygame.RLEACCEL)
                    glyphs.append(opaque)
                shades.append(glyphs)
            self.atlas.append(shades)

    def _calibrate_tones(self):
        """Compensa a densidade das letras para respeitar a luz da foto."""
        # Uma letra cheia ilumina mais que uma letra fina na mesma cor.
        # Compenso isso aqui para não criar manchas aleatórias sobre a pele.
        self.tonal_tiles = np.empty((self.HUES, self.LEVELS, 3), dtype=object)
        target = np.linspace(0, 1, self.LEVELS)
        density = (
            self.coverage.min()
            + (self.coverage.max() - self.coverage.min()) * target**0.55
        )
        candidates = np.argsort(np.abs(density[:, None] - self.coverage), axis=1)[:, :3]
        weights = np.array([0.2126, 0.7152, 0.0722])
        self.tonal_response = np.zeros((self.HUES, self.LEVELS, 3))
        for hue in range(self.HUES):
            luminance = self.palette[hue] @ weights
            desired = target * self.coverage.max() * luminance[-1] * 0.94
            for level in range(self.LEVELS):
                for variant, glyph in enumerate(candidates[level]):
                    shade = int(
                        np.abs(
                            luminance * self.coverage[glyph] - desired[level]
                        ).argmin()
                    )
                    self.tonal_tiles[hue, level, variant] = self.atlas[hue][shade][
                        glyph
                    ]
                    self.tonal_response[hue, level, variant] = (
                        luminance[shade] * self.coverage[glyph]
                    )

    def _build_grid_cache(self, animation):
        """Prepara o caminho rápido do retrato depois de montado."""
        cw, ch = self.tile_size
        self.grid_pixels = np.empty((self.HUES, self.LEVELS, 3, ch, cw, 3), np.uint8)
        for hue in range(self.HUES):
            for level in range(self.LEVELS):
                for variant in range(3):
                    self.grid_pixels[hue, level, variant] = pygame.surfarray.array3d(
                        self.tonal_tiles[hue, level, variant]
                    ).transpose(1, 0, 2)
        self.grid_surface = pygame.Surface(
            (animation.cols * cw, animation.rows * ch)
        ).convert()
        self.grid_surface.set_colorkey((0, 0, 0))

    def _build_title(self, animation):
        """Reconstrói o título com letras pequenas, como as outras formas."""
        self.title_font = pygame.font.Font(
            font_path(), max(22, round(animation.height * 0.065))
        )
        title_mask = self.title_font.render("KALI LINUX", True, (255, 255, 255))
        pixels = pygame.surfarray.array_alpha(title_mask)
        tx = (animation.width - title_mask.get_width()) / 2
        xx, yy = np.mgrid[0 : pixels.shape[0] : 7, 0 : pixels.shape[1] : 7]
        keep = pixels[xx, yy] > 70
        self.title_points = np.column_stack(
            [xx[keep] + tx, yy[keep] + animation.height * 0.81]
        ).astype(np.float32)
        self.star = self.font.render("+", True, (255, 210, 185)).convert_alpha()

    def glyph_blits(self, positions, brightness, glyphs, hue):
        levels = np.clip(
            brightness / 255 * (self.LEVELS - 1), 0, self.LEVELS - 1
        ).astype(np.int32)
        active = np.flatnonzero(levels > 1)
        positions = np.rint(positions[active] - np.array(self.tile_size) / 2).astype(
            np.int32
        )
        tiles = self.tonal_tiles[hue, levels[active], glyphs[active] % 3]
        return list(zip(tiles.tolist(), positions.tolist()))

    def draw(self, t, help_visible=False, playback=None, fps=0):
        self.surface.fill((0, 0, 0))
        state = self.animation.state(t)
        hue = int(np.clip(round(state.blue * (self.HUES - 1)), 0, self.HUES - 1))
        self._draw_background(t, hue)
        if 3 <= t <= 9:
            self._draw_portrait_grid(state, hue)
        else:
            self.surface.blits(
                self.glyph_blits(state.positions, state.brightness, state.glyphs, hue),
                doreturn=False,
            )
        self._draw_glints(t)
        self._draw_title(t, hue)
        self._apply_glow()
        if help_visible and playback is not None:
            self.hud(playback, state.stage, fps)
        return self.surface

    def _draw_background(self, t, hue):
        """Move os rastros de código sem trocar o ruído a cada quadro."""
        bg = self.animation.background.copy()
        bg[:, 0] = (
            bg[:, 0] + t * (7 + np.sin(self.animation.background_phase) * 3)
        ) % self.animation.width
        bg[:, 1] += np.sin(t * 0.4 + self.animation.background_phase) * 2
        commands = []
        for trail in range(4):
            positions = bg.copy()
            positions[:, 0] -= trail * self.animation.cell * 1.1
            light = (20 + 15 * np.sin(self.animation.background_phase + t * 0.6)) * (
                1 - trail * 0.19
            )
            glyph = (np.arange(len(bg)) * 7 + trail * 3) % len(CHARS)
            commands.extend(self.glyph_blits(positions, light, glyph, hue))
        self.surface.blits(commands, doreturn=False)

    def _draw_portrait_grid(self, state, hue):
        """Monta os mesmos caracteres em bloco enquanto a grade está parada."""
        # Com as letras paradas na grade, monto o bloco de uma vez no NumPy.
        # O resultado é o mesmo desenho individual, com menos trabalho por quadro.
        levels = np.clip(
            state.brightness / 255 * (self.LEVELS - 1), 0, self.LEVELS - 1
        ).astype(np.int32)
        tiles = self.grid_pixels[
            hue,
            levels.reshape(self.animation.rows, self.animation.cols),
            (state.glyphs % 3).reshape(self.animation.rows, self.animation.cols),
        ]
        pixels = tiles.transpose(0, 2, 1, 3, 4).reshape(
            self.grid_surface.get_height(), self.grid_surface.get_width(), 3
        )
        pygame.surfarray.blit_array(self.grid_surface, pixels.transpose(1, 0, 2))
        self.surface.blit(
            self.grid_surface, tuple(self.animation.grid_origin.astype(int))
        )

    def _draw_glints(self, t):
        """Os pequenos brilhos também são feitos com o caractere +."""
        if 7 < t < 11.5:
            gain = float(ease((t - 7) / 1.4)) * (1 - float(ease((t - 9) / 2.5)))
            self.draw_star(self.animation.center + [0, -8 * self.animation.scale], gain)
            self.draw_star(
                self.animation.center
                + [160 * self.animation.scale, 56 * self.animation.scale],
                gain * 0.6,
            )
        if 11.5 < t < 19:
            for i in range(5):
                angle = i * 1.25 + t * 0.3
                pos = (
                    self.animation.center
                    + np.array([np.cos(angle) * 240, np.sin(angle) * 200])
                    * self.animation.scale
                )
                self.draw_star(pos, 0.25 + 0.25 * np.sin(t + i) ** 2)

    def _draw_title(self, t, hue):
        """Revela o título quando o dragão termina de se formar."""
        if t > 19:
            alpha = float(ease((t - 19) / 1.2))
            self.surface.blits(
                self.glyph_blits(
                    self.title_points,
                    np.full(len(self.title_points), 190 * alpha),
                    np.full(len(self.title_points), CHARS.index("#")),
                    hue,
                ),
                doreturn=False,
            )

    def _apply_glow(self):
        """Espalha um pouco da luz das letras sem apagar seus detalhes."""
        small = pygame.transform.smoothscale(
            self.surface, (self.animation.width // 4, self.animation.height // 4)
        )
        glow = pygame.transform.smoothscale(small, self.surface.get_size())
        glow.fill((35, 28, 23), special_flags=pygame.BLEND_RGB_MULT)
        self.surface.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def draw_star(self, pos, alpha):
        if alpha < 0.01:
            return
        tile = self.star.copy()
        tile.set_alpha(int(255 * alpha))
        self.surface.blit(
            tile,
            (int(pos[0] - tile.get_width() / 2), int(pos[1] - tile.get_height() / 2)),
        )
        for scale in (2, 3):
            flare = pygame.transform.smoothscale(
                tile, (tile.get_width() * scale, tile.get_height() * scale)
            )
            flare.set_alpha(int(26 * alpha))
            self.surface.blit(
                flare,
                (
                    int(pos[0] - flare.get_width() / 2),
                    int(pos[1] - flare.get_height() / 2),
                ),
            )

    def hud(self, playback, stage, fps):
        w, h = self.surface.get_size()
        panel = pygame.Surface((w, 70))
        panel.fill((4, 4, 5))
        panel.set_alpha(225)
        self.surface.blit(panel, (0, h - 70))
        lines = [
            f"{stage}   {playback.time:04.1f} / {playback.duration:.0f}s   {playback.speed:g}x   {fps:.0f} FPS"
            + ("   PAUSADO" if playback.paused else ""),
            "ESPACO pausa  |  R reinicia  |  <- -> tempo  |  1-5 cenas  |  +/- velocidade  |  F tela cheia  |  H oculta  |  ESC sai",
        ]
        for i, line in enumerate(lines):
            self.surface.blit(
                self.small_font.render(line, True, (195, 146, 112)),
                (16, h - 62 + i * 23),
            )
        pygame.draw.rect(self.surface, (50, 24, 14), (16, h - 10, w - 32, 2))
        pygame.draw.rect(
            self.surface,
            (230, 117, 63),
            (16, h - 10, int((w - 32) * playback.time / playback.duration), 2),
        )


class App:
    """Liga a simulação à janela e aos controles do teclado."""

    def __init__(self, args):
        self.args = args
        pygame.display.init()
        pygame.font.init()
        self.flags = pygame.RESIZABLE
        self.screen = pygame.display.set_mode((args.width, args.height), self.flags)
        pygame.display.set_caption("IRINA / ASCII vivo — espaço: pausa · H: controles")
        self.animation = Animation(
            args.width, args.height, args.cell, args.seed, args.photo, args.logo
        )
        self.renderer = Renderer(self.animation)
        self.playback = Playback()
        self.playback.loop = not args.once
        self.playback.time = args.start
        self.help_visible = True
        self.running = True
        self.fullscreen = False
        self.window_size = (args.width, args.height)
        self.viewport = pygame.Rect(0, 0, args.width, args.height)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            k = event.key
            if k == pygame.K_ESCAPE:
                self.running = False
            elif k == pygame.K_SPACE:
                self.playback.paused = not self.playback.paused
            elif k == pygame.K_r:
                self.playback.restart()
            elif k == pygame.K_h:
                self.help_visible = not self.help_visible
            elif k == pygame.K_RIGHT:
                self.playback.seek(self.playback.time + 1)
            elif k == pygame.K_LEFT:
                self.playback.seek(self.playback.time - 1)
            elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                self.playback.speed = min(2.0, self.playback.speed + 0.25)
            elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.playback.speed = max(0.25, self.playback.speed - 0.25)
            elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                self.playback.seek((0, 5.5, 8.5, 12.5, 20)[k - pygame.K_1])
            elif k == pygame.K_f:
                self.fullscreen = not self.fullscreen
                if self.fullscreen:
                    self.window_size = self.screen.get_size()
                    self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                else:
                    self.screen = pygame.display.set_mode(
                        self.window_size, pygame.RESIZABLE
                    )
        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.help_visible
        ):
            x, y = event.pos
            rect = self.viewport
            if rect.left <= x <= rect.right and rect.bottom - 24 <= y <= rect.bottom:
                self.playback.seek((x - rect.left) / rect.width * DURATION)

    def present(self, surface):
        sw, sh = self.screen.get_size()
        w, h = surface.get_size()
        ratio = min(sw / w, sh / h)
        size = (round(w * ratio), round(h * ratio))
        self.viewport = pygame.Rect((sw - size[0]) // 2, (sh - size[1]) // 2, *size)
        self.screen.fill((0, 0, 0))
        output = (
            surface if size == (w, h) else pygame.transform.smoothscale(surface, size)
        )
        self.screen.blit(output, self.viewport)
        pygame.display.flip()

    def run(self):
        clock = pygame.time.Clock()
        started = time.perf_counter()
        frames = 0
        # O relógio só começa depois que as letras em cache estão prontas.
        delta = 0.0
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle_event(event)
                if not self.running:
                    break
                self.playback.update(delta)
                self.present(
                    self.renderer.draw(
                        self.playback.time,
                        self.help_visible,
                        self.playback,
                        clock.get_fps(),
                    )
                )
                frames += 1
                delta = clock.tick(self.args.fps) / 1000
                if (
                    self.args.quit_after
                    and time.perf_counter() - started >= self.args.quit_after
                ):
                    break
        finally:
            if self.args.quit_after:
                print(
                    json.dumps(
                        dict(
                            native_window_frames=frames,
                            seconds=round(time.perf_counter() - started, 2),
                            average_fps=round(
                                frames / (time.perf_counter() - started), 1
                            ),
                        )
                    )
                )
            pygame.quit()

    def check(self):
        folder = ROOT / "output/live_checks"
        folder.mkdir(parents=True, exist_ok=True)
        times = (0.2, 1.4, 3.2, 3.75, 5.5, 8.5, 10.2, 12.5, 16.5, 20)
        for t in times:
            surface = self.renderer.draw(t)
            pygame.image.save(surface, str(folder / f"{t:04.1f}.png"))
        start = time.perf_counter()
        for t in np.linspace(0, DURATION, 180):
            self.renderer.draw(float(t))
        elapsed = time.perf_counter() - start
        # Testo os controles pelo mesmo caminho usado pelos eventos da janela.
        for key in (pygame.K_SPACE, pygame.K_r, pygame.K_3, pygame.K_MINUS, pygame.K_h):
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        for event in pygame.event.get():
            self.handle_event(event)
        assert (
            self.playback.time == 8.5
            and self.playback.speed == 0.75
            and not self.help_visible
        )
        report = {
            "frames_benchmarked": 180,
            "seconds": round(elapsed, 3),
            "render_fps": round(180 / elapsed, 1),
            "resolution": [self.args.width, self.args.height],
            "particles": self.animation.n,
            "snapshots": len(times),
            "keyboard_event_check": "passed",
        }
        (folder / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        pygame.quit()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument(
        "--cell",
        type=int,
        default=6,
        help="Espaçamento dos caracteres; 6 detalhado (padrão), 8 equilibrado, 12 grande",
    )
    p.add_argument(
        "--fps", type=int, default=60, help="Limite de atualização da janela"
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--photo", type=Path, default=ROOT / "assets/irina.jpg")
    p.add_argument("--logo", type=Path, default=ROOT / "assets/kali-dragon.png")
    p.add_argument(
        "--once", action="store_true", help="Pausa no final em vez de repetir"
    )
    p.add_argument("--start", type=float, default=0, help="Tempo inicial em segundos")
    p.add_argument(
        "--check",
        action="store_true",
        help="Testa os desenhos e controles sem abrir janela",
    )
    p.add_argument("--quit-after", type=float, default=0, help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    if not (480 <= args.width <= 2560 and 270 <= args.height <= 1440):
        p.error("Dimensões: largura 480..2560, altura 270..1440.")
    if not 6 <= args.cell <= 24:
        p.error("--cell deve estar entre 6 e 24.")
    if not 15 <= args.fps <= 144:
        p.error("--fps deve estar entre 15 e 144.")
    if not np.isfinite(args.start) or not 0 <= args.start <= DURATION:
        p.error("--start deve estar entre 0 e 22.")
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.check:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
    try:
        app = App(args)
        if args.check:
            app.check()
        else:
            app.run()
    except (OSError, ValueError, pygame.error) as error:
        pygame.quit()
        raise SystemExit(f"Não foi possível executar a animação: {error}")


if __name__ == "__main__":
    main()
