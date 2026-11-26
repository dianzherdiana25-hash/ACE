// Zero-dependency Chromium CDP Live Browser Runtime for ACE v3 (Node 24 stdlib).
// Launches Chromium with persistent `user_data_dir`, strict domain allowlist,
// file upload via DOM.setFileInputFiles, screenshot proof, and CAPTCHA/2FA/Login stop-gate.
"use strict";

import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on("data", (c) => chunks.push(c));
    process.stdin.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    process.stdin.on("error", reject);
  });
}

function httpGetJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let body = "";
      res.on("data", (d) => { body += d; });
      res.on("end", () => {
        try {
          resolve(JSON.parse(body));
        } catch (err) {
          reject(err);
        }
      });
    }).on("error", reject);
  });
}

function hostMatchesAllowlist(hostname, allowlist) {
  const host = String(hostname || "").toLowerCase();
  if (!host) return false;
  for (const allowedRaw of allowlist) {
    const allowed = String(allowedRaw || "").toLowerCase().trim();
    if (!allowed) continue;
    if (host === allowed) return true;
    if (allowed.startsWith(".") && (host.endsWith(allowed) || host === allowed.slice(1))) return true;
    if (!allowed.includes("://") && host.endsWith("." + allowed)) return true;
  }
  return false;
}

class CDPClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.handlers = new Map();
    this.ready = new Promise((resolve, reject) => {
      this.ws.addEventListener("open", () => resolve());
      this.ws.addEventListener("error", (ev) => reject(new Error("WebSocket CDP error")));
    });
    this.ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(String(ev.data));
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message || JSON.stringify(msg.error)));
        else resolve(msg.result || {});
      } else if (msg.method && this.handlers.has(msg.method)) {
        for (const fn of this.handlers.get(msg.method)) {
          try { fn(msg.params || {}); } catch (_) {}
        }
      }
    });
  }

  on(method, fn) {
    if (!this.handlers.has(method)) this.handlers.set(method, []);
    this.handlers.get(method).push(fn);
  }

  async call(method, params = {}, timeoutMs = 15000) {
    await this.ready;
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout calling ${method}`));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (val) => { clearTimeout(timer); resolve(val); },
        reject: (err) => { clearTimeout(timer); reject(err); },
      });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  close() {
    try { this.ws.close(); } catch (_) {}
  }
}

async function _spawnChromiumOnce(binaryPath, userDataDir, headless, noSandbox) {
  fs.mkdirSync(userDataDir, { recursive: true });
  const args = [
    `--user-data-dir=${userDataDir}`,
    "--remote-debugging-port=0",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--window-size=1280,900",
    "about:blank",
  ];
  if (noSandbox) args.unshift("--no-sandbox");
  if (headless) args.unshift("--headless=new");
  const proc = spawn(binaryPath, args, { stdio: ["ignore", "ignore", "pipe"] });
  const port = await new Promise((resolve, reject) => {
    let stderrBuf = "";
    const timer = setTimeout(() => reject(new Error(`Chromium DevTools port timeout: ${stderrBuf.slice(-300)}`)), 15000);
    proc.stderr.on("data", (chunk) => {
      stderrBuf += chunk.toString("utf8");
      const m = stderrBuf.match(/ws:\/\/127\.0\.0\.1:(\d+)\/devtools\/browser\//);
      if (m) {
        clearTimeout(timer);
        resolve(Number(m[1]));
      }
    });
    proc.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`Chromium exited prematurely (${code}): ${stderrBuf.slice(-300)}`));
    });
  });
  return { proc, port };
}

async function launchChromium(binaryPath, userDataDir, headless, noSandboxOption) {
  let spawned;
  if (noSandboxOption === true) {
    spawned = await _spawnChromiumOnce(binaryPath, userDataDir, headless, true);
  } else {
    try {
      spawned = await _spawnChromiumOnce(binaryPath, userDataDir, headless, false);
    } catch (err) {
      if (noSandboxOption === false) throw err;
      spawned = await _spawnChromiumOnce(binaryPath, userDataDir, headless, true);
    }
  }
  const { proc, port } = spawned;

  // Poll /json/list briefly for the initial page target.
  let target = null;
  for (let i = 0; i < 30; i++) {
    try {
      const targets = await httpGetJson(`http://127.0.0.1:${port}/json/list`);
      target = targets.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
      if (target) break;
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 150));
  }
  if (!target) throw new Error("No Chromium page target available");
  return { proc, port, wsUrl: target.webSocketDebuggerUrl };
}

async function evalJs(cdp, expression, timeoutMs = 10000) {
  const res = await cdp.call("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  }, timeoutMs);
  if (res.exceptionDetails) {
    throw new Error(res.exceptionDetails.text || "JS evaluation failed");
  }
  return res.result ? res.result.value : undefined;
}

async function inspectAuthState(cdp) {
  const info = await evalJs(cdp, `(() => {
    const url = String(location.href || "");
    const title = String(document.title || "");
    const bodyText = String((document.body && document.body.innerText) || "").slice(0, 6000);
    const lower = (url + " " + title + " " + bodyText).toLowerCase();
    const hasPw = !!document.querySelector('input[type="password"]');
    const hasCaptchaFrame = !!document.querySelector('iframe[src*="captcha"], iframe[src*="turnstile"], div[class*="captcha"], input[name*="captcha"]');
    const has2FAInput = !!document.querySelector('input[name="approvals_code"], input[name*="otp"], input[autocomplete="one-time-code"]');
    return { url, title, bodyText, lower, hasPw, hasCaptchaFrame, has2FAInput };
  })()`);

  const textHash = createHash("sha256").update(info.bodyText).digest("hex");
  const lower = info.lower;
  if (info.hasCaptchaFrame || /verify you are human|captcha|recaptcha|hcaptcha|turnstile|anti-bot/i.test(lower)) {
    return { auth_status: "CAPTCHA_DETECTED", url: info.url, title: info.title, dom_sha256: textHash };
  }
  if (info.has2FAInput || /two-factor|2fa|approvals_code|autentikasi dua faktor|kode verifikasi/i.test(lower)) {
    return { auth_status: "TWO_FACTOR_REQUIRED", url: info.url, title: info.title, dom_sha256: textHash };
  }
  if (info.hasPw || /\/login\b|checkpoint\/|masuk ke facebook|log in to facebook|silakan masuk/i.test(lower)) {
    return { auth_status: "LOGIN_REQUIRED", url: info.url, title: info.title, dom_sha256: textHash };
  }
  return { auth_status: "AUTHENTICATED", url: info.url, title: info.title, dom_sha256: textHash };
}

async function waitForSelector(cdp, selector, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  const selJson = JSON.stringify(selector);
  while (Date.now() < deadline) {
    const found = await evalJs(cdp, `!!document.querySelector(${selJson})`);
    if (found) return true;
    await new Promise((r) => setTimeout(r, 150));
  }
  throw new Error(`Selector tidak muncul dalam ${timeoutMs}ms: ${selector}`);
}

async function main() {
  const rawInput = await readStdin();
  const plan = JSON.parse(rawInput);
  const allowHosts = Array.isArray(plan.allowed_hosts) ? plan.allowed_hosts : [];
  const timeoutMs = Number(plan.timeout_ms || 12000);
  const screenshotDir = plan.screenshot_dir ? String(plan.screenshot_dir) : "";
  if (screenshotDir) fs.mkdirSync(screenshotDir, { recursive: true });

  const { proc, wsUrl } = await launchChromium(
    plan.browser_binary,
    plan.user_data_dir,
    plan.headless !== false,
    plan.no_sandbox
  );
  const cdp = new CDPClient(wsUrl);
  const stepResults = [];
  let blockedRequests = 0;
  let finalStatus = "completed";
  let stopReason = null;

  try {
    await cdp.call("Page.enable");
    await cdp.call("DOM.enable");
    await cdp.call("Runtime.enable");
    await cdp.call("Fetch.enable", { patterns: [{ urlPattern: "*", requestStage: "Request" }] });

    cdp.on("Fetch.requestPaused", async (params) => {
      const reqUrl = String((params.request && params.request.url) || "");
      let allowed = false;
      if (reqUrl.startsWith("about:") || reqUrl.startsWith("data:") || reqUrl.startsWith("blob:")) {
        allowed = true;
      } else {
        try {
          const parsed = new URL(reqUrl);
          allowed = hostMatchesAllowlist(parsed.hostname, allowHosts);
        } catch (_) {
          allowed = false;
        }
      }
      if (!allowed) {
        blockedRequests++;
        await cdp.call("Fetch.failRequest", { requestId: params.requestId, errorReason: "BlockedByClient" }).catch(() => {});
      } else {
        await cdp.call("Fetch.continueRequest", { requestId: params.requestId }).catch(() => {});
      }
    });

    for (let idx = 0; idx < (plan.steps || []).length; idx++) {
      const step = plan.steps[idx];
      const stepId = String(step.id || `step_${idx + 1}`);
      const op = String(step.op || "");
      try {
        let evidence = {};
        if (op === "navigate") {
          const targetUrl = String(step.url || "");
          const parsed = new URL(targetUrl);
          if (!hostMatchesAllowlist(parsed.hostname, allowHosts)) {
            throw new Error(`DOMAIN_BLOCKED: ${parsed.hostname} di luar allowlist ${JSON.stringify(allowHosts)}`);
          }
          let loaded = false;
          const loadPromise = new Promise((res) => {
            cdp.on("Page.loadEventFired", () => { if (!loaded) { loaded = true; res(); } });
            setTimeout(() => { if (!loaded) { loaded = true; res(); } }, Math.min(timeoutMs, 8000));
          });
          await cdp.call("Page.navigate", { url: targetUrl }, timeoutMs);
          await loadPromise;
          await new Promise((r) => setTimeout(r, 250));
          const auth = await inspectAuthState(cdp);
          evidence = auth;
          if (step.stop_on_auth !== false && auth.auth_status !== "AUTHENTICATED") {
            if (screenshotDir) {
              const shot = await cdp.call("Page.captureScreenshot", { format: "png" });
              const outPng = path.join(screenshotDir, `${stepId}_auth_gate.png`);
              fs.writeFileSync(outPng, Buffer.from(shot.data, "base64"));
              evidence.screenshot_path = outPng;
            }
            stepResults.push({ id: stepId, op, status: "auth_required", evidence });
            finalStatus = "WAITING_FOR_OWNER_AUTH";
            stopReason = auth.auth_status;
            break;
          }
        } else if (op === "wait_selector") {
          await waitForSelector(cdp, String(step.selector), Number(step.timeout_ms || timeoutMs));
          evidence = { found: true, selector: step.selector };
        } else if (op === "click") {
          const sel = String(step.selector);
          await waitForSelector(cdp, sel, Number(step.timeout_ms || timeoutMs));
          const clicked = await evalJs(cdp, `(() => {
            const el = document.querySelector(${JSON.stringify(sel)});
            if (!el) return false;
            el.scrollIntoView({ block: "center" });
            el.click();
            return true;
          })()`);
          if (!clicked) throw new Error(`Gagal klik selector: ${sel}`);
          await new Promise((r) => setTimeout(r, 250));
          evidence = { clicked: sel };
        } else if (op === "click_if_present") {
          const sel = String(step.selector);
          const timeoutWait = Number(step.timeout_ms || 1200);
          const deadline = Date.now() + timeoutWait;
          let found = false;
          while (Date.now() < deadline) {
            found = await evalJs(cdp, `!!document.querySelector(${JSON.stringify(sel)})`);
            if (found) break;
            await new Promise((r) => setTimeout(r, 150));
          }
          if (found) {
            await evalJs(cdp, `(() => {
              const el = document.querySelector(${JSON.stringify(sel)});
              if (el) { el.scrollIntoView({ block: "center" }); el.click(); }
              return true;
            })()`);
            await new Promise((r) => setTimeout(r, 400));
          }
          evidence = { clicked: !!found, selector: sel };
        } else if (op === "fill") {
          const sel = String(step.selector);
          const val = String(step.value || "");
          await waitForSelector(cdp, sel, Number(step.timeout_ms || timeoutMs));
          await evalJs(cdp, `(() => {
            const el = document.querySelector(${JSON.stringify(sel)});
            if (!el) throw new Error("selector missing");
            el.focus();
            if ("value" in el) {
              el.value = ${JSON.stringify(val)};
            } else {
              el.textContent = ${JSON.stringify(val)};
            }
            el.dispatchEvent(new Event("input", { bubbles: true }));
            el.dispatchEvent(new Event("change", { bubbles: true }));
            return true;
          })()`);
          evidence = { filled: sel, value_sha256: createHash("sha256").update(val).digest("hex") };
        } else if (op === "upload_file") {
          const sel = String(step.selector);
          const fpath = String(step.file_path);
          if (!fs.existsSync(fpath)) throw new Error(`File upload tidak ada: ${fpath}`);
          await waitForSelector(cdp, sel, Number(step.timeout_ms || timeoutMs));
          const doc = await cdp.call("DOM.getDocument", { depth: 1 });
          const node = await cdp.call("DOM.querySelector", { nodeId: doc.root.nodeId, selector: sel });
          if (!node.nodeId) throw new Error(`Input file node tidak ditemukan: ${sel}`);
          await cdp.call("DOM.setFileInputFiles", { nodeId: node.nodeId, files: [fpath] });
          await new Promise((r) => setTimeout(r, 300));
          evidence = { uploaded_file: path.basename(fpath), bytes: fs.statSync(fpath).size };
        } else if (op === "read_text") {
          const sel = String(step.selector || "body");
          await waitForSelector(cdp, sel, Number(step.timeout_ms || timeoutMs));
          const txt = await evalJs(cdp, `(() => {
            const el = document.querySelector(${JSON.stringify(sel)});
            return el ? String(el.innerText || el.textContent || "").trim() : "";
          })()`);
          evidence = {
            text: String(txt || "").slice(0, Number(step.max_chars || 2000)),
            text_sha256: createHash("sha256").update(String(txt || "")).digest("hex"),
          };
        } else if (op === "check_auth_state") {
          const auth = await inspectAuthState(cdp);
          evidence = auth;
          if (step.stop_on_auth !== false && auth.auth_status !== "AUTHENTICATED") {
            stepResults.push({ id: stepId, op, status: "auth_required", evidence });
            finalStatus = "WAITING_FOR_OWNER_AUTH";
            stopReason = auth.auth_status;
            break;
          }
        } else if (op === "screenshot") {
          const shot = await cdp.call("Page.captureScreenshot", { format: "png" });
          const fname = step.filename ? path.basename(String(step.filename)) : `${stepId}.png`;
          const outDir = screenshotDir || process.cwd();
          fs.mkdirSync(outDir, { recursive: true });
          const outPng = path.join(outDir, fname);
          fs.writeFileSync(outPng, Buffer.from(shot.data, "base64"));
          evidence = { screenshot_path: outPng, bytes: fs.statSync(outPng).size };
        } else if (op === "wait_for_owner_login") {
          // Used when headless=false so owner can finish Facebook/KBM login interactively.
          const waitBudget = Number(step.wait_ms || 120000);
          const deadline = Date.now() + waitBudget;
          let auth = await inspectAuthState(cdp);
          while (auth.auth_status !== "AUTHENTICATED" && Date.now() < deadline) {
            await new Promise((r) => setTimeout(r, 1000));
            auth = await inspectAuthState(cdp);
          }
          evidence = auth;
          if (auth.auth_status !== "AUTHENTICATED") {
            finalStatus = "WAITING_FOR_OWNER_AUTH";
            stopReason = auth.auth_status;
            stepResults.push({ id: stepId, op, status: "timeout_waiting_auth", evidence });
            break;
          }
        } else {
          throw new Error(`Operasi live_browser tidak didukung: ${op}`);
        }
        stepResults.push({ id: stepId, op, status: "ok", evidence });
      } catch (err) {
        if (screenshotDir) {
          try {
            const shot = await cdp.call("Page.captureScreenshot", { format: "png" });
            fs.writeFileSync(path.join(screenshotDir, `${stepId}_error.png`), Buffer.from(shot.data, "base64"));
          } catch (_) {}
        }
        stepResults.push({ id: stepId, op, status: "failed", evidence: { error: String(err.message || err) } });
        finalStatus = "failed";
        stopReason = String(err.message || err);
        break;
      }
    }

    process.stdout.write(JSON.stringify({
      status: finalStatus,
      reason: stopReason,
      blocked_requests: blockedRequests,
      steps: stepResults,
    }) + "\n");
  } finally {
    cdp.close();
    try { proc.kill("SIGTERM"); } catch (_) {}
  }
}

main().catch((err) => {
  process.stdout.write(JSON.stringify({
    status: "failed",
    reason: String(err.message || err),
    blocked_requests: 0,
    steps: [],
  }) + "\n");
  process.exit(1);
});
