#!/usr/bin/env python3
"""Taklif kartasini yasaydi -- har til uchun bitta JPEG.

Telegram taklif xabariga rasm qo'shish uchun kerak. Rasm o'yinning
daftar uslubiga mos: qog'oz fon, chiziqlar, qo'lda chizilgandek mushuk.

Chiziqlar ataylab biroz qaltiroq: ruler bilan chizilgan tekis doira
qog'ozga qalam bilan chizilgandek ko'rinmaydi. Qaltirash urug'i qat'iy,
shuning uchun har ishga tushirishda aynan bir xil rasm chiqadi.

    python3 tools/make_invite.py          # web/invite-{uz,en,ru}.jpg

Zaruriy shart: Pillow. Shrift macOS'dagi Bradley Hand -- o'yin CSS'ida
ham shu zaxira shrift sifatida yozilgan va kirillni to'liq qoplaydi.
"""

import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
PAPER = (250, 246, 236)
RULE = (214, 226, 238)
MARGIN = (227, 185, 176)
INK = (48, 43, 36)
SOFT = (141, 131, 112)
ACCENT = (198, 93, 110)

FONT = "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf"

TEXT = {
    "uz": ("Chiz va Top", "Ikki kishilik chizish va topish o'yini"),
    "en": ("Draw & Guess", "A two-player drawing and guessing game"),
    "ru": ("Рисуй и угадай", "Игра на двоих: рисуй и угадывай"),
}

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "web")


def font(size):
    return ImageFont.truetype(FONT, size)


class Hand:
    """Qalam bilan chizilgandek chiziqlar."""

    def __init__(self, draw, rng):
        self.d = draw
        self.rng = rng

    def _wobble(self, amount=2.0):
        return self.rng.uniform(-amount, amount)

    def line(self, p0, p1, fill=INK, width=5, segments=12, amount=2.0):
        (x0, y0), (x1, y1) = p0, p1
        pts = []
        for i in range(segments + 1):
            t = i / segments
            pts.append((x0 + (x1 - x0) * t + self._wobble(amount),
                        y0 + (y1 - y0) * t + self._wobble(amount)))
        self.d.line(pts, fill=fill, width=width, joint="curve")

    def arc(self, cx, cy, rx, ry, a0, a1, fill=INK, width=5, amount=2.5):
        pts = []
        steps = max(12, int(abs(a1 - a0) / 6))
        for i in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * i / steps)
            pts.append((cx + math.cos(a) * rx + self._wobble(amount),
                        cy + math.sin(a) * ry + self._wobble(amount)))
        self.d.line(pts, fill=fill, width=width, joint="curve")

    def circle(self, cx, cy, rx, ry, **kw):
        self.arc(cx, cy, rx, ry, 0, 360, **kw)


def paper(d):
    """Daftar varaqi: faqat ko'ndalang chiziqlar.

    Chap chekka chizig'i olib tashlandi -- markazlashtirilgan kompozitsiya
    bilan to'qnashardi va rasmni chap tomonga og'dirib ko'rsatardi.
    """
    y = 212
    while y < H - 40:
        d.line([(56, y), (W - 56, y)], fill=RULE, width=2)
        y += 58


def cat(h, cx, cy, s):
    """Mushuk: o'yinning chizish yarmi.

    Mayda joylarda (ko'z, burun) qaltirash kamaytirilgan -- katta qaltirash
    kichik shaklni chizgandek emas, qaltiragandek ko'rsatadi.
    """
    h.circle(cx, cy, 98 * s, 88 * s, width=7)
    # quloqlar
    h.line((cx - 72 * s, cy - 62 * s), (cx - 98 * s, cy - 130 * s), width=7)
    h.line((cx - 98 * s, cy - 130 * s), (cx - 29 * s, cy - 88 * s), width=7)
    h.line((cx + 72 * s, cy - 62 * s), (cx + 98 * s, cy - 130 * s), width=7)
    h.line((cx + 98 * s, cy - 130 * s), (cx + 29 * s, cy - 88 * s), width=7)
    # ko'zlar -- yopiq, mamnun
    h.arc(cx - 37 * s, cy - 8 * s, 17 * s, 15 * s, 200, 340, width=6, amount=1.0)
    h.arc(cx + 37 * s, cy - 8 * s, 17 * s, 15 * s, 200, 340, width=6, amount=1.0)
    # burun va og'iz
    h.line((cx - 10 * s, cy + 24 * s), (cx + 10 * s, cy + 24 * s),
           width=6, amount=1.0)
    h.arc(cx - 17 * s, cy + 26 * s, 17 * s, 16 * s, 10, 150, width=5, amount=1.0)
    h.arc(cx + 17 * s, cy + 26 * s, 17 * s, 16 * s, 30, 170, width=5, amount=1.0)
    # mo'ylovlar -- yuz chetidan boshlanadi, ustidan emas
    for dy, spread in ((-4, -14), (12, 4)):
        h.line((cx - 86 * s, cy + dy * s), (cx - 150 * s, cy + spread * s),
               width=4, amount=1.2)
        h.line((cx + 86 * s, cy + dy * s), (cx + 150 * s, cy + spread * s),
               width=4, amount=1.2)


def bubble(h, cx, cy, rx, ry):
    """Fikr pufagi -- raqib topishga urinayotgani.

    Qalam variantidan voz kechildi: u mushukka yopishib, karnaydek
    ko'rinardi. Pufak esa o'yinning ikkinchi yarmini -- topishni -- to'g'ridan
    to'g'ri aytadi, va mushuk bilan birga butun o'yinni bitta rasmda beradi.
    """
    h.circle(cx, cy, rx, ry, width=6, amount=2.0)
    # chapga, mushuk tomonga qaragan dumaloq quyruq
    for i, (dx, dy, r) in enumerate(((-rx - 26, 44, 17), (-rx - 62, 78, 11))):
        h.circle(cx + dx, cy + dy, r, r, width=5, amount=1.2)


def card(lang):
    title, subtitle = TEXT[lang]
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    rng = random.Random(7)          # qat'iy urug': rasm har safar bir xil
    h = Hand(d, rng)

    paper(d)

    # Chap tomonda chizilgan narsa, o'ng tomonda topa olmaslik: o'yinning
    # ikki yarmi muvozanatda. Oldingi variantda mushuk markazda yolg'iz
    # turib, atrofi bo'sh qolardi.
    cat(h, 404, 416, 1.46)
    bubble(h, 918, 372, 182, 146)
    d.text((918, 368), "?", font=font(196), fill=ACCENT, anchor="mm")

    d.text((640, 108), title, font=font(112), fill=INK, anchor="mm")
    d.text((640, 672), subtitle, font=font(42), fill=SOFT, anchor="mm")

    # chekka ramka -- qog'oz varaqdek
    d.rectangle([14, 14, W - 15, H - 15], outline=(226, 219, 203), width=3)

    path = os.path.join(OUT, "invite-%s.jpg" % lang)
    img.save(path, "JPEG", quality=88, optimize=True)
    return path, os.path.getsize(path)


if __name__ == "__main__":
    for lang in ("uz", "en", "ru"):
        path, size = card(lang)
        print("%s  %6.1f KB" % (os.path.relpath(path), size / 1024.0))
