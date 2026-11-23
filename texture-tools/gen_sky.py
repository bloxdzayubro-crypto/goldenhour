#!/usr/bin/env python3
"""リアルな空(スカイボックス)を作る。昼・夕方・朝方・夜の 4 種類。

使い方:
  python tools/gen_sky.py --out <出力先のフォルダ> [--size 1024] [--variants day sunset dawn night] [--preview <フォルダ>]
  → <out>/GoldenHour-Sky-<名前>/skyBoxes/default/{nx,ny,nz,px,py,pz}.jpg

- 立方体の 6 面の貼り方は、OpenGL の決まり(公式のサンプルの空で、継ぎ目の色が合うことを確認した)。
- 空の色・雲・星は、「方向」だけで決まる式で描くので、面の境目で、つながる。
- 太陽の向きは、ゲームの標準の空の太陽(高さ約 54°、向き (-0.56, 0.81, -0.18))に合わせてある(昼)。
  シェーダーの光・影は、この太陽の向きで動くので、昼の空と、いちばん合う。
- 注意: 画像の空に替えると、ゲームの「earth」の空(昼夜・太陽・月・星の動き)は、止まる。
"""
import argparse
import os

import numpy as np
from PIL import Image

SUN_DEFAULT = np.array([-0.5590, 0.8090, -0.1820])  # ゲームの標準の空の太陽(クライアントの式から計算)
SUN_DEFAULT /= np.linalg.norm(SUN_DEFAULT)

# GL キューブマップ: 面 → (画像の列 sc, 行 tc) から、方向を作る
FACE_DIR = {
    "px": lambda sc, tc: (np.ones_like(sc), -tc, -sc),
    "nx": lambda sc, tc: (-np.ones_like(sc), -tc, sc),
    "py": lambda sc, tc: (sc, np.ones_like(sc), tc),
    "ny": lambda sc, tc: (sc, -np.ones_like(sc), -tc),
    "pz": lambda sc, tc: (sc, -tc, np.ones_like(sc)),
    "nz": lambda sc, tc: (-sc, -tc, -np.ones_like(sc)),
}


def face_directions(face, n):
    u = (np.arange(n) + 0.5) / n
    sc, tc = np.meshgrid(2 * u - 1, 2 * u - 1)  # tc: 上の行ほど -1
    x, y, z = FACE_DIR[face](sc, tc)
    d = np.stack([x, y, z], -1).astype(np.float64)
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


# ───── ノイズ ─────
M32 = 0xFFFFFFFF


def _h(ix, iy, iz, seed):
    h = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
    h &= M32
    h = ((h ^ (h >> 13)) * 1274126177) & M32
    h ^= h >> 16
    return (h & 0xFFFFFF) / 16777215.0


def smooth(t):
    return t * t * (3 - 2 * t)


def vnoise2(x, y, seed=0):
    ix = np.floor(x).astype(np.int64)
    iy = np.floor(y).astype(np.int64)
    fx = smooth(x - ix)
    fy = smooth(y - iy)
    a = _h(ix, iy, 0, seed)
    b = _h(ix + 1, iy, 0, seed)
    c = _h(ix, iy + 1, 0, seed)
    d = _h(ix + 1, iy + 1, 0, seed)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def vnoise3(p, seed=0):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    ix = np.floor(x).astype(np.int64)
    iy = np.floor(y).astype(np.int64)
    iz = np.floor(z).astype(np.int64)
    fx, fy, fz = smooth(x - ix), smooth(y - iy), smooth(z - iz)
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (fx if dx else 1 - fx) * (fy if dy else 1 - fy) * (fz if dz else 1 - fz)
                out = out + w * _h(ix + dx, iy + dy, iz + dz, seed)
    return out


def fbm2(x, y, octaves=5, seed=0):
    out = 0.0
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out = out + amp * vnoise2(x, y, seed + o * 7)
        tot += amp
        x, y = x * 2.03 + 11.7, y * 2.03 + 5.3
        amp *= 0.5
    return out / tot


# ───── 空の式 ─────
def srgb_to_lin(c):
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def smoothstep(a, b, x):
    return smooth(np.clip((x - a) / (b - a), 0.0, 1.0))


VARIANTS = {
    # sun: 太陽の高さ(度)と向き(度、0 = 標準の太陽の向き)。None = 標準の太陽をそのまま
    "day": dict(
        sun=SUN_DEFAULT, sun_power=26.0, zenith=(48, 108, 214), mid=(98, 160, 232), horizon=(196, 222, 246),
        glow=(255, 236, 200), glow_k=0.55, warm=0.0, cloud=(0.43, 0.70), cloud_lit=(255, 252, 246), cloud_shadow=(140, 160, 192),
        cloud_amount=1.05, stars=0.0, moon=None, ground=(150, 172, 196), exposure=1.0,
    ),
    "sunset": dict(
        elev=6.0, azim=0.0, sun_power=30.0, zenith=(34, 52, 128), mid=(120, 96, 150), horizon=(255, 150, 72),
        glow=(255, 176, 96), glow_k=0.95, warm=1.0, warm_colour=(255, 112, 52), cool_colour=(150, 112, 170),
        cloud=(0.46, 0.76), cloud_lit=(255, 168, 110), cloud_shadow=(78, 70, 118),
        cloud_amount=1.15, stars=0.0, moon=None, ground=(120, 84, 96), exposure=1.0,
    ),
    "dawn": dict(
        elev=9.0, azim=0.0, sun_power=24.0, zenith=(70, 104, 178), mid=(150, 150, 190), horizon=(255, 200, 164),
        glow=(255, 206, 160), glow_k=0.8, warm=0.75, warm_colour=(255, 164, 120), cool_colour=(176, 160, 204),
        cloud=(0.43, 0.72), cloud_lit=(255, 214, 190), cloud_shadow=(120, 118, 160),
        cloud_amount=1.05, stars=0.0, moon=None, ground=(150, 132, 150), exposure=1.0,
    ),
    # 曇り(gloomy 用): 太陽が見えない、重い雲
    "overcast": dict(
        sun=SUN_DEFAULT, sun_power=0.0, zenith=(112, 124, 140), mid=(150, 160, 174), horizon=(196, 204, 214),
        glow=(255, 250, 240), glow_k=0.0, warm=0.0, cloud=(0.26, 0.52), cloud_lit=(214, 218, 224), cloud_shadow=(104, 112, 128),
        cloud_amount=1.5, stars=0.0, moon=None, ground=(120, 130, 144), exposure=0.95,
    ),
    "night": dict(
        sun=None, sun_power=0.0, zenith=(4, 7, 22), mid=(8, 14, 38), horizon=(24, 36, 66),
        glow=(120, 150, 220), glow_k=0.35, warm=0.0, cloud=(0.58, 0.86), cloud_lit=(52, 62, 96), cloud_shadow=(8, 12, 28),
        cloud_amount=0.42, stars=1.0, moon=dict(elev=42.0, azim=40.0), ground=(14, 20, 38), exposure=1.0,
    ),
}


def sun_vector(v):
    if v.get("sun") is not None:
        return v["sun"]
    if "elev" in v:
        base = np.array([SUN_DEFAULT[0], 0.0, SUN_DEFAULT[2]])
        base /= np.linalg.norm(base)
        a = np.radians(v.get("azim", 0.0))
        ca, sa = np.cos(a), np.sin(a)
        h = np.array([base[0] * ca - base[2] * sa, 0.0, base[0] * sa + base[2] * ca])
        e = np.radians(v["elev"])
        s = np.array([h[0] * np.cos(e), np.sin(e), h[2] * np.cos(e)])
        return s / np.linalg.norm(s)
    return np.array([0.0, -1.0, 0.0])


def star_field(D, strength):
    p = D * 70.0
    ip = np.floor(p).astype(np.int64)
    fp = p - ip
    sel = _h(ip[..., 0], ip[..., 1], ip[..., 2], 101)
    present = (sel > 0.965).astype(float)
    sp = 0.25 + 0.5 * np.stack([_h(ip[..., 0], ip[..., 1], ip[..., 2], 102 + k) for k in range(3)], -1)
    dist = np.linalg.norm(fp - sp, axis=-1)
    mag = _h(ip[..., 0], ip[..., 1], ip[..., 2], 110) ** 2
    rad = 0.10 + 0.14 * mag
    s = np.exp(-((dist / rad) ** 2)) * (0.35 + 2.4 * mag) * present
    tint = _h(ip[..., 0], ip[..., 1], ip[..., 2], 111)[..., None]
    col = np.where(tint > 0.5, np.array([1.0, 0.86, 0.72]), np.array([0.74, 0.84, 1.0]))
    return s[..., None] * col * strength


def render(D, v, seed=3):
    S = sun_vector(v)
    y = D[..., 1]
    elev = np.clip(y, 0, 1)
    zen, mid, hor = (srgb_to_lin(v[k]) for k in ("zenith", "mid", "horizon"))

    # 空の色: 天頂 → 中間 → 地平線(地平線に近いほど、明るく淡い)
    t1 = smoothstep(0.0, 1.0, 1.0 - elev) ** 1.6
    t2 = (1.0 - elev) ** 5.0
    col = zen * (1 - t1)[..., None] + mid * t1[..., None]
    col = col * (1 - t2)[..., None] + hor * t2[..., None]

    # 太陽方向の光(散乱の輪): 広いぼんやりした光 + 近くの強い光
    cg = np.clip(np.sum(D * S, -1), -1, 1)
    ang = np.arccos(cg)
    glow = srgb_to_lin(v["glow"])
    g = v["glow_k"] * (0.35 * np.exp(-ang * 2.2) + 0.9 * np.exp(-ang * 9.0) + 1.6 * np.exp(-ang * 38.0))
    if v["sun_power"] > 0:
        col = col + glow * g[..., None]

    # 夕方・朝方: 地平線が、太陽側は暖色、反対側は寒色に染まる
    if v["warm"] > 0:
        flat = D[..., [0, 2]]
        flat = flat / np.maximum(np.linalg.norm(flat, axis=-1, keepdims=True), 1e-6)
        sflat = S[[0, 2]] / max(np.linalg.norm(S[[0, 2]]), 1e-6)
        sa = np.sum(flat * sflat, -1) * 0.5 + 0.5
        band = np.exp(-np.maximum(y, 0) * 5.5)
        warm = srgb_to_lin(v["warm_colour"])
        cool = srgb_to_lin(v["cool_colour"])
        tint = warm * (sa ** 2.2)[..., None] + cool * ((1 - sa) ** 1.5)[..., None] * 0.55
        col = col + tint * (band * v["warm"] * 0.55)[..., None]

    # 地平線より下: もや(地平線の色から、暗い地面の色へ)
    below = np.clip(-y, 0, 1)
    ground = srgb_to_lin(v["ground"])
    gmix = smoothstep(0.0, 0.35, below)
    col = col * (1 - gmix)[..., None] + (ground * (0.85 - 0.25 * below)[..., None]) * gmix[..., None]

    # 太陽の円盤(白く焼ける)
    if v["sun_power"] > 0:
        disc = 1.0 - smoothstep(0.0042, 0.0085, ang)
        col = col + glow * (disc * v["sun_power"])[..., None] * (y > -0.02)[..., None]

    # 雲: 空の平面に、視線を投げて、ノイズを引く。2 層(大きな塊 + 細かい塊)。太陽の側の薄さで、光と影をつける
    up = np.maximum(y, 0.0)
    P = D[..., [0, 2]] / (up + 0.16)[..., None]
    lo, hi = v["cloud"]
    n1 = fbm2(P[..., 0] * 0.55 + 3.1, P[..., 1] * 0.55 + 7.7, 5, seed)
    n2 = fbm2(P[..., 0] * 1.9 + 40.0, P[..., 1] * 1.9 + 11.0, 4, seed + 31)
    dens_raw = n1 * 0.72 + n2 * 0.28
    cover = smoothstep(lo, hi, dens_raw * v["cloud_amount"] - (v["cloud_amount"] - 1.0) * 0.05)
    fade = smoothstep(0.015, 0.20, y)
    cover = cover * fade
    sxz = S[[0, 2]] / max(np.linalg.norm(S[[0, 2]]), 1e-6)
    off = sxz * 0.10
    n1s = fbm2((P[..., 0] + off[0]) * 0.55 + 3.1, (P[..., 1] + off[1]) * 0.55 + 7.7, 5, seed)
    thick = np.clip(0.5 + (n1 - n1s) * 5.0, 0, 1)  # 太陽側へ向かって薄い = 明るい縁
    lit = srgb_to_lin(v["cloud_lit"])
    shd = srgb_to_lin(v["cloud_shadow"])
    ccol = shd * (1 - thick)[..., None] + lit * thick[..., None]
    # 太陽の近くの雲は、縁が銀色に輝く
    ccol = ccol + glow * (np.exp(-ang * 6.0) * (1 - cover) * 0.5)[..., None] * (v["sun_power"] > 0)
    col = col * (1 - 0.92 * cover)[..., None] + ccol * (0.92 * cover)[..., None]

    # 夜: 星・天の川・月
    if v["stars"] > 0:
        sky_open = smoothstep(-0.02, 0.10, y) * (1 - 0.92 * cover)
        col = col + star_field(D, v["stars"]) * sky_open[..., None]
        axis = np.array([0.35, 0.55, 0.76])
        axis /= np.linalg.norm(axis)
        band = np.exp(-((np.sum(D * axis, -1) / 0.22) ** 2))
        mw = vnoise3(D * 3.0, 17) * 0.55 + vnoise3(D * 7.0, 19) * 0.3 + vnoise3(D * 31.0, 29) * 0.15
        lanes = smoothstep(0.35, 0.70, vnoise3(D * 6.0, 23))
        mwc = np.array([0.55, 0.62, 0.86]) * (band * (0.35 + 0.65 * mw) * (1 - 0.35 * lanes) * 0.17)[..., None]
        col = col + mwc * sky_open[..., None]
    if v["moon"]:
        e, a = np.radians(v["moon"]["elev"]), np.radians(v["moon"]["azim"])
        base = np.array([SUN_DEFAULT[0], 0.0, SUN_DEFAULT[2]])
        base /= np.linalg.norm(base)
        ca, sa = np.cos(a), np.sin(a)
        h = np.array([base[0] * ca - base[2] * sa, 0.0, base[0] * sa + base[2] * ca])
        M = np.array([h[0] * np.cos(e), np.sin(e), h[2] * np.cos(e)])
        M /= np.linalg.norm(M)
        mang = np.arccos(np.clip(np.sum(D * M, -1), -1, 1))
        r = 0.046
        disc = 1.0 - smoothstep(r * 0.94, r, mang)
        # 月の表面: 模様(クレーターの明暗)と、少し欠けた陰
        local = (D - M) * 28.0
        surf = 0.78 + 0.22 * (vnoise3(local, 41) * 0.6 + vnoise3(local * 2.3, 43) * 0.4)
        ph = np.clip(0.55 + 0.45 * np.sum((D - M) * np.array([0.7, 0.2, -0.6]), -1) / r, 0.0, 1.0)
        moon = disc * surf * (0.45 + 0.55 * ph)
        halo = np.exp(-mang * 16.0) * 0.20 + np.exp(-mang * 60.0) * 0.35
        col = col + (np.array([1.0, 0.97, 0.90]) * (moon * 1.15)[..., None]) * (1 - 0.6 * cover)[..., None]
        col = col + np.array([0.55, 0.66, 0.95]) * (halo * 0.55)[..., None]

    return col * v["exposure"]


def tonemap_srgb(col, dither=True, seed=5):
    # 滑らかな肩つきの階調圧縮(白飛びを避ける)。そのあと sRGB へ
    a = np.maximum(col, 0)
    mapped = 1.0 - np.exp(-a * 1.15)
    mapped = np.where(a < 0.35, a * 1.05, 0.35 * 1.05 + (1 - 0.35 * 1.05) * (1 - np.exp(-(a - 0.35) * 1.4)))
    mapped = np.clip(mapped, 0, 1)
    srgb = np.where(mapped <= 0.0031308, mapped * 12.92, 1.055 * mapped ** (1 / 2.4) - 0.055)
    if dither:
        rng = np.random.default_rng(seed)
        srgb = srgb + (rng.random(srgb.shape) - 0.5) / 255.0  # 縞(バンディング)を消す、ごく弱いノイズ
    return (np.clip(srgb, 0, 1) * 255 + 0.5).astype(np.uint8)


def write_skybox(name, v, out_dir, size, quality):
    d = os.path.join(out_dir, f"GoldenHour-Sky-{name}", "skyBoxes", "default")
    os.makedirs(d, exist_ok=True)
    for face in FACE_DIR:
        D = face_directions(face, size)
        img = tonemap_srgb(render(D, v), seed=hash(face) & 0xFFFF)
        Image.fromarray(img, "RGB").save(os.path.join(d, face + ".jpg"), quality=quality, subsampling=0, optimize=True)
    return d


def equirect_preview(v, path, w=1600, h=800):
    lon = (np.arange(w) + 0.5) / w * 2 * np.pi - np.pi
    lat = np.pi / 2 - (np.arange(h) + 0.5) / h * np.pi
    LON, LAT = np.meshgrid(lon, lat)
    D = np.stack([np.cos(LAT) * np.cos(LON), np.sin(LAT), np.cos(LAT) * np.sin(LON)], -1)
    Image.fromarray(tonemap_srgb(render(D, v)), "RGB").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--quality", type=int, default=94)
    ap.add_argument("--variants", nargs="+", default=["day", "sunset", "dawn", "night"])
    ap.add_argument("--preview", default=None, help="全方位の確認用の画像(equirect)を、このフォルダに書く")
    args = ap.parse_args()
    for name in args.variants:
        v = VARIANTS[name]
        d = write_skybox(name.capitalize(), v, args.out, args.size, args.quality)
        print("→", d)
        if args.preview:
            os.makedirs(args.preview, exist_ok=True)
            equirect_preview(v, os.path.join(args.preview, f"sky_{name}.png"))


if __name__ == "__main__":
    main()
