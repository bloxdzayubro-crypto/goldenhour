#!/usr/bin/env python3
"""ゲームのクライアント(chunks/bqoxjr.textureNameTable*.js)から、テクスチャ名の表を取り出して、tools/_client/texture_names.txt に書く。
シェーダーの bloxdTextureId* の名前を、公式コンパイラで検証するのに要る(名前の表が空だと、全部「そんなテクスチャは無い」になる)。
使い方: python extract_texture_names.py <クライアントの chunks フォルダ>"""
import glob
import os
import re
import sys

chunks = sys.argv[1]
f = glob.glob(os.path.join(chunks, "bqoxjr.textureNameTable*.js"))[0]
s = open(f, encoding="utf-8", errors="replace").read()
i = s.index('const LQ="') + len('const LQ="')
j = s.index('"', i)
names = re.split(r"\\n", s[i:j])
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_client", "texture_names.txt")
open(out, "w", encoding="utf-8").write("\n".join(names))
print(len(names), "個 →", out)
print("雪に関する名前:", [n for n in names if "snow" in n])
print("最初の 5 個:", names[:5])
