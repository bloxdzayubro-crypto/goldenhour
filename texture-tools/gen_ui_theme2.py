#!/usr/bin/env python3
"""ゲームの取り込みの制限(pack_css_check.py を参照)の中で、効く形の UI 用 CSS を作る。

  1. 自動の着せ替え: ゲームの CSS(全 48 ファイル)から、「最後が .クラス名 で終わる」規則を拾い(@media・疑似クラス・属性は除く)、
     青系の色 → 金・茶色系に置き換えた宣言を、`.クラス名 { … !important; }` にする。
       - 同じクラスが、文脈によって違う色を持つ場合は、いちばん多い色を採る(取りこぼしを減らす)。
       - 「Body」「Header」のような、どこにでもある名前は、すべての文脈で色が一致するときだけ。
       - 許可されたプロパティ(背景・枠・影・文字色)だけ。 色の変数(--buttonNormalColour など)は、許されていない。
  2. 手書き: hand_rules.css。 自動より、あとに置く(同じクラス・同じプロパティは、手書きが勝つ)。
  3. 顔の画像: PNG を、%XX だけで書いた data: URL にする(`;` と `=` が使えないため、base64 は、使えない)。
使い方: python gen_ui_theme2.py <ゲームの CSS のフォルダ> <face.png> <出力> [--report]"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_ui_theme as g  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GENERIC = set("""Selected Active Disabled Hidden Body Header Footer Container Wrapper Inner Outer Title Text Icon Button Item Row Column Left Right Top Bottom Label Content Panel Card Tab List Input Close Name Background Image Primary Secondary Small Large Medium Open Closed Hover Focus Pressed Visible Show Shown Hide Dark Light Blue Red Green Gold Purple Touch Mobile Desktop Wide Narrow Full Half Center Start End First Last Next Previous Back Main Base Overlay Popup Menu Buttons Section Sections Group Rows Cell Cells Bar Fill Track Thumb Divider Spacer Filler Bubble Message Messages Badge Tag Tags Chip Link Links Page Screen View Views""".split())
PROPS_OK = re.compile(r"^(background(-color|-image)?|border(-(top|right|bottom|left))?(-color)?|box-shadow|outline)$")
LAST_CLASS = re.compile(r"\.([A-Za-z][A-Za-z\d]*)$")
ANY_CLASS = re.compile(r"\.([A-Za-z][A-Za-z\d]*)")
BAD = '$&;<=>?@[\\]^{|}~'


def multi_hue(v):
    """虹色(いろいろな色相が混ざる値)か。青系だけを置き換えると、途中が、茶色に化けるので、そのまま残す。"""
    import colorsys
    bins = set()
    for m in g.HEX.finditer(v):
        t = m.group(1)
        if len(t) in (3, 4):
            t = "".join(c * 2 for c in t)
        r, gg, b = (int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        h, l, sat = colorsys.rgb_to_hls(r, gg, b)
        if sat > 0.25 and 0.15 < l < 0.9:
            bins.add(int(h * 360 // 45))
    for m in g.RGB.finditer(v):
        r, gg, b = (float(m.group(i)) / 255.0 for i in (1, 2, 3))
        h, l, sat = colorsys.rgb_to_hls(r, gg, b)
        if sat > 0.25 and 0.15 < l < 0.9:
            bins.add(int(h * 360 // 45))
    return len(bins) >= 4


def collect(src):
    """クラスごとに、(プロパティ, 元の値, 置き換えた値, 文脈の種類) を集める。"""
    per = collections.defaultdict(list)
    files = sorted(os.listdir(src), key=lambda f: (f != "main.css", f))
    for f in files:
        if not f.endswith(".css"):
            continue
        css = open(os.path.join(src, f), encoding="utf-8", errors="replace").read()
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

        def walk(text, kind):
            for prelude, body in g.split_top(text):
                if prelude.startswith("@"):
                    if prelude.lower().startswith(("@media", "@supports", "@container", "@layer")):
                        walk(body, "media")
                    continue
                for sel in [s.strip() for s in re.split(r",(?![^(]*\))", prelude)]:
                    if "DocsSite" in sel or "WorldCodeAi" in sel or "CodeEditor" in sel:
                        continue
                    m = LAST_CLASS.search(sel)
                    if m and kind == "plain":
                        name, ctx = m.group(1), "plain"
                    else:
                        cs = ANY_CLASS.findall(sel)
                        if not cs:
                            continue
                        name, ctx = cs[-1], ("media" if kind == "media" else "pseudo")
                    for d in g.split_decls(body):
                        if ":" not in d:
                            continue
                        p, v = d.split(":", 1)
                        p, v = p.strip(), v.strip()
                        if not PROPS_OK.match(p) or "url(" in v:
                            continue
                        nv = g.conv_value(v)
                        if nv != v and not multi_hue(v):
                            per[name].append((p, v, nv, ctx))
        walk(css, "plain")
    return per


def decide(per):
    """採る宣言と、取りこぼし(理由別)を返す。"""
    take, missed = {}, collections.defaultdict(list)
    for name, items in per.items():
        plain = [x for x in items if x[3] == "plain"]
        if not plain:
            missed["疑似クラス・@media だけ(表せない)"].append(name)
            continue
        generic = name in GENERIC or len(name) < 5
        decls = []
        for p in sorted({x[0] for x in plain}):
            vals = collections.Counter(x[2] for x in plain if x[0] == p)
            if any(c in v for v in vals for c in BAD):
                continue
            if generic and len(vals) != 1:
                missed["ありふれた名前で、文脈ごとに色が違う"].append(name)
                continue
            if generic and name in ("Selected", "Active", "Disabled", "Hidden", "Left", "Right", "Top", "Bottom"):
                missed["ありふれた名前(にじむので除外)"].append(name)
                continue
            nv = vals.most_common(1)[0][0]
            decls.append("%s: %s !important;" % (p, nv.replace("!important", "").strip()))
        if decls:
            take[name] = decls
    return take, missed


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src, face_path, out = args[0], args[1], args[2]
    per = collect(src)
    take, missed = decide(per)
    auto = [".%s { %s }" % (n, " ".join(d)) for n, d in sorted(take.items())]
    face = open(face_path, "rb").read()
    face_url = 'url("data:image/png,%s")' % "".join("%%%02X" % b for b in face)
    hand = open(os.path.join(HERE, "hand_rules.css"), encoding="utf-8").read().replace("__FACE__", face_url)
    text = "\n".join(auto) + "\n" + hand
    open(out, "w", encoding="utf-8").write(text)
    print("自動:", len(take), "クラス / 手書き + 顔 →", out, len(text) // 1024, "KB")
    if "--report" in sys.argv:
        for k, v in missed.items():
            print("取りこぼし:", k, len(v), sorted(set(v))[:40])


if __name__ == "__main__":
    main()
