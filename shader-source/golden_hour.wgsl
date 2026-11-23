// Golden Hour — Bloxd シェーダーパック (apiVersion 5)
//
// ねらい: のっぺりした標準の見た目を、立体的で、リアルで、光に色がある見た目にする。
//   立体感
//   - 凹凸: テクスチャの明暗から表面の凹凸(法線)を作る。レンガの目地、鉱石の粒、石の割れ目に陰影が出る。
//   - 面取り: ブロックの縁を、ごくわずかに丸める(縁に光と影が出る)。縁の溝(接する所の暗がり)も付ける。
//   - 影: 太陽・月の影をはっきり効かせる。日向は暖色、影は寒色。自分の足元の影は、弱める。
//   - 光の筋: 木漏れ日・洞窟の入口に、空気中の光の筋。雲の影が、ゆっくり地面を流れる。
//   光に色
//   - 光る素材は、素材そのものの色で光る(クリスタルは緑、溶岩は赤橙)。光源の色の光だまりが、周りに落ちる。
//   葉っぱ
//   - 逆光で透ける(明るい葉ほど薄く光る)。つや、葉の 1 枚ごとの色のばらつき、風でのそよぎ(非 strict のみ)。
//   水
//   - 波長ごとに吸収が違う色、6 つの波 + 細かいさざ波、空と雲の反射、太陽のきらめき、岸の泡の筋。
//
// 設計: strict なゲームでも有効(頂点を動かす処理は、非 strict のときだけ)。discard なし。
//   数値は、全部、下の「調整用の値」で変えられる。
// 注意: ここに書く名前は、"bloxd" で始められない(エンジン予約)。

// ───── 調整用の値(立体感) ─────
const RELIEF_DEPTH: f32 = 0.10;                      // 凹凸の深さ(大きいほど、はっきり)
const CAVITY: f32 = 1.8;                             // くぼみを暗く・出っ張りを明るく(0.0 = なし)
const BEVEL: f32 = 0.0;                              // ブロックの縁の面取りの大きさ(0.0 = なし。境界線が目立つので、既定は切ってある)
const BEVEL_WIDTH: f32 = 0.10;                       // 面取りの幅(ブロックの辺に対する割合)
const EDGE_DARK: f32 = 0.0;                          // ブロックの縁の溝の暗さ(0.0 = なし)
const ORE_RAISE: f32 = 0.60;                         // 鉱石(色つき・明るい粒)を、光で浮き上がらせる強さ(0.0 = なし)
const ORE_SHINE: f32 = 0.45;                         // 鉱石の宝石のような輝き(0.0 = なし)
const ORE_GLOW: f32 = 0.10;                          // 鉱石の色の粒の、自分自身の発光(0.0 = なし)。ダイヤの水色などが、際立つ
const METAL_SHEEN: f32 = 0.70;                       // 金属(鉄・銀・金など)の質感の強さ(0.0 = なし)。アイテム・防具・mob(ゴーレムなど)に効く
const SHADOW_STRENGTH: f32 = 0.80;                   // 影の濃さ(1.0 = 標準どおり、0.0 = 影なし)
const SUN_BOOST: f32 = 0.28;                         // 日向をさらに明るく(日向と影の差を強める。0.0 = なし)
const SHAFT: f32 = 0.20;                             // 光の筋の強さ(0.0 = なし)
const SHAFT_DENSITY: f32 = 0.012;                    // 空気の濃さ(大きいほど、遠くまで筋が見える)
const CLOUD_SHADOW: f32 = 0.16;                      // 雲の影の濃さ(0.0 = なし)
const CLOUD_SCALE: f32 = 0.018;                      // 小さいほど、雲が大きい
const CLOUD_SPEED: f32 = 0.35;                       // 雲の流れる速さ

// ───── 調整用の値(光と色) ─────
const SUN_WARM: vec3f = vec3f(1.10, 0.98, 0.82);     // 昼の日向の色味(掛け算)
const SUNSET_WARM: vec3f = vec3f(1.30, 0.80, 0.52);  // 朝夕の日向の色味
const SHADOW_COOL: vec3f = vec3f(0.86, 0.94, 1.12);  // 日陰(空からの光)の色味
const GROUND_BOUNCE: vec3f = vec3f(1.05, 0.97, 0.88);// 下向きの面に回り込む、地面の暖かい光
const SKY_FILL: vec3f = vec3f(0.95, 0.99, 1.07);     // 上向きの面に回り込む、空の青い光
const SPILL: f32 = 0.40;                             // 光源の色の光だまりの強さ
const SPILL_VIVID: f32 = 1.5;                        // 大きいほど、光の色が濃くなる
const GLOW_SATURATION: f32 = 1.30;                   // 光る素材の色の濃さ
const GLOW_BASE: f32 = 0.10;                         // 光る素材の最低限の明るさ
const GLOW_PEAK: f32 = 0.50;                         // 光る素材の、明るい部分の追加の明るさ
const EMISSIVE_PULSE: f32 = 0.10;                    // 発光の脈動の強さ

// ───── 調整用の値(質感・葉っぱ) ─────
const LARGE_VARIATION: f32 = 0.07;                   // 大きな起伏の色むら(0.0 = なし)
const BLOCK_VARIATION: f32 = 0.05;                   // ブロックごとの明暗差
const GRAIN: f32 = 0.025;                            // 細かな粒状感
const SPEC_ROCK: f32 = 0.12;                         // 岩のつや
const SPEC_LEAF: f32 = 0.07;                         // 葉っぱのつや
const GLITTER: f32 = 0.60;                           // 砂のきらめき
const RIM_SKY: f32 = 0.05;                           // 斜めの面が空を映す量
const LEAF_GLOW: vec3f = vec3f(0.16, 0.26, 0.05);    // 葉っぱが透けて光る色
const LEAF_DAPPLE: f32 = 0.05;                       // 葉の 1 枚ごとの色のばらつき
const LEAF_CUTOUT: f32 = 0.06;                       // これより暗い(黒い)葉の部分は、透明にする(非 strict のみ)
const LEAF_SWAY: f32 = 0.14;                         // 葉っぱが風でゆれる幅(ブロック。0.0 = なし。非 strict のみ)
const PLANT_SWAY: f32 = 0.28;                        // 草・花などが風でゆれる幅(ブロック。0.0 = なし。非 strict のみ)
const LEAF_BITS: f32 = 1.0;                          // 空中を舞い落ちる葉の量(0.0 = なし)。木の近くだけに出る。strict でも効く
const LEAF_BITS_DENSITY: f32 = 0.50;                 // 空中の区画のうち、葉が入っている割合
const LEAF_BITS_SIZE: f32 = 0.05;                    // 葉(正方形)の半分の大きさ(ブロック)
const LEAF_BITS_CELL: f32 = 3.0;                     // 空中の区画の大きさ(ブロック)。小さいほど、葉が密
const SNOW_FALL: f32 = 1.0;                          // 雪の量(0.0 = なし)。雪(白い面)の近くだけに降る。strict でも効く
const SNOW_DENSITY: f32 = 0.60;                      // 空中の区画のうち、雪の粒が入っている割合
const SNOW_SIZE: f32 = 0.11;                         // 雪の粒の半径(ブロック)
const SNOW_CELL: f32 = 2.2;                          // 空中の区画の大きさ(ブロック)
const SNOW_FALL_SPEED: f32 = 1.5;                    // 降る速さ(ブロック/秒)
const LEAF_BITS_FALL: f32 = 1.1;                     // 落ちる速さ(ブロック/秒)
const DAPPLE: f32 = 0.40;                            // 木の下の、動く木漏れ日の明るさ(0.0 = なし)
const GUST: f32 = 0.40;                              // 草の上を渡る、風の明るさの波の強さ(0.0 = なし)
const PLAYER_SHADOW: f32 = 0.55;                     // 地面に落ちるプレイヤー・mob の影の濃さ(0.0 = 消す、1.0 = 標準どおり)

// ───── 調整用の値(空気・仕上げ) ─────
const HAZE_WARM: vec3f = vec3f(0.34, 0.18, 0.05);    // 太陽方向のかすみの色
const HAZE_POWER: f32 = 5.0;                         // 大きいほど、かすみが太陽の周りだけに絞られる
const SATURATION: f32 = 1.16;                        // 彩度(1.0 = そのまま)
const CONTRAST: f32 = 1.10;                          // コントラスト(1.0 = そのまま)
const SHOULDER_KNEE: f32 = 0.80;                     // これより明るい部分を、なだらかに丸める

// ───── 調整用の値(水) ─────
const WATER_SHALLOW: vec3f = vec3f(0.46, 0.88, 0.92);
const WATER_SHORE: vec3f = vec3f(0.40, 0.92, 0.82);  // 岸の浅いところの、明るい青緑
const WATER_DEEP: vec3f = vec3f(0.05, 0.28, 0.48);
const WATER_ABSORB: vec3f = vec3f(0.30, 0.10, 0.055);// 赤・緑・青の吸収(大きいほど早く消える)
const WATER_ALPHA_ABSORB: f32 = 0.22;                // 大きいほど、浅いうちに不透明になる
const WATER_BRIGHT: f32 = 1.30;                      // 水全体の明るさ(1.0 = そのまま)
const WATER_RIPPLE: f32 = 0.11;                      // 大きなさざ波の強さ
const WATER_MICRO: f32 = 0.12;                       // 細かいさざ波の強さ
const WATER_REFLECT: f32 = 0.72;                     // 空を映す強さ
const WATER_CLOUDS: f32 = 0.65;                      // 水面に映る雲の濃さ
const SUN_GLINT: f32 = 2.0;                          // 太陽の反射の強さ
const WATER_GLOW: f32 = 0.7;                         // 日なたの水の、内側からの青緑の明るさ
const WATER_RINGS: f32 = 1.0;                        // 水面に広がる波紋の強さ(0.0 = なし)
const WATER_RING_CELL: f32 = 2.6;                    // 波紋が起きる区画の大きさ(ブロック)
const WATER_RING_DENSITY: f32 = 0.75;                // 区画のうち、波紋が起きる割合
const WATER_SPLASH: f32 = 1.0;                       // 波紋の起きた瞬間の、水しぶき(白い泡)の強さ
const UNDERWATER_FX: f32 = 1.0;                      // 水中の演出(底の光の網目・青緑の色味)の強さ(0.0 = なし)

// ───── 小さな道具 ─────
fn luma(c: vec3f) -> f32 {
    return dot(c, vec3f(0.2126, 0.7152, 0.0722));
}

// 色の仕上げ: 彩度とコントラスト。
fn grade(c: vec3f) -> vec3f {
    let l = luma(c);
    var g = mix(vec3f(l), c, SATURATION);
    g = (g - vec3f(0.5)) * CONTRAST + vec3f(0.5);
    return max(g, vec3f(0.0));
}

// 明るい部分をなだらかに丸める。knee より暗い部分は、そのまま。
fn shoulder(x: vec3f) -> vec3f {
    let room = 1.0 - SHOULDER_KNEE;
    let over = max(x - vec3f(SHOULDER_KNEE), vec3f(0.0));
    return min(x, vec3f(SHOULDER_KNEE)) + room * (vec3f(1.0) - exp(-over / room));
}

// 太陽の向き。ゲームの空が「画像の空(スカイボックス)」のときは、太陽の向きが無い(ゼロ)ので、
// 影を落とす光の向き(標準の空の太陽。常に地平線より上)の逆向きで、代わりにする。
fn sunDirection() -> vec3f {
    let s = bloxdSunDirection();
    if (dot(s, s) < 0.0001) {
        return -bloxdShadowDirection();
    }
    return s;
}

// 太陽が地平線の上にあるほど 1(夜は 0)。
fn sunVisible(sun: vec3f) -> f32 {
    return smoothstep(-0.10, 0.12, sun.y);
}

// 朝夕(太陽が低い)ほど 1。
fn sunsetAmount(sun: vec3f) -> f32 {
    return (1.0 - smoothstep(0.05, 0.50, sun.y)) * sunVisible(sun);
}

// その面が属するワールドのブロック座標。
fn faceBlock(position: vec3f, normal: vec3f) -> vec3i {
    return vec3i(floor(position - normal * 0.5)) + bloxdRenderOffset();
}

// 整数の座標ごとに決まる、0〜1 の疑似乱数。
fn blockHash(p: vec3i) -> f32 {
    var h: u32 = u32(p.x) * 374761393u + u32(p.y) * 668265263u + u32(p.z) * 2147483647u;
    h = (h ^ (h >> 13u)) * 1274126177u;
    h = h ^ (h >> 16u);
    return f32(h & 65535u) / 65535.0;
}

fn hash21(p: vec2f) -> f32 {
    let q = fract(p * vec2f(123.34, 456.21));
    let r = q + vec2f(dot(q, q + vec2f(45.32, 45.32)));
    return fract(r.x * r.y);
}

// なめらかなノイズ(0〜1)。
fn vnoise(p: vec2f) -> f32 {
    let i = floor(p);
    let fr = fract(p);
    let u = fr * fr * (vec2f(3.0) - 2.0 * fr);
    let a = hash21(i);
    let b = hash21(i + vec2f(1.0, 0.0));
    let c = hash21(i + vec2f(0.0, 1.0));
    let d = hash21(i + vec2f(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// 3 段重ねのノイズ(0〜1 あたり)。
fn fbm(p: vec2f) -> f32 {
    return vnoise(p) * 0.55 + vnoise(p * 2.03 + vec2f(17.1, 9.2)) * 0.30 + vnoise(p * 4.11 + vec2f(3.7, 31.4)) * 0.15;
}

fn fogAmount(light: BloxdLightIn) -> f32 {
    return saturate(light.fogAlpha);
}

// 太陽の方向だけ、霧に暖色を足す。
fn addHaze(colour: vec3f, light: BloxdLightIn, sun: vec3f) -> vec3f {
    let view = normalize(light.position - bloxdEyePosition());
    let toward = pow(saturate(dot(view, sun)), HAZE_POWER) * sunVisible(sun);
    return colour + HAZE_WARM * toward * fogAmount(light) * (1.0 - underwaterAmount(light));
}

// 水中らしさ(0〜1): 霧が濃く、霧の色が暗い青緑のとき。エンジンの霧の色・濃さから、推定する。
fn underwaterAmount(light: BloxdLightIn) -> f32 {
    let fc = light.fogColour;
    let blueRatio = fc.z / max(fc.x, 0.02);
    return smoothstep(0.30, 0.70, light.fogAlpha) * smoothstep(1.8, 3.2, blueRatio) * (1.0 - smoothstep(0.50, 0.75, luma(fc))) * UNDERWATER_FX;
}

// 水中の底に揺れる、光の網目(コースティクス)。p は水平の位置、t は時間。
fn caustic(p: vec2f, t: f32) -> f32 {
    let a = sin(p.x * 3.0 + t * 1.3 + sin(p.y * 2.1 + t * 0.9) * 1.5);
    let b = sin(p.y * 3.3 - t * 1.1 + sin(p.x * 2.4 - t * 1.2) * 1.4);
    return pow(saturate(1.0 - abs(a + b) * 0.5), 5.0);
}

// 空気中の光の筋: 目からこの画素までの途中で、太陽が当たっている割合を数える。
fn shafts(light: BloxdLightIn, sun: vec3f, sunColour: vec3f) -> vec3f {
    let eye = bloxdEyePosition();
    let dist = distance(light.position, eye);
    let view = (light.position - eye) / max(dist, 0.001);
    let phase = 0.15 + 0.85 * pow(saturate(dot(view, sun)), 8.0);
    let sunny = (bloxdAirShadow(0.15) + bloxdAirShadow(0.35) + bloxdAirShadow(0.55) + bloxdAirShadow(0.75) + bloxdAirShadow(0.92)) * 0.2;
    let density = 1.0 - exp(-dist * SHAFT_DENSITY);
    let uw = underwaterAmount(light);
    let shaftColour = mix(sunColour, light.fogColour * 1.4, uw);
    return shaftColour * (density * sunny * phase * SHAFT * sunVisible(sun) * (1.0 - 0.4 * uw));
}

// 鉱石らしさ(0〜1): 色がはっきりしている粒(ダイヤ・エメラルド・金・ラピスなど)、または、とても明るい粒。
fn oreMask(rgb: vec3f) -> f32 {
    let mx = max(max(rgb.x, rgb.y), rgb.z);
    let mn = min(min(rgb.x, rgb.y), rgb.z);
    let colourful = smoothstep(0.18, 0.38, mx - mn);
    let bright = smoothstep(0.78, 0.95, mx);
    return max(colourful, bright);
}

// テクスチャの明るさ(高さの代わり)。uv は 0〜1 に収める(端で反対側にまわり込むと、境界に偽の段差ができる)。
// oreOn が 1 のとき、鉱石の粒は、さらに高く(出っ張って)扱う。
fn texHeight(textureId: u32, uv: vec2f, mip: f32, oreOn: f32) -> f32 {
    let rgb = bloxdTexel(textureId, clamp(uv, vec2f(0.0), vec2f(0.9999)), mip).rgb;
    return luma(rgb) + oreMask(rgb) * oreOn * ORE_RAISE;
}

// 面取りの高さの変化(0 → 1 になめらかに上がる坂の傾き)。x は縁からの距離。
fn bevelSlope(x: f32) -> f32 {
    let s = saturate(x / BEVEL_WIDTH);
    return 6.0 * s * (1.0 - s) / BEVEL_WIDTH;
}

// 凹凸 + 面取り: 表面の法線(xyz)と、明暗の補正(w、暗いほど負)を作る。
// 画面上の微分を使うので、条件分岐より前に呼ぶこと。
fn reliefInfo(light: BloxdLightIn) -> vec4f {
    let n = normalize(light.normal);
    let dp1 = dpdx(light.position);
    let dp2 = dpdy(light.position);
    let du1 = dpdx(light.uv);
    let du2 = dpdy(light.uv);

    let ts = vec2f(1.0) / max(vec2f(bloxdTextureSize(light.mipLevel)), vec2f(1.0));
    let f = fract(light.uv);
    let oreOn = select(0.0, 1.0, light.flags.rock);
    let h0 = texHeight(light.textureId, f, light.mipLevel, oreOn);
    let hl = texHeight(light.textureId, f - vec2f(ts.x, 0.0), light.mipLevel, oreOn);
    let hr = texHeight(light.textureId, f + vec2f(ts.x, 0.0), light.mipLevel, oreOn);
    let hd = texHeight(light.textureId, f - vec2f(0.0, ts.y), light.mipLevel, oreOn);
    let hu = texHeight(light.textureId, f + vec2f(0.0, ts.y), light.mipLevel, oreOn);

    // 遠くでは、細かい凹凸を消す(ちらつき防止)。
    let fade = 1.0 - smoothstep(0.4, 2.0, light.mipLevel);
    let slopeU = (hr - hl) * 0.5 / ts.x;
    let slopeV = (hu - hd) * 0.5 / ts.y;

    // 面取り: 置かれたブロック(不透明な立方体)の縁だけ。
    let onBlock = select(0.0, 1.0, light.flags.opaque && light.flags.placed);
    let bfade = onBlock * (1.0 - smoothstep(0.8, 2.5, light.mipLevel));
    let bevU = (bevelSlope(f.x) - bevelSlope(1.0 - f.x)) * BEVEL * bfade;
    let bevV = (bevelSlope(f.y) - bevelSlope(1.0 - f.y)) * BEVEL * bfade;

    // 画面上の微分から、uv の向きに沿った接線(tangent)と従接線(bitangent)を作る。
    let dp2perp = cross(dp2, n);
    let dp1perp = cross(n, dp1);
    let tangent = dp2perp * du1.x + dp1perp * du2.x;
    let bitangent = dp2perp * du1.y + dp1perp * du2.y;
    let inv = inverseSqrt(max(max(dot(tangent, tangent), dot(bitangent, bitangent)), 0.000000000001));

    let su = slopeU * RELIEF_DEPTH * fade + bevU;
    let sv = slopeV * RELIEF_DEPTH * fade + bevV;
    let bent = normalize(n - (tangent * inv * su + bitangent * inv * sv));

    let mean = (hl + hr + hd + hu) * 0.25;
    let edge = min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y));
    let crease = EDGE_DARK * (1.0 - smoothstep(0.0, 0.06, edge)) * bfade;
    return vec4f(bent, (h0 - mean) * fade * CAVITY - crease);
}

// 舞い落ちる葉の色: 緑 → 黄 → 橙 → 赤茶(pick は 0〜1)。
fn leafBitColour(pick: f32) -> vec3f {
    let i = i32(pick * 4.999);
    var palette = array<vec3f, 5>(
        vec3f(0.36, 0.62, 0.16), vec3f(0.50, 0.72, 0.20), vec3f(0.72, 0.78, 0.22), vec3f(0.88, 0.62, 0.18), vec3f(0.80, 0.38, 0.14)
    );
    return palette[i];
}

// 空中を舞い落ちる葉: この画素へ向かう視線に沿って、空中の区画(落ちながら動く)を調べて、葉(回る正方形)が視線を横切るなら、
// その色を、画素の手前に重ねる。頂点を動かさないので、strict のゲームでも効く。trees は、木の近さ(0 = 描かない)。
// 出典(仕組みの参考): ユーザーが共有してくれた別のシェーダーパックの、落ち葉の描き方。コードは、自分で書き直した。
fn floatingLeaves(c: vec3f, light: BloxdLightIn, trees: f32, sv: f32, sky: f32) -> vec3f {
    if (trees < 0.2 || LEAF_BITS <= 0.0) {
        return c;
    }
    let eye = bloxdEyePosition();
    let toSurface = light.position - eye;
    let surfaceDistance = length(toSurface);
    let d = toSurface / max(surfaceDistance, 0.001);
    let reach = min(surfaceDistance, 6.0);
    let t = bloxdSeconds();
    let fall = t * LEAF_BITS_FALL;
    var across = cross(d, vec3f(0.0, 1.0, 0.0));
    if (dot(across, across) < 0.0001) {
        across = vec3f(1.0, 0.0, 0.0);
    }
    across = normalize(across);
    let along = cross(across, d);
    let origin = vec3f(bloxdRenderOffset() % vec3i(3072));
    let stride = 6.0 / 8.0;
    for (var i = 0; i < 8; i++) {
        let s = (f32(i) + 0.5) * stride;
        if (s > reach + LEAF_BITS_CELL) {
            break;
        }
        // 区画の並びを、上へ動かす = 葉が、下へ落ちて見える。
        let sliding = eye + origin + d * s + vec3f(0.0, fall, 0.0);
        let cell = vec3i(floor(sliding / LEAF_BITS_CELL));
        if (blockHash(cell + vec3i(0, 0, 7919)) > LEAF_BITS_DENSITY) {
            continue;
        }
        let h2 = blockHash(cell + vec3i(11, 3, 5));
        let h3 = blockHash(cell + vec3i(-7, 13, 2));
        let phase = h2 * bloxdTau;
        let inCell = 0.25 + 0.5 * vec3f(h2, h3, blockHash(cell + vec3i(4, -9, 21)));
        let sway = vec3f(sin(t * 1.3 + phase), 0.0, cos(t * 0.9 + phase * 1.7)) * 0.7;
        let bit = (vec3f(cell) + inCell) * LEAF_BITS_CELL - vec3f(0.0, fall, 0.0) + sway - origin;
        let offset = bit - eye;
        let depth = dot(offset, d);
        if (depth < 0.3 || depth > surfaceDistance - 0.05) {
            continue;
        }
        let off = offset - d * depth;
        var on = vec2f(dot(off, across), dot(off, along));
        // 回りながら、ひらひら(幅が伸び縮み)。
        let spin = t * 1.6 + phase;
        on = vec2f(cos(spin) * on.x - sin(spin) * on.y, sin(spin) * on.x + cos(spin) * on.y);
        let flip = max(abs(cos(t * 2.2 + phase * 2.3)), 0.25);
        if (abs(on.x) < LEAF_BITS_SIZE * flip && abs(on.y) < LEAF_BITS_SIZE) {
            let colour = leafBitColour(h3);
            let lit = colour * (0.30 + 0.45 * sv) * (0.45 + 0.55 * sky) + colour * 0.10;
            return mix(c, lit, saturate(LEAF_BITS));
        }
    }
    return c;
}


// 雪: 雪(白くて色の薄い面)を見ているとき、その手前の空中を、細かな白い粒が、ゆっくり、ゆらゆらと降る。
// 葉と同じく、視線に沿って区画を調べる仕組みなので、strict のゲームでも効く。
fn snowFlakes(c: vec3f, light: BloxdLightIn, amount: f32, sv: f32, sky: f32) -> vec3f {
    if (amount < 0.2 || SNOW_FALL <= 0.0) {
        return c;
    }
    let eye = bloxdEyePosition();
    let toSurface = light.position - eye;
    let surfaceDistance = length(toSurface);
    let d = toSurface / max(surfaceDistance, 0.001);
    let reach = min(surfaceDistance, 26.0);
    let t = bloxdSeconds();
    let fall = t * SNOW_FALL_SPEED;
    var across = cross(d, vec3f(0.0, 1.0, 0.0));
    if (dot(across, across) < 0.0001) {
        across = vec3f(1.0, 0.0, 0.0);
    }
    across = normalize(across);
    let along = cross(across, d);
    let origin = vec3f(bloxdRenderOffset() % vec3i(3072));
    for (var i = 0; i < 12; i++) {
        let s = (f32(i) + 0.5) * 2.2;
        if (s > reach + SNOW_CELL) {
            break;
        }
        let sliding = eye + origin + d * s + vec3f(0.0, fall, 0.0);
        let cell = vec3i(floor(sliding / SNOW_CELL));
        if (blockHash(cell + vec3i(5, 0, 313)) > SNOW_DENSITY) {
            continue;
        }
        let h2 = blockHash(cell + vec3i(17, 5, 9));
        let h3 = blockHash(cell + vec3i(-3, 19, 6));
        let phase = h2 * bloxdTau;
        let inCell = 0.2 + 0.6 * vec3f(h2, h3, blockHash(cell + vec3i(8, -4, 27)));
        let sway = vec3f(sin(t * 0.8 + phase), 0.0, cos(t * 0.6 + phase * 1.3)) * 0.35;
        let bit = (vec3f(cell) + inCell) * SNOW_CELL - vec3f(0.0, fall, 0.0) + sway - origin;
        let offset = bit - eye;
        let depth = dot(offset, d);
        if (depth < 0.3 || depth > surfaceDistance - 0.05) {
            continue;
        }
        let off = offset - d * depth;
        let on = vec2f(dot(off, across), dot(off, along));
        let size = SNOW_SIZE * (0.8 + 0.6 * h3);
        let r2 = dot(on, on);
        if (r2 < size * size) {
            // 雪の結晶: 6 本の腕(ゆっくり回る)+ 中心の丸み
            let ang = atan2(on.y, on.x) + t * 0.6 + phase;
            let arm = pow(abs(cos(3.0 * ang)), 6.0);
            let reach = size * (0.34 + 0.66 * arm);
            if (r2 < reach * reach) {
                let lit = vec3f(0.92, 0.95, 1.0) * (0.55 + 0.45 * sv) * (0.5 + 0.5 * sky) + vec3f(0.06);
                return mix(c, lit, saturate(SNOW_FALL) * 0.9);
            }
        }
    }
    return c;
}

// ───── 光の仕上げ(地形とモデルで共通) ─────
// modelMix: 0 = 地形(ブロック)、1 = モデル(プレイヤー・mob・アイテム)。
// モデルは、テクスチャの凹凸・くぼみ・強い影・強いコントラストを使わない(ごちゃついて、暗く見えるため)。
fn shade(surface: BloxdSurface, light: BloxdLightIn, modelMix: f32) -> vec3f {
    // 凹凸(微分を使うので、最初に呼ぶ)。
    let rel = reliefInfo(light);
    let rn = mix(rel.xyz, normalize(light.normal), modelMix);
    let cavity = rel.w * (1.0 - modelMix);

    let sun = sunDirection();
    let sv = sunVisible(sun);
    let warmth = sunsetAmount(sun);
    let sunColour = mix(vec3f(1.0, 0.96, 0.88), vec3f(1.0, 0.60, 0.30), warmth);
    let lightColour = mix(vec3f(0.60, 0.70, 1.00), sunColour, sv);
    let towardLight = -bloxdShadowDirection();
    let t = bloxdSeconds();
    let wp = bloxdWorldPosition(light.position);
    let n = normalize(light.normal);
    let eyeDist = distance(light.position, bloxdEyePosition());
    let view = normalize(light.position - bloxdEyePosition());
    let toEye = -view;
    let sky = light.skyLight;

    // 日が当たっている割合: 標準の光のうち、直射が占める割合 × 影。
    // 影: 精密な影(bloxdShadow)と、ブロックだけが作る影(bloxdAirShadow)がある。
    //   地形: プレイヤー・mob の影は、PLAYER_SHADOW の濃さで落とす(ブロックの影は、そのまま)。
    //   モデル: プレイヤー・mob 自身の影(自分の体に落ちるごちゃついた影)は使わず、ブロックの影だけを、少し薄めて使う。
    let shading = bloxdShading(light);
    let directPart = light.directional * light.diffuse;
    let share = saturate(luma(directPart) / max(luma(shading), 0.001));
    let shadowFull = bloxdShadow();
    let shadowBlocks = bloxdAirShadow(clamp(1.0 - 0.4 / max(eyeDist, 0.5), 0.0, 1.0));
    let blocksOnly = max(shadowFull, shadowBlocks);
    let shadowMix = mix(blocksOnly, shadowFull, PLAYER_SHADOW * (1.0 - modelMix));
    let shadow = mix(1.0, shadowMix, SHADOW_STRENGTH * mix(1.0, 0.7, modelMix));
    // 木の下(ブロックの影の中で、空の光は届いている所): 動く木漏れ日の斑点が、日向になる。
    let canopy = (1.0 - shadowBlocks) * sv * smoothstep(0.85, 0.99, sky);
    let dappleSpots = smoothstep(0.55, 0.75, vnoise(wp.xz * 0.7 + vec2f(t * 0.25, t * 0.10)));
    let sunny = max(share * shadow, canopy * dappleSpots * DAPPLE * share);

    // 雲の影: 日向の光だけを、ゆっくり暗くする。
    let cloudNoise = fbm(wp.xz * CLOUD_SCALE + vec2f(t * CLOUD_SPEED, t * CLOUD_SPEED * 0.35));
    let cloud = smoothstep(0.50, 0.78, cloudNoise);
    let sunLeft = 1.0 - CLOUD_SHADOW * cloud * sv;

    // 標準の光(エンジンの計算そのまま)を土台にする。
    var c = bloxdLitColour(surface, light);

    // 凹凸・面取りで、太陽の当たり方を変える。影の部分は、直射のぶんを引く。
    let lam0 = saturate(dot(n, towardLight));
    let lam1 = saturate(dot(rn, towardLight));
    let ratio = mix(1.0, clamp(lam1 / max(lam0, 0.25), 0.25, 1.9), step(0.05, lam0));
    c = c * ((1.0 - share) + share * ratio * shadow);

    // 日向をさらに明るく: 日向と影の差(コントラスト)が出て、陽ざしの強さが出る。
    c = c * (1.0 + SUN_BOOST * sunny * sv * (1.0 - 0.7 * modelMix));

    // 日向は暖色(雲の影のぶん暗く)、日陰は寒色(空の光が届く所だけ)。
    c = c * mix(vec3f(1.0), mix(SUN_WARM, SUNSET_WARM, warmth), sunny);
    c = c * mix(vec3f(1.0), vec3f(sunLeft), sunny);
    c = c * mix(vec3f(1.0), SHADOW_COOL, (1.0 - sunny) * sky);

    // 空と地面からの回り込み光(上向き = 空の青、下向き = 地面の暖かみ)。
    let hemi = rn.y * 0.5 + 0.5;
    c = c * mix(vec3f(1.0), mix(GROUND_BOUNCE, SKY_FILL, hemi), sky * (1.0 - sunny * 0.6));

    // 草の上を、風で、明るい波が渡る(日向のとき)。strict でも、風の動きが見える。
    let grassTop = select(0.0, 1.0, light.flags.dirt && light.flags.vegetation) * smoothstep(0.5, 0.9, n.y);
    let gustWave = smoothstep(0.55, 1.0, sin(dot(wp.xz, vec2f(0.6, 0.8)) * 0.3 - t * 1.6 + vnoise(wp.xz * 0.08) * 4.0));
    c = c * (1.0 + grassTop * gustWave * GUST * sunny);

    // くぼみ・縁の溝は暗く、出っ張りは明るく。
    c = c * (1.0 + clamp(cavity, -0.45, 0.45));

    // 水中: 青緑の色味と、底に揺れる光の網目。
    let uw = underwaterAmount(light);
    c = mix(c, c * vec3f(0.72, 1.0, 1.10), uw * 0.6);
    c = c + vec3f(0.30, 0.62, 0.66) * caustic(wp.xz * 1.1 + wp.y * 0.4, t) * uw * saturate(n.y * 0.7 + 0.3) * (0.4 + 0.6 * sky) * 0.45;

    // 光源の色の光だまり: 光の色(溶岩 = オレンジ、クリスタル = 緑 …)を濃くして、素材にのせる。
    let bl = light.blockLight;
    let blMax = max(max(bl.x, bl.y), max(bl.z, 0.0001));
    let vivid = pow(bl / blMax, vec3f(SPILL_VIVID));
    let flicker = 1.0 + 0.07 * sin(t * 6.5 + dot(floor(wp), vec3f(1.7, 2.3, 1.1)));
    c = c + surface.colour * vivid * pow(blMax, 1.2) * SPILL * flicker * (1.0 - 0.5 * sunny);

    // つや: 太陽(夜は月)の反射。岩は硬く、葉っぱは広く弱く。
    let halfv = normalize(towardLight + toEye);
    let ndh = saturate(dot(rn, halfv));
    let sunTerm = sunny * sunLeft;
    var spec: f32 = 0.0;
    if (light.flags.rock) {
        // 岩: 硬いつや。鉱石の粒は、宝石のように鋭く輝く。
        let tex = bloxdTexel(light.textureId, clamp(fract(light.uv), vec2f(0.0), vec2f(0.9999)), light.mipLevel).rgb;
        let ore = oreMask(tex);
        spec = pow(ndh, 40.0) * SPEC_ROCK + ore * pow(ndh, 24.0) * ORE_SHINE;
    }
    if (light.flags.vegetation) {
        spec = pow(ndh, 9.0) * SPEC_LEAF;
    }
    // アイテム(手に持った・落ちている・飛んでいる): 色のはっきりした部分(ダイヤ・宝石)を、鋭く輝かせる。
    if (light.flags.held || light.flags.dropped || light.flags.thrown) {
        let tex = bloxdTexel(light.textureId, clamp(fract(light.uv), vec2f(0.0), vec2f(0.9999)), light.mipLevel).rgb;
        let gem = smoothstep(0.30, 0.55, max(max(tex.x, tex.y), tex.z) - min(min(tex.x, tex.y), tex.z));
        spec = spec + gem * pow(ndh, 20.0) * ORE_SHINE * 1.5;
    }
    // 金属の質感(アイテム・防具・mob): テクスチャの色から、金属(明るい灰色 = 鉄・銀、黄色 = 金)を見つけて、
    // 空の映り込み(縁ほど強く)と、太陽の鋭い反射を足す。色見本のアイテムは、面ごとにべた塗りなので、画像では質感を出せない。それを、ここで補う。
    if (modelMix > 0.5) {
        let metalTex = bloxdTexel(light.textureId, clamp(fract(light.uv), vec2f(0.0), vec2f(0.9999)), light.mipLevel).rgb;
        let mtMax = max(max(metalTex.x, metalTex.y), metalTex.z);
        let mtSat = mtMax - min(min(metalTex.x, metalTex.y), metalTex.z);
        let steel = smoothstep(0.42, 0.68, luma(metalTex)) * (1.0 - smoothstep(0.10, 0.24, mtSat));
        let goldish = smoothstep(0.22, 0.40, mtSat) * smoothstep(0.35, 0.60, metalTex.x) * step(metalTex.z, metalTex.y * 0.75);
        let metal = max(steel, goldish) * METAL_SHEEN;
        let reflDir = reflect(view, rn);
        let envUp = saturate(reflDir.y);
        let envColour = mix(light.fogColour, light.fogColour * vec3f(0.65, 0.85, 1.35), envUp) * (0.35 + 0.65 * sky);
        let edgeK = pow(1.0 - saturate(dot(rn, toEye)), 3.0);
        c = c + mix(vec3f(1.0), metalTex * 1.6, goldish) * envColour * metal * (0.15 + 0.5 * edgeK);
        c = c + lightColour * metal * pow(ndh, 60.0) * 0.9 * sunTerm;
    }
    c = c + lightColour * spec * sunTerm;

    // 砂: 細かな粒が、ときどききらめく。
    if (light.flags.sand) {
        let g = blockHash(vec3i(floor(wp * 14.0)));
        let sparkle = step(0.988, g) * (0.3 + 0.7 * pow(ndh, 6.0));
        c = c + lightColour * sparkle * GLITTER * sunTerm;
    }

    // 葉っぱ: 太陽に向かって見ると透けて光る。明るい葉(薄い葉)ほど、よく透ける。
    if (light.flags.vegetation) {
        let thin = 0.35 + luma(surface.colour) * 1.4;
        let against = pow(saturate(dot(view, sun)), 2.5);
        c = c + surface.colour * LEAF_GLOW * against * thin * sky * sv * sunLeft * shadow;
    }

    // 斜めの面は、空の色をうっすら映す。
    let rim = pow(1.0 - saturate(dot(n, toEye)), 4.0);
    c = c + light.fogColour * rim * RIM_SKY * sky;

    // 明るい部分を丸めて、色を仕上げる。発光は、そのあとに足す(丸めない)。
    // (モデルは、コントラストを掛けず、暗くしない。)
    c = mix(grade(shoulder(c)), shoulder(c), modelMix * 0.7) + surface.emission;

    // 霧(エンジンの式)、光の筋、太陽方向のかすみ。
    var o = bloxdApplyFog(c, light);
    o = o + shafts(light, sun, sunColour);
    o = addHaze(o, light, sun);

    // 空中を舞い落ちる葉(葉のブロックを見ているときだけ。草のブロック・屋根の下には出さない)。モデル(プレイヤーなど)には、描かない。
    let foliage = select(0.0, 1.0, light.flags.vegetation && !light.flags.dirt);
    let withLeaves = floatingLeaves(o, light, foliage * (1.0 - modelMix), sv, sky);
    // 雪: 白くて色の薄い面(雪のブロック)を見ているとき。
    let alb = surface.colour;
    let hi = max(alb.r, max(alb.g, alb.b));
    let lo = min(alb.r, min(alb.g, alb.b));
    // 雪のブロックだけ: とても明るく、わずかに青い(B − R が 0.02〜0.075)。白い羊毛・コンクリート・石英(青みなし / 黄みあり)・月光石(青すぎる)は、除く。
    let blueBias = alb.b - alb.r;
    let snowy = smoothstep(0.84, 0.90, luma(alb)) * smoothstep(0.020, 0.035, blueBias) * (1.0 - smoothstep(0.070, 0.095, blueBias)) * (1.0 - smoothstep(0.06, 0.12, hi - lo)) * (1.0 - modelMix);
    return snowFlakes(withLeaves, light, snowy, sv, sky);
}

// ───── 地形(水とモデル以外のブロック) ─────
#ifndef BLOXD_STRICT
// 葉っぱ: 風でわずかにゆれる。隣のブロックと共有する頂点は、同じ位置関数でずらすので、すき間はできない。
// strict なゲームでは、頂点を動かせないので、この関数ごと使わない。
fn bloxdTerrainVertex(vertex: BloxdVertexIn) -> BloxdVertex {
    var v: BloxdVertex = bloxdDefaultVertex(vertex);
    if (vertex.flags.vegetation && !vertex.flags.dirt) {
        let wp = bloxdWorldPosition(vertex.position);
        let t = bloxdSeconds();
        let gust = 0.75 + 0.25 * sin(t * 0.37 + wp.x * 0.05 + wp.z * 0.03);
        let sway = vec3f(
            sin(t * 2.6 + wp.x * 0.9 + wp.y * 0.7),
            0.35 * sin(t * 3.4 + wp.z * 1.1 + wp.x * 0.5),
            sin(t * 2.1 + wp.z * 0.8 + wp.y * 0.6)
        );
        v.position = vertex.position + sway * LEAF_SWAY * gust;
    }
    return v;
}
#endif

#ifndef BLOXD_STRICT
// 草・花・作物などの平面の植物: 風でゆれる。上の頂点ほど大きく、根もとは動かさない。
fn bloxdModelVertex(vertex: BloxdVertexIn) -> BloxdVertex {
    var v: BloxdVertex = bloxdDefaultVertex(vertex);
    if (vertex.flags.placed && (vertex.flags.flat || vertex.flags.vegetation) && !vertex.flags.slab && !vertex.flags.stairs) {
        let wp = bloxdWorldPosition(vertex.position);
        let t = bloxdSeconds();
        // 高さの割合: モデルの座標があればそれを、なければ、ブロック内の高さを使う。
        let ly = vertex.localPosition.y;
        let wLocal = saturate(ly / select(1.0, 16.0, abs(ly) > 1.5));
        let wWorld = fract(wp.y + 0.001);
        let hasLocal = step(0.0001, dot(vertex.localPosition, vertex.localPosition));
        // 根もと(高さ 0)でも、3 割強は動かす。高さの推定が外れても、植物全体が、ゆれて見えるように。
        let w = mix(0.35, 1.0, mix(wWorld, wLocal, hasLocal));
        let gust = 0.75 + 0.25 * sin(t * 0.43 + wp.x * 0.06 + wp.z * 0.04);
        let sway = vec3f(
            sin(t * 3.2 + wp.x * 1.3 + wp.z * 0.9),
            0.0,
            sin(t * 2.7 + wp.z * 1.1 - wp.x * 0.7)
        );
        v.position = vertex.position + sway * PLANT_SWAY * gust * w * (0.4 + 0.6 * w);
    }
    return v;
}
#endif

fn bloxdTerrainSurface(surface: BloxdSurfaceIn) -> BloxdSurface {
    var s: BloxdSurface = bloxdDefaultSurface(surface);
    let wp = bloxdWorldPosition(surface.position);

#ifndef BLOXD_STRICT
    // 葉っぱ: 黒い(透明な)部分を、透かす。strict なゲームでは、discard が禁止なので、この処理は使わない。
    if (surface.flags.vegetation && !surface.flags.dirt) {
        let leafTexel = bloxdTexel(surface.textureId, clamp(fract(surface.uv), vec2f(0.0), vec2f(0.9999)), min(surface.mipLevel, 1.0));
        if (leafTexel.a < 0.5 || luma(leafTexel.rgb) < LEAF_CUTOUT) {
            discard;
        }
    }
#endif

    if (surface.flags.emissive) {
        // 光る素材: 素材そのものの色で光る。明るい部分(溶岩の筋、クリスタルの面)ほど強く。
        let l = luma(surface.colour);
        let glow = mix(vec3f(l), surface.colour, GLOW_SATURATION);
        let veins = smoothstep(0.25, 0.85, l);
        let b = faceBlock(surface.position, surface.normal);
        let pulse = 0.5 + 0.5 * sin(bloxdSeconds() * 1.6 + f32(b.x + b.z) * 0.7);
        let breathe = 1.0 + EMISSIVE_PULSE * (pulse * 2.0 - 1.0);
        s.emission = glow * (GLOW_BASE + GLOW_PEAK * veins) * breathe;
    } else {
        // 普通のブロック: 大きな起伏 + ブロックごと + 細かな粒、の 3 段で色をゆらす。
        let h = blockHash(faceBlock(surface.position, surface.normal));
        let tone = fbm(wp.xz * 0.045 + vec2f(wp.y * 0.03, wp.y * 0.017));
        let grain = blockHash(vec3i(floor(wp * 16.0)));
        let k = 1.0 + (tone - 0.5) * 2.0 * LARGE_VARIATION + (h - 0.5) * 2.0 * BLOCK_VARIATION + (grain - 0.5) * 2.0 * GRAIN;
        var col = surface.colour * k;
        // 植物: 起伏に合わせて、緑が少し黄色寄り・青緑寄りにゆれる。
        if (surface.flags.vegetation) {
            col = col * mix(vec3f(0.93, 1.02, 0.90), vec3f(1.07, 1.02, 0.88), tone);
            // 葉っぱ(草ブロック以外): 葉の 1 枚ごとに、明るさと黄緑の度合いが少し違う。
            if (!surface.flags.dirt) {
                let leaf = blockHash(vec3i(floor(wp * 8.0)) + vec3i(7, 3, 5));
                col = col * (1.0 + (leaf - 0.5) * 2.0 * LEAF_DAPPLE);
            }
        }
        s.colour = col;
        // 鉱石: 色のはっきりした粒・明るい粒(ダイヤの水色など)が、ほんのり自分で光る。
        if (surface.flags.rock) {
            let oreTex = bloxdTexel(surface.textureId, clamp(fract(surface.uv), vec2f(0.0), vec2f(0.9999)), surface.mipLevel).rgb;
            s.emission = oreTex * oreMask(oreTex) * ORE_GLOW;
        }
    }
    return s;
}

fn bloxdTerrainLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    var o: BloxdLight = bloxdDefaultLight(surface, light);
    o.colour = shade(surface, light, 0.0);
    return o;
}

// ───── モデル(プレイヤー・アイテム・mob・スラブなど) ─────
// アイテム(手に持った・落ちている・飛んでいる)の、色のはっきりした部分(ダイヤ・宝石)が、ほんのり自分で光る。
fn bloxdModelSurface(surface: BloxdSurfaceIn) -> BloxdSurface {
    var s: BloxdSurface = bloxdDefaultSurface(surface);
    if (surface.flags.held || surface.flags.dropped || surface.flags.thrown) {
        let itemTex = bloxdTexel(surface.textureId, clamp(fract(surface.uv), vec2f(0.0), vec2f(0.9999)), surface.mipLevel).rgb;
        let gem = smoothstep(0.30, 0.55, max(max(itemTex.x, itemTex.y), itemTex.z) - min(min(itemTex.x, itemTex.y), itemTex.z));
        s.emission = itemTex * gem * ORE_GLOW * 0.35;
    }
    return s;
}

// 光の仕上げは地形と共通だが、モデル用に、凹凸・強い影・強いコントラストは使わない(modelMix = 1)。
fn bloxdModelLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    var o: BloxdLight = bloxdDefaultLight(surface, light);
    o.colour = shade(surface, light, 1.0);
    return o;
}

// ───── 液体(水) ─────
// 波紋と水しぶき: 区画ごとに、ときどき、水面の 1 点に水滴が落ちたことにして、輪が広がる(波の傾きを返す)。
// 戻り値: xy = 波の傾き、z = 水しぶき(落ちた瞬間の白い泡と、輪の頂の泡)。
fn rippleField(p: vec2f, t: f32) -> vec3f {
    var acc = vec3f(0.0);
    let base = floor(p / WATER_RING_CELL);
    for (var j = -1; j <= 1; j++) {
        for (var i = -1; i <= 1; i++) {
            let cell = base + vec2f(f32(i), f32(j));
            if (hash21(cell + vec2f(31.7, 7.3)) > WATER_RING_DENSITY) {
                continue;
            }
            let h2 = hash21(cell + vec2f(5.1, 19.9));
            let h3 = hash21(cell + vec2f(13.3, 2.7));
            let period = 2.6 + 2.0 * h2;
            let tt = t + h3 * period * 7.0;
            let k = floor(tt / period);
            let age = tt - k * period;
            if (age > 2.3) {
                continue;
            }
            let hx = hash21(cell + vec2f(k * 1.37, 3.9));
            let hy = hash21(cell + vec2f(8.2, k * 2.11));
            let centre = (cell + vec2f(0.2 + 0.6 * hx, 0.2 + 0.6 * hy)) * WATER_RING_CELL;
            let off = p - centre;
            let d = length(off);
            let radius = age * 0.85;
            let x = d - radius;
            let w = 0.17;
            let env = exp(-(x * x) / (2.0 * w * w));
            let fade = saturate(1.0 - age / 2.3);
            let dh = env * (-(x / (w * w)) * cos(x * 24.0) - 24.0 * sin(x * 24.0));
            acc = vec3f(acc.xy + (off / max(d, 0.001)) * dh * fade * fade * 0.0040, acc.z);
            // 水しぶき: 落ちた瞬間の泡(中心)と、最初の輪の頂の泡
            let born = saturate(1.0 - age / 0.45);
            acc.z += exp(-d * d / 0.03) * born + env * saturate(1.0 - age / 1.1) * 0.35;
        }
    }
    return acc;
}

// 水面の法線: 6 つの大きな波 + 細かいさざ波。p は水平の位置、t は時間、detail は細かさの度合い(遠くは 0)。
fn waterNormal(p: vec2f, t: f32, detail: f32) -> vec3f {
    let k1 = vec2f(1.30, 0.50);
    let k2 = vec2f(-0.70, 1.60);
    let k3 = vec2f(2.90, -1.70);
    let k4 = vec2f(-3.80, -3.10);
    let k5 = vec2f(5.60, 4.20);
    let k6 = vec2f(-6.30, 2.40);
    let g = k1 * (0.50 * cos(dot(p, k1) + t * 1.10))
          + k2 * (0.30 * cos(dot(p, k2) + t * 1.70))
          + k3 * (0.15 * cos(dot(p, k3) + t * 2.30))
          + k4 * (0.08 * cos(dot(p, k4) + t * 3.10))
          + k5 * (0.04 * cos(dot(p, k5) + t * 3.90))
          + k6 * (0.03 * cos(dot(p, k6) + t * 4.60));

    // 細かいさざ波: ノイズの傾きから作る。
    let e = 0.12;
    let flow = vec2f(t * 0.6, -t * 0.45);
    let q = p * 5.0 + flow;
    let m0 = vnoise(q);
    let mx = vnoise(q + vec2f(e * 5.0, 0.0));
    let my = vnoise(q + vec2f(0.0, e * 5.0));
    let micro = vec2f(mx - m0, my - m0) / e * WATER_MICRO * detail;

    let rg = rippleField(p, t).xy * WATER_RINGS * detail;
    return normalize(vec3f(-(g.x * WATER_RIPPLE + micro.x + rg.x), 1.0, -(g.y * WATER_RIPPLE + micro.y + rg.y)));
}

// 水面に映る空: 水平線は霧の色、上は青く。薄い雲と、太陽のまわりのぼんやりした光。
fn waterSky(r: vec3f, light: BloxdLightIn, sun: vec3f, sunColour: vec3f, t: f32) -> vec3f {
    let sv = sunVisible(sun);
    let up = saturate(r.y);
    var col = mix(light.fogColour, light.fogColour * vec3f(0.65, 0.85, 1.35), pow(up, 0.6));
    // 雲: 視線の向きを、空の平面に投げて、ノイズを引く。
    let cp = r.xz / (r.y + 0.25) * 0.9 + vec2f(t * 0.02, t * 0.008);
    let cl = smoothstep(0.52, 0.80, fbm(cp)) * smoothstep(0.02, 0.25, r.y);
    let cloudColour = mix(light.fogColour * 1.1, sunColour * 0.95 + vec3f(0.1), sv * 0.6);
    col = mix(col, cloudColour, cl * WATER_CLOUDS);
    col = col + sunColour * pow(saturate(dot(r, sun)), 12.0) * 0.25 * sv;
    return col * (0.35 + 0.65 * light.skyLight);
}

fn bloxdLiquidSurface(surface: BloxdSurfaceIn) -> BloxdSurface {
    var s: BloxdSurface = bloxdDefaultSurface(surface);

    // 水の厚み: 目から水面までと、水の向こうの不透明なものまでの差。
    var thickness: f32 = 6.0;
#ifdef BLOXD_SCENE_DEPTH
    let behind = bloxdOpaqueBehind();
    if (behind.hit) {
        thickness = max(behind.distance - distance(surface.position, bloxdEyePosition()), 0.0);
    }
#endif

    // 色: 波長ごとに吸収が違う。赤から先に消えて、深いほど青緑 → 濃い青になる。岸の浅いところは明るい青緑。
    let transmit = exp(-thickness * WATER_ABSORB);
    let tinted = mix(surface.colour * 1.3, WATER_SHALLOW, 0.7);
    var colour = mix(WATER_DEEP, tinted, transmit);
    colour = mix(colour, WATER_SHORE, (1.0 - smoothstep(0.0, 2.5, thickness)) * 0.28);

    // 岸の泡: 浅いところだけ。波打ち際に沿って、動く筋になる。
    let wp = bloxdWorldPosition(surface.position);
    let t = bloxdSeconds();
    let foamBand = 1.0 - smoothstep(0.0, 0.55, thickness);
    let flicker = 0.55 + 0.45 * vnoise(wp.xz * 3.2 + vec2f(t * 0.6, -t * 0.4));
    let rings = 0.55 + 0.45 * sin(thickness * 16.0 - t * 1.8 + vnoise(wp.xz * 2.0) * 5.0);
    let foam = foamBand * flicker * rings;
    colour = mix(colour, vec3f(0.92, 0.98, 1.0), foam * 0.6);
    s.colour = colour;
    s.emission = vec3f(0.55, 0.60, 0.62) * foam * 0.20;

#ifdef BLOXD_ALPHA
    // 浅いほど透明、深いほど不透明に。
    let depthK = 1.0 - exp(-thickness * WATER_ALPHA_ABSORB);
    s.alpha = clamp(mix(surface.alpha * 0.45, min(surface.alpha * 1.15 + 0.05, 0.88), depthK), 0.0, 1.0);
#endif
    return s;
}

fn bloxdLiquidLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    var o: BloxdLight = bloxdDefaultLight(surface, light);

    let sun = sunDirection();
    let sv = sunVisible(sun);
    let t = bloxdSeconds();
    let wp = bloxdWorldPosition(light.position);
    let clear = 1.0 - fogAmount(light);
    let sky = light.skyLight;
    let sunColour = mix(vec3f(1.0, 0.96, 0.88), vec3f(1.0, 0.60, 0.30), sunsetAmount(sun));
    let eyeDist = distance(light.position, bloxdEyePosition());

    // さざ波: 水面(上向きの面)だけ、法線を揺らす。遠くは、細かいさざ波を消す(ちらつき防止)。
    var n = normalize(light.normal);
    if (abs(light.normal.y) > 0.5) {
        n = waterNormal(wp.xz, t, 1.0 - smoothstep(25.0, 70.0, eyeDist));
    }

    let view = normalize(light.position - bloxdEyePosition());
    let facing = saturate(dot(-view, n));
    let fresnel = 0.02 + 0.98 * pow(1.0 - facing, 5.0);

    // 空と雲の反射。
    let refl = reflect(view, n);
    let r = vec3f(refl.x, abs(refl.y), refl.z);
    var c = mix(o.colour, waterSky(r, light, sun, sunColour, t), fresnel * WATER_REFLECT * clear);

    // 日なたの水は、内側からうっすら青緑に光る。
    c = c + vec3f(0.02, 0.10, 0.12) * WATER_GLOW * sky * sv * clear;

    // 太陽: ふんわりした照り返し + 鋭いきらめき + 細かくちらつく光の粒。
    let towardSun = saturate(dot(r, sun));
    let gate = hash21(floor(wp.xz * 7.0) + vec2f(floor(t * 2.0), 3.0));
    let twinkle = step(0.90, gate) * pow(towardSun, 40.0) * 1.6;
    let glint = (pow(towardSun, 220.0) * SUN_GLINT + pow(towardSun, 24.0) * 0.22 + twinkle) * sky * sv * clear;
    c = c + sunColour * glint;
    // 水しぶき(泡): 水面の上向きの面だけ。
    if (abs(light.normal.y) > 0.5 && eyeDist < 60.0) {
        let foam = saturate(rippleField(wp.xz, t).z) * WATER_SPLASH * WATER_RINGS;
        c = mix(c, vec3f(0.92, 0.97, 1.0) * (0.45 + 0.55 * sky) * (0.6 + 0.4 * sv), foam * 0.55 * clear);
    }

    c = mix(c, grade(shoulder(c * WATER_BRIGHT)), clear);
    c = c + shafts(light, sun, sunColour);
    o.colour = addHaze(c, light, sun);

    // 水の中から、水面を見上げたとき: 真上は窓のように空が見え、斜めは全反射で、青緑の鏡になる。
    let eyeSide = dot(normalize(light.normal), -view);
    if (eyeSide < 0.0) {
        let nEye = -n;
        let tr = refract(view, nEye, 1.333);
        let tir = select(0.0, 1.0, dot(tr, tr) < 0.0001);
        let skyThrough = waterSky(vec3f(tr.x, abs(tr.y), tr.z), light, sun, sunColour, t);
        let mirror = vec3f(0.05, 0.32, 0.45) * (0.4 + 0.6 * sky);
        let shimmer = 0.85 + 0.15 * sin(t * 1.4 + wp.x * 2.0 + wp.z * 1.7);
        let ceiling = mix(skyThrough * 0.95, mirror * shimmer, tir);
        o.colour = mix(ceiling, light.fogColour, fogAmount(light) * 0.5);
    }
    return o;
}
