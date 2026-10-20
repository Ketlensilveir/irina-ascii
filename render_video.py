"""Exportador opcional da animação ASCII para vídeo; separado da execução ao vivo."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DURATION = 16.0
CHARS = " .,:;i+*oO%#@"


def ease(x):
    x = np.clip(x, 0, 1)
    return x * x * x * (x * (x * 6 - 15) + 10)


def font_at(size):
    for p in (
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ):
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def spatial_order(p):
    """A ordenação Morton mantém vizinhas as partículas próximas na imagem."""
    q = np.clip(p / [1080, 1920] * 1023, 0, 1023).astype(np.uint32)
    code = np.zeros(len(p), np.uint32)
    for bit in range(10):
        code |= ((q[:, 0] >> bit) & 1) << (2 * bit)
        code |= ((q[:, 1] >> bit) & 1) << (2 * bit + 1)
    return np.argsort(code, kind="stable")


class Scene:
    def __init__(
        self,
        width,
        height,
        seed=42,
        photo=ROOT / "assets/irina.jpg",
        logo=ROOT / "assets/kali-dragon.png",
        cell=7,
    ):
        self.w, self.h = width, height
        self.scale = width / 1080
        self.cell = cell
        self.photo = cv2.imread(str(photo))
        if self.photo is None:
            raise FileNotFoundError(f"Fotografia não encontrada: {photo}")
        # Coordenadas medidas na fotografia de referência, com 707 × 1536 pixels.
        # Todo o recorte acontece em memória; o arquivo original fica intacto.
        self.photo = cv2.resize(self.photo, (707, 1536))
        self.eye = np.array([212.0, 518.0])
        cols, rows = int(1080 // cell), int(1920 // (cell * 1.5))
        self.cols, self.rows = cols, rows
        gx, gy = np.meshgrid(
            (np.arange(cols) + 0.5) * 1080 / cols, (np.arange(rows) + 0.5) * 1920 / rows
        )
        self.grid = np.column_stack([gx.ravel(), gy.ravel()]).astype(np.float32)
        self.n = len(self.grid)
        self.rng = np.random.default_rng(seed)
        self.phase = self.rng.uniform(0, 2 * np.pi, self.n)
        self.glyph = self.rng.integers(3, len(CHARS), self.n)
        self.heart = self.shape_points("heart", logo)
        self.dragon = self.shape_points("dragon", logo)
        # As mesmas partículas seguem do início ao fim das transformações.
        order = spatial_order(self.grid)
        for attr in ("heart", "dragon"):
            p = getattr(self, attr)
            target = np.empty_like(p)
            target[order] = p[spatial_order(p)]
            setattr(self, attr, target)
        self.atlas = self.make_atlas()
        self.ambient = self.rng.uniform([0, 0], [1080, 1920], (180, 2))
        self.eye_color, self.eye_glyph = self.portrait(6.0)
        self.heart_color = np.tile([255.0, 54.0, 102.0], (self.n, 1))
        self.dragon_color = np.tile([66.0, 185.0, 255.0], (self.n, 1))

    def shape_points(self, kind, logo):
        mask = np.zeros((1920, 1080), np.uint8)
        if kind == "heart":
            a = np.linspace(0, 2 * np.pi, 1000)
            x = 16 * np.sin(a) ** 3
            y = 13 * np.cos(a) - 5 * np.cos(2 * a) - 2 * np.cos(3 * a) - np.cos(4 * a)
            points = np.column_stack([540 + x * 24, 900 - y * 24]).astype(np.int32)
            cv2.fillPoly(mask, [points], 255)
            # A borda recebe mais luz, deixando o miolo do coração mais leve.
            inner = cv2.erode(mask, np.ones((45, 45), np.uint8))
            mask = np.maximum(mask - inner, (inner * 0.11).astype(np.uint8))
        else:
            raw = cv2.imread(str(logo), cv2.IMREAD_UNCHANGED)
            if raw is None or raw.ndim != 3 or raw.shape[2] != 4:
                raise ValueError(f"Logo PNG com transparência inválido: {logo}")
            alpha = raw[:, :, 3]
            yy, xx = np.where(alpha > 5)
            alpha = alpha[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1]
            ratio = min(900 / alpha.shape[1], 700 / alpha.shape[0])
            alpha = cv2.resize(alpha, None, fx=ratio, fy=ratio)
            ah, aw = alpha.shape
            mask[
                760 - ah // 2 : 760 - ah // 2 + ah, 540 - aw // 2 : 540 - aw // 2 + aw
            ] = alpha
        yy, xx = np.where(mask > 0)
        weights = mask[yy, xx].astype(float)
        index = self.rng.choice(len(xx), self.n, p=weights / weights.sum())
        return np.column_stack([xx[index], yy[index]]).astype(np.float32)

    def make_atlas(self):
        self.cw = max(2, round(self.cell * self.scale))
        self.ch = max(3, round(self.cell * 1.5 * self.scale))
        atlas = []
        font = font_at(self.ch)
        for char in CHARS:
            tile = Image.new("L", (self.cw, self.ch))
            d = ImageDraw.Draw(tile)
            bbox = d.textbbox((0, 0), char, font=font)
            d.text(
                ((self.cw - d.textlength(char, font=font)) / 2, -bbox[1]),
                char,
                font=font,
                fill=255,
            )
            atlas.append(np.asarray(tile) / 255.0)
        return np.array(atlas, np.float32)

    def camera(self, t):
        p = ease((t - 3) / 3)
        # O zoom exponencial mantém a sensação de aproximação contínua.
        zoom = np.exp(np.log(19.0) * p)
        center = np.array([315.0, 650.0]) * (1 - p) + self.eye * p
        return center, zoom

    def portrait(self, t):
        center, zoom = self.camera(t)
        xy = center + (self.grid - [540, 960]) / (1.75 * zoom)
        # A pálpebra usa a pele vizinha para fechar o olho dentro de uma elipse.
        sampled = (
            cv2.remap(
                self.photo,
                xy[:, 0].astype(np.float32).reshape(self.rows, self.cols),
                xy[:, 1].astype(np.float32).reshape(self.rows, self.cols),
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REPLICATE,
            )
            .reshape(-1, 3)[:, ::-1]
            .astype(float)
        )
        blink = float(np.exp(-(((t - 2.35) / 0.115) ** 2)))
        if blink > 0.001:
            for ex, ey, rx, ry in ((212, 518, 34, 15), (351, 511, 36, 16)):
                dx, dy = (xy[:, 0] - ex) / rx, (xy[:, 1] - ey) / ry
                ellipse = dx * dx + dy * dy
                lid = (ellipse < 1) & (
                    np.abs(dy) > (1 - blink) * np.sqrt(np.maximum(0, 1 - dx * dx))
                )
                skinxy = xy.copy()
                skinxy[:, 1] = ey - 21
                skin = cv2.remap(
                    self.photo,
                    skinxy[:, 0].astype(np.float32).reshape(self.rows, self.cols),
                    skinxy[:, 1].astype(np.float32).reshape(self.rows, self.cols),
                    cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE,
                ).reshape(-1, 3)[:, ::-1]
                sampled[lid] = skin[lid]
                crease = (np.abs(dx) < 0.98) & (np.abs(dy) < 0.09) & (blink > 0.8)
                sampled[crease] *= 0.22
        lum = sampled @ np.array([0.2126, 0.7152, 0.0722])
        # Preservo os tons da foto e mantenho as letras estáveis entre os quadros.
        colors = np.clip(np.sqrt(sampled / 255) * 280 + 8, 0, 255)
        colors *= 0.6 + 0.4 * ease((t + 0.3) / 1.3)
        indices = np.clip(
            ((lum / 255) ** 0.72 * (len(CHARS) - 4) + 3).astype(int), 1, len(CHARS) - 1
        )
        return colors, indices

    def state(self, t):
        if t <= 6:
            colors, glyph = self.portrait(t)
            return self.grid.copy(), colors, glyph
        if t < 8:
            p = ease((t - 6) / 2)
            pos = self.grid * (1 - p) + self.heart * p
            # As curvas chegam e saem paradas para não dar trancos na transição.
            arc = np.sin(np.pi * p) ** 2
            pos += (
                np.column_stack(
                    [np.sin(self.phase + p * 4) * 95, np.cos(self.phase + p * 4) * 65]
                )
                * arc
            )
            col = self.eye_color * (1 - p) + self.heart_color * p
            return pos, col, np.where(p < 0.45, self.eye_glyph, self.glyph)
        beat = (
            1
            + 0.032
            * np.sin(2 * np.pi * (t - 8) * 1.2)
            * np.sin(np.pi * np.clip((t - 8) / 2.5, 0, 1)) ** 2
        )
        if t <= 10.5:
            return (
                (self.heart - [540, 900]) * beat + [540, 900],
                self.heart_color,
                self.glyph,
            )
        p = ease((t - 10.5) / 4)
        pos = self.heart * (1 - p) + self.dragon * p
        arc = np.sin(np.pi * p) ** 2
        pos += (
            np.column_stack(
                [np.cos(self.phase + 5 * p) * 160, np.sin(self.phase + 5 * p) * 120]
            )
            * arc
        )
        col = self.heart_color * (1 - p) + self.dragon_color * p
        return pos, col, self.glyph

    def stamp(self, canvas, positions, colors, glyph):
        x = np.rint(positions[:, 0] * self.scale - self.cw / 2).astype(int)
        y = np.rint(positions[:, 1] * self.scale - self.ch / 2).astype(int)
        valid = (x >= 0) & (y >= 0) & (x + self.cw <= self.w) & (y + self.ch <= self.h)
        x, y, colors, glyph = x[valid], y[valid], colors[valid], glyph[valid]
        # Cada partícula visível é uma letra desenhada a partir do atlas.
        for dy in range(self.ch):
            for dx in range(self.cw):
                intensity = self.atlas[glyph, dy, dx, None]
                value = (colors * intensity).astype(np.uint8)
                np.maximum.at(canvas, (y + dy, x + dx), value)

    def label(self, canvas, text, y, color, alpha=1, size=40):
        # Os títulos também são reconstruídos com os mesmos caracteres.
        tile = Image.new("L", (1080, 110))
        d = ImageDraw.Draw(tile)
        f = font_at(size)
        d.text(((1080 - d.textlength(text, font=f)) / 2, 0), text, font=f, fill=255)
        mask = np.asarray(tile)
        yy, xx = np.mgrid[0:110:5, 0:1080:5]
        val = mask[yy, xx].ravel() / 255
        good = val > 0.1
        points = np.column_stack([xx.ravel()[good], yy.ravel()[good] + y])
        colors = np.tile(color, (len(points), 1)) * val[good, None] * alpha
        self.stamp(canvas, points, colors, np.full(len(points), len(CHARS) - 2))

    def frame(self, t):
        pos, colors, glyph = self.state(t)
        canvas = np.zeros((self.h, self.w, 3), np.uint8)
        canvas[:] = [2, 4, 10]
        self.stamp(canvas, pos, colors, glyph)
        a = self.ambient.copy()
        a[:, 0] += np.sin(t * 0.3 + np.arange(len(a))) * 12
        a[:, 1] = (a[:, 1] - t * 15) % 1920
        tint = np.array([35, 65, 90])
        self.stamp(canvas, a, np.tile(tint, (len(a), 1)), np.full(len(a), 3))
        if t > 14:
            self.label(
                canvas,
                "KALI LINUX",
                1170,
                [90, 200, 255],
                float(ease((t - 14) / 0.8)),
                78,
            )
            self.label(
                canvas,
                "THE QUIETER YOU BECOME",
                1330,
                [50, 100, 145],
                float(ease((t - 14.4) / 0.8)),
                29,
            )
        # O brilho vem apenas da luz emitida pelas letras.
        glow = cv2.GaussianBlur(canvas, (0, 0), 1.7 * self.scale)
        return cv2.addWeighted(canvas, 1, glow, 0.38, 0)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--height", type=int, default=1920)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--duration", type=float, default=DURATION)
    p.add_argument("--photo", type=Path, default=ROOT / "assets/irina.jpg")
    p.add_argument("--logo", type=Path, default=ROOT / "assets/kali-dragon.png")
    p.add_argument("--output", type=Path)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--cell", type=int, default=7)
    p.add_argument("--stills", action="store_true")
    args = p.parse_args(argv)
    if args.preview:
        args.width, args.height = 540, 960
    if args.width <= 0 or args.height <= 0 or args.width % 2 or args.height % 2:
        p.error("Dimensões devem ser positivas e pares.")
    if abs(args.width / args.height - 9 / 16) > 0.001:
        p.error("Use proporção vertical 9:16.")
    if not 1 <= args.fps <= 120 or args.duration <= 0 or not 4 <= args.cell <= 24:
        p.error("FPS 1..120, duração positiva e célula 4..24.")
    if args.output is None:
        args.output = (
            ROOT
            / "output"
            / ("preview.mp4" if args.preview else "irina_kali_1080x1920.mp4")
        )
    return args


def main(argv=None):
    a = parse_args(argv)
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg não encontrado no PATH. Consulte README.md.")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    scene = Scene(a.width, a.height, a.seed, a.photo, a.logo, a.cell)
    if a.stills:
        for t in (1.5, 2.35, 4.5, 6, 7, 8.8, 11.5, 12.5, 14.8):
            Image.fromarray(scene.frame(t)).save(
                a.output.parent / f"frame_{t:05.2f}.jpg"
            )
        return
    temporary = a.output.with_name(a.output.stem + ".partial.mp4")
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{a.width}x{a.height}",
        "-r",
        str(a.fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "17",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        total = round(a.duration * a.fps)
        for n in range(total):
            proc.stdin.write(scene.frame(n / a.fps).tobytes())
            if n % a.fps == 0:
                print(f"{n // a.fps:02d}s / {a.duration:g}s", flush=True)
        proc.stdin.close()
        if proc.wait():
            raise RuntimeError("FFmpeg não concluiu a codificação.")
        temporary.replace(a.output)
    except BaseException:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.terminate()
        proc.wait()
        raise
    metadata = dict(
        width=a.width,
        height=a.height,
        fps=a.fps,
        frames=total,
        duration=total / a.fps,
        seed=a.seed,
        cell=a.cell,
        photo_sha256=hashlib.sha256(a.photo.read_bytes()).hexdigest(),
    )
    a.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Salvo: {a.output}", flush=True)


if __name__ == "__main__":
    main()
