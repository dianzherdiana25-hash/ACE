import React from "react";
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type ReelScene = {
  id: string;
  tag?: string;
  headline?: string;
  narration: string;
  highlightWord?: string;
  metricLabel?: string;
  metricValue?: string;
  cta?: string;
  durationMs: number;
  sourceRef?: string;
};

export type ReelsCompositionProps = {
  title: string;
  channelBadge?: string;
  subtitleBadge?: string;
  cta?: string;
  qualityScoreBp?: number;
  width?: number;
  height?: number;
  fps?: number;
  scenes: ReelScene[];
};

interface Palette {
  bgTop: string;
  bgBottom: string;
  orbA: string;
  orbB: string;
  accent: string;
  accentSoft: string;
  accentText: string;
}

const PALETTES: Palette[] = [
  {
    bgTop: "#090D1A",
    bgBottom: "#171F3A",
    orbA: "rgba(255, 196, 46, 0.30)",
    orbB: "rgba(56, 189, 248, 0.24)",
    accent: "#FFC42E",
    accentSoft: "rgba(255, 196, 46, 0.16)",
    accentText: "#090D1A",
  },
  {
    bgTop: "#071413",
    bgBottom: "#0F2B28",
    orbA: "rgba(52, 211, 153, 0.30)",
    orbB: "rgba(34, 211, 238, 0.22)",
    accent: "#34D399",
    accentSoft: "rgba(52, 211, 153, 0.16)",
    accentText: "#042019",
  },
  {
    bgTop: "#130B1E",
    bgBottom: "#291445",
    orbA: "rgba(244, 114, 182, 0.32)",
    orbB: "rgba(167, 139, 250, 0.24)",
    accent: "#F472B6",
    accentSoft: "rgba(244, 114, 182, 0.16)",
    accentText: "#1E091A",
  },
  {
    bgTop: "#081224",
    bgBottom: "#10284A",
    orbA: "rgba(56, 189, 248, 0.30)",
    orbB: "rgba(99, 102, 241, 0.24)",
    accent: "#38BDF8",
    accentSoft: "rgba(56, 189, 248, 0.16)",
    accentText: "#05192B",
  },
];

const FONT_STACK =
  '"Inter", "SF Pro Display", "Segoe UI", "Roboto", "DejaVu Sans", system-ui, sans-serif';

function renderHighlightedHeadline(
  headline: string,
  highlightWord: string | undefined,
  accent: string
): React.ReactNode {
  const clean = headline.trim();
  const target = (highlightWord || "").trim();
  if (!target) return clean;
  const idx = clean.toUpperCase().indexOf(target.toUpperCase());
  if (idx === -1) return clean;
  const before = clean.slice(0, idx);
  const match = clean.slice(idx, idx + target.length);
  const after = clean.slice(idx + target.length);
  return (
    <>
      {before}
      <span
        style={{
          color: accent,
          textShadow: `0 0 28px ${accent}55`,
        }}
      >
        {match}
      </span>
      {after}
    </>
  );
}

const SceneSlide: React.FC<{
  scene: ReelScene;
  index: number;
  totalScenes: number;
  durationInFrames: number;
  palette: Palette;
  channelBadge: string;
  subtitleBadge: string;
  fallbackTitle: string;
  fallbackCta: string;
  qualityScoreBp: number;
}> = ({
  scene,
  index,
  totalScenes,
  durationInFrames,
  palette,
  channelBadge,
  subtitleBadge,
  fallbackTitle,
  fallbackCta,
  qualityScoreBp,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({
    frame,
    fps,
    config: { damping: 16, stiffness: 135, mass: 0.85 },
  });
  const cardSpring = spring({
    frame: Math.max(0, frame - 4),
    fps,
    config: { damping: 14, stiffness: 120 },
  });
  const exitOpacity = interpolate(
    frame,
    [Math.max(0, durationInFrames - 8), durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const floatA = Math.sin(frame / 18 + index) * 26;
  const floatB = Math.cos(frame / 22 + index * 2) * 30;

  const words = (scene.narration || "").trim().split(/\s+/).filter(Boolean);
  const wordWindow = Math.max(1, words.length);
  const activeWordIdx = Math.min(
    wordWindow - 1,
    Math.floor((frame / Math.max(1, durationInFrames - 4)) * wordWindow)
  );

  // Window words to 8 max centered/chunked so long captions stay crisp & readable
  const chunkSize = 8;
  const chunkIndex = Math.floor(activeWordIdx / chunkSize);
  const visibleWords = words.slice(
    chunkIndex * chunkSize,
    chunkIndex * chunkSize + chunkSize
  );
  const visibleOffset = chunkIndex * chunkSize;

  const headline = (
    scene.headline ||
    fallbackTitle ||
    "ACE REELS STUDIO"
  ).toUpperCase();
  const tagText = (
    scene.tag || `0${index + 1} • ${index === 0 ? "HOOK" : index === totalScenes - 1 ? "AKSI" : "INTI"}`
  ).toUpperCase();

  const ctaLabel =
    scene.cta || (index === totalScenes - 1 ? fallbackCta : "");

  const barCount = 18;
  const pulseCta = 1 + Math.sin(frame * 0.25) * 0.035;

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(165deg, ${palette.bgTop} 0%, ${palette.bgBottom} 100%)`,
        fontFamily: FONT_STACK,
        color: "#F8FAFC",
        opacity: exitOpacity,
        overflow: "hidden",
      }}
    >
      {/* Animated Bokeh Orbs (pure smooth radial gradients without slow CPU blur filter) */}
      <div
        style={{
          position: "absolute",
          top: 90 + floatA,
          left: -140 + floatB * 0.5,
          width: 520,
          height: 520,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${palette.orbA} 0%, transparent 66%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 180 + floatB,
          right: -130 + floatA * 0.5,
          width: 540,
          height: 540,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${palette.orbB} 0%, transparent 66%)`,
        }}
      />

      {/* Subtle Top Rim Vignette */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at 50% 0%, rgba(255,255,255,0.06) 0%, transparent 55%)",
        }}
      />

      {/* Safe Area Inner Canvas (720x1280 logical grid) */}
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          padding: "88px 52px 260px 52px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          boxSizing: "border-box",
        }}
      >
        {/* Top Channel & Counter Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: 12,
            opacity: interpolate(enter, [0, 1], [0.4, 1]),
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 14,
                background: palette.accent,
                color: palette.accentText,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 900,
                fontSize: 18,
                boxShadow: `0 6px 24px ${palette.accent}55`,
              }}
            >
              ACE
            </div>
            <div>
              <div style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-0.01em" }}>
                {channelBadge}
              </div>
              <div style={{ fontSize: 13, color: "rgba(226,232,240,0.78)", fontWeight: 600 }}>
                {subtitleBadge}
              </div>
            </div>
          </div>

          <div
            style={{
              padding: "8px 16px",
              borderRadius: 999,
              background: "rgba(15, 23, 42, 0.72)",
              border: `1.5px solid ${palette.accent}66`,
              fontSize: 14,
              fontWeight: 800,
              color: palette.accent,
              letterSpacing: "0.04em",
            }}
          >
            QA {(qualityScoreBp / 100).toFixed(0)}%
          </div>
        </div>

        {/* Center-Top Hero Headline */}
        <div
          style={{
            transform: `translateY(${interpolate(enter, [0, 1], [36, 0])}px) scale(${interpolate(
              enter,
              [0, 1],
              [0.95, 1]
            )})`,
            opacity: interpolate(enter, [0, 0.8], [0, 1]),
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 18px",
              borderRadius: 999,
              background: palette.accentSoft,
              border: `1.5px solid ${palette.accent}88`,
              color: palette.accent,
              fontSize: 16,
              fontWeight: 800,
              letterSpacing: "0.08em",
              marginBottom: 20,
            }}
          >
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: palette.accent,
                display: "inline-block",
              }}
            />
            {tagText}
          </div>

          <div
            style={{
              fontSize: headline.length > 44 ? 44 : 52,
              lineHeight: 1.08,
              fontWeight: 900,
              letterSpacing: "-0.025em",
              color: "#FFFFFF",
              textShadow: "0 10px 30px rgba(0,0,0,0.45)",
            }}
          >
            {renderHighlightedHeadline(headline, scene.highlightWord, palette.accent)}
          </div>
        </div>

        {/* Structured Metric / Proof Glass Card */}
        <div
          style={{
            transform: `translateY(${interpolate(cardSpring, [0, 1], [28, 0])}px)`,
            opacity: interpolate(cardSpring, [0, 1], [0, 1]),
            background: "rgba(10, 16, 32, 0.72)",
            border: `1.5px solid rgba(255, 255, 255, 0.14)`,
            borderTop: `3px solid ${palette.accent}`,
            borderRadius: 28,
            padding: "24px 28px",
            boxShadow: "0 24px 60px rgba(0, 0, 0, 0.45)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 16,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  letterSpacing: "0.1em",
                  color: "rgba(148, 163, 184, 0.95)",
                }}
              >
                {scene.metricLabel || "STATUS NARASI"}
              </div>
              <div
                style={{
                  fontSize: 34,
                  fontWeight: 900,
                  color: palette.accent,
                  letterSpacing: "-0.02em",
                  marginTop: 2,
                }}
              >
                {scene.metricValue || `${index + 1}/${totalScenes} LIVE`}
              </div>
            </div>

            {/* Live Kinetic Waveform Equalizer */}
            <div style={{ display: "flex", alignItems: "flex-end", gap: 5, height: 48 }}>
              {Array.from({ length: barCount }).map((_, b) => {
                const wave =
                  0.32 +
                  0.68 *
                    Math.abs(
                      Math.sin(frame * 0.24 + b * 0.55 + index * 1.1) *
                        Math.cos(frame * 0.11 + b * 0.28)
                    );
                return (
                  <div
                    key={b}
                    style={{
                      width: 6,
                      height: `${Math.round(wave * 44)}px`,
                      borderRadius: 99,
                      background:
                        b % 3 === 0 ? palette.accent : "rgba(248, 250, 252, 0.45)",
                    }}
                  />
                );
              })}
            </div>
          </div>

          {scene.sourceRef ? (
            <div
              style={{
                fontSize: 13,
                color: "rgba(203, 213, 225, 0.85)",
                fontFamily: "monospace",
                background: "rgba(255,255,255,0.06)",
                padding: "6px 12px",
                borderRadius: 10,
                display: "inline-block",
              }}
            >
              ✓ source_ref: {scene.sourceRef}
            </div>
          ) : null}
        </div>

        {/* Synchronized Karaoke Captions */}
        <div
          style={{
            minHeight: 150,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            padding: "8px 6px",
          }}
        >
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              justifyContent: "center",
              gap: "10px 8px",
              lineHeight: 1.35,
            }}
          >
            {visibleWords.map((w, wi) => {
              const absIdx = visibleOffset + wi;
              const isCurrent = absIdx === activeWordIdx;
              const isPast = absIdx < activeWordIdx;
              return (
                <span
                  key={`${absIdx}-${w}`}
                  style={{
                    fontSize: 30,
                    fontWeight: 800,
                    padding: isCurrent ? "4px 14px" : "4px 6px",
                    borderRadius: 12,
                    background: isCurrent ? palette.accent : "rgba(9, 13, 26, 0.55)",
                    color: isCurrent
                      ? palette.accentText
                      : isPast
                      ? "#FFFFFF"
                      : "rgba(226, 232, 240, 0.72)",
                    transform: isCurrent ? "scale(1.08)" : "scale(1)",
                    boxShadow: isCurrent ? `0 8px 24px ${palette.accent}55` : "none",
                  }}
                >
                  {w}
                </span>
              );
            })}
          </div>
        </div>

        {/* Bottom CTA Pill inside safe-zone */}
        <div
          style={{
            minHeight: 68,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {ctaLabel ? (
            <div
              style={{
                transform: `scale(${pulseCta})`,
                padding: "16px 32px",
                borderRadius: 999,
                background: palette.accent,
                color: palette.accentText,
                fontSize: 22,
                fontWeight: 900,
                letterSpacing: "0.03em",
                boxShadow: `0 12px 36px ${palette.accent}66`,
              }}
            >
              {ctaLabel} →
            </div>
          ) : (
            <div
              style={{
                fontSize: 15,
                fontWeight: 700,
                letterSpacing: "0.14em",
                color: "rgba(226, 232, 240, 0.55)",
              }}
            >
              ACE REMOTION STUDIO • REELS 9:16
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const ReelsComposition: React.FC<ReelsCompositionProps> = (props) => {
  const frame = useCurrentFrame();
  const { width, fps } = useVideoConfig();
  const scale = width / 720;

  const scenes = (props.scenes && props.scenes.length > 0 ? props.scenes : []).map(
    (s, i) => ({
      ...s,
      id: s.id || `sc_${i + 1}`,
      frames: Math.max(24, Math.round((Math.max(800, s.durationMs || 3000) / 1000) * fps)),
    })
  );

  let cursor = 0;
  const timeline = scenes.map((s) => {
    const startFrame = cursor;
    cursor += s.frames;
    return { ...s, startFrame };
  });

  const activeSceneIdx = Math.max(
    0,
    timeline.findIndex(
      (s) => frame >= s.startFrame && frame < s.startFrame + s.frames
    )
  );
  const currentPalette = PALETTES[activeSceneIdx % PALETTES.length];

  return (
    <AbsoluteFill style={{ backgroundColor: "#070B14" }}>
      {/* Responsive scaler from logical 720x1280 space */}
      <div
        style={{
          width: 720,
          height: 1280,
          transform: `scale(${scale})`,
          transformOrigin: "top left",
          position: "relative",
        }}
      >
        {timeline.map((sc, idx) => (
          <Sequence
            key={`${sc.id}-${idx}`}
            from={sc.startFrame}
            durationInFrames={sc.frames}
          >
            <SceneSlide
              scene={sc}
              index={idx}
              totalScenes={timeline.length}
              durationInFrames={sc.frames}
              palette={PALETTES[idx % PALETTES.length]}
              channelBadge={props.channelBadge || "@ACE.Studio"}
              subtitleBadge={props.subtitleBadge || "Verified Research • High-Bar QA"}
              fallbackTitle={props.title}
              fallbackCta={props.cta || "SIMPAN & IKUTI SEKARANG"}
              qualityScoreBp={props.qualityScoreBp || 9200}
            />
          </Sequence>
        ))}

        {/* Top Reels Segmented Progress Bar (Always visible on top) */}
        <div
          style={{
            position: "absolute",
            top: 44,
            left: 36,
            right: 36,
            display: "flex",
            gap: 8,
            zIndex: 30,
          }}
        >
          {timeline.map((sc, idx) => {
            const fill =
              frame < sc.startFrame
                ? 0
                : frame >= sc.startFrame + sc.frames
                ? 1
                : (frame - sc.startFrame) / Math.max(1, sc.frames);
            return (
              <div
                key={`bar-${idx}`}
                style={{
                  flex: sc.frames,
                  height: 7,
                  borderRadius: 99,
                  background: "rgba(255, 255, 255, 0.22)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${Math.round(fill * 100)}%`,
                    height: "100%",
                    borderRadius: 99,
                    background:
                      idx <= activeSceneIdx ? currentPalette.accent : "#FFFFFF",
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
