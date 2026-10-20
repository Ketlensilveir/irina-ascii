"""Calcula a animação ASCII em qualquer instante, sem depender da janela."""

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*+:."
DURATION = 22.0


def ease(x):
    """Suaviza a entrada e a saída para evitar trancos nas transições."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (6 * x - 15) + 10)


@dataclass
class State:
    """Posições, letras e iluminação que o renderizador recebe a cada quadro."""

    positions: np.ndarray
    brightness: np.ndarray
    glyphs: np.ndarray
    blue: float
    stage: str


class Playback:
    """Cuida do relógio da animação, da pausa e da velocidade."""

    def __init__(self, duration=DURATION):
        self.duration, self.time = duration, 0.0
        self.paused, self.speed, self.loop = False, 1.0, True

    def update(self, delta):
        if not self.paused:
            self.time += max(0.0, delta) * self.speed
            if self.time > self.duration:
                if self.loop:
                    self.time %= self.duration
                else:
                    self.time = self.duration
                    self.paused = True

    def seek(self, time):
        self.time = float(np.clip(time, 0, self.duration))

    def restart(self):
        self.time = 0.0
        self.paused = False


class Animation:
    """Mantém a identidade das partículas do rosto até a formação do dragão."""

    def __init__(
        self,
        width=1280,
        height=720,
        cell=6,
        seed=42,
        photo=ROOT / "assets/irina.jpg",
        logo=ROOT / "assets/kali-dragon.png",
    ):
        self.width, self.height, self.cell = width, height, cell
        self.center = np.array([width / 2, height / 2], np.float32)
        self.scale = height / 720
        self.cols, self.rows = width // cell, height // round(cell * 1.3)
        self.grid_origin = np.array(
            [
                (width - self.cols * cell) / 2,
                (height - self.rows * round(cell * 1.3)) / 2,
            ]
        )
        xx, yy = np.meshgrid(
            (np.arange(self.cols) + 0.5) * cell + self.grid_origin[0],
            (np.arange(self.rows) + 0.5) * round(cell * 1.3) + self.grid_origin[1],
        )
        self.grid = np.column_stack([xx.ravel(), yy.ravel()]).astype(np.float32)
        self.n = len(self.grid)
        self.rng = np.random.default_rng(seed)
        self.phase = self.rng.uniform(0, 2 * np.pi, self.n)
        self.glyphs = self.rng.integers(0, len(CHARS), self.n)
        self.intensity = self.rng.uniform(0.7, 1.0, self.n)
        self.birth = yy.ravel() / height * 1.4 + self.rng.uniform(0, 1.0, self.n)
        self.spawn = self.grid + np.column_stack(
            [
                self.rng.normal(0, 55 * self.scale, self.n),
                self.rng.uniform(-100, -20, self.n) * self.scale,
            ]
        )
        self._load_portrait(photo)
        self._build_silhouette()
        self.heart, self.heart_light = self.make_shape("heart", logo)
        self.dragon, self.dragon_light = self.make_shape("dragon", logo)
        self.end_eye, self.eye_glyphs = self.portrait(9.0)
        self.background = self.rng.uniform([0, 0], [width, height], (280, 2))
        self.background_phase = self.rng.uniform(0, 6.28, len(self.background))

    def _load_portrait(self, photo):
        """Lê a referência e realça detalhes sem alterar o arquivo original."""
        raw = cv2.imread(str(photo))
        if raw is None:
            raise FileNotFoundError(f"Fotografia não encontrada: {photo}")
        self.photo = cv2.resize(raw, (707, 1536))
        gray = cv2.cvtColor(self.photo, cv2.COLOR_BGR2GRAY)
        local = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(12, 16)).apply(gray)
        # Misturo pouco contraste local para manter as sombras naturais do rosto.
        self.luminance = cv2.addWeighted(gray, 0.72, local, 0.28, 0)
        softened = cv2.GaussianBlur(self.luminance, (0, 0), 1.1)
        self.luminance = cv2.addWeighted(self.luminance, 1.28, softened, -0.28, 0)

    def _build_silhouette(self):
        """Separa a Irina do fundo, respeitando a curva do chapéu."""
        # Coordenadas da foto original. A lateral acompanha a curva arredondada do chapéu.
        outline = np.array(
            [
                (0, 360),
                (12, 315),
                (45, 275),
                (90, 245),
                (126, 224),
                (206, 208),
                (290, 196),
                (377, 202),
                (453, 230),
                (519, 285),
                (556, 353),
                (566, 426),
                (548, 486),
                (507, 529),
                (466, 562),
                (470, 672),
                (488, 786),
                (552, 899),
                (620, 1080),
                (690, 1208),
                (48, 1208),
                (78, 992),
                (100, 833),
                (116, 684),
                (119, 610),
                (116, 567),
                (98, 579),
                (78, 575),
                (55, 558),
                (35, 532),
                (16, 502),
                (4, 471),
                (0, 435),
            ],
            np.int32,
        )
        mask = np.zeros(self.photo.shape[:2], np.uint8)
        cv2.fillPoly(mask, [outline], 255)
        self.silhouette = cv2.GaussianBlur(mask, (0, 0), 4)

    def _order(self, p):
        """Ordena por vizinhança espacial para reduzir cruzamentos na transformação."""
        q = np.clip(p / [self.width, self.height] * 1023, 0, 1023).astype(np.uint32)
        code = np.zeros(len(p), np.uint32)
        for bit in range(10):
            code |= ((q[:, 0] >> bit) & 1) << (2 * bit)
            code |= ((q[:, 1] >> bit) & 1) << (2 * bit + 1)
        return np.argsort(code, kind="stable")

    def make_shape(self, kind, logo):
        mask = np.zeros((self.height, self.width), np.uint8)
        cx, cy = self.center
        if kind == "heart":
            a = np.linspace(0, 2 * np.pi, 1000)
            r = min(self.height * 0.019, self.width * 0.018)
            points = np.column_stack(
                [
                    cx + 16 * np.sin(a) ** 3 * r,
                    cy
                    - (
                        13 * np.cos(a)
                        - 5 * np.cos(2 * a)
                        - 2 * np.cos(3 * a)
                        - np.cos(4 * a)
                    )
                    * r,
                ]
            )
            cv2.fillPoly(mask, [points.astype(np.int32)], 255)
            distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
            light = np.where(
                mask > 0, 0.42 + 0.58 * np.exp(-distance / max(1, 15 * self.scale)), 0
            )
        else:
            raw = cv2.imread(str(logo), cv2.IMREAD_UNCHANGED)
            if raw is None or raw.ndim != 3 or raw.shape[2] != 4:
                raise ValueError(f"Logo PNG com transparência inválido: {logo}")
            alpha = raw[:, :, 3]
            yy, xx = np.where(alpha > 10)
            if len(xx) == 0:
                raise ValueError("Logo totalmente transparente.")
            alpha = alpha[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1]
            ratio = min(
                self.width * 0.64 / alpha.shape[1], self.height * 0.65 / alpha.shape[0]
            )
            alpha = cv2.resize(alpha, None, fx=ratio, fy=ratio)
            h, w = alpha.shape
            x, y = int(cx - w / 2), int(cy - h / 2 - 20 * self.scale)
            mask[y : y + h, x : x + w] = alpha
            mask = cv2.dilate(
                mask, np.ones((max(1, round(self.cell * 0.55)),) * 2, np.uint8)
            )
            light = mask / 255.0
        step = self.cell
        xx, yy = np.meshgrid(
            np.arange(step / 2, self.width, step),
            np.arange(step / 2, self.height, step * 1.3),
        )
        xy = np.column_stack([xx.ravel(), yy.ravel()]).astype(np.float32)
        values = light[xy[:, 1].astype(int), xy[:, 0].astype(int)]
        keep = values > 0.08
        xy, values = xy[keep], values[keep]
        if not len(xy):
            raise ValueError("A figura é pequena demais para esta grade.")
        # Cada célula da figura recebe uma letra. As partículas excedentes apagam ao chegar.
        idx = np.arange(self.n) % len(xy)
        positions = xy[idx]
        intensity = values[idx] * np.where(np.arange(self.n) < len(xy), 1.0, 0.0)
        target_order = self._order(positions)
        source_order = self._order(self.grid)
        ordered = np.empty_like(positions)
        ordered_light = np.empty(self.n)
        ordered[source_order] = positions[target_order]
        ordered_light[source_order] = intensity[target_order]
        return ordered, ordered_light * 245

    def camera(self, t):
        # O zoom é exponencial para a aproximação parecer contínua, mesmo perto da íris.
        face = float(ease((t - 4.5) / 1.6))
        iris = float(ease((t - 6.3) / 2.7))
        start = np.array([300.0, 545.0])
        middle = np.array([284.0, 558.0])
        eye = np.array([212.0, 518.0])
        center = (start * (1 - face) + middle * face) * (1 - iris) + eye * iris
        magnification = 1.30 * np.exp(np.log(2.0) * face + np.log(16.0) * iris)
        return center, magnification * self.scale

    def portrait(self, t):
        center, mag = self.camera(t)
        xy = center + (self.grid - self.center) / mag

        def sample(image, points=xy):
            return (
                cv2.remap(
                    image,
                    points[:, 0].astype(np.float32).reshape(self.rows, self.cols),
                    points[:, 1].astype(np.float32).reshape(self.rows, self.cols),
                    cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                )
                .ravel()
                .astype(np.float32)
            )

        lum = sample(self.luminance)
        blink = math.exp(-(((t - 3.75) / 0.12) ** 2))
        if blink > 0.001:
            for ex, ey, rx, ry in ((212, 518, 33, 15), (351, 511, 35, 16)):
                dx, dy = (xy[:, 0] - ex) / rx, (xy[:, 1] - ey) / ry
                inside = (dx * dx + dy * dy) < 1
                closed = inside & (
                    np.abs(dy) > (1 - blink) * np.sqrt(np.maximum(0, 1 - dx * dx))
                )
                skinxy = xy.copy()
                skinxy[:, 1] = ey - 24
                skin = sample(self.luminance, skinxy)
                lum[closed] = skin[closed]
                crease = (np.abs(dx) < 0.95) & (np.abs(dy) < 0.10)
                lum[crease] *= 1 - 0.85 * blink
        mask = sample(self.silhouette) / 255
        lum = 255 * (np.clip(lum / 255, 0, 1) ** 0.88) * mask
        # A identidade fixa das letras evita que o rosto fique cintilando.
        glyphs = self.glyphs.copy()
        return lum, glyphs

    def state(self, t):
        """Retorna a cena no tempo pedido; não depende do quadro anterior."""
        t = float(np.clip(t, 0, DURATION))
        if t <= 9:
            return self._portrait_state(t)
        if t < 11.5:
            return self._eye_to_heart_state(t)
        if t <= 14:
            return self._heart_state(t)
        return self._heart_to_dragon_state(t)

    def _portrait_state(self, t):
        """Forma o retrato por letras e acompanha a aproximação da câmera."""
        lum, glyphs = self.portrait(t)
        reveal = ease((t - self.birth) / 0.6)
        positions = self.spawn * (1 - reveal[:, None]) + self.grid * reveal[:, None]
        return State(
            positions,
            lum * reveal,
            glyphs,
            0.0,
            "IRINA" if t < 4.5 else ("ROSTO" if t < 6.3 else "OLHO"),
        )

    def _eye_to_heart_state(self, t):
        """Leva as partículas do olho até o coração por trajetórias curvas."""
        progress = float(ease((t - 9) / 2.5))
        positions = self.grid * (1 - progress) + self.heart * progress
        arc = math.sin(math.pi * progress) ** 2
        positions += (
            np.column_stack(
                [
                    np.sin(self.phase + progress * 4) * 90,
                    np.cos(self.phase + progress * 4) * 60,
                ]
            )
            * arc
            * self.scale
        )
        brightness = self.end_eye * (1 - progress) + self.heart_light * progress
        return State(positions, brightness, self.eye_glyphs, 0.0, "OLHO → CORAÇÃO")

    def _heart_state(self, t):
        """Faz o coração pulsar, chegando parado às duas transições."""
        beat = (
            1
            + 0.045
            * math.sin((t - 11.5) * math.pi * 2 * 1.1)
            * math.sin(math.pi * (t - 11.5) / 2.5) ** 2
        )
        return State(
            (self.heart - self.center) * beat + self.center,
            self.heart_light,
            self.eye_glyphs,
            0.0,
            "CORAÇÃO",
        )

    def _heart_to_dragon_state(self, t):
        """Reorganiza o coração no dragão e muda a luz aos poucos."""
        progress = float(ease((t - 14) / 5))
        positions = self.heart * (1 - progress) + self.dragon * progress
        arc = math.sin(math.pi * progress) ** 2
        positions += (
            np.column_stack(
                [
                    np.cos(self.phase + 5 * progress) * 125,
                    np.sin(self.phase + 5 * progress) * 95,
                ]
            )
            * arc
            * self.scale
        )
        brightness = self.heart_light * (1 - progress) + self.dragon_light * progress
        return State(
            positions,
            brightness,
            self.eye_glyphs,
            progress * 0.82,
            "CORAÇÃO → KALI" if t < 19 else "KALI LINUX",
        )
