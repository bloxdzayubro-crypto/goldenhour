// シェーダーパックの公式検証(apiVersion 5)。bloxd.io の公式コンパイラ(WASM)を、そのまま Node で動かす。
// 使い方: node tools/validate5.mjs [パックのフォルダ(既定: pack)]
//  - tools/_client/ の中身は、公式クライアントから取った公式コンパイラ(compiler_chunk.js = JS の接着剤、shader_pack.wasm)。
//    クライアントの更新で apiVersion が変わったら、取り直す(README 参照)。
//  - 6 種類(strict/許可 × 地形/液体/モデル)の完成形 WGSL を tools/variants.json に書き出す(compile.html で WebGPU コンパイル)。
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const packDir = path.resolve(process.argv[2] ?? path.join(here, "../pack"));
const clientDir = path.join(here, "_client");

// 公式の JS 接着剤(wasm-bindgen)を取り出す。
const src = fs.readFileSync(path.join(clientDir, "compiler_chunk.js"), "utf8");
const a = src.indexOf("class qQ{");
const b = src.indexOf("var EQ=wQ(2811)");
if (a < 0 || b < 0) throw new Error("コンパイラの接着剤が見つからない(クライアントの構造が変わった可能性)");
const api = new Function(
  src.slice(a, b) + "\nreturn {compile:oQ,apiNum:bQ,initSync:hQ,hdrVer:YQ};"
)();
api.initSync({ module: fs.readFileSync(path.join(clientDir, "shader_pack.wasm")) });
const API = api.apiNum();
const programs = ["terrain", "liquid", "model"]; // 公式の並び順(chunk 内の LQ.d)
const keyOf = (i) => `${i >= programs.length ? "strict" : "allow"}/${programs[i % programs.length]}`;

// パックを読む。
const manifest = JSON.parse(fs.readFileSync(path.join(packDir, "pack.json"), "utf8"));
console.log(`公式コンパイラ: apiVersion ${API} / ヘッダ版 ${api.hdrVer()}`);
if (manifest.apiVersion !== API) {
  console.error(`apiVersion が違う: pack.json=${manifest.apiVersion} / 公式=${API}`);
  process.exit(1);
}
function walk(dir, base = "") {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
    d.isDirectory() ? walk(path.join(dir, d.name), base + d.name + "/") : [base + d.name]
  );
}
const wgsl = walk(packDir)
  .filter((p) => p.toLowerCase().endsWith(".wgsl"))
  .sort()
  .map((p) => ({ path: p, source: fs.readFileSync(path.join(packDir, p), "utf8") }));
const totalKB = wgsl.reduce((n, f) => n + Buffer.byteLength(f.source), 0) / 1024;
console.log(`.wgsl ${wgsl.length} 個 / 合計 ${totalKB.toFixed(1)} KB(上限 256 KB)`);

// テクスチャ名の表(textures)は、パックが bloxdTextureId* を参照するときだけ要る。空で渡す。
// テクスチャ名の表: ゲームのクライアントから取り出したもの(tools/extract_texture_names.py)があれば、渡す。
const namesFile = path.join(clientDir, "texture_names.txt");
const texNames = fs.existsSync(namesFile) ? fs.readFileSync(namesFile, "utf8").split(/\r?\n/).filter(Boolean) : [];
const pack = api.compile(
  wgsl.map((f) => f.path),
  wgsl.map((f) => f.source),
  texNames,
  Uint32Array.from(texNames.map((_, i) => i)),
  [],
  [],
  []
);
const errors = JSON.parse(pack.errorsJson);
const offInStrict = JSON.parse(pack.offInStrictJson);
const names = Array.from(pack.validationModuleKeys);
const codes = pack.validationModuleCodes;

const fmt = (e) => `  ${e[0] ?? "(全体)"}:${e[1]}  ${e[2]}${e[3] ? "  [variants " + e[3].join(",") + "]" : ""}`;
if (errors.length) {
  console.log(`\n公式検証: エラー ${errors.length} 件`);
  errors.forEach((e) => console.log(fmt(e)));
  process.exit(1);
}
console.log("公式検証: エラーなし");
if (offInStrict.length) {
  console.log("\n注意: strict(厳格)なゲームでは、次の理由で、パックの一部/全体が無効になる:");
  offInStrict.forEach((e) => console.log(fmt(e)));
} else {
  console.log("strict(厳格)なゲームでも有効(頂点移動・discard なし)");
}
console.log(`\n完成形の WGSL: ${names.length} 種類`);
const out = names.map((n, i) => ({ key: keyOf(n), code: codes[i] }));
out.forEach((v) => console.log(`  ${v.key}  ${(v.code.length / 1024).toFixed(1)} KB`));
fs.writeFileSync(path.join(here, "variants.json"), JSON.stringify(out));
console.log("→ tools/variants.json に書き出した(compile.html で WebGPU コンパイルを確認)");
pack.free();
