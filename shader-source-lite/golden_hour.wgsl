// Golden Hour Lite 2: 本当に軽い版(本編の簡略化ではなく、最小の手書き)。
//
// 軽さの理由: 影(bloxdShadow / bloxdAirShadow)を、1 回も呼ばない。 テクスチャの追加の読み出し・ノイズ・繰り返しも、無い。
//   やること = エンジンの標準の光 + 色の仕上げ(日向は暖色、日陰は寒色、彩度・コントラスト)+ 水の色と、空の映り込み(固定の計算だけ)。
// 本編との違い: 影の濃さ・形は、エンジンの標準のまま(このパックでは、変えない)。 落ち葉・雪・波紋・凹凸・光の筋・雲の影・金属の質感は、無い。
// strict でも効く(頂点を動かさない、discard なし)。 名前は "bloxd" で始められない(エンジン予約)。

const SATURATION: f32 = 1.14;                        // 彩度(1.0 = そのまま)
const CONTRAST: f32 = 1.07;                          // コントラスト(1.0 = そのまま)
const SUN_WARM: vec3f = vec3f(1.08, 0.99, 0.86);     // 日向の色味(掛け算)
const SHADE_COOL: vec3f = vec3f(0.90, 0.96, 1.08);   // 日陰の色味(掛け算)
const WATER_TINT: vec3f = vec3f(0.30, 0.82, 0.88);   // 水の色(青緑)
const WATER_MIX: f32 = 0.45;                         // 水の色を、どれだけ、混ぜるか
const WATER_SKY: f32 = 0.55;                         // 斜めから見たときの、空の映り込みの強さ

fn liteLuma(c: vec3f) -> f32 {
    return dot(c, vec3f(0.2126, 0.7152, 0.0722));
}

// 色の仕上げ。sun = 日向の度合い(0〜1)。
fn liteGrade(c: vec3f, sun: f32) -> vec3f {
    var o = c * mix(SHADE_COOL, SUN_WARM, sun);
    let l = liteLuma(o);
    o = mix(vec3f(l), o, SATURATION);
    o = (o - vec3f(0.45)) * CONTRAST + vec3f(0.45);
    return max(o, vec3f(0.0));
}

fn liteLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    var o: BloxdLight = bloxdDefaultLight(surface, light);
    let lit = bloxdLitColour(surface, light);
    let sun = saturate(light.directional) * light.skyLight;
    o.colour = bloxdApplyFog(liteGrade(lit, sun) + surface.emission, light);
    return o;
}

fn bloxdTerrainLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    return liteLight(surface, light);
}

fn bloxdModelLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    return liteLight(surface, light);
}

// ───── 水 ─────
fn bloxdLiquidSurface(surface: BloxdSurfaceIn) -> BloxdSurface {
    var s: BloxdSurface = bloxdDefaultSurface(surface);
    s.colour = mix(surface.colour, WATER_TINT, WATER_MIX);
    return s;
}

fn bloxdLiquidLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    let lit = bloxdLitColour(surface, light);
    let view = normalize(light.position - bloxdEyePosition());
    let facing = saturate(dot(-view, normalize(light.normal)));
    let fresnel = 0.03 + 0.97 * pow(1.0 - facing, 4.0);
    let sky = light.fogColour * vec3f(0.85, 1.0, 1.25) * (0.4 + 0.6 * light.skyLight);
    let reflected = mix(lit, sky, saturate(fresnel * WATER_SKY));
    let sun = saturate(light.directional) * light.skyLight;
    var o: BloxdLight = bloxdDefaultLight(surface, light);
    o.colour = bloxdApplyFog(liteGrade(reflected, sun) + surface.emission, light);
    return o;
}
