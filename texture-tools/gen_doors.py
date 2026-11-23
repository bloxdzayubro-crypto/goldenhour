#!/usr/bin/env python3
"""ドア・トラップドアなど(8x8 の、穴あきの板の絵)を、木目・板の継ぎ目・節・面取り・くぼみの影・釘で、リアルに描き直す。
ドットの形(穴の位置・色の塊)は保つ(ぼかさない)。穴(透明)は、そのまま。 平均の色は、元に合わせる(明るさが、ずれないように)。
使い方: python gen_doors.py <入力フォルダ(複数可)> --out <テクスチャのフォルダ>"""
import os, re, sys, argparse
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_textures as gt  # noqa: E402
import gen_icons as gic  # noqa: E402

DOOR_RE = re.compile(r"(_door_(top|bottom)|_trapdoor)$|^iron_trapdoor$|_door_(top|bottom)$")


def render_door(arr, target=64, name="door"):
    h, w = arr.shape[:2]
    s = max(1, target // max(h, w))
    H, W = h * s, w * s
    rng = np.random.default_rng(gt.seed_for(name) & 0xFFFF)
    A = np.repeat(np.repeat((arr[..., 3] > 0.5).astype(np.float32), s, 0), s, 1)
    col = np.repeat(np.repeat(arr[..., :3], s, 0), s, 1).astype(np.float32)
    mx, mn = col.max(-1), col.min(-1)
    metal = float(np.mean(((mx - mn) / np.maximum(mx, 1e-3))[A > 0.5] < 0.16)) > 0.5 if (A > 0.5).any() else False
    trap = "trapdoor" in name
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lum = gic.luma(col)
    # 色の塊の内側だけ、なめらかに(境目は保つ)
    col = gic.bilateral(col, max(1.2, s * 0.35), 0.08, max(2, int(s * 0.7)))

    # --- 高さ: 色の明暗の境目 + 形の縁(穴の周り) ---
    Hgt = 0.9 * gt.blur(A, s * 0.30, False) + 0.8 * gt.blur(lum, s * 0.30, False)
    gy, gx = np.gradient(Hgt)
    K = s * 1.9
    nx, ny, nz = -gx * K, -gy * K, np.ones_like(gx)
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx * inv, ny * inv, nz * inv
    L = np.array([-0.55, -0.6, 0.58]); L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    nh = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1)

    if not metal:
        # --- 木目: 流れる向き(ドア = 縦、トラップドア = 横)に、ゆがんだ年輪の筋 ---
        along = xx if not trap else yy   # 筋が、この座標で変わる(筋は、もう一方の方向へ伸びる)
        across = yy if not trap else xx
        warp = (gt.tile_noise(H, W, 3, 3, rng) - 0.5) * 18.0 * (s / 8.0)
        warp2 = (gt.tile_noise(H, W, 8, 8, rng) - 0.5) * 3.0 * (s / 8.0)
        rings = np.sin((along + warp) * 0.62 + (across * 0.05)) * 0.5 + 0.5
        fine = np.sin((along + warp * 0.6 + warp2) * 2.3) * 0.5 + 0.5
        streak = gt.tile_noise(H, W, 2 if not trap else 40, 40 if not trap else 2, rng) - 0.5
        grain = (rings - 0.5) * 0.17 + (fine - 0.5) * 0.07 + streak * 0.14
        # --- 板の継ぎ目: 1 枚の板の幅 = 2 ドット。継ぎ目は、暗い線 + 隣に明るい縁 ---
        board = (along // (s * 2)).astype(np.float32)
        bh = np.sin(board * 12.9898 + 4.1) * 43758.5453
        tone = (bh - np.floor(bh) - 0.5) * 0.13  # 板ごとの色の違い
        pos = along % (s * 2)
        seam = np.clip(1.0 - pos / (s * 0.22), 0, 1) * 0.28 + np.clip(1.0 - (s * 2 - pos) / (s * 0.22), 0, 1) * 0.0
        hi = np.clip(1.0 - np.abs(pos - s * 0.34) / (s * 0.18), 0, 1) * 0.06
        # --- 節: 1〜2 個(色の塊の中に、暗い楕円の年輪) ---
        knot = np.zeros((H, W), np.float32)
        for _ in range(int(rng.integers(1, 3))):
            cx, cy = rng.random() * W, rng.random() * H
            r = s * (0.45 + 0.35 * rng.random())
            d = np.sqrt(((xx - cx) / (r * (0.7 if not trap else 1.4))) ** 2 + ((yy - cy) / (r * (1.4 if not trap else 0.7))) ** 2)
            knot += np.clip(1.0 - d, 0, 1) * (0.28 + 0.12 * np.sin(d * 14.0))
        pores = (gt.tile_noise(H, W, H, W, rng) - 0.5) * 0.06
        wood_mod = 1.0 + grain + tone - seam + hi - knot + pores
        out = col * wood_mod[..., None]
        shade = 0.66 + 0.62 * diff
        out = out * shade[..., None]
        out = out + ((nh ** 20.0) * 0.07)[..., None] * np.array([1.0, 0.94, 0.82])
        # --- 釘: 色の塊の角に、小さな暗い釘(頭だけ光る) ---
        # (穴の周りの、色の塊の四隅を、見つける代わりに、固定の格子 4 ドットごとに置く)
        nails = np.zeros((H, W), np.float32)
        spec_n = np.zeros((H, W), np.float32)
        step = s * 4
        for cyy in range(int(s * 0.9), H, step):
            for cxx in (int(s * 0.9), W - int(s * 0.9)):
                d = np.sqrt((xx - cxx) ** 2 + (yy - cyy) ** 2)
                nails += np.clip(1.0 - d / (s * 0.28), 0, 1)
                spec_n += np.clip(1.0 - np.sqrt((xx - cxx + s * 0.1) ** 2 + (yy - cyy + s * 0.1) ** 2) / (s * 0.12), 0, 1)
        if trap:
            nails *= 0.0; spec_n *= 0.0
        out = out * (1.0 - 0.55 * np.clip(nails, 0, 1)[..., None]) + spec_n[..., None] * 0.35
    else:
        # --- 鉄: 研いだ筋 + 継ぎ目 + リベット + 強い反射 ---
        brushed = (gt.tile_noise(H, W, H // 2, 3, rng) - 0.5) * 2.0
        fine = gt.tile_noise(H, W, H // 2, W // 2, rng) - 0.5
        scratch = (gt.tile_noise(H, W, 6, 60, rng) - 0.5)
        mod = 1.0 + brushed * 0.12 + fine * 0.07 + scratch * 0.10
        out = col * mod[..., None] * (0.62 + 0.80 * diff)[..., None]
        out = out + ((nh ** 16.0) * 0.28)[..., None] * np.array([0.95, 1.0, 1.06]) + ((nh ** 4.0) * 0.05)[..., None]
        riv = np.zeros((H, W), np.float32); rhi = np.zeros((H, W), np.float32)
        for cyy in (int(s * 0.9), H - int(s * 0.9)):
            for cxx in (int(s * 0.9), W - int(s * 0.9)):
                d = np.sqrt((xx - cxx) ** 2 + (yy - cyy) ** 2)
                riv += np.clip(1.0 - d / (s * 0.34), 0, 1)
                rhi += np.clip(1.0 - np.sqrt((xx - cxx + s * 0.12) ** 2 + (yy - cyy + s * 0.12) ** 2) / (s * 0.14), 0, 1)
        out = out * (1.0 - 0.35 * np.clip(riv, 0, 1)[..., None]) + rhi[..., None] * 0.45

    # --- 穴の縁のくぼみの影(奥行き) ---
    ao = gt.blur(1.0 - A, s * 0.45, False) * A
    out = out * (1.0 - 0.30 * np.clip(ao * 1.4, 0, 1))[..., None]
    # 彩度・コントラスト
    l2 = gic.luma(out)[..., None]
    out = l2 + (out - l2) * 1.12
    out = (out - 0.5) * 1.10 + 0.5
    # 平均の色を、元に合わせる
    m = A > 0.5
    if m.any():
        om = np.asarray(arr[..., :3], np.float32)[(arr[..., 3] > 0.5)].mean(0)
        nm = np.clip(out, 0, 1)[m].mean(0)
        out = out * (om / np.maximum(nm, 1e-4))
    res = np.concatenate([np.clip(out, 0, 1), A[..., None]], -1)
    res[..., :3] *= (A > 0.5)[..., None]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=64)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    seen = set()
    for d in a.src:
        for f in sorted(os.listdir(d)):
            n, ext = os.path.splitext(f)
            if ext.lower() != ".png" or n in seen or not DOOR_RE.search(n):
                continue
            im = Image.open(os.path.join(d, f)).convert("RGBA")
            if max(im.size) > 16:
                continue
            arr = np.asarray(im, np.float32) / 255.0
            r = render_door(arr, a.size, n)
            Image.fromarray((np.clip(r, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(a.out, n + ".png"), optimize=True)
            seen.add(n)
    print("ドア類:", len(seen), "枚 →", a.out)


if __name__ == "__main__":
    main()
