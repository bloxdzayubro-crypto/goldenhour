#!/usr/bin/env python3
"""Bloxd 標準テクスチャ(default2)から、「絵柄を変えずに、リアルで精細」にしたテクスチャパックを作る。

使い方:
  python tools/gen_textures.py --src <default2/textures のフォルダ> --out <出力先のパックのフォルダ> [--scale 4] [--preview 比較画像.png]

  --scale: 何倍にするか。8x8 の元を、4 → 32x32、8 → 64x64。
  元のテクスチャは、公式リポジトリ https://github.com/Bloxdy/texturePacks の default2/textures。
  (このフォルダには、公式の素材は、置かない。--src で、外から読むだけ。)

やること(素材の名前から種類を判定して、種類ごとに足す):
  1. 滑らかに拡大(縁は、タイルの継ぎ目が出ないよう、回り込ませて補間)。透明な素材は、縁をなめらかな輪郭にする。
  2. 細部を足す: 石 = 粒 + ひび割れ / 土・砂 = 細かな粒 / 草 = 草の筋 / 木 = 木目 / 葉 = 葉脈 / 羊毛 = 繊維 など。
     足す細部は、全部、タイルしても継ぎ目が出ない(周期的な)ノイズ。元の絵柄の輪郭(鉱石の粒、レンガの目地)の近くでは、弱める。
  3. 輪郭を少し締める(アンシャープ)、彩度とコントラストを、ほんの少し上げる。
"""
import argparse
import hashlib
import os
import re
import sys

import numpy as np
from PIL import Image

# ───── 調整用の値 ─────
SATURATION = 1.10        # 彩度(1.0 = そのまま)
CONTRAST = 1.08          # コントラスト(1.0 = そのまま)
SHARPEN = 1.40           # 輪郭の締め(0.0 = なし)
MID_SCALE = 0.55         # 中くらいの大きさのむら(もやもやして見える)の強さの倍率
EMBOSS = 1.0              # 焼き込みの陰影(立体感)の強さの倍率(0.0 = なし)
DETAIL = 1.0             # 足す細部の強さの倍率(0.0 = 細部なし、拡大だけ)


def seed_for(name):
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16)


# ───── 素材の種類 ─────
# (正規表現, 種類) を、上から順に試す。
RULES = [
    (r"^(lava|water)\d*$", "liquid"),
    (r"portal\d*$", "liquid"),
    (r"(sapling|_plant_stage|_bush|dangling_vine|^vines?$|lily_pad)", "plant"),
    (r"(door|trapdoor|^ladder)", "planks"),
    (r"(fireball|iceball|toxin_ball|bouncy_bomb|grenade|rocket|spawn|drop_location|custom_lobby|protector|obby_|explosive_paint|mailbox|redstone_lamp|moonstone_explosive|texture$)", "plain"),
    (r"(glass|^ice$|melting_ice|^net$|cobweb)", "glass"),
    (r"(^leaves_|fallen_|berry_bush|spectral_grass)", "leaf"),
    (r"(allium|azure|orchid|cornflower|dandelion|lily|oxeye|tulip|rose|catnip|fern|tall_?grass|jungle_tall|pine_grass$|^(brown|red)_mushroom$|mushroom_stem|wheat_|rice_|corn_stage|cotton_plant|_stem|^melon_stem|small_cactus|attached_)", "plant"),
    (r"(grass_block|grass_top|grass_side|pine_grass_block|jungle_grass_block|slab_.*grass)", "grass"),
    (r"(^log_|_log$|^stripped_|hay_block)", "log"),
    (r"(planks|bookshelf|slab_(aspen|cedar|cherry|jungle|mango|palm|pear|pine|plum|spectral)_side)", "planks"),
    (r"(^snow|packed_snow)", "snow"),
    (r"(^sand$|red_sand$)", "sand"),
    (r"(dirt|farmland|^clay$|hardened_clay|gravel)", "soil"),
    (r"(coal_block|iron_block|gold_block|diamond_block|emerald_block|lapis_block|moonstone_block|quartz)", "metal"),
    (r"(stone|brick|cobble|andesite|diorite|granite|bedrock|obsidian|netherrack|end_stone|_ore$|sandstone|carved|chiseled|messy|green_stone|^net)", "stone"),
    (r"(wool|leather)", "wool"),
    (r"(glazed_terracotta)", "clay"),
    (r"(^chalk)", "chalk"),
    (r"(concrete)", "concrete"),
]


# 縁を回り込ませて補間してよい(= 並べて継ぎ目が出ないはずの)種類。本棚・看板のような、1 枚で完結する絵や、植物・ガラスは、回り込ませない。
TILEABLE = {"stone", "ore", "soil", "sand", "snow", "grass", "leaf", "wool", "concrete", "metal", "log", "planks", "chalk"}


def classify(name):
    for pat, cls in RULES:
        if re.search(pat, name):
            return cls
    return "plain"


# 種類ごとの細部のパラメータ。amp は、明るさに掛ける振れ幅(0.05 = ±5%)。
#   fine = 細かい粒 / mid = 中くらいのむら / streak = 筋(向き: v = 縦, h = 横) / crack = ひび割れ(ボロノイの境界) / cells = 細胞状の模様
PARAMS = {
    "stone":    dict(fine=0.055, mid=0.060, crack=0.20, cracks_k=5, emboss=1.0),
    "ore":      dict(fine=0.045, mid=0.050, crack=0.08, cracks_k=4, emboss=0.8),
    "soil":     dict(fine=0.075, mid=0.060, specks=0.10, emboss=0.8),
    "sand":     dict(fine=0.055, mid=0.035, emboss=0.6),
    "snow":     dict(fine=0.030, mid=0.030, emboss=0.5),
    "grass":    dict(fine=0.060, mid=0.050, streak=0.10, streak_dir="v", emboss=0.7),
    "leaf":     dict(fine=0.075, mid=0.075, cells=0.11, cells_k=9, emboss=0.8),
    "log":      dict(fine=0.040, streak=0.11, streak_dir="v", emboss=0.9),
    "planks":   dict(fine=0.035, streak=0.08, streak_dir="h", emboss=0.9),
    "wool":     dict(fine=0.040, mid=0.025, weave=0.075, emboss=0.6),
    "concrete": dict(fine=0.035, mid=0.030, pores=0.14, emboss=0.6),
    "metal":    dict(fine=0.020, streak=0.03, streak_dir="v", emboss=0.7),
    "plant":    dict(fine=0.035, mid=0.040, emboss=0.6),
    "clay":     dict(fine=0.030, gloss=0.10, crack=0.10, cracks_k=4, emboss=0.7),
    "chalk":    dict(fine=0.050, pores=0.10, mid=0.030, emboss=0.6),
    "plain":    dict(fine=0.045, mid=0.030, emboss=0.8),
    "glass":    dict(),
    "liquid":   dict(),
    # アイテム(3D モデルに埋め込まれた小さな画像)用。色の見本のような画像が多いので、細かく、控えめに。
    "item_metal": dict(fine=0.030, streak=0.045, streak_dir="v"),
    "item_wood":  dict(fine=0.035, streak=0.07, streak_dir="v"),
    "item_plain": dict(fine=0.030, mid=0.020),
    # mob・プレイヤー・装備・マントの皮(アトラス)。UV で貼られた絵なので、絵柄は変えず、ごく細かな粒だけ。
    "skin":     dict(fine=0.050, mid=0.040, fur=0.090, emboss=1.2),
}


# ───── 周期的ノイズ(タイルしても継ぎ目が出ない) ─────
def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def tile_noise(h, w, cells_y, cells_x, rng):
    cells_y = max(1, int(cells_y))
    cells_x = max(1, int(cells_x))
    g = rng.random((cells_y, cells_x)).astype(np.float32)
    ys = np.arange(h) * cells_y / h
    xs = np.arange(w) * cells_x / w
    y0 = np.floor(ys).astype(int)
    x0 = np.floor(xs).astype(int)
    fy = _smooth(ys - y0)[:, None].astype(np.float32)
    fx = _smooth(xs - x0)[None, :].astype(np.float32)
    y1 = (y0 + 1) % cells_y
    x1 = (x0 + 1) % cells_x
    y0 %= cells_y
    x0 %= cells_x
    a = g[y0][:, x0]
    b = g[y0][:, x1]
    c = g[y1][:, x0]
    d = g[y1][:, x1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(h, w, base_cells, octaves, rng):
    out = np.zeros((h, w), np.float32)
    amp, total, cells = 1.0, 0.0, base_cells
    for _ in range(octaves):
        out += amp * tile_noise(h, w, cells, cells, rng)
        total += amp
        amp *= 0.5
        cells *= 2
    return out / total


def voronoi_edge(h, w, k, rng):
    """周期的なボロノイ図の、境界までの近さ(境界で 0、細胞の中心で大きい)。"""
    pts = rng.random((k, 2)).astype(np.float32) * np.array([h, w], np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    dists = []
    for oy in (-h, 0, h):
        for ox in (-w, 0, w):
            for py, px in pts:
                dists.append(np.sqrt((yy - (py + oy)) ** 2 + (xx - (px + ox)) ** 2))
    d = np.sort(np.stack(dists, 0), axis=0)
    return (d[1] - d[0]) / (0.5 * (h + w) / np.sqrt(k))


# ───── 画像の道具 ─────
def luma(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def resize_plane(p, scale, wrap):
    pad = 2
    pp = np.pad(p, pad, mode="wrap" if wrap else "edge")
    im = Image.fromarray(pp.astype(np.float32), mode="F")
    im = im.resize((pp.shape[1] * scale, pp.shape[0] * scale), Image.BICUBIC)
    a = np.asarray(im, dtype=np.float32)
    return a[pad * scale:-pad * scale, pad * scale:-pad * scale]


def local_minmax(img, wrap):
    """各チャンネルの、周囲 3x3 の最小・最大(img: HxWxC)。"""
    h, w = img.shape[:2]
    p = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode="wrap" if wrap else "edge")
    stack = np.stack([p[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)], 0)
    return stack.min(0), stack.max(0)


def blur(p, sigma, wrap):
    r = max(1, int(sigma * 3))
    xs = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-(xs ** 2) / (2 * sigma * sigma))
    k /= k.sum()
    mode = "wrap" if wrap else "edge"
    q = np.pad(p, ((0, 0), (r, r)), mode=mode)
    q = sum(k[i] * q[:, i:i + p.shape[1]] for i in range(len(k)))
    q = np.pad(q, ((r, r), (0, 0)), mode=mode)
    q = sum(k[i] * q[i:i + p.shape[0], :] for i in range(len(k)))
    return q


def gradient_mag(p):
    gy, gx = np.gradient(p)
    return np.sqrt(gx * gx + gy * gy)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ───── 1 枚(1 フレーム)の加工 ─────
def process_frame(arr, name, cls, scale, rng, tile=True, crisp=False, sigma=None):
    """arr: HxWx4 の float32(0〜1)。返り値: (H*scale)x(W*scale)x4。"""
    h, w = arr.shape[:2]
    H, W = h * scale, w * scale
    alpha = arr[..., 3]
    has_alpha = alpha.min() < 0.999
    wrap = tile and not has_alpha  # 不透明なブロックの素材は、タイルするので、縁を回り込ませて補間する(アイテムの画像は、しない)

    # 1. 拡大(透明部分の色が混ざらないよう、アルファを掛けてから拡大する)
    # 拡大は、「ドットをそのまま拡大 → 軽くぼかす」方式。元の絵柄の輪郭と色(2 トーンの陰影・鉱石の粒)を保ったまま、
    # 角だけが丸くなる。滑らかな補間(バイキュービック)は、粒の周りに色が移るので、使わない。
    pre = arr[..., :3] * alpha[..., None]

    def nearest_up(p):
        return np.repeat(np.repeat(p, scale, 0), scale, 1)

    sig_up = sigma if sigma is not None else max(0.45, scale * 0.06)  # ごく弱いぼかし(ギザギザを消す程度)。強いと、ぼんやりする
    if crisp:
        # 色見本(パレット)の画像用: 色の境目を、ぼかさない(各面が、見本の 1 色を指しているので、色が混ざると、変な色になる)。
        up_pre = np.stack([nearest_up(pre[..., c]) for c in range(3)], -1)
        up_a = nearest_up(alpha)
    else:
        up_pre = np.stack([blur(nearest_up(pre[..., c]), sig_up, wrap) for c in range(3)], -1)
        up_a = np.clip(blur(nearest_up(alpha), sig_up, wrap), 0.0, 1.0)
    soft = ((alpha > 0.05) & (alpha < 0.95)).mean() > 0.25  # 半透明の素材(ガラス・氷など)
    if has_alpha and not soft:
        out_a = (up_a > 0.5).astype(np.float32)  # くっきりした輪郭(葉・植物など)
    else:
        out_a = up_a
    rgb = np.where(up_a[..., None] > 0.02, up_pre / np.maximum(up_a[..., None], 0.02), 0.0)
    rgb = np.clip(rgb, 0.0, 1.0)

    # 2. 輪郭を少し締める(アンシャープ)
    if SHARPEN > 0 and cls not in ("liquid",) and not crisp:
        # 明るさだけを締める(3 チャンネルに同じ量を足す)ので、色が隣に移らない。
        lum0 = luma(rgb)
        d = (lum0 - blur(lum0, max(0.8, scale * 0.30), wrap)) * SHARPEN
        rgb = np.clip(rgb + d[..., None], 0.0, 1.0)

    # 3. 細部を足す
    prm = PARAMS.get(cls, {})
    if prm and DETAIL > 0:
        lum = luma(rgb)
        # 元の絵柄の輪郭(鉱石の粒、レンガの目地)の近くは、細部を弱める。
        edge = smoothstep(0.04, 0.18, blur(gradient_mag(lum) * scale, 1.0, wrap))
        weight = (0.45 + 0.55 * (1.0 - edge)) * DETAIL
        mod = np.zeros((H, W), np.float32)
        if "fine" in prm:
            mod += prm["fine"] * (tile_noise(H, W, H // 2, W // 2, rng) - 0.5) * 2.0
        if "mid" in prm:
            mod += prm["mid"] * MID_SCALE * (fbm(H, W, max(2, H // 8), 3, rng) - 0.5) * 2.0
        if "streak" in prm:
            along = H // 16 + 1
            across = W // 2
            if prm.get("streak_dir") == "v":
                n = tile_noise(H, W, max(1, H // 16), across, rng)
            else:
                n = tile_noise(H, W, across, max(1, W // 16), rng)
            mod += prm["streak"] * (n - 0.5) * 2.0
        if "crack" in prm:
            ve = voronoi_edge(H, W, prm.get("cracks_k", 5), rng)
            gate = smoothstep(0.50, 0.72, fbm(H, W, max(2, H // 8), 2, rng))  # ひび割れは、ところどころだけ
            line = 1.0 - smoothstep(0.0, 0.10, ve)
            mod -= prm["crack"] * line * gate
        if "cells" in prm:
            ve = voronoi_edge(H, W, prm.get("cells_k", 9), rng)
            mod -= prm["cells"] * (1.0 - smoothstep(0.0, 0.22, ve))
        if "weave" in prm:
            # 織り目: 縦糸と横糸が交互に浮き沈みする格子 + 糸 1 本ごとのむら
            period = max(3.0, H / 12.0)
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            cx = np.sin(xx / period * np.pi * 2) * 0.5 + 0.5
            cy = np.sin(yy / period * np.pi * 2) * 0.5 + 0.5
            over = ((np.floor(xx / (period / 2)) + np.floor(yy / (period / 2))) % 2) < 1
            thread = np.where(over, cx, cy)
            mod += prm["weave"] * (thread - 0.5) * 2.0
            mod += prm["weave"] * 0.6 * (tile_noise(H, W, max(1, int(H / (period / 2))), max(1, int(W / (period / 2))), rng) - 0.5) * 2.0
        if "pores" in prm:
            # 気孔: 小さな暗いくぼみ(ぽつぽつ)と、ごく薄い色むら
            pn = tile_noise(H, W, H // 2, W // 2, rng)
            pit = smoothstep(0.86, 0.97, pn)
            mod -= prm["pores"] * pit
            mod += prm["pores"] * 0.25 * (tile_noise(H, W, max(2, H // 6), max(2, W // 6), rng) - 0.5) * 2.0
        if "gloss" in prm:
            # 釉薬の光沢: 斜めの柔らかい明るい帯
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            band = np.exp(-(((xx + yy) / (H + W) - 0.42) / 0.16) ** 2)
            mod += prm["gloss"] * (band - 0.35)
        if "fur" in prm:
            # 毛並み: 斜めの細い筋(2 方向を重ねる)
            a = tile_noise(H, W, max(2, H // 3), max(2, W // 14), rng)
            b = tile_noise(H, W, max(2, H // 14), max(2, W // 3), rng)
            mod += prm["fur"] * ((a - 0.5) + (b - 0.5))
        if "specks" in prm:
            sp = tile_noise(H, W, H, W, rng)
            mod += prm["specks"] * (smoothstep(0.88, 0.97, sp) - smoothstep(0.88, 0.97, 1.0 - sp))
        rgb = np.clip(rgb * (1.0 + mod * weight)[..., None], 0.0, 1.0)

    # 3b. 焼き込みの陰影: 明るさを「高さ」と見立てて、左上からの光で、凹凸の陰影と、くぼみの暗さを、画像そのものに焼き込む。
    #     シェーダーは、一部のゲームでしか効かないので、テクスチャ単体で、立体感が出るようにする。
    emb = prm.get("emboss", 0.0) * EMBOSS
    if emb > 0 and cls not in ("liquid", "glass"):
        lum1 = luma(rgb)
        hl = blur(lum1, max(1.0, scale * 0.55), wrap)
        gy, gx = np.gradient(hl)
        light = np.clip(0.6 * (gx + gy) * scale * 1.6 * emb, -0.30, 0.30)
        cav = np.clip(blur(lum1, max(2.0, scale * 2.2), wrap) - lum1, 0.0, 0.25) * 1.4 * emb
        rgb = np.clip(rgb * (1.0 + light - cav)[..., None], 0.0, 1.0)

    # 4. 色の仕上げ
    l = luma(rgb)[..., None]
    rgb = l + (rgb - l) * SATURATION
    rgb = (rgb - 0.5) * CONTRAST + 0.5
    rgb = np.clip(rgb, 0.0, 1.0)
    return np.concatenate([rgb, out_a[..., None]], -1)


def process_file(path, scale, skin_target=None):
    name = os.path.splitext(os.path.basename(path))[0]
    im = Image.open(path).convert("RGBA")
    arr = np.asarray(im, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]
    if skin_target:
        # 皮: 元の絵の大きさに応じて、短いほうの辺が skin_target 以上になる倍率(切り上げ)。ぼかさず、元のドットを保つ。
        scale = max(1, -(-skin_target // min(h, w)))
        cls = "skin"
    else:
        # 元が 16x16 のものは、倍率を半分にして、出力の大きさ(8 x 倍率)を、全部そろえる(アトラスは、全部同じ大きさで扱われる)。
        scale = max(1, (8 * scale) // min(h, w))
        cls = classify(name)
    if cls == "stone" and name.endswith("_ore"):
        cls = "ore"  # 鉱石: 粒の絵柄を主役にするので、ひび割れは弱める
    tile = cls in TILEABLE and "bookshelf" not in name and "mailbox" not in name
    crisp = bool(skin_target)  # 皮は、ぼかさない(ぼかすと、ぼやける)。ドットの輪郭を保つ
    sigma = None
    rng = np.random.default_rng(seed_for(name))
    # 縦に連なったアニメーション(フレームが正方形で縦に並ぶ)は、フレームごとに拡大する。細部のノイズは、全フレームで同じ。
    if not skin_target and h > w and h % w == 0:
        frames = []
        for i in range(h // w):
            fr_rng = np.random.default_rng(seed_for(name))
            frames.append(process_frame(arr[i * w:(i + 1) * w], name, cls, scale, fr_rng, tile=tile))
        out = np.concatenate(frames, 0)
    elif not skin_target and w > h and w % h == 0:
        frames = []
        for i in range(w // h):
            fr_rng = np.random.default_rng(seed_for(name))
            frames.append(process_frame(arr[:, i * h:(i + 1) * h], name, cls, scale, fr_rng, tile=tile))
        out = np.concatenate(frames, 1)
    else:
        out = process_frame(arr, name, cls, scale, rng, tile=tile, crisp=crisp, sigma=sigma)
    return name, cls, Image.fromarray((np.clip(out, 0, 1) * 255.0 + 0.5).astype(np.uint8), "RGBA")


def make_preview(src, out_dir, names, scale, path):
    tiles = []
    for n in names:
        sp = os.path.join(src, n + ".png")
        op = os.path.join(out_dir, "textures", n + ".png")
        if not (os.path.exists(sp) and os.path.exists(op)):
            continue
        a = Image.open(sp).convert("RGBA")
        b = Image.open(op).convert("RGBA")
        cell = 8 * scale * 2  # 見やすいよう、さらに 2 倍に
        # 3x3 でタイルして、継ぎ目も見えるようにする
        def tile(im, size):
            t = Image.new("RGBA", (size * 2, size * 2), (60, 60, 70, 255))
            r = im.resize((size, size), Image.NEAREST if im.size[0] < size else Image.LANCZOS)
            bg = Image.new("RGBA", (size, size), (60, 60, 70, 255))
            bg.alpha_composite(r)
            for yy in range(2):
                for xx in range(2):
                    t.paste(bg, (xx * size, yy * size))
            return t
        ta, tb = tile(a, cell), tile(b, cell)
        pair = Image.new("RGBA", (cell * 4 + 6, cell * 2), (20, 20, 24, 255))
        pair.paste(ta, (0, 0))
        pair.paste(tb, (cell * 2 + 6, 0))
        tiles.append(pair)
    if not tiles:
        return
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    tw, th = tiles[0].size
    sheet = Image.new("RGBA", (tw * cols + 10 * (cols - 1), th * rows + 10 * (rows - 1)), (20, 20, 24, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * (tw + 10), (i // cols) * (th + 10)))
    sheet.convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="default2/textures のフォルダ")
    ap.add_argument("--out", required=True, help="出力先のパックのフォルダ(中に textures/ を作る)")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--extra-src", default=None, help="default/textures のフォルダ。--src に無い 8x8 / 16x16 のブロックの素材(ドア・苗・ポータルなど)も、加える")
    ap.add_argument("--preview", default=None, help="比較画像(左 = 元、右 = 加工後。2x2 でタイル)の出力先")
    args = ap.parse_args()

    out_tex = os.path.join(args.out, "textures")
    os.makedirs(out_tex, exist_ok=True)
    jobs = [os.path.join(args.src, f) for f in sorted(os.listdir(args.src)) if f.lower().endswith(".png")]
    if args.extra_src:
        done = {os.path.basename(p) for p in jobs}
        for f in sorted(os.listdir(args.extra_src)):
            if not f.lower().endswith(".png") or f in done or "_Atlas" in f:
                continue
            w, h = Image.open(os.path.join(args.extra_src, f)).size
            # ブロックの素材だけ(8x8 / 16x16、または、縦に連なったアニメーション)。10x10 の効果アイコンや、mob のスキンは、除く。
            if (w, h) in ((8, 8), (16, 16)) or (w == 8 and h % 8 == 0):
                jobs.append(os.path.join(args.extra_src, f))
    files = jobs
    counts = {}
    for p in files:
        name, cls, img = process_file(p, args.scale)
        img.save(os.path.join(out_tex, name + ".png"), optimize=True)
        counts[cls] = counts.get(cls, 0) + 1
    print(f"{len(files)} 枚を {args.scale} 倍にして書き出した → {out_tex}")
    print("種類の内訳:", ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
    if args.preview:
        names = ["stone", "cobblestone_mossy", "dirt", "grass_block_side", "grass_top", "sand", "planks_pine", "log_pine",
                 "leaves_pine", "coal_ore", "diamond_ore", "gold_ore", "stonebrick", "gravel", "bookshelf", "sandstone_normal",
                 "wool_colored_red", "brick", "dandelion", "tall_grass_bottom", "glass", "lava", "snow", "obsidian"]
        make_preview(args.src, args.out, names, args.scale, args.preview)
        print("比較画像:", args.preview)


if __name__ == "__main__":
    main()
