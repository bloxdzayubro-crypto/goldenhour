// アイテムのモデル(GLB)の「色見本(パレット)」を、模様つきにする。
//
// 問題: アイテムのモデルは、どの面も、色見本の 1 点(ドットの中心)だけを指している。だから、見本の画像を精細にしても、
//       面は、1 色のべた塗りにしかならない。
// 対策: (1) 各面の UV を、見本の「1 マス全体」を指すように広げる(面の位置から、マス内の座標を決める)。
//       (2) 見本の画像を、1 マスが R x R ピクセルの模様つき(金属の筋・宝石の面取り・木目 …)に作り直す。
// 形(頂点・法線)は、そのまま。UV と画像だけを変える。Draco で圧縮し直す。
//
// 使い方: node uvx.mjs --src <GLB のフォルダ> [<別のフォルダ> …] --catalogue <catalogue.json> --out <出力フォルダ>
//                      [--scale 8] [--only 名前1,名前2] [--skip 名前1,名前2]
import fs from "node:fs";
import path from "node:path";
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import draco3d from "draco3dgltf";
import sharp from "sharp";

const args = process.argv.slice(2);
const opt = { src: [], catalogue: null, out: null, scale: 8, only: null, skip: new Set(), icons: null, quality: null, maxBad: 0.12 };
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === "--src") { while (args[i + 1] && !args[i + 1].startsWith("--")) opt.src.push(args[++i]); }
  else if (a === "--catalogue") opt.catalogue = args[++i];
  else if (a === "--out") opt.out = args[++i];
  else if (a === "--scale") opt.scale = Number(args[++i]);
  else if (a === "--icons") opt.icons = args[++i];
  else if (a === "--quality") opt.quality = args[++i];
  else if (a === "--max-bad") opt.maxBad = Number(args[++i]);
  else if (a === "--only") opt.only = new Set(args[++i].split(",").filter(Boolean));
  else if (a === "--skip") opt.skip = new Set(args[++i].split(",").filter(Boolean));
}
if (!opt.src.length || !opt.out) { console.error("--src と --out が要る"); process.exit(1); }
fs.mkdirSync(opt.out, { recursive: true });

// ───── 疑似乱数・ノイズ ─────
function h2(x, y, s) {
  let h = Math.imul(x | 0, 374761393) ^ Math.imul(y | 0, 668265263) ^ Math.imul(s | 0, 2246822519);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967295;
}
const clamp = (v, a = 0, b = 255) => Math.max(a, Math.min(b, v));

// ───── 色見本の 1 マスの模様 ─────
function classify(r, g, b) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
  const sat = (mx - mn) / 255;
  const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  if (sat < 0.14) return lum > 0.32 ? "metal" : "dark";
  if (r > g * 1.05 && g > b * 1.4 && sat > 0.35 && lum > 0.45) return "gold";
  if (r > g && g > b && lum < 0.62 && sat < 0.7) return "wood";
  if (sat > 0.45 && lum > 0.30) return "gem";
  return "plain";
}

// R x R ピクセルの 1 マス(RGBA)。(r,g,b) は元の色。
function cellPattern(r, g, b, a, R, seed) {
  const cls = classify(r, g, b);
  const out = new Uint8ClampedArray(R * R * 4);
  const sx = Math.floor(h2(seed, 7, 1) * 997), sy = Math.floor(h2(seed, 9, 2) * 991);
  for (let y = 0; y < R; y++) {
    for (let x = 0; x < R; x++) {
      const u = (x + 0.5) / R, v = (y + 0.5) / R;
      let m = 1.0; // 明るさの倍率
      let tr = 1, tg = 1, tb = 1; // 色味
      const grain = h2(x + sx, y + sy, 3) - 0.5;
      if (cls === "metal") {
        // 研いだ金属: 縦の筋 + 上が明るく下が暗い + 左上の鋭い反射
        const streak = h2(x + sx, 0, 5) - 0.5;
        m = 1.0 + streak * 0.14 + grain * 0.05 + (0.5 - v) * 0.20 + (0.5 - u) * 0.06;
        if (u + v < 0.55) m += 0.10 * (0.55 - (u + v)) * 3;
      } else if (cls === "gold") {
        const streak = h2(x + sx, 0, 6) - 0.5;
        m = 1.0 + streak * 0.10 + grain * 0.05 + (0.5 - v) * 0.30;
        tr = 1.0; tg = 0.98 + (0.5 - v) * 0.10; tb = 0.9 + (0.5 - v) * 0.2;
        if (u + v < 0.5) m += 0.18;
      } else if (cls === "gem") {
        // 宝石: 面取りのような明暗(左上が明るく、右下が暗い)+ 中心の光る点
        const d = Math.hypot(u - 0.32, v - 0.30);
        m = 1.0 + (0.5 - (u * 0.6 + v * 0.4)) * 0.55 + grain * 0.04;
        const edge = Math.min(u, v, 1 - u, 1 - v);
        m *= 0.86 + 0.14 * Math.min(1, edge * 6);
        if (d < 0.17) { m += (0.17 - d) * 3.6; tr = tg = tb = 1.0; }
      } else if (cls === "wood") {
        const streak = h2(0, y + sy, 8) - 0.5; // 横の木目
        m = 1.0 + streak * 0.20 + grain * 0.05 + (0.5 - v) * 0.10;
      } else if (cls === "dark") {
        m = 1.0 + grain * 0.18 + (0.5 - v) * 0.12;
      } else {
        m = 1.0 + grain * 0.07 + (0.5 - v) * 0.10;
      }
      const k = (y * R + x) * 4;
      let rr = r * m * tr, gg = g * m * tg, bb = b * m * tb;
      // 明るく飛ぶぶんは、白に向かって、なだらかに
      const over = Math.max(rr, gg, bb);
      if (over > 255) { const e = Math.min(1, (over - 255) / 255); rr = rr + (255 - rr) * e; gg = gg + (255 - gg) * e; bb = bb + (255 - bb) * e; }
      out[k] = clamp(rr); out[k + 1] = clamp(gg); out[k + 2] = clamp(bb); out[k + 3] = a;
    }
  }
  return { data: out, cls };
}


// ───── アイコンを、手に持ったときのモデルに貼る ─────
// 手に持つアイテムは、8x8 の格子に並んだ小さな立方体で、色は色見本から取っている。前面・背面の各面は、アイコンの 1 ドットに対応する。
// 新しいアイコン(面取り・つや・影つき)の画像を、前面・背面に、そのまま貼り(アイコンの見た目と一致する)、側面には、縁のドットの色を貼る。
const slug = (n) => n.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
async function loadIcon(name) {
  if (!opt.icons) return null;
  const p = path.join(opt.icons, slug(name) + ".png");
  if (!fs.existsSync(p)) return null;
  const dec = await sharp(p).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const W = dec.info.width, H = dec.info.height;
  // 形(ほぼ不透明な部分)の外接の四角形
  let x0 = W, y0 = H, x1 = -1, y1 = -1;
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (dec.data[(y * W + x) * 4 + 3] > 230) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  if (x1 < 0) return null;
  return { data: dec.data, W, H, bbox: [x0, y0, x1 + 1, y1 + 1] };
}

// 格子のモデルか(面が全部、軸に沿っていて、座標の種類が少ない)
function gridInfo(prims) {
  const xs = new Set(), ys = new Set();
  let mnx = Infinity, mxx = -Infinity, mny = Infinity, mxy = -Infinity, bad = 0, total = 0;
  const q = [0, 0, 0], nrm = [0, 0, 0];
  for (const prim of prims) {
    const pos = prim.getAttribute("POSITION"), nor = prim.getAttribute("NORMAL");
    if (!nor) return null;
    for (let i = 0; i < pos.getCount(); i++) {
      pos.getElement(i, q); nor.getElement(i, nrm);
      xs.add(Math.round(q[0] * 1000)); ys.add(Math.round(q[1] * 1000));
      mnx = Math.min(mnx, q[0]); mxx = Math.max(mxx, q[0]); mny = Math.min(mny, q[1]); mxy = Math.max(mxy, q[1]);
      total++; if (Math.max(Math.abs(nrm[0]), Math.abs(nrm[1]), Math.abs(nrm[2])) < 0.99) bad++;
    }
  }
  if (bad > total * 0.02 || xs.size > 14 || ys.size > 14 || mxx - mnx < 3 || mxy - mny < 3) return null;
  return { mnx, mxx, mny, mxy };
}

function mapPrimsToIcon(prims, icon, g) {
  // モデルの外接の四角形(格子)を、アイコンの形の外接の四角形に対応させる。アイコンが、モデルより、1 ドットずつ大きいとき(縁取りぶん)は、縮める。
  const pxPerCell = icon.W / 10; // アイコンの 1 ドットの大きさ(10x10 を、拡大したもの)
  let [bx0, by0, bx1, by1] = icon.bbox;
  const wx = g.mxx - g.mnx, wy = g.mxy - g.mny;
  const iw = (bx1 - bx0) / pxPerCell, ih = (by1 - by0) / pxPerCell;
  if (Math.abs(iw - (wx + 2)) < 0.6 && Math.abs(ih - (wy + 2)) < 0.6) { bx0 += pxPerCell; bx1 -= pxPerCell; by0 += pxPerCell; by1 -= pxPerCell; }
  const u0 = bx0 / icon.W, u1 = bx1 / icon.W, v0 = by0 / icon.H, v1 = by1 / icon.H;
  const U = (x) => u0 + ((x - g.mnx) / wx) * (u1 - u0);
  const Un = (x) => u1 - ((x - g.mnx) / wx) * (u1 - u0); // 背面: 左右を反転(アイコンが、鏡像にならないように)
  const V = (y) => v1 - ((y - g.mny) / wy) * (v1 - v0);  // 画像は、上が 0
  const clampIn = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  let faces = 0;
  const p = [0, 0, 0], n = [0, 0, 0];
  for (const prim of prims) {
    const pos = prim.getAttribute("POSITION"), nor = prim.getAttribute("NORMAL"), uv = prim.getAttribute("TEXCOORD_0");
    for (let i = 0; i < pos.getCount(); i++) {
      pos.getElement(i, p); nor.getElement(i, n);
      const ax = Math.abs(n[0]) > 0.99 ? 0 : Math.abs(n[1]) > 0.99 ? 1 : 2;
      const sg = Math.sign(n[ax]) || 1;
      let u, v;
      if (ax === 2) { u = U(p[0]); v = V(p[1]); } // 前面も背面も、同じブロックの面なので、同じドットの色(背面は、裏から見ると、左右が反対に見えるのが、正しい)
      else if (ax === 0) { const xin = clampIn(p[0] - sg * 0.5, g.mnx + 0.5, g.mxx - 0.5); u = U(xin); v = V(p[1]); }
      else { const yin = clampIn(p[1] - sg * 0.5, g.mny + 0.5, g.mxy - 0.5); u = U(p[0]); v = V(yin); }
      // 画像の端(ドットの境目)を、わずかに内側へ(隣のドットの色が、混ざらないように)
      const e = 0.0015;
      uv.setElement(i, [clampIn(u, 0, 1) * (1 - 2 * e) + e, clampIn(v, 0, 1) * (1 - 2 * e) + e]);
    }
    faces++;
  }
  return faces;
}

// ───── モデルの処理 ─────
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({
    "draco3d.decoder": await draco3d.createDecoderModule(),
    "draco3d.encoder": await draco3d.createEncoderModule(),
  });

function faceComponents(indices, vertexCount) {
  // 三角形でつながっている頂点の集まり = 1 つの面(四角形)
  const parent = new Int32Array(vertexCount).map((_, i) => i);
  const find = (x) => { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; };
  const uni = (a, b) => { a = find(a); b = find(b); if (a !== b) parent[a] = b; };
  for (let i = 0; i + 2 < indices.length; i += 3) { uni(indices[i], indices[i + 1]); uni(indices[i], indices[i + 2]); }
  const groups = new Map();
  const used = new Set(indices);
  for (const v of used) { const r = find(v); if (!groups.has(r)) groups.set(r, []); groups.get(r).push(v); }
  return [...groups.values()];
}

async function processModel(file, name) {
  const doc = await io.read(file);
  const root = doc.getRoot();
  // テクスチャごとに、それを使うプリミティブを集める
  const byTex = new Map();
  for (const mesh of root.listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
      const mat = prim.getMaterial();
      const tex = mat && mat.getBaseColorTexture();
      if (!tex || !prim.getAttribute("TEXCOORD_0") || !prim.getAttribute("POSITION")) continue;
      if (!byTex.has(tex)) byTex.set(tex, []);
      byTex.get(tex).push(prim);
    }
  }
  let changed = 0;
  for (const [tex, prims] of byTex) {
    const img = tex.getImage();
    if (!img) continue;
    const dec = await sharp(Buffer.from(img)).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const W = dec.info.width, H = dec.info.height;
    if (Math.min(W, H) <= 1 || Math.max(W, H) > 16) continue; // 色見本は、小さい(8x8 〜 16x16)
    // 各面の UV が 1 点か(= 色見本の使い方か)を調べる
    let constFaces = 0, allFaces = 0;
    const plans = [];
    for (const prim of prims) {
      const pos = prim.getAttribute("POSITION"), uv = prim.getAttribute("TEXCOORD_0");
      let idx = prim.getIndices();
      const indices = idx ? Array.from(idx.getArray()) : Array.from({ length: pos.getCount() }, (_, i) => i);
      const faces = faceComponents(indices, pos.getCount());
      const p = [0, 0, 0], u = [0, 0], u0 = [0, 0];
      for (const verts of faces) {
        allFaces++;
        uv.getElement(verts[0], u0);
        let same = true;
        for (const vtx of verts) { uv.getElement(vtx, u); if (Math.abs(u[0] - u0[0]) > 1e-4 || Math.abs(u[1] - u0[1]) > 1e-4) { same = false; break; } }
        if (same && verts.length >= 3) { constFaces++; plans.push({ prim, verts, u0: [u0[0], u0[1]] }); }
      }
    }
    if (allFaces === 0 || constFaces / allFaces < 0.6) continue; // 色見本ではない(本物の絵)。ここでは触らない
    // 新しいアイコンがあり、格子のモデルなら、アイコンを、そのまま貼る(手に持ったとき・落ちたときが、アイコンと同じ見た目になる)
    const icon = await loadIcon(name);
    const g = icon ? gridInfo(prims) : null;
    // 貼る前の UV を控えておく(あとで、元の絵と色が合わないモデルは、アイコンを貼らずに、元へ戻す)
    const savedUV = icon && g ? prims.map((pr) => { const a = pr.getAttribute("TEXCOORD_0"); const arr = []; for (let i = 0; i < a.getCount(); i++) { const t = [0, 0]; a.getElement(i, t); arr.push(t); } return arr; }) : null;
    let iconOk = false;
    if (icon && g) {
      mapPrimsToIcon(prims, icon, g);
      // 品質チェック: 面ごとに、元の色(色見本)と、貼ったアイコンの色を比べる。合わない面が多い = 形が、アイコンと合っていない。
      let bad = 0, tot = 0, sum = 0;
      for (const { prim, verts, u0 } of plans) {
        const uvA = prim.getAttribute("TEXCOORD_0");
        const cu = [0, 0]; let su = 0, sv = 0;
        for (const vtx of verts) { uvA.getElement(vtx, cu); su += cu[0]; sv += cu[1]; }
        su /= verts.length; sv /= verts.length;
        const ix = Math.min(icon.W - 1, Math.max(0, Math.floor(su * icon.W))), iy = Math.min(icon.H - 1, Math.max(0, Math.floor(sv * icon.H)));
        const ik = (iy * icon.W + ix) * 4;
        const ox = Math.min(W - 1, Math.floor(u0[0] * W)), oy = Math.min(H - 1, Math.floor(u0[1] * H));
        const ok = (oy * W + ox) * 4;
        const d = Math.hypot(icon.data[ik] - dec.data[ok], icon.data[ik + 1] - dec.data[ok + 1], icon.data[ik + 2] - dec.data[ok + 2]) / 441.7;
        tot++; sum += d; if (d > 0.42) bad++;
      }
      const frac = tot ? bad / tot : 0;
      if (opt.quality) fs.appendFileSync(opt.quality, JSON.stringify({ name, faces: tot, frac: +frac.toFixed(3), mean: +(tot ? sum / tot : 0).toFixed(3) }) + String.fromCharCode(10));
      iconOk = frac <= opt.maxBad;
      if (!iconOk) {
        prims.forEach((pr, k) => { const a = pr.getAttribute("TEXCOORD_0"); savedUV[k].forEach((t, i) => a.setElement(i, t)); });
        iconRejected++;
      }
    }
    if (icon && g && iconOk) {
      const rgba = Buffer.from(icon.data);
      for (let i = 3; i < rgba.length; i += 4) rgba[i] = 255; // 材質は「不透明」。透明度は使わない
      const png = await sharp(rgba, { raw: { width: icon.W, height: icon.H, channels: 4 } }).png().toBuffer();
      tex.setImage(new Uint8Array(png)).setMimeType("image/png");
      changed++;
      iconMapped++;
      continue;
    }
    // 面の位置から、マス内の座標を決めて、UV を広げる
    const inset = 0.10;
    for (const { prim, verts, u0 } of plans) {
      const pos = prim.getAttribute("POSITION"), uv = prim.getAttribute("TEXCOORD_0");
      const P = verts.map((vtx) => { const q = [0, 0, 0]; pos.getElement(vtx, q); return q; });
      // 面の法線(最初の 3 頂点)から、いちばん大きい軸を落として、残り 2 軸を、面の座標にする
      const a = P[0], b = P[1], c = P[2];
      const e1 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], e2 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      const n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]].map(Math.abs);
      const drop = n[0] >= n[1] && n[0] >= n[2] ? 0 : n[1] >= n[2] ? 1 : 2;
      const ax = [0, 1, 2].filter((i) => i !== drop);
      const mn = [Infinity, Infinity], mx = [-Infinity, -Infinity];
      for (const q of P) for (let k = 0; k < 2; k++) { mn[k] = Math.min(mn[k], q[ax[k]]); mx[k] = Math.max(mx[k], q[ax[k]]); }
      const cx = Math.floor(u0[0] * W), cy = Math.floor(u0[1] * H);
      verts.forEach((vtx, i) => {
        const q = P[i];
        const t0 = mx[0] - mn[0] > 1e-9 ? (q[ax[0]] - mn[0]) / (mx[0] - mn[0]) : 0.5;
        const t1 = mx[1] - mn[1] > 1e-9 ? (q[ax[1]] - mn[1]) / (mx[1] - mn[1]) : 0.5;
        uv.setElement(vtx, [(cx + inset + t0 * (1 - 2 * inset)) / W, (cy + inset + t1 * (1 - 2 * inset)) / H]);
      });
    }
    // 画像を、1 マスが R x R の模様つきに作り直す
    const R = opt.scale;
    const out = Buffer.alloc(W * R * H * R * 4);
    const seedBase = [...name].reduce((s, ch) => (s * 31 + ch.charCodeAt(0)) | 0, 7);
    for (let cy = 0; cy < H; cy++) {
      for (let cx = 0; cx < W; cx++) {
        const k = (cy * W + cx) * 4;
        const cell = cellPattern(dec.data[k], dec.data[k + 1], dec.data[k + 2], 255, R, seedBase + cx * 13 + cy * 101);
        for (let y = 0; y < R; y++) {
          for (let x = 0; x < R; x++) {
            const s = (y * R + x) * 4, d = (((cy * R + y) * (W * R)) + (cx * R + x)) * 4;
            out[d] = cell.data[s]; out[d + 1] = cell.data[s + 1]; out[d + 2] = cell.data[s + 2]; out[d + 3] = 255;
          }
        }
      }
    }
    const png = await sharp(out, { raw: { width: W * R, height: H * R, channels: 4 } }).png().toBuffer();
    tex.setImage(new Uint8Array(png)).setMimeType("image/png");
    changed++;
  }
  return { doc, changed };
}

const cat = opt.catalogue ? JSON.parse(fs.readFileSync(opt.catalogue, "utf8")) : null;
let allowed = null;
if (cat) {
  const b = new Set(cat.block || []), s = new Set(cat.static || []);
  const clash = new Set([...b].filter((n) => s.has(n)));
  allowed = new Set([...b, ...s].filter((n) => !clash.has(n)));
}
const seen = new Set();
let done = 0, skipped = 0, failed = 0, total = 0, iconMapped = 0, iconRejected = 0;
for (const dir of opt.src) {
  for (const f of fs.readdirSync(dir).sort()) {
    if (!f.toLowerCase().endsWith(".glb") || seen.has(f)) continue;
    const name = f.slice(0, -4);
    if (allowed && !allowed.has(name)) continue;
    if (opt.only && !opt.only.has(name)) continue;
    if (opt.skip.has(name)) continue;
    seen.add(f);
    total++;
    try {
      const { doc, changed } = await processModel(path.join(dir, f), name);
      if (changed > 0) { await io.write(path.join(opt.out, f), doc); done++; } else skipped++;
    } catch (e) {
      failed++;
      console.error("失敗:", f, String(e).slice(0, 160));
    }
  }
}
console.log(`対象 ${total} 個: 模様つきにした ${done} 個(うち、アイコンを貼った ${iconMapped} 個、色が合わず、貼らなかった ${iconRejected} 個)、色見本ではない/そのまま ${skipped} 個、失敗 ${failed} 個 → ${opt.out}`);
