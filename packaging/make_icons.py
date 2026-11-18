"""Generate the icons (.ico and .png) for the five apps with simple drawings. Requires Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
WHITE = (255, 255, 255, 255)
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def billcutter(d, color):  # card cut by a diagonal line
    d.rounded_rectangle((90, 160, 422, 352), radius=28, outline=WHITE, width=22)
    d.rectangle((90, 215, 422, 250), fill=WHITE)
    d.line((150, 430, 362, 82), fill=(255, 224, 110, 255), width=28)


def vault(d, color):  # padlock
    d.line((178, 215, 178, 250), fill=WHITE, width=30)
    d.line((334, 215, 334, 250), fill=WHITE, width=30)
    d.arc((178, 105, 334, 260), 180, 360, fill=WHITE, width=30)
    d.rounded_rectangle((126, 240, 386, 420), radius=34, fill=WHITE)
    d.ellipse((234, 296, 278, 340), fill=color)
    d.rectangle((248, 326, 264, 378), fill=color)


def photo_cleaner(d, color):  # camera
    d.rectangle((190, 128, 322, 182), fill=WHITE)
    d.rounded_rectangle((76, 168, 436, 398), radius=40, fill=WHITE)
    d.ellipse((181, 205, 331, 355), fill=color)
    d.ellipse((211, 235, 301, 325), fill=WHITE)


def finance(d, color):  # chart bars
    for left, height in ((116, 150), (221, 245), (326, 330)):
        d.rounded_rectangle((left, 410 - height, left + 72, 410), radius=14, fill=WHITE)


def branchchat(d, color):  # tree with two branches
    d.line((256, 150, 256, 262), fill=WHITE, width=26)
    d.line((256, 262, 148, 376), fill=WHITE, width=26)
    d.line((256, 262, 364, 376), fill=WHITE, width=26)
    for x, y, r in ((256, 140, 44), (148, 388, 40), (364, 388, 40)):
        d.ellipse((x - r, y - r, x + r, y + r), fill=WHITE)


ICONS = {
    "billcutter": ((209, 73, 91), billcutter),
    "vault": ((47, 75, 124), vault),
    "photo-cleaner": ((14, 124, 134), photo_cleaner),
    "finance": ((58, 125, 68), finance),
    "branchchat": ((123, 79, 179), branchchat),
}


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    for name, (rgb, draw_glyph) in ICONS.items():
        color = (*rgb, 255)
        image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=110, fill=color)
        draw_glyph(draw, color)
        image.save(ASSETS / f"{name}.png")
        image.save(ASSETS / f"{name}.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
        print("icon:", name)


if __name__ == "__main__":
    main()
