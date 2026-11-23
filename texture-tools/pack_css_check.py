#!/usr/bin/env python3
"""ゲーム(bloxd.io のクライアント)が、テクスチャパックの CSS を取り込む手順を、そのまま再現して、「実際に効く CSS」を書き出す。

ゲームのコード(main.js)から読み取った仕組み:
  1. 取り込み: 正規表現  /\\.([a-zA-Z:\\d]+)\\s*\\{\\s*([^}]+)\\s*\\}/g  で、「.クラス名 { 宣言 }」だけを拾う。
       → クラス名は、英字・数字・コロンだけ(ハイフン・アンダースコアは不可)。 `.A .B { }` は、最後の `.B` だけの規則になる(文脈は、失われる)。
       → 宣言は  /([a-zA-Z-]+)\\s*:\\s*([^;]+);/g  (各宣言の最後に `;` が要る。値に `;` は入れられない)。
  2. 許されるプロパティは、決まった一覧だけ(background・border・box-shadow・filter・color・opacity・padding・width など。content・変数・inset・object-fit は不可)。
  3. 値に、次の文字が 1 つでもあると、その宣言は、捨てられる:  $ & ; < = > ? @ [ \\ ] ^ { | } ~
  4. url() は、data: と、決まった数のサイト以外は不可。 src( image( image-set( cross-fade( も不可。
  5. 出力: `.クラス名 { プロパティ: 値; }`(`!important` は、値の一部として通る)。
使い方: python pack_css_check.py <パックの CSS> [<効く CSS の出力先>]"""
import re
import sys

ALLOWED = set("""background background-color background-image backdrop-filter background-size background-position background-repeat image-rendering filter touch-action color opacity visibility border border-radius border-color border-style border-width border-image-source border-image-slice border-image-width border-image-outset border-image-repeat border-image outline contain box-shadow font font-family font-size font-weight font-style line-height text-align text-shadow -webkit-text-stroke text-stroke letter-spacing word-spacing text-transform text-decoration white-space overflow cursor padding padding-top padding-right padding-bottom padding-left margin margin-top margin-right margin-bottom margin-left width height min-width min-height max-width max-height aspect-ratio position top right bottom left display flex flex-direction flex-wrap justify-content align-items align-content gap order flex-grow flex-shrink flex-basis align-self grid grid-template-columns grid-template-rows grid-template-areas grid-template grid-auto-columns grid-auto-rows grid-auto-flow grid-column-gap grid-row-gap grid-gap grid-area justify-self place-self place-items place-content transform rotate scale translate transition z-index""".split())
FORBIDDEN = set('$&;<=>?@[\\]^{|}~')
BAD_FUNC = re.compile(r"(?:src|image|image-set|cross-fade)\(", re.I)
URL_ALL = re.compile(r"url\(", re.I)
URL_OK = re.compile(r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^\"'()\s]*))\s*\)", re.I)
HOSTS_OK = {"https://bloxd.invalid", "https://fonts.gstatic.com"}
HREF_OK = {"https://i.imgur.com/MEcjBFQ.png"}

RULE = re.compile(r"\.([a-zA-Z:\d]+)\s*\{\s*([^}]+)\s*\}")
DECL = re.compile(r"([a-zA-Z-]+)\s*:\s*([^;]+);")


def url_ok(v):
    if "\\" in v or BAD_FUNC.search(v):
        return False
    ms = list(URL_OK.finditer(v))
    if len(ms) != len(URL_ALL.findall(v)):
        return False
    for m in ms:
        u = next((g for g in m.groups() if g is not None), "")
        if u.startswith("data:"):
            continue
        mm = re.match(r"^(https?://[^/]+)", u)
        if not (mm and mm.group(1) in HOSTS_OK) and u not in HREF_OK:
            return False
    return True


def effective(css):
    styles, dropped = {}, []
    for m in RULE.finditer(css):
        name, body = m.group(1), m.group(2)
        for d in DECL.finditer(body):
            p, v = d.group(1), d.group(2)
            if p not in ALLOWED:
                dropped.append((name, p, "プロパティが許可されていない"))
                continue
            if any(c in FORBIDDEN for c in v):
                dropped.append((name, p, "値に禁止の文字: " + "".join(sorted({c for c in v if c in FORBIDDEN}))))
                continue
            if not url_ok(v):
                dropped.append((name, p, "url() が許可されていない"))
                continue
            styles.setdefault(name, {})[p] = v
    return styles, dropped


def render(styles):
    out = []
    for name, props in styles.items():
        out.append(".%s {%s} " % (name.replace(":", "\\:"), "".join(" %s: %s;" % (p, v) for p, v in props.items())))
    return "".join(out)


if __name__ == "__main__":
    css = open(sys.argv[1], encoding="utf-8").read()
    styles, dropped = effective(css)
    n = sum(len(v) for v in styles.values())
    print("効く規則: %d クラス、宣言 %d 個。 捨てられた宣言: %d 個" % (len(styles), n, len(dropped)))
    for x in dropped[:25]:
        print("  捨てられた:", x)
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(render(styles))
