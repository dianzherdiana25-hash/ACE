#!/usr/bin/env node
/**
 * Programmatic Remotion 9:16 Vertical Reels Renderer for ACE Media Studio.
 *
 * Usage:
 *   node src/render.mjs --input <props.json> --output <reels.mp4> [--cover <cover.png>]
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const STUDIO_ROOT = path.resolve(__dirname, "..");

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k.startsWith("--") && i + 1 < argv.length) {
      args[k.slice(2)] = argv[++i];
    }
  }
  return args;
}

function findBrowserExecutable() {
  const candidates = [
    process.env.REMOTION_BROWSER_EXECUTABLE,
    process.env.CHROME_PATH,
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
  ].filter(Boolean);
  for (const c of candidates) {
    try {
      if (fs.existsSync(c)) {
        return c;
      }
    } catch {
      // ignore
    }
  }
  return undefined;
}

async function getBundleLocation() {
  const cacheDir = path.join(os.tmpdir(), "ace-remotion-bundle-v1");
  const marker = path.join(cacheDir, "index.html");
  const srcMtime = Math.max(
    fs.statSync(path.join(STUDIO_ROOT, "src", "ReelsComposition.tsx")).mtimeMs,
    fs.statSync(path.join(STUDIO_ROOT, "src", "Root.tsx")).mtimeMs,
    fs.statSync(path.join(STUDIO_ROOT, "src", "index.ts")).mtimeMs
  );
  if (fs.existsSync(marker)) {
    try {
      if (fs.statSync(marker).mtimeMs >= srcMtime) {
        return cacheDir;
      }
    } catch {
      // rebuild bundle
    }
  }
  fs.mkdirSync(cacheDir, { recursive: true });
  return bundle({
    entryPoint: path.join(STUDIO_ROOT, "src", "index.ts"),
    outDir: cacheDir,
    webpackOverride: (cfg) => cfg,
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.output) {
    throw new Error("Missing required --output <path.mp4>");
  }

  let inputProps = {};
  if (args.input) {
    inputProps = JSON.parse(fs.readFileSync(args.input, "utf-8"));
  }

  const outMp4 = path.resolve(args.output);
  fs.mkdirSync(path.dirname(outMp4), { recursive: true });

  const browserExecutable = findBrowserExecutable();
  const chromeMode = browserExecutable ? "chrome-for-testing" : "headless-shell";
  const gl = args.gl || "swangle";
  const crf = args.crf ? Number(args.crf) : 21;
  const concurrency = args.concurrency ? Number(args.concurrency) : 2;
  const muted = args.muted !== "false";

  const serveUrl = await getBundleLocation();
  const chromiumOptions = {
    gl,
    headless: true,
    enableMultiProcessOnLinux: true,
  };

  const composition = await selectComposition({
    serveUrl,
    id: "AceVerticalReel",
    inputProps,
    browserExecutable: browserExecutable || null,
    chromeMode,
    chromiumOptions,
    logLevel: "error",
  });

  let lastLoggedPct = -25;
  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    pixelFormat: "yuv420p",
    outputLocation: outMp4,
    inputProps,
    crf,
    muted,
    overwrite: true,
    concurrency,
    browserExecutable: browserExecutable || null,
    chromeMode,
    chromiumOptions,
    logLevel: "error",
    onProgress: args.progress
      ? ({ progress, renderedFrames, encodedFrames }) => {
          const pct = Math.floor(progress * 100);
          if (pct >= lastLoggedPct + 20 || pct === 100) {
            lastLoggedPct = pct;
            process.stderr.write(
              `[remotion] ${pct}% rendered=${renderedFrames}/${composition.durationInFrames} encoded=${encodedFrames}\n`
            );
          }
        }
      : undefined,
  });

  if (args.cover) {
    const outCover = path.resolve(args.cover);
    fs.mkdirSync(path.dirname(outCover), { recursive: true });
    // Pick frame ~0.6s into hook for rich visible cover artwork
    const coverFrame = Math.min(composition.durationInFrames - 1, Math.round(composition.fps * 0.65));
    await renderStill({
      composition,
      serveUrl,
      output: outCover,
      frame: coverFrame,
      imageFormat: "png",
      inputProps,
      overwrite: true,
      browserExecutable: browserExecutable || null,
      chromeMode,
      chromiumOptions,
      logLevel: "error",
    });
  }

  process.stdout.write(
    JSON.stringify({
      ok: true,
      renderer: "remotion",
      compositionId: composition.id,
      width: composition.width,
      height: composition.height,
      fps: composition.fps,
      durationInFrames: composition.durationInFrames,
      durationSec: Number((composition.durationInFrames / composition.fps).toFixed(3)),
      videoPath: outMp4,
      coverPath: args.cover ? path.resolve(args.cover) : null,
      browserExecutable: browserExecutable || "bundled",
    }) + "\n"
  );
}

main().catch((err) => {
  process.stderr.write((err && err.stack ? err.stack : String(err)) + "\n");
  process.exit(1);
});
