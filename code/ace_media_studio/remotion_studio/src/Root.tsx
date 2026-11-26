import React from "react";
import { Composition } from "remotion";
import { ReelsComposition, ReelsCompositionProps } from "./ReelsComposition";

export const defaultReelsProps: ReelsCompositionProps = {
  title: "Rahasia 3 Detik Pertama Reels Viral",
  channelBadge: "@ACE.Studio",
  subtitleBadge: "Verified Research • High-Bar QA",
  cta: "SIMPAN & IKUTI TIPSNYA",
  qualityScoreBp: 9400,
  scenes: [
    {
      id: "sc_hook",
      tag: "01 • HOOK 3 DETIK",
      headline: "KENAPA REELS SEPI DI 3 DETIK PERTAMA?",
      narration:
        "90 persen penonton swipe sebelum detik keempat karena layar diam tanpa hook visual.",
      highlightWord: "3 DETIK",
      metricLabel: "RETENSI AWAL",
      metricValue: "+2.4x",
      durationMs: 3600,
      sourceRef: "riset/hook_retention_01",
    },
    {
      id: "sc_strategy",
      tag: "02 • STRATEGI",
      headline: "PAKAI KONTRAS GERAK + KATA KUNCI",
      narration:
        "Gabungkan teks hook besar di zona aman atas dengan ritme subtitle sinkron kata demi kata.",
      highlightWord: "ZONA AMAN",
      metricLabel: "SKOR RETENTION",
      metricValue: "92%",
      durationMs: 4200,
      sourceRef: "riset/visual_pacing_02",
    },
    {
      id: "sc_cta",
      tag: "03 • AKSI SEKARANG",
      headline: "LOLOS FILTER KUALITAS BARU PUBLISH",
      narration:
        "Simpan template Reels ini dan cek skor kualitas sebelum diunggah ke Facebook Reels!",
      highlightWord: "SIMPAN",
      metricLabel: "QUALITY GATE",
      metricValue: ">= 85%",
      durationMs: 3600,
      cta: "SIMPAN & IKUTI SEKARANG",
      sourceRef: "riset/quality_gate_03",
    },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition<any, ReelsCompositionProps>
      id="AceVerticalReel"
      component={ReelsComposition}
      durationInFrames={342}
      fps={30}
      width={720}
      height={1280}
      defaultProps={defaultReelsProps}
      calculateMetadata={({ props }) => {
        const fps = Number(props.fps || 30);
        const totalMs = (props.scenes || []).reduce(
          (acc: number, s) => acc + Math.max(800, Number(s.durationMs || 3000)),
          0
        );
        const durationInFrames = Math.max(fps * 5, Math.round((totalMs / 1000) * fps));
        return {
          durationInFrames,
          fps,
          width: Number(props.width || 720),
          height: Number(props.height || 1280),
        };
      }}
    />
  );
};
