// Golden Hour Mid: 本編の見た目を、なるべく残して、重い処理だけを外した中間版。
//
// 残したもの: 日向は暖色・日陰は寒色・朝夕の赤み / ブロックごとの色のゆらぎと粒 / 光る素材と、鉱石・宝石の発光 / 金属の質感(鉄・金の反射)
//            / 水の色・空の映り込み・太陽のきらめき・小さな波 / 太陽方向のかすみ / 彩度・コントラスト・明るい部分の丸め / 影(1 回だけ)。
// 外したもの: 落ち葉・雪・水の波紋・凹凸(微分と画像 5 回読み)・光の筋(影 5 回)・雲の影・木漏れ日・水中のコースティクス・水面の雲(ノイズ重ね)。
// 影の計算は、1 回だけ(SHADOW_MODE)。 0 = 影なし(最軽量)、1 = ブロックの影だけ(ぼかした・軽い)、2 = 精密な影(プレイヤー・mob も)。
// strict でも効く(頂点を動かさない、discard なし)。 名前は "bloxd" で始められない(エンジン予約)。

const SHADOW_MODE: i32 = 1;                          // 0 = なし / 1 = ブロックの影(軽い)/ 2 = 精密な影(重め)
const SHADOW_STRENGTH: f32 = 0.80;                   // 影の濃さ

const SATURATION: f32 = 1.16;
const CONTRAST: f32 = 1.08;
const SHOULDER_KNEE: f32 = 0.80;
const SUN_WARM: vec3f = vec3f(1.10, 0.98, 0.82);
const SUNSET_WARM: vec3f = vec3f(1.30, 0.80, 0.52);
const SHADE_COOL: vec3f = vec3f(0.86, 0.94, 1.12);
const SUN_BOOST: f32 = 0.22;
const VARIATION: f32 = 0.06;                         // ブロックごとの明暗差
const GRAIN: f32 = 0.022;                            // 細かな粒
const ORE_GLOW: f32 = 0.10;
const GLOW_SATURATION: f32 = 1.30;
const GLOW_BASE: f32 = 0.10;
const GLOW_PEAK: f32 = 0.50;
const METAL_SHEEN: f32 = 0.60;
const RIM_SKY: f32 = 0.05;
const HAZE_WARM: vec3f = vec3f(0.34, 0.18, 0.05);
const HAZE_POWER: f32 = 5.0;

const WATER_SHALLOW: vec3f = vec3f(0.46, 0.88, 0.92);
const WATER_DEEP: vec3f = vec3f(0.05, 0.28, 0.48);
const WATER_BRIGHT: f32 = 1.25;
const WATER_REFLECT: f32 = 0.70;
const WATER_RIPPLE: f32 = 0.11;
const SUN_GLINT: f32 = 1.6;

fn luma(c: vec3f) -> f32 {
    return dot(c, vec3f(0.2126, 0.7152, 0.0722));
}

fn grade(c: vec3f) -> vec3f {
    let l = luma(c);
    var g = mix(vec3f(l), c, SATURATION);
    g = (g - vec3f(0.5)) * CONTRAST + vec3f(0.5);
    return max(g, vec3f(0.0));
}

fn shoulder(x: vec3f) -> vec3f {
    let room = 1.0 - SHOULDER_KNEE;
    let over = max(x - vec3f(SHOULDER_KNEE), vec3f(0.0));
    return min(x, vec3f(SHOULDER_KNEE)) + room * (vec3f(1.0) - exp(-over / room));
}

// 太陽の向き(画像の空のゲームでは、影の光の向きの逆で代用)。
fn sunDirection() -> vec3f {
    let s = bloxdSunDirection();
    if (dot(s, s) < 0.0001) {
        return -bloxdShadowDirection();
    }
    return s;
}

fn sunVisible(sun: vec3f) -> f32 {
    return smoothstep(-0.10, 0.12, sun.y);
}

fn sunsetAmount(sun: vec3f) -> f32 {
    return (1.0 - smoothstep(0.05, 0.50, sun.y)) * sunVisible(sun);
}

fn faceBlock(position: vec3f, normal: vec3f) -> vec3i {
    return vec3i(floor(position - normal * 0.5)) + bloxdRenderOffset();
}

fn blockHash(p: vec3i) -> f32 {
    var h: u32 = u32(p.x) * 374761393u + u32(p.y) * 668265263u + u32(p.z) * 2147483647u;
    h = (h ^ (h >> 13u)) * 1274126177u;
    h = h ^ (h >> 16u);
    return f32(h & 65535u) / 65535.0;
}

fn oreMask(rgb: vec3f) -> f32 {
    let mx = max(max(rgb.x, rgb.y), rgb.z);
    let mn = min(min(rgb.x, rgb.y), rgb.z);
    let colourful = smoothstep(0.18, 0.38, mx - mn);
    let bright = smoothstep(0.78, 0.95, mx);
    return max(colourful, bright);
}

// 影(1 回だけ)。1 = 日向、0 = 影。
fn shadowAmount() -> f32 {
    if (SHADOW_MODE == 1) {
        return bloxdAirShadow(1.0);
    }
    if (SHADOW_MODE == 2) {
        return bloxdShadow();
    }
    return 1.0;
}

// 太陽方向のかすみ。
fn addHaze(colour: vec3f, light: BloxdLightIn, sun: vec3f) -> vec3f {
    let view = normalize(light.position - bloxdEyePosition());
    let toward = pow(saturate(dot(view, sun)), HAZE_POWER) * sunVisible(sun);
    return colour + HAZE_WARM * toward * saturate(light.fogAlpha);
}

// 地形とモデルの、共通の光。modelMix: 0 = 地形、1 = モデル。
fn shade(surface: BloxdSurface, light: BloxdLightIn, modelMix: f32) -> vec3f {
    let sun = sunDirection();
    let sv = sunVisible(sun);
    let warmth = sunsetAmount(sun);
    let sunColour = mix(vec3f(1.0, 0.96, 0.88), vec3f(1.0, 0.60, 0.30), warmth);
    let n = normalize(light.normal);
    let view = normalize(light.position - bloxdEyePosition());
    let sky = light.skyLight;

    // 標準の光(影なし)と、そのうち、直射が占める割合。
    var c = bloxdLitColour(surface, light);
    let shading = bloxdShading(light);
    let directPart = light.directional * light.diffuse;
    let share = saturate(luma(directPart) / max(luma(shading), 0.001));
    let shadow = mix(1.0, shadowAmount(), SHADOW_STRENGTH);
    c = c * ((1.0 - share) + share * shadow);

    // 日向をさらに明るく、日向は暖色(朝夕は赤み)、日陰は寒色。
    let sunny = share * shadow;
    c = c * (1.0 + SUN_BOOST * sunny * sv);
    c = c * mix(SHADE_COOL, mix(SUN_WARM, SUNSET_WARM, warmth), sunny);

    // 斜めの面は、空の色をうっすら映す。
    let rim = pow(1.0 - saturate(dot(n, -view)), 4.0);
    c = c + light.fogColour * rim * RIM_SKY * sky;

    // 金属の質感(アイテム・防具・mob): 明るい灰色 = 鉄・銀、黄色 = 金を、色から見つけて、空の映り込みと、太陽の反射を足す。
    if (modelMix > 0.5) {
        let metalTex = bloxdTexel(light.textureId, clamp(fract(light.uv), vec2f(0.0), vec2f(0.9999)), light.mipLevel).rgb;
        let mtMax = max(max(metalTex.x, metalTex.y), metalTex.z);
        let mtSat = mtMax - min(min(metalTex.x, metalTex.y), metalTex.z);
        let steel = smoothstep(0.42, 0.68, luma(metalTex)) * (1.0 - smoothstep(0.10, 0.24, mtSat));
        let goldish = smoothstep(0.22, 0.40, mtSat) * smoothstep(0.35, 0.60, metalTex.x) * step(metalTex.z, metalTex.y * 0.75);
        let metal = max(steel, goldish) * METAL_SHEEN;
        let reflDir = reflect(view, n);
        let envColour = mix(light.fogColour, light.fogColour * vec3f(0.65, 0.85, 1.35), saturate(reflDir.y)) * (0.35 + 0.65 * sky);
        let edgeK = pow(1.0 - saturate(dot(n, -view)), 3.0);
        c = c + mix(vec3f(1.0), metalTex * 1.6, goldish) * envColour * metal * (0.15 + 0.5 * edgeK);
        let half = normalize(-view - bloxdShadowDirection());
        c = c + sunColour * metal * pow(saturate(dot(n, half)), 60.0) * 0.9 * sunny;
    }

    // 色の仕上げと、霧・かすみ。発光は、仕上げのあとに足す(丸めない)。
    c = mix(grade(shoulder(c)), shoulder(c), modelMix * 0.7) + surface.emission;
    var o = bloxdApplyFog(c, light);
    o = addHaze(o, light, sun);
    return o;
}

// ───── 地形(水とモデル以外のブロック) ─────
fn bloxdTerrainSurface(surface: BloxdSurfaceIn) -> BloxdSurface {
    var s: BloxdSurface = bloxdDefaultSurface(surface);
    if (surface.flags.emissive) {
        // 光る素材: 素材そのものの色で光る。明るい部分ほど強く。
        let l = luma(surface.colour);
        let glow = mix(vec3f(l), surface.colour, GLOW_SATURATION);
        s.emission = glow * (GLOW_BASE + GLOW_PEAK * smoothstep(0.25, 0.85, l));
    } else {
        // 普通のブロック: ブロックごと + 細かな粒、の 2 段で色をゆらす。
        let wp = bloxdWorldPosition(surface.position);
        let h = blockHash(faceBlock(surface.position, surface.normal));
        let grain = blockHash(vec3i(floor(wp * 16.0)));
        s.colour = surface.colour * (1.0 + (h - 0.5) * 2.0 * VARIATION + (grain - 0.5) * 2.0 * GRAIN);
        // 鉱石: 色のはっきりした粒・明るい粒が、ほんのり自分で光る。
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

// ───── モデル(プレイヤー・アイテム・mob など) ─────
fn bloxdModelSurface(surface: BloxdSurfaceIn) -> BloxdSurface {
    var s: BloxdSurface = bloxdDefaultSurface(surface);
    if (surface.flags.held || surface.flags.dropped || surface.flags.thrown) {
        let itemTex = bloxdTexel(surface.textureId, clamp(fract(surface.uv), vec2f(0.0), vec2f(0.9999)), surface.mipLevel).rgb;
        let gem = smoothstep(0.30, 0.55, max(max(itemTex.x, itemTex.y), itemTex.z) - min(min(itemTex.x, itemTex.y), itemTex.z));
        s.emission = itemTex * gem * ORE_GLOW * 0.35;
    }
    return s;
}

fn bloxdModelLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    var o: BloxdLight = bloxdDefaultLight(surface, light);
    o.colour = shade(surface, light, 1.0);
    return o;
}

// ───── 水 ─────
// 水面の法線: 2 つの大きな波(足し算だけ)。
fn waterNormal(p: vec2f, t: f32) -> vec3f {
    let k1 = vec2f(1.30, 0.50);
    let k2 = vec2f(-0.70, 1.60);
    let g = k1 * (0.55 * cos(dot(p, k1) + t * 1.10)) + k2 * (0.35 * cos(dot(p, k2) + t * 1.70));
    return normalize(vec3f(-g.x * WATER_RIPPLE * 2.0, 1.0, -g.y * WATER_RIPPLE * 2.0));
}

fn bloxdLiquidSurface(surface: BloxdSurfaceIn) -> BloxdSurface {
    var s: BloxdSurface = bloxdDefaultSurface(surface);
    // 色: 浅い青緑 → 深い青(目からの距離で、近似)。 水の向こうの深さは、読まない(軽くするため)。
    let depthK = smoothstep(2.0, 24.0, distance(surface.position, bloxdEyePosition()));
    s.colour = mix(mix(surface.colour * 1.3, WATER_SHALLOW, 0.7), WATER_DEEP, depthK * 0.6);
    return s;
}

fn bloxdLiquidLight(surface: BloxdSurface, light: BloxdLightIn) -> BloxdLight {
    var o: BloxdLight = bloxdDefaultLight(surface, light);
    let sun = sunDirection();
    let sv = sunVisible(sun);
    let wp = bloxdWorldPosition(light.position);
    let t = bloxdSeconds();
    let sunColour = mix(vec3f(1.0, 0.96, 0.88), vec3f(1.0, 0.60, 0.30), sunsetAmount(sun));
    var n = normalize(light.normal);
    if (abs(light.normal.y) > 0.5) {
        n = waterNormal(wp.xz, t);
    }
    let view = normalize(light.position - bloxdEyePosition());
    let fresnel = 0.02 + 0.98 * pow(1.0 - saturate(dot(-view, n)), 5.0);
    let refl = reflect(view, n);
    let r = vec3f(refl.x, abs(refl.y), refl.z);
    let skyCol = mix(light.fogColour, light.fogColour * vec3f(0.65, 0.85, 1.35), pow(saturate(r.y), 0.6)) * (0.35 + 0.65 * light.skyLight);
    var c = mix(bloxdLitColour(surface, light), skyCol, fresnel * WATER_REFLECT * (1.0 - saturate(light.fogAlpha)));
    // 太陽の照り返しと、鋭いきらめき。
    let towardSun = saturate(dot(r, sun));
    c = c + sunColour * (pow(towardSun, 200.0) * SUN_GLINT + pow(towardSun, 24.0) * 0.2) * light.skyLight * sv;
    c = grade(shoulder(c * WATER_BRIGHT)) + surface.emission;
    o.colour = addHaze(bloxdApplyFog(c, light), light, sun);
    return o;
}
