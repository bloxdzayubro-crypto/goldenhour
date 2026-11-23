#!/usr/bin/env python3
"""雪のブロックの絵に、シェーダーが見分けるための「印」をつける: とても明るく、わずかに青い(B − R が 0.045 以上)。
白い羊毛・コンクリート・石英などには青みが無い(または黄み)ので、シェーダーの雪は、雪のブロックの近くにだけ降る。
何度実行しても、同じ結果(R を 0.955 までに抑え、B を R + 0.045〜0.068 に収める)。
使い方: python tag_snow.py <テクスチャのフォルダ> ..."""
import os
import sys

import numpy as np
from PIL import Image

NAMES = ["snow", "packed_snow"]
for d in sys.argv[1:]:
    for n in NAMES:
        p = os.path.join(d, n + ".png")
        if not os.path.exists(p):
            continue
        a = np.asarray(Image.open(p).convert("RGBA"), np.float32) / 255.0
        r = np.minimum(a[..., 0], 0.955)
        g = np.maximum(a[..., 1], r + 0.022)
        b = np.clip(a[..., 2], r + 0.045, r + 0.068)
        a[..., 0], a[..., 1], a[..., 2] = r, np.minimum(g, 1.0), np.minimum(b, 1.0)
        Image.fromarray((a * 255 + 0.5).astype(np.uint8), "RGBA").save(p, optimize=True)
        m = a[..., 3] > 0.5
        br = a[..., 2][m] - a[..., 0][m]
        print(p.split("textures")[0][-30:], n, "B-R 最小 %.3f 平均 %.3f" % (br.min(), br.mean()))
