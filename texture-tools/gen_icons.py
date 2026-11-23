#!/usr/bin/env python3
"""10x10 などの小さなドット絵(アイテムのアイコン・植物の絵)を、「別の表現」で描き直す。単なる拡大ではない。

  1. 輪郭: 透明度の形を、なめらかに丸めて拡大(ギザギザの階段を、なくす)。
  2. 色: 色の境目を保ったまま、領域の中を、なめらかに(バイラテラル)。黒い縁取りは、領域の色に染めて、やわらかくする。
  3. 立体: 形から「丸みのある高さ」を作り、左上からの光で、陰影と、つや(スペキュラ)をつける。素材(金属・宝石・金・木・食べ物)ごとに、つやの強さと模様が違う。
  4. 仕上げ: 縁の暗がり(AO)、細かな粒、彩度とコントラスト。

使い方は build_all.py から。単体: python tools/gen_icons.py --src <png のフォルダ> --out <出力> [--names a b]
"""
import argparse
import os
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_textures as gt  # noqa: E402


def luma(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def blur(p, sigma):
    return gt.blur(p.astype(np.float32), max(0.3, sigma), False)


def upscale_mask(a, s):
    """透明度(0/1 が多い)を、なめらかな輪郭で拡大する。"""
    pad = 2
    pp = np.pad(a.astype(np.float32), pad, mode="edge")
    im = Image.fromarray(pp, mode="F").resize((pp.shape[1] * s, pp.shape[0] * s), Image.BICUBIC)
    u = np.asarray(im, dtype=np.float32)[pad * s:-pad * s, pad * s:-pad * s]
    return smoothstep(0.38, 0.62, u)


def bilateral(img, sigma_s, sigma_r, radius):
    """色の境目を、あまり、にじませずに、なめらかにする。img: HxWx3 (0..1)。"""
    h, w, _ = img.shape
    pad = np.pad(img, ((radius, radius), (radius, radius), (0, 0)), mode="edge")
    acc = np.zeros_like(img)
    wsum = np.zeros((h, w, 1), np.float32)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            ws = np.exp(-(dx * dx + dy * dy) / (2 * sigma_s * sigma_s))
            sh = pad[radius + dy:radius + dy + h, radius + dx:radius + dx + w]
            d2 = np.sum((sh - img) ** 2, -1, keepdims=True)
            wt = ws * np.exp(-d2 / (2 * sigma_r * sigma_r))
            acc += sh * wt
            wsum += wt
    return acc / np.maximum(wsum, 1e-6)


def classify_pixels(c):
    """各画素の素材らしさ(0〜1): metal / gem / gold / wood / dark。"""
    mx = c.max(-1)
    mn = c.min(-1)
    sat = mx - mn
    lum = luma(c)
    metal = smoothstep(0.30, 0.55, lum) * (1 - smoothstep(0.10, 0.22, sat))
    gem = smoothstep(0.35, 0.55, sat) * smoothstep(0.30, 0.5, lum) * (1 - (c[..., 0] > c[..., 1] * 1.1) * (c[..., 1] > c[..., 2] * 1.3))
    gold = smoothstep(0.30, 0.5, sat) * (c[..., 0] > c[..., 1] * 1.05) * (c[..., 1] > c[..., 2] * 1.3) * smoothstep(0.45, 0.65, lum)
    wood = smoothstep(0.12, 0.3, sat) * (1 - smoothstep(0.35, 0.6, lum)) * (c[..., 0] > c[..., 2])
    dark = 1 - smoothstep(0.08, 0.22, lum)
    return metal.astype(np.float32), gem.astype(np.float32), gold.astype(np.float32), wood.astype(np.float32), dark.astype(np.float32)


def render_icon(arr, target=80, outline_soften=0.85, seed=1):
    """arr: HxWx4 (0..1)。返り値: (H*s)x(W*s)x4。"""
    h, w = arr.shape[:2]
    s = max(1, int(round(target / max(h, w))))
    H, W = h * s, w * s
    rng = np.random.default_rng(seed)
    alpha = arr[..., 3]
    # 1. 輪郭
    A = upscale_mask((alpha > 0.5).astype(np.float32) if (alpha < 0.999).any() else alpha, s)
    A = np.maximum(A, 0.0) if (alpha < 0.999).any() else np.ones((H, W), np.float32)
    # 2. 色: 最近傍で拡大 → 透明な所の色を、近くの色で埋める → バイラテラルで、領域の中を、なめらかに
    rgb = arr[..., :3].copy()
    wgt = (alpha > 0.5).astype(np.float32)[..., None]
    fill = blur_color(rgb * wgt, wgt, 1.5)  # 透明部分に、にじみ出す色(縁の色が、黒く沈まないように)
    rgb = np.where(wgt > 0, rgb, fill)
    big = np.repeat(np.repeat(rgb, s, 0), s, 1).astype(np.float32)
    col = bilateral(big, max(1.5, s * 0.55), 0.22, max(2, int(s * 1.1)))
    # 黒い縁取りを、内側の色に染めて、やわらかくする(絵が、重く見えない)
    lum0 = luma(col)
    outline = (1 - smoothstep(0.07, 0.20, lum0)) * (A > 0.3)
    inner_w = (1 - outline)[..., None] * (A > 0.3)[..., None]
    inner = blur_color(col * inner_w, inner_w, s * 0.9)
    col = col * (1 - outline_soften * outline[..., None]) + (inner * 0.58) * (outline_soften * outline[..., None])
    # 3. 立体: 形から、丸みのある高さ。色の明暗も、少し高さにする
    dome = blur(A, s * 0.75)
    Hgt = 1.4 * dome + 0.35 * blur(luma(col), s * 0.35)
    gy, gx = np.gradient(blur(Hgt, s * 0.25))
    K = s * 0.9
    nx, ny, nz = -gx * K, -gy * K, np.ones_like(gx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx * inv, ny * inv, nz * inv
    L = np.array([-0.50, -0.62, 0.60]); L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    nh = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1)
    metal, gem, gold, wood, dark = classify_pixels(col)
    metal, gem, gold, wood, dark = (blur(x, s * 0.4) for x in (metal, gem, gold, wood, dark))
    gloss = 0.14 + 0.62 * metal + 0.70 * gem + 0.50 * gold + 0.04 * wood
    shade = 0.58 + 0.62 * diff
    spec = (nh ** 30.0) * gloss * 0.9 + (nh ** 6.0) * gloss * 0.12
    # 4. 素材の模様
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    diag = (xx - yy) / (1.4142 * s)
    streak = gt.tile_noise(H, W, 1, 1, rng) * 0  # 形の保持用(使わない)
    brushed = (np.sin(diag * 6.0 + gt.tile_noise(H, W, max(2, H // 6), max(2, W // 6), rng) * 4.0) * 0.5)
    grain = gt.tile_noise(H, W, H // 2, W // 2, rng) - 0.5
    woodgrain = (gt.tile_noise(H, W, max(2, H // 14), max(2, W // 2), rng) - 0.5)
    tex = 1.0 + brushed * 0.06 * metal + grain * 0.06 + woodgrain * 0.22 * wood + (grain * 0.10) * gem
    out = col * (shade * tex)[..., None]
    # 宝石の光の点
    sparkle = (nh ** 90.0) * gem
    out = out + np.stack([spec, spec, spec], -1) * np.where(gold[..., None] > 0.3, np.array([1.0, 0.86, 0.55]), np.array([1.0, 1.0, 1.0]))
    out = out + sparkle[..., None] * 0.8
    # 縁の暗がり(AO)と、縁の細い明るい光
    edge_dark = 1 - blur(A, s * 1.2)
    ao = np.clip(edge_dark * 1.1, 0, 0.5)
    out = out * (1 - ao[..., None] * 0.5)
    rim = np.clip(blur(A, s * 0.5) - blur(A, s * 1.1), 0, 1)
    out = out + (rim[..., None] * 0.10)
    # 色の仕上げ
    lum = luma(out)[..., None]
    out = lum + (out - lum) * 1.14
    out = (out - 0.5) * 1.07 + 0.5
    res = np.clip(np.concatenate([out, A[..., None]], -1), 0, 1)
    res[..., :3] *= (A > 0.001)[..., None]
    return res


def render_icon_crisp(arr, target=80, seed=1):
    """アイコン用(角を丸めない版)。ドットの輪郭は、そのまま(ギザギザを保つ)。立体感は、面取りの陰影と、素材の質感でつくる。
      1. 色・形: ドットをそのまま拡大(ぼかさない)。
      2. 凹凸: 元の明暗(輪郭の暗い線 → 内側の色)から、高さの地図を作り、左上の光で、縁に面取りの明暗をつける(輪郭は、丸めない)。
      3. 素材: 金属 = 研いだ筋 + 鋭い光、宝石 = 面の明暗 + 光の点、金 = ぎらつき、木 = 木目、食べ物 = 弱いつや。
      4. 仕上げ: 細かな粒、わずかな影(右下)、彩度とコントラスト。"""
    h, w = arr.shape[:2]
    s = max(1, int(round(target / max(h, w))))
    H, W = h * s, w * s
    rng = np.random.default_rng(seed)
    alpha0 = (arr[..., 3] > 0.5).astype(np.float32)
    A = np.repeat(np.repeat(alpha0, s, 0), s, 1)
    col = np.repeat(np.repeat(arr[..., :3], s, 0), s, 1).astype(np.float32)
    col = bilateral(col, max(1.2, s * 0.40), 0.10, max(2, int(s * 0.8)))  # 色の塊の内側だけ、なめらかに(境目・輪郭は保つ)
    lum_src = luma(arr[..., :3])
    # 高さの地図: 色の明暗(輪郭の黒 = 低い、明るい色 = 高い)+ 形の内側ほど高い。ドットの境目で、はっきり立ち上がるように、軽くだけぼかす。
    inner = gt.blur(alpha0, 0.9, False)
    H0 = 0.55 * lum_src + 0.9 * inner
    Hup = np.asarray(Image.fromarray(H0.astype(np.float32), mode="F").resize((W, H), Image.BILINEAR), dtype=np.float32)
    Hup = blur(Hup, s * 0.28)
    gy, gx = np.gradient(Hup)
    K = s * 2.1
    nx, ny, nz = -gx * K, -gy * K, np.ones_like(gx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx * inv, ny * inv, nz * inv
    L = np.array([-0.55, -0.6, 0.58]); L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    nh = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1)
    metal, gem, gold, wood, dark = classify_pixels(col)
    gloss = 0.16 + 0.80 * metal + 1.00 * gem + 0.75 * gold + 0.06 * wood
    shade = 0.66 + 0.62 * diff
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # 素材の模様(ドットごとの塊の中で、連続する)
    diag = (xx - yy) / (1.4142 * s)
    brushed = np.sin(diag * 7.0 + gt.tile_noise(H, W, max(2, H // 8), max(2, W // 8), rng) * 4.0) * 0.5
    fine = gt.tile_noise(H, W, H // 2, W // 2, rng) - 0.5
    gwood = gt.tile_noise(H, W, max(2, H // 16), max(2, W // 2), rng) - 0.5
    tex = 1.0 + brushed * 0.16 * metal + fine * 0.12 + gwood * 0.36 * wood + fine * 0.22 * gem
    out = col * (shade * tex)[..., None]
    spec = (nh ** 28.0) * gloss * 0.55 + (nh ** 5.0) * gloss * 0.05
    out = out + np.stack([spec] * 3, -1) * np.where(gold[..., None] > 0.3, np.array([1.0, 0.86, 0.55]), np.array([1.0, 1.0, 1.0]))
    out = out + ((nh ** 70.0) * gem)[..., None] * 1.0
    # 右下に、ごく薄い影(浮いて見える)。形の外にだけ落とす
    shadow = np.roll(np.roll(A, int(s * 0.5), 0), int(s * 0.5), 1)
    shadow = blur(shadow, s * 0.35) * (1 - A)
    # 縁の黒い輪郭は、少しだけ、内側の色に寄せる(真っ黒の重さを減らす)
    ol = (1 - smoothstep(0.07, 0.20, luma(col))) * A
    innerc = blur_color(col * (A * (1 - ol))[..., None], (A * (1 - ol))[..., None], s * 0.9)
    out = out * (1 - 0.35 * ol[..., None]) + (innerc * 0.30) * (0.35 * ol[..., None])
    lum = luma(out)[..., None]
    out = lum + (out - lum) * 1.03
    out = (out - 0.5) * 1.05 + 0.5
    # 平均の明るさ・色を、元の絵に合わせる(明るくなりすぎない)。形の内側の、元の平均と比べる。
    m = A > 0.5
    if m.any():
        om = (arr[..., :3] * (arr[..., 3:4] > 0.5)).sum((0, 1)) / max(1.0, float((arr[..., 3] > 0.5).sum()))
        nm = np.clip(out, 0, 1)[m].mean(0)
        out = out * (om / np.maximum(nm, 1e-4)) * 0.90  # 元より、少し暗めに(ゲームの光・シェーダーが、さらに明るくするため)
    rgb = np.clip(out, 0, 1)
    # 影を、アルファに(形の外は、暗い半透明)
    a_final = np.clip(np.maximum(A, shadow * 0.45), 0, 1)
    rgb = np.where((A > 0)[..., None], rgb, np.zeros_like(rgb))
    return np.concatenate([rgb, a_final[..., None]], -1)


def render_plant(arr, target=64, seed=1):
    """植物(切り抜きの絵)用。形(小麦の隙間・葉の切れ込み)を保ち、ごく小さな丸みと、葉脈・粒・弱いつやだけを足す。"""
    h, w = arr.shape[:2]
    s = max(1, int(round(target / max(h, w))))
    H, W = h * s, w * s
    rng = np.random.default_rng(seed)
    alpha = np.repeat(np.repeat(arr[..., 3], s, 0), s, 1)
    A = blur((alpha > 0.5).astype(np.float32), 0.55)  # 輪郭は、ドットの形のまま、ギザギザの角だけ、わずかに丸める
    col = np.repeat(np.repeat(arr[..., :3], s, 0), s, 1).astype(np.float32)
    wgt = (A > 0.3).astype(np.float32)[..., None]
    col = bilateral(np.where(wgt > 0, col, blur_color(col * wgt, wgt, 2.0)), max(1.0, s * 0.35), 0.10, max(2, int(s * 0.7)))
    lum = luma(col)
    # 小さな丸み(葉の厚み)+ 明暗の凹凸
    Hgt = 0.7 * blur(A, s * 0.45) + 0.9 * blur(lum, s * 0.30)
    gy, gx = np.gradient(blur(Hgt, s * 0.2))
    K = s * 1.5
    nx, ny, nz = -gx * K, -gy * K, np.ones_like(gx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx * inv, ny * inv, nz * inv
    L = np.array([-0.5, -0.6, 0.62]); L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    nh = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vein = gt.tile_noise(H, W, max(2, H // 3), max(2, W // 24), rng) - 0.5  # 縦の筋(葉脈・茎)
    grain = gt.tile_noise(H, W, H // 2, W // 2, rng) - 0.5
    blotch = gt.tile_noise(H, W, max(2, H // 10), max(2, W // 10), rng) - 0.5
    shade = 0.74 + 0.40 * diff
    out = col * (shade * (1.0 + vein * 0.18 + grain * 0.07 + blotch * 0.12))[..., None] + ((nh ** 20.0) * 0.10)[..., None]
    lum2 = luma(out)[..., None]
    out = lum2 + (out - lum2) * 1.15
    out = (out - 0.5) * 1.07 + 0.5
    res = np.clip(np.concatenate([out, A[..., None]], -1), 0, 1)
    res[..., :3] *= (A > 0.001)[..., None]
    return res


def blur_color(c, wgt, sigma):
    """重み付きのぼかし(重みの無い所の色が、混ざらない)。"""
    num = np.stack([blur(c[..., k], sigma) for k in range(3)], -1)
    den = blur(wgt[..., 0] if wgt.ndim == 3 else wgt, sigma)[..., None]
    return num / np.maximum(den, 1e-4)


def render_armour(arr, scale=4):
    """着る防具の展開図(64x64 の部品の絵)。ドットの形・面の明暗は保ち(ぼかさない)、金属の研いだ筋、狭い面取り、つやを足す。"""
    h, w = arr.shape[:2]
    H, W = h * scale, w * scale
    rng = np.random.default_rng(7)
    alpha = np.repeat(np.repeat(arr[..., 3], scale, 0), scale, 1)
    col = np.repeat(np.repeat(arr[..., :3], scale, 0), scale, 1).astype(np.float32)
    A = (alpha > 0.5).astype(np.float32)
    lum = luma(col)
    # 部品の縁の、狭い面取り(幅は、ほぼ 1 ドット)+ 面の明暗の凹凸
    Hgt = 1.0 * blur(A, scale * 0.55) + 0.9 * blur(lum, scale * 0.35)
    gy, gx = np.gradient(blur(Hgt, scale * 0.2))
    K = scale * 2.6
    nx, ny, nz = -gx * K, -gy * K, np.ones_like(gx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx * inv, ny * inv, nz * inv
    L = np.array([-0.5, -0.6, 0.62]); L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    nh = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1)
    shade = 0.88 + (diff - 0.6) * 0.95
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    brushed = (gt.tile_noise(H, W, H, 1, rng) - 0.5) * 2.0  # 横の、研いだ筋(行ごとの明暗)
    grain = gt.tile_noise(H, W, H // 2, W // 2, rng) - 0.5
    spec = (nh ** 24.0) * 0.16 + (nh ** 7.0) * 0.03
    # 面の明暗(元の絵)を、少し強める(元のドットの facets を、はっきり)
    contrast = 1.0 + (lum - blur(lum, scale * 1.5))[..., None] * 2.3
    out = col * contrast * (shade * (1.0 + brushed * 0.12 + grain * 0.08))[..., None] + spec[..., None] * np.array([1.0, 0.98, 0.95])
    lum2 = luma(out)[..., None]
    out = lum2 + (out - lum2) * 1.18
    # 平均の色を、元に合わせる(色相・明るさが、ずれないように。ゲームは、この画像を、そのまま、防具に貼る)
    m = A > 0.5
    if m.any():
        orig_mean = col[m].mean(0)
        new_mean = np.clip(out, 0, 1)[m].mean(0)
        out = out * (orig_mean / np.maximum(new_mean, 1e-4))
    res = np.clip(np.concatenate([out, A[..., None]], -1), 0, 1)
    res[..., :3] *= (A > 0)[..., None]
    return res


def load(path):
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255.0


def save(arr, path):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(path, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target", type=int, default=80)
    ap.add_argument("--names", nargs="*", default=None)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for f in sorted(os.listdir(args.src)):
        n = os.path.splitext(f)[0]
        if not f.lower().endswith(".png") or (args.names and n not in args.names):
            continue
        a = load(os.path.join(args.src, f))
        save(render_armour(a) if re.search(r"armou?r", n, re.I) and a.shape[0] >= 32 else render_icon(a, args.target, seed=gt.seed_for(n) & 0xFFFF), os.path.join(args.out, n + ".png"))
        print(n, a.shape[:2])


if __name__ == "__main__":
    main()
