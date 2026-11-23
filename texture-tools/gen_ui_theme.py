#!/usr/bin/env python3
"""ゲームの画面(UI)全体を、青系 → 金・茶色の配色に着せ替える CSS を、自動で作る。

やり方: ゲームの CSS(bloxd.io の static/css/*.css を取得したもの)を全部読み、
  背景・枠・影・色の変数のうち、青系の色(色相 195〜275°、彩度が高め)を、金・茶色系に置き換えた規則だけを、
  同じセレクターで書き出す(すべて !important)。 クラス名を、ひとつずつ調べなくても、ホーム・設定・クラフト・チャット…の全部の部品に、同じ雰囲気が及ぶ。
  ボタンの色の変数(--buttonNormalColour など)も、青系だけが変わる(緑・赤・紫・金のボタンは、そのまま = 意味が、保たれる)。
使い方: python gen_ui_theme.py <ゲームの CSS を入れたフォルダ> <出力の CSS>"""
import colorsys
import os
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else ""
OUT = sys.argv[2] if len(sys.argv) > 2 else ""

HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
RGB = re.compile(r"rgba?\(\s*([\d.]+)\s*[, ]\s*([\d.]+)\s*[, ]\s*([\d.]+)\s*(?:[,/]\s*([^)]+?)\s*)?\)")
HSL = re.compile(r"hsla?\(\s*([\d.]+)(?:deg)?\s*[, ]\s*([\d.]+)%\s*[, ]\s*([\d.]+)%\s*(?:[,/]\s*([^)]+?)\s*)?\)")


def warm(r, g, b):
    """青系なら、金・茶色系に。そうでなければ、None。 r, g, b は 0〜1。"""
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    deg = h * 360.0
    if not (195.0 <= deg <= 275.0) or s < 0.18:
        return None
    # 暗い色は、濃い茶色に。明るい青(アクセント)は、金に。
    nh = 36.0 / 360.0
    ns = min(0.66, s * 0.78)
    nl = l * 0.94 if l < 0.5 else min(0.82, 0.40 + (l - 0.5) * 0.85)
    return colorsys.hls_to_rgb(nh, nl, ns)


def conv_hex(m):
    t = m.group(1)
    if len(t) in (3, 4):
        t = "".join(c * 2 for c in t)
    r, g, b = (int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    a = t[6:8] if len(t) == 8 else ""
    w = warm(r, g, b)
    if w is None:
        return m.group(0)
    return "#%02x%02x%02x%s" % (round(w[0] * 255), round(w[1] * 255), round(w[2] * 255), a)


def conv_rgb(m):
    r, g, b = (float(m.group(i)) / 255.0 for i in (1, 2, 3))
    w = warm(r, g, b)
    if w is None:
        return m.group(0)
    a = m.group(4)
    c = "%d,%d,%d" % (round(w[0] * 255), round(w[1] * 255), round(w[2] * 255))
    return "rgba(%s,%s)" % (c, a) if a is not None else "rgb(%s)" % c


def conv_hsl(m):
    h, sat, lig = float(m.group(1)) / 360.0, float(m.group(2)) / 100.0, float(m.group(3)) / 100.0
    r, g, b = colorsys.hls_to_rgb(h % 1.0, lig, sat)
    w = warm(r, g, b)
    if w is None:
        return m.group(0)
    a = m.group(4)
    c = "%d,%d,%d" % (round(w[0] * 255), round(w[1] * 255), round(w[2] * 255))
    return "rgba(%s,%s)" % (c, a) if a is not None else "rgb(%s)" % c


def conv_value(v):
    return HSL.sub(conv_hsl, RGB.sub(conv_rgb, HEX.sub(conv_hex, v)))


PROPS = re.compile(r"^(background(-color|-image)?|border(-[a-z]+)*(-color)?|box-shadow|outline(-color)?|--[A-Za-z0-9-]+)$")


def split_top(css):
    """波括弧の入れ子を見て、(前置き, 中身) の並びに分ける。文字列・括弧の中は、無視する。"""
    out, i, n = [], 0, len(css)
    while i < n:
        j = i
        depth_p = 0
        while j < n and not (css[j] == "{" and depth_p == 0):
            c = css[j]
            if c == "(":
                depth_p += 1
            elif c == ")":
                depth_p = max(0, depth_p - 1)
            elif c in "\"'":
                q = c
                j += 1
                while j < n and css[j] != q:
                    j += 2 if css[j] == "\\" else 1
            elif c == ";" and depth_p == 0:
                pass
            j += 1
        if j >= n:
            break
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            c = css[k]
            if c in "\"'":
                q = c
                k += 1
                while k < n and css[k] != q:
                    k += 2 if css[k] == "\\" else 1
            elif c == "(":
                # url(data:...;...) の ; や { を飛ばす
                d2 = 1
                k += 1
                while k < n and d2:
                    if css[k] == "(":
                        d2 += 1
                    elif css[k] == ")":
                        d2 -= 1
                    elif css[k] in "\"'":
                        q = css[k]
                        k += 1
                        while k < n and css[k] != q:
                            k += 2 if css[k] == "\\" else 1
                    k += 1
                continue
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            k += 1
        out.append((prelude, css[j + 1:k - 1]))
        i = k
    return out


def split_decls(body):
    out, cur, dp = [], [], 0
    q = None
    for c in body:
        if q:
            cur.append(c)
            if c == q:
                q = None
            continue
        if c in "\"'":
            q = c
        elif c == "(":
            dp += 1
        elif c == ")":
            dp = max(0, dp - 1)
        elif c == ";" and dp == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(c)
    if cur:
        out.append("".join(cur))
    return [d.strip() for d in out if d.strip()]


def themed_rule(prelude, body):
    keep = []
    for d in split_decls(body):
        if ":" not in d:
            continue
        p, v = d.split(":", 1)
        p, v = p.strip(), v.strip()
        if not PROPS.match(p) or "url(" in v or "var(" in v and p.startswith("--") is False and False:
            continue
        nv = conv_value(v)
        if nv != v:
            keep.append("%s:%s!important" % (p, nv.replace("!important", "").strip()))
    if not keep:
        return None
    return "%s{%s}" % (prelude, ";".join(keep))


def process(css, seen):
    out = []
    for prelude, body in split_top(css):
        if prelude.startswith("@"):
            low = prelude.lower()
            if low.startswith(("@media", "@supports", "@container", "@layer")):
                inner = process(body, seen)
                if inner:
                    out.append("%s{%s}" % (prelude, "".join(inner)))
            continue  # @keyframes, @font-face など: 触らない
        if "DocsSite" in prelude or "WorldCodeAi" in prelude or "CodeEditor" in prelude:
            continue  # ドキュメント・コードエディターは、そのまま
        r = themed_rule(prelude, body)
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def main():
    files = sorted(os.listdir(SRC), key=lambda f: (f != "main.css", f))
    seen, parts, total = set(), [], 0
    for f in files:
        if not f.endswith(".css"):
            continue
        css = open(os.path.join(SRC, f), encoding="utf-8", errors="replace").read()
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        rules = process(css, seen)
        total += len(rules)
        parts.append("".join(rules))
    text = "/* 自動生成(gen_ui_theme.py): ゲームの画面全体の、青系の色 → 金・茶色系。 手書きの部分は、golden_hour_ui.css のほう。 */\n" + "\n".join(parts) + "\n"
    open(OUT, "w", encoding="utf-8").write(text)
    print("規則", total, "個、", len(text) // 1024, "KB →", OUT)


if __name__ == "__main__":
    main()
