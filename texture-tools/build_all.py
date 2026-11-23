#!/usr/bin/env python3
"""ゲームの「今の」素材を全部、リアルで精細にして、1 つのテクスチャパックのフォルダにまとめる。

入力(どれも、公式の最新。このフォルダには置かない):
  --default2  公式リポジトリ(https://github.com/Bloxdy/texturePacks)の default2/textures(ゲームが読み込む default2.json と同一)
  --media     ゲームのクライアントに組み込まれた画像(https://bloxd.io/static/media/…png)を取得したフォルダ。
              ブロックの素材(default2 に無い分: ドア・チェスト・はしご・苗・機械…)と、mob・プレイヤー・装備・マントの皮がある。
  --models    最新のモデル(GLB)のフォルダ(複数可)。ブロック用(bloxd.io/static/media/…glb)と、アイテム・防具用(static1.bloxd.io/models/…glb)。
  --catalogue クライアントから取り出した、モデルの目録(block / static / lifeform の名前)。
出力: <out>/textures/*.png と <out>/models/*.glb

  python tools/build_all.py --default2 … --media … --models … … --catalogue … --out GoldenHour-Textures-64-All
"""
import argparse
import json
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_textures as gt  # noqa: E402
import gen_items as gi  # noqa: E402
import gen_icons as gic  # noqa: E402

# ブロックの素材ではない画像(パーティクル・画面の部品など)。処理しない。
NOT_BLOCK = {"bubble", "critical_hit", "drift", "effect_5", "generic_2", "glint", "heart", "scary_face", "soul_0",
             "square_particle", "textureNotFound", "Question Mark"}
NOT_BLOCK_RE = re.compile(r"^destroy_stage_")
SKIN_RE = re.compile(r"(Atlas|_attachable|^cape_|Armour|^\d+_)")


def to_img(a):
    import numpy as np
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")


def is_blocklike(w, h):
    return (w, h) in ((8, 8), (16, 16)) or (w == 8 and h % 8 == 0) or (w == 16 and h % 16 == 0 and h > 16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--default2", required=True)
    ap.add_argument("--media", required=True)
    ap.add_argument("--models", required=True, nargs="+")
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=8, help="ブロックの素材の倍率(8 → 64x64)")
    ap.add_argument("--skin-size", type=int, default=256, help="皮の短いほうの辺の、最小の大きさ")
    ap.add_argument("--model-size", type=int, default=64, help="モデルの埋め込み画像の、最小の大きさ")
    ap.add_argument("--no-skins", action="store_true")
    ap.add_argument("--no-icons", action="store_true", help="アイテムのアイコンを、描き直さない")
    ap.add_argument("--only-icons-armour", action="store_true", help="アイコンと防具だけ(他は、そのまま)作り直す。モデルも、触らない")
    ap.add_argument("--icon-size", type=int, default=80, help="アイコンの大きさ(10x10 の元は、8 倍の 80x80)")
    ap.add_argument("--no-models", action="store_true", help="モデル(アイテム・防具など)を含めない。ブロックの素材だけの、軽いパックにする")
    args = ap.parse_args()

    tex = os.path.join(args.out, "textures")
    os.makedirs(tex, exist_ok=True)
    done = set()
    counts = {"block": 0, "block_media": 0, "skin": 0}

    # 1. ブロックの素材(default2)
    for f in ([] if args.only_icons_armour else sorted(os.listdir(args.default2))):
        if not f.lower().endswith(".png"):
            continue
        name, cls, img = gt.process_file(os.path.join(args.default2, f), args.scale)
        if cls == "plant":
            # 植物: 形(隙間・切れ込み)を保つ専用の描き方(葉脈・繊維・小さな丸み・弱いつや)
            img = to_img(gic.render_plant(gic.load(os.path.join(args.default2, f)), args.scale * 8, seed=gt.seed_for(name) & 0xFFFF))
        img.save(os.path.join(tex, name + ".png"), optimize=True)
        done.add(name)
        counts["block"] += 1

    # 2. ブロックの素材(ゲームに組み込まれた、default2 に無い分)と、3. 皮
    for f in sorted(os.listdir(args.media)):
        if not f.lower().endswith(".png"):
            continue
        name = os.path.splitext(f)[0]
        if name in done:
            continue
        path = os.path.join(args.media, f)
        try:
            w, h = Image.open(path).size
        except Exception:
            continue
        low = name.lower()
        if re.search(r"armou?r(_\d+)?$", low) and min(w, h) >= 32:
            # 着る防具の展開図: 金属の質感(ぼかさない)
            if args.no_skins:
                continue
            n = name
            img = to_img(gic.render_armour(gic.load(path), 1))  # 元の大きさのまま(ゲームが、防具のアトラスを、この画像から組み立てる)
            counts["armour"] = counts.get("armour", 0) + 1
        elif args.only_icons_armour and not (max(w, h) <= 24 and not is_blocklike(w, h)):
            continue
        elif is_blocklike(w, h) and name not in NOT_BLOCK and not NOT_BLOCK_RE.match(name):
            n, cls, img = gt.process_file(path, args.scale)
            if cls == "plant":
                img = to_img(gic.render_plant(gic.load(path), args.scale * 8, seed=gt.seed_for(n) & 0xFFFF))
            counts["block_media"] += 1
        elif max(w, h) <= 24 and name not in NOT_BLOCK:
            # アイテムのアイコン(10x10 など): 別の表現(丸みのある立体の陰影・つや・素材の模様)で、描き直す
            if args.no_icons:
                continue
            n = name
            img = to_img(gic.render_icon_crisp(gic.load(path), args.icon_size, seed=gt.seed_for(name) & 0xFFFF))
            counts["icon"] = counts.get("icon", 0) + 1
        elif min(w, h) >= 32:
            if args.no_skins:
                continue
            n, cls, img = gt.process_file(path, args.scale, skin_target=args.skin_size)
            counts["skin"] += 1
        else:
            continue
        img.save(os.path.join(tex, n + ".png"), optimize=True)
        done.add(n)
    print("素材:", counts, "合計", len(done), "枚")

    # 4. モデル
    if args.no_models or args.only_icons_armour:
        return
    cat = json.load(open(args.catalogue, encoding="utf-8"))
    # ブロック用とアイテム用で、同じ名前のモデルが、ある(たとえば、置いたドアと、アイテムのドア)。パックは、名前で上書きするので、
    # どちらか片方の形で、もう片方を上書きしてしまい、形が壊れる(ドア・ベッドで確認)。名前が重なるものは、上書きしない。
    block_names = set(cat.get("block", []))
    static_names = set(cat.get("static", []))
    clash = block_names & static_names
    allowed = (block_names | static_names) - clash
    print(f"名前が重なる(上書きしない)モデル: {len(clash)} 個")
    out_models = os.path.join(args.out, "models")
    os.makedirs(out_models, exist_ok=True)
    changed = same = bad = 0
    seen = set()
    for src in args.models:
        for f in sorted(os.listdir(src)):
            if not f.lower().endswith(".glb") or f in seen or f[:-4] not in allowed:
                continue
            seen.add(f)
            try:
                if gi.process_model(os.path.join(src, f), os.path.join(out_models, f), args.model_size):
                    changed += 1
                else:
                    same += 1
            except Exception as e:
                bad += 1
                print("失敗:", f, e)
    mb = sum(os.path.getsize(os.path.join(out_models, x)) for x in os.listdir(out_models)) / 1048576
    print(f"モデル: {changed} 個の画像を差し替え(そのまま {same}、失敗 {bad})。{mb:.1f} MB")


if __name__ == "__main__":
    main()
