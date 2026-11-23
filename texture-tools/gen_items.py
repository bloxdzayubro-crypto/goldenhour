#!/usr/bin/env python3
"""アイテムの 3D モデル(GLB)に埋め込まれた小さな画像を、gen_textures.py と同じ手法で精細にして、差し替える。

使い方:
  python tools/gen_items.py --src <default/models のフォルダ> --out <パックのフォルダ> [--size 32]

- 元は、公式リポジトリ https://github.com/Bloxdy/texturePacks の default/models(このフォルダには、公式の素材は、置かない)。
- 形(頂点・UV)は、いじらない。モデルの中の 8x8 / 16x16 の画像だけを、--size x --size に拡大して細部を足す
  (UV は 0〜1 の割合なので、画像を大きくしても、貼り方は、変わらない)。
  それより大きい画像(32 以上)、色の対応表(256x1)、画像が無いモデルは、そのまま(出力もしない)。
- 出力: <out>/models/<元と同じ名前>.glb(画像を差し替えたものだけ)
"""
import argparse
import io
import json
import os
import re
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_textures as gt  # noqa: E402


def read_glb(path):
    b = open(path, "rb").read()
    magic, ver, length = struct.unpack("<4sII", b[:12])
    if magic != b"glTF":
        raise ValueError("not a GLB")
    off, js, binc = 12, None, b""
    while off < len(b):
        cl, ct = struct.unpack("<I4s", b[off:off + 8])
        data = b[off + 8:off + 8 + cl]
        if ct == b"JSON":
            js = json.loads(data.decode("utf-8"))
        elif ct.startswith(b"BIN"):
            binc = data
        off += 8 + cl
    return js, binc


def write_glb(path, js, binc):
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    binc = binc + b"\0" * ((4 - len(binc) % 4) % 4)
    total = 12 + 8 + len(jb) + (8 + len(binc) if binc else 0)
    out = struct.pack("<4sII", b"glTF", 2, total)
    out += struct.pack("<I4s", len(jb), b"JSON") + jb
    if binc:
        out += struct.pack("<I4s", len(binc), b"BIN\0") + binc
    open(path, "wb").write(out)


def item_class(name):
    n = name.lower()
    if re.search(r"(sword|axe|pickaxe|shovel|hoe|ingot|helmet|chestplate|leggings|boots|gauntlet|armou?r|shield|bucket|shears|rod|hammer|dagger|spear|knife|gun|rifle|pistol|ak-47|awp|dmr|fmr|gpmg|deagle|bomb|grenade|rocket)", n):
        return "item_metal"
    if re.search(r"(stick|bow|wood|plank|log|crossbow|torch|ladder|door|chest|barrel|sign|bed|table|fence|crate|bench|pedestal|furnace|workbench|shelf)", n):
        return "item_wood"
    return "item_plain"


def enhance_png(data, key, cls, target, force_opaque=False):
    """埋め込み画像を、target 以上の大きさに(元が小さい場合)拡大して、細部を足す。大きい画像(target 以上)は、大きさを変えず、細部と色の仕上げだけ。"""
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    w, h = im.size
    arr = np.asarray(im, dtype=np.float32) / 255.0
    if force_opaque:
        # 材質が「不透明」のモデルは、画像の透明度を使わない(透明度が 0 のまま、色だけが入っている画像が多い)。
        # 透明として扱うと、色が黒くなって、絵が壊れる(ドア・ベッドで確認)。
        arr[..., 3] = 1.0
    m = min(w, h)
    scale = max(1, -(-target // m))  # 切り上げ(10x10 → 7 倍 = 70x70)
    rng = np.random.default_rng(gt.seed_for(key))
    # 倍率 1(元から大きい画像)は、ぼかさず・締めず、細部と色の仕上げだけ。小さい画像は、色の境目をぼかさない拡大(色見本・小さな絵の両方に安全)。
    out = gt.process_frame(arr, key, cls, scale, rng, tile=False, crisp=True)
    img = Image.fromarray((np.clip(out, 0, 1) * 255.0 + 0.5).astype(np.uint8), "RGBA")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def process_model(src_path, dst_path, target):
    js, binc = read_glb(src_path)
    imgs = js.get("images", [])
    name = os.path.splitext(os.path.basename(src_path))[0]
    cls = item_class(name)
    new_data = {}
    # 画像ごとに、それを使う材質の alphaMode を調べる(既定は OPAQUE)。
    tex_src = {i: tx.get("source") for i, tx in enumerate(js.get("textures", []))}
    modes = {}
    for mat in js.get("materials", []):
        bt = mat.get("pbrMetallicRoughness", {}).get("baseColorTexture")
        if bt is not None:
            modes.setdefault(tex_src.get(bt.get("index")), set()).add(mat.get("alphaMode", "OPAQUE"))
    for i, im in enumerate(imgs):
        if "bufferView" not in im:
            continue
        bv = js["bufferViews"][im["bufferView"]]
        raw = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        try:
            pil = Image.open(io.BytesIO(raw))
        except Exception:
            continue
        w, h = pil.size
        # 処理しないもの: 色の対応表(256x1 など、幅だけの帯)、1 ピクセルの画像、巨大な画像。
        if min(w, h) <= 1 or max(w, h) > 512:
            continue
        new_data[im["bufferView"]] = enhance_png(raw, f"{name}#{i}", cls, target, force_opaque=(modes.get(i) == {"OPAQUE"}))
    if not new_data:
        return False
    # すべての bufferView を、並べ直す(4 バイト境界)。差し替えた画像だけ、中身が変わる。
    chunks = []
    pos = 0
    for idx, bv in enumerate(js["bufferViews"]):
        data = new_data.get(idx)
        if data is None:
            data = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        pad = (4 - pos % 4) % 4
        chunks.append(b"\0" * pad)
        pos += pad
        bv["byteOffset"] = pos
        bv["byteLength"] = len(data)
        chunks.append(data)
        pos += len(data)
    js["buffers"][0]["byteLength"] = pos
    js["buffers"][0].pop("uri", None)
    write_glb(dst_path, js, b"".join(chunks))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, nargs="+", help="モデル(GLB)のフォルダ。複数可(最新のモデルを取得した、ブロック用・静的用のフォルダ)")
    ap.add_argument("--catalogue", default=None, help="目録(catalogue.json)。あれば、その block / static の名前のモデルだけを処理する(生き物のモデルは、パックで差し替えられない)")
    ap.add_argument("--out", required=True, help="パックのフォルダ(中に models/ を作る)")
    ap.add_argument("--size", type=int, default=32, help="埋め込み画像の出力の大きさ(既定 32)")
    args = ap.parse_args()
    out_dir = os.path.join(args.out, "models")
    os.makedirs(out_dir, exist_ok=True)
    allowed = None
    if args.catalogue:
        cat = json.load(open(args.catalogue, encoding="utf-8"))
        allowed = set(cat.get("block", [])) | set(cat.get("static", []))
    done = skipped = bad = excluded = 0
    total = 0
    seen = set()
    for src in args.src:
        for f in sorted(os.listdir(src)):
            if not f.lower().endswith(".glb") or f in seen:
                continue
            name = f[:-4]
            if allowed is not None and name not in allowed:
                excluded += 1
                continue
            seen.add(f)
            total += 1
            try:
                if process_model(os.path.join(src, f), os.path.join(out_dir, f), args.size):
                    done += 1
                else:
                    skipped += 1
            except Exception as e:  # 1 つ壊れても、全体は止めない
                bad += 1
                print("失敗:", f, e)
    print(f"対象外(目録に無い・生き物など) {excluded}")
    mb = sum(os.path.getsize(os.path.join(out_dir, x)) for x in os.listdir(out_dir)) / 1048576
    print(f"モデル {total} 個のうち、{done} 個の画像を差し替えた(そのまま {skipped}、失敗 {bad})。出力 {mb:.1f} MB → {out_dir}")


if __name__ == "__main__":
    main()
