"""Draw the original project icon; no official logos or external assets."""

from pathlib import Path

from PIL import Image, ImageDraw

BRAND = Path(__file__).resolve().parents[1] / "custom_components/ninebot_connect/brand"


def build() -> None:
    """Rasterize the same vector primitives at both required icon sizes."""
    scale = 4
    canvas = Image.new("RGBA", (256 * scale, 256 * scale))
    draw = ImageDraw.Draw(canvas)

    def points(values):
        return [tuple(int(value * scale) for value in point) for point in values]

    def line(values, width=10):
        draw.line(points(values), fill="white", width=width * scale, joint="curve")
        radius = width * scale / 2
        for x, y in points([values[0], values[-1]]):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="white")

    draw.rounded_rectangle((0, 0, 1023, 1023), radius=56 * scale, fill="#087F8C")
    for x in (60, 195):
        draw.ellipse(
            ((x - 22) * scale, 163 * scale, (x + 22) * scale, 207 * scale),
            outline="white",
            width=8 * scale,
        )
    line([(62, 184), (89, 151), (162, 151), (135, 178), (67, 178)])
    line([(195, 184), (166, 97), (148, 97)])
    line([(91, 151), (84, 130)])
    line([(75, 129), (113, 129)])
    draw.polygon(
        points([(127, 34), (103, 78), (121, 78), (112, 110), (151, 63), (131, 63), (143, 34)]),
        fill="#F7D44C",
    )
    BRAND.mkdir(parents=True, exist_ok=True)
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        canvas.resize((size, size), Image.Resampling.LANCZOS).save(BRAND / name, optimize=True)


if __name__ == "__main__":
    build()
