"""Localhost Anime Studio Web UI and REST/SSE API Server (`ace web`, Appendices Y, Z, AC).

Implements:
- Loopback binding (`127.0.0.1`) with automatic free-port fallback (`WEB01`, `WEB02`, `WEB18`)
- Shared SQLite + FencedStore state with CLI (`WEB24`)
- Two main blocks: 'Ngobrol dengan ACE' and 'Cerita ACE' (`WEB03`-`WEB15`)
- Cursor-based `/api/events?after=<seq>` & SSE stream without duplicate cards (`WEB16`)
- Offline-ready inline SVG Anime Companion with 5 data-driven states (`mendengar`, `bekerja`, `belajar`, `menunggu`, `selesai`) (`WEB12`, `WEB19`)
- Mobile-first responsive CSS (`360x800`), `>=44px` touch targets, `16px` input font, `prefers-reduced-motion`, and strict XSS escaping (`WEB20`-`WEB23`)
"""
from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import threading
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .autonomy_loop import AutonomyOrchestrator
from .coding_loop import CodingAgentLoop
from .language import ConversationalEngine
from .models_backend import ModelRouter
from .store import OperationalStore


ANIME_WEB_HTML = r"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>ACE Studio — Ruang Kerja &amp; Cerita Aktivitas</title>
  <style>
    :root {
      --bg-primary: #0C1120;
      --bg-surface: #151D31;
      --bg-elevated: #1D2742;
      --text-primary: #E9EDFF;
      --text-secondary: #A8B3CF;
      --accent-primary: #B9A3FF;
      --accent-secondary: #70DDD1;
      --status-ok: #4ADE80;
      --status-learn: #FBBF24;
      --status-warn: #F87171;
      --radius-card: 20px;
      --radius-pill: 999px;
      --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, sans-serif;
      --font-mono: ui-monospace, "Cascadia Code", "Fira Code", monospace;
    }

    *, *::before, *::after {
      box-sizing: border-box;
    }

    html, body {
      margin: 0;
      padding: 0;
      width: 100%;
      max-width: 100vw;
      overflow-x: hidden;
      background: radial-gradient(circle at 15% 10%, #1B2544 0%, var(--bg-primary) 60%);
      color: var(--text-primary);
      font-family: var(--font-sans);
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }

    /* Top Header Bar */
    .studio-header {
      position: sticky;
      top: 0;
      z-index: 30;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 12px 16px;
      background: rgba(12, 17, 32, 0.88);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid rgba(185, 163, 255, 0.18);
    }

    .brand-group {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .brand-logo {
      width: 36px;
      height: 36px;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
      display: grid;
      place-items: center;
      color: #0C1120;
      font-weight: 800;
      font-size: 16px;
      box-shadow: 0 4px 14px rgba(185, 163, 255, 0.3);
    }

    .brand-title {
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0.2px;
      margin: 0;
    }

    .brand-subtitle {
      font-size: 12px;
      color: var(--text-secondary);
      margin: 0;
    }

    .badge-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: var(--radius-pill);
      background: var(--bg-elevated);
      border: 1px solid rgba(185, 163, 255, 0.24);
      font-size: 12px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--status-ok);
    }

    /* Mobile Tab Switcher (visible on compact viewports) */
    .mobile-tabs {
      display: flex;
      gap: 8px;
      padding: 10px 16px 0;
    }

    .tab-btn {
      flex: 1;
      min-height: 44px;
      min-width: 44px;
      border-radius: 14px;
      border: 1px solid rgba(185, 163, 255, 0.22);
      background: var(--bg-surface);
      color: var(--text-secondary);
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
    }

    .tab-btn.active {
      background: linear-gradient(135deg, rgba(185, 163, 255, 0.24), rgba(112, 221, 209, 0.18));
      color: var(--text-primary);
      border-color: var(--accent-primary);
    }

    /* Main Two-Block Studio Grid */
    .studio-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 16px;
      padding: 14px 16px 28px;
      max-width: 1320px;
      margin: 0 auto;
    }

    @media (min-width: 900px) {
      .mobile-tabs {
        display: none;
      }
      .studio-grid {
        grid-template-columns: 1.15fr 0.85fr;
        align-items: start;
      }
      .studio-panel {
        display: flex !important;
      }
    }

    .studio-panel {
      display: flex;
      flex-direction: column;
      background: var(--bg-surface);
      border: 1px solid rgba(185, 163, 255, 0.18);
      border-radius: var(--radius-card);
      box-shadow: 0 12px 32px rgba(5, 8, 18, 0.45);
      overflow: hidden;
    }

    .studio-panel.hidden-mobile {
      display: none;
    }

    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 18px;
      background: rgba(29, 39, 66, 0.65);
      border-bottom: 1px solid rgba(185, 163, 255, 0.14);
    }

    .panel-title {
      font-size: 16px;
      font-weight: 700;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    /* Starter Prompt Chips */
    .starter-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 12px 16px;
      border-bottom: 1px solid rgba(185, 163, 255, 0.1);
    }

    .chip-btn {
      min-height: 44px;
      min-width: 44px;
      padding: 8px 14px;
      border-radius: var(--radius-pill);
      border: 1px solid rgba(112, 221, 209, 0.32);
      background: rgba(29, 39, 66, 0.75);
      color: var(--text-primary);
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }

    .chip-btn:hover {
      border-color: var(--accent-secondary);
      transform: translateY(-1px);
    }

    /* Chat Stream */
    .chat-messages {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 16px;
      min-height: 320px;
      max-height: 55vh;
      overflow-y: auto;
    }

    .msg-bubble {
      max-width: 88%;
      padding: 12px 15px;
      border-radius: 18px;
      font-size: 15px;
      line-height: 1.55;
      word-wrap: break-word;
      overflow-wrap: anywhere;
    }

    .msg-user {
      align-self: flex-end;
      background: linear-gradient(135deg, #392E6D, #283A66);
      border: 1px solid rgba(185, 163, 255, 0.4);
      color: var(--text-primary);
      border-bottom-right-radius: 6px;
    }

    .msg-assistant {
      align-self: flex-start;
      background: var(--bg-elevated);
      border: 1px solid rgba(112, 221, 209, 0.25);
      color: var(--text-primary);
      border-bottom-left-radius: 6px;
    }

    .msg-meta {
      font-size: 11px;
      color: var(--text-secondary);
      margin-top: 6px;
    }

    /* Task Control Strip inside Chat Panel */
    .task-control-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 10px 16px;
      background: rgba(12, 17, 32, 0.55);
      border-top: 1px solid rgba(185, 163, 255, 0.12);
    }

    .control-btn {
      min-height: 44px;
      min-width: 44px;
      padding: 8px 14px;
      border-radius: 12px;
      border: 1px solid rgba(185, 163, 255, 0.3);
      background: var(--bg-elevated);
      color: var(--text-primary);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
    }

    /* Chat Input Area (16px font to prevent mobile zoom) */
    .chat-composer {
      display: flex;
      gap: 10px;
      padding: 12px 16px;
      background: var(--bg-elevated);
      border-top: 1px solid rgba(185, 163, 255, 0.18);
    }

    .chat-input {
      flex: 1;
      min-height: 46px;
      max-height: 120px;
      padding: 10px 14px;
      border-radius: 14px;
      border: 1px solid rgba(185, 163, 255, 0.3);
      background: var(--bg-primary);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: 16px;
      resize: vertical;
    }

    .send-btn {
      min-height: 46px;
      min-width: 84px;
      padding: 0 18px;
      border-radius: 14px;
      border: none;
      background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
      color: #0C1120;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
    }

    /* Anime Companion Stage inside Cerita ACE */
    .companion-stage {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px;
      background: linear-gradient(145deg, rgba(29, 39, 66, 0.9), rgba(18, 25, 46, 0.9));
      border-bottom: 1px solid rgba(185, 163, 255, 0.16);
    }

    .avatar-frame {
      width: 96px;
      height: 96px;
      flex-shrink: 0;
      border-radius: 22px;
      background: radial-gradient(circle at 50% 35%, rgba(185, 163, 255, 0.28), rgba(12, 17, 32, 0.9));
      border: 1.5px solid rgba(185, 163, 255, 0.45);
      display: grid;
      place-items: center;
      position: relative;
      transition: border-color 0.25s ease;
    }

    .avatar-frame[data-state="bekerja"] {
      border-color: var(--accent-secondary);
    }
    .avatar-frame[data-state="belajar"] {
      border-color: var(--status-learn);
    }
    .avatar-frame[data-state="selesai"] {
      border-color: var(--status-ok);
    }

    .companion-status-box {
      flex: 1;
      min-width: 0;
    }

    .companion-state-badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: var(--radius-pill);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      background: rgba(185, 163, 255, 0.2);
      color: var(--accent-primary);
      margin-bottom: 6px;
    }

    .companion-headline {
      margin: 0;
      font-size: 14px;
      color: var(--text-primary);
    }

    /* Story Feed */
    .story-feed {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 16px;
      max-height: 60vh;
      overflow-y: auto;
    }

    .story-card {
      padding: 14px 16px;
      border-radius: 18px;
      background: var(--bg-elevated);
      border: 1px solid rgba(185, 163, 255, 0.18);
    }

    .story-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 6px;
    }

    .story-narrative {
      margin: 0 0 10px;
      font-size: 14.5px;
      color: var(--text-primary);
    }

    details.evidence-drawer {
      margin-top: 8px;
      border-top: 1px dashed rgba(168, 179, 207, 0.2);
      padding-top: 8px;
      font-size: 12px;
      color: var(--text-secondary);
    }

    details.evidence-drawer summary {
      cursor: pointer;
      font-weight: 600;
      color: var(--accent-secondary);
      min-height: 32px;
      display: inline-flex;
      align-items: center;
    }

    .evidence-pre {
      margin: 8px 0 0;
      padding: 10px;
      border-radius: 10px;
      background: var(--bg-primary);
      font-family: var(--font-mono);
      font-size: 11.5px;
      color: var(--text-secondary);
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-all;
    }

    .artifact-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 6px;
      margin-right: 6px;
      padding: 6px 12px;
      border-radius: 10px;
      background: rgba(112, 221, 209, 0.14);
      border: 1px solid rgba(112, 221, 209, 0.35);
      color: var(--accent-secondary);
      font-size: 12px;
      text-decoration: none;
    }

    @keyframes floatSlow {
      0%, 100% { transform: translateY(0px); }
      50% { transform: translateY(-3px); }
    }

    .avatar-svg {
      animation: floatSlow 3.5s ease-in-out infinite;
    }

    /* Reduced Motion Accessibility (WEB20) */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after, .avatar-svg, .chip-btn {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
        scroll-behavior: auto !important;
      }
    }
  </style>
</head>
<body>
  <header class="studio-header">
    <div class="brand-group">
      <div class="brand-logo" aria-hidden="true">A</div>
      <div>
        <h1 class="brand-title">ACE Studio Lokal</h1>
        <p class="brand-subtitle">Asisten Rekayasa &amp; Otonomi Terverifikasi</p>
      </div>
    </div>
    <div class="badge-row">
      <span class="status-pill" id="badge-mode">
        <span class="status-dot" id="dot-mode"></span>
        <span id="text-mode">Memuat mode...</span>
      </span>
      <span class="status-pill" id="badge-model">Model: lokal</span>
    </div>
  </header>

  <nav class="mobile-tabs" aria-label="Navigasi Ruang Kerja">
    <button type="button" class="tab-btn active" id="tab-ngobrol" onclick="switchMobileTab('ngobrol')">
      Ngobrol dengan ACE
    </button>
    <button type="button" class="tab-btn" id="tab-cerita" onclick="switchMobileTab('cerita')">
      Cerita ACE
    </button>
  </nav>

  <main class="studio-grid">
    <!-- BLOCK 1: NGOBROL DENGAN ACE -->
    <section class="studio-panel" id="panel-ngobrol" aria-labelledby="heading-ngobrol">
      <div class="panel-header">
        <h2 class="panel-title" id="heading-ngobrol">Ngobrol dengan ACE</h2>
        <span id="active-task-badge" style="font-size:12px;color:var(--text-secondary);">Siap menerima tugas</span>
      </div>

      <div class="starter-chips" aria-label="Contoh perintah cepat">
        <button type="button" class="chip-btn" onclick="sendQuickPrompt('Buatkan aplikasi catatan pengeluaran sederhana')">
          Buat catatan pengeluaran
        </button>
        <button type="button" class="chip-btn" onclick="sendQuickPrompt('Jelaskan dulu rencananya, jangan kerjakan dulu')">
          Jelaskan rencana dulu
        </button>
        <button type="button" class="chip-btn" onclick="sendQuickPrompt('Perbaiki bug diskon pada script perhitungan')">
          Perbaiki bug kode
        </button>
        <button type="button" class="chip-btn" onclick="sendQuickPrompt('Udah sampai mana status sekarang?')">
          Cek progres
        </button>
      </div>

      <div class="chat-messages" id="chat-messages" role="log" aria-live="polite"></div>

      <div class="task-control-bar" id="task-control-bar">
        <span id="task-control-label" style="font-size:12.5px;color:var(--text-secondary);">
          Kendali tugas aktif:
        </span>
        <div style="display:flex;gap:8px;">
          <button type="button" class="control-btn" onclick="controlActiveTask('pause')">Jeda</button>
          <button type="button" class="control-btn" onclick="controlActiveTask('resume')">Lanjutkan</button>
          <button type="button" class="control-btn" onclick="controlActiveTask('stop')">Hentikan</button>
        </div>
      </div>

      <form class="chat-composer" id="chat-form" onsubmit="submitChatForm(event)">
        <textarea
          id="chat-input"
          class="chat-input"
          rows="1"
          placeholder="Tulis permintaanmu dalam Bahasa Indonesia..."
          aria-label="Pesan untuk ACE"
          required
        ></textarea>
        <button type="submit" class="send-btn" id="send-btn">Kirim</button>
      </form>
    </section>

    <!-- BLOCK 2: CERITA ACE -->
    <section class="studio-panel" id="panel-cerita" aria-labelledby="heading-cerita">
      <div class="panel-header">
        <h2 class="panel-title" id="heading-cerita">Cerita ACE</h2>
        <span id="story-count-badge" style="font-size:12px;color:var(--text-secondary);">Aktivitas nyata</span>
      </div>

      <!-- Anime Companion Avatar bound to real runtime state (WEB12) -->
      <div class="companion-stage">
        <div class="avatar-frame" id="ace-anime-companion" data-state="mendengar">
          <svg class="avatar-svg" width="76" height="76" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Karakter Studio Anime ACE">
            <!-- Studio Halo & Hair Back -->
            <circle cx="50" cy="50" r="42" fill="#1D2742" stroke="#B9A3FF" stroke-width="2" />
            <!-- Headphone Band -->
            <path d="M20 50 C20 24, 80 24, 80 50" stroke="#70DDD1" stroke-width="5" stroke-linecap="round" fill="none" />
            <rect x="14" y="42" width="9" height="18" rx="4" fill="#B9A3FF" />
            <rect x="77" y="42" width="9" height="18" rx="4" fill="#B9A3FF" />
            <!-- Anime Hair & Face -->
            <circle cx="50" cy="54" r="24" fill="#FFE7D6" />
            <path d="M25 48 C26 26, 74 26, 75 48 C68 38, 58 42, 50 36 C42 42, 32 38, 25 48 Z" fill="#6D59B5" />
            <!-- Expressive Anime Eyes -->
            <ellipse cx="41" cy="54" rx="4.2" ry="5" fill="#1B1F38" />
            <ellipse cx="59" cy="54" rx="4.2" ry="5" fill="#1B1F38" />
            <circle cx="42.5" cy="52.2" r="1.6" fill="#FFFFFF" />
            <circle cx="60.5" cy="52.2" r="1.6" fill="#FFFFFF" />
            <!-- Gentle Smile -->
            <path id="avatar-mouth" d="M45 64 Q50 68 55 64" stroke="#C96A6A" stroke-width="2.2" stroke-linecap="round" fill="none" />
            <!-- Status Indicator Gem -->
            <circle id="avatar-gem" cx="50" cy="21" r="4.5" fill="#70DDD1" />
          </svg>
        </div>
        <div class="companion-status-box">
          <span class="companion-state-badge" id="companion-state-label">MENDENGAR</span>
          <p class="companion-headline" id="companion-headline">
            ACE siap mendengarkan instruksi Bahasa Indonesia darimu di ruang studio lokal.
          </p>
        </div>
      </div>

      <div class="story-feed" id="story-feed" aria-live="polite"></div>
    </section>
  </main>

  <script>
    const STATE = {
      conversationId: "conv_utama",
      lastSequence: 0,
      seenEventIds: new Set(),
      activeTaskId: null,
    };

    const STATE_HEADLINES = {
      mendengar: "ACE sedang mendengarkan dan siap menerima permintaan barumu.",
      bekerja: "ACE sedang menulis kode dan menjalankan pengujian di ruang kerja lokal.",
      belajar: "ACE sedang mempelajari pola baru dan memvalidasi eksperimen kecil.",
      menunggu: "ACE sedang menunggu syarat lanjutan atau balasan worker pendamping.",
      selesai: "Tugas terakhir berhasil diselesaikan dan lulus verifikasi otomatis."
    };

    function switchMobileTab(tab) {
      const pNgobrol = document.getElementById("panel-ngobrol");
      const pCerita = document.getElementById("panel-cerita");
      const bNgobrol = document.getElementById("tab-ngobrol");
      const bCerita = document.getElementById("tab-cerita");
      if (tab === "cerita") {
        pNgobrol.classList.add("hidden-mobile");
        pCerita.classList.remove("hidden-mobile");
        bCerita.classList.add("active");
        bNgobrol.classList.remove("active");
      } else {
        pCerita.classList.add("hidden-mobile");
        pNgobrol.classList.remove("hidden-mobile");
        bNgobrol.classList.add("active");
        bCerita.classList.remove("active");
      }
    }

    function updateCompanionAvatar(avatarState, customHeadline) {
      const valid = ["mendengar", "bekerja", "belajar", "menunggu", "selesai"].includes(avatarState)
        ? avatarState
        : "mendengar";
      const frame = document.getElementById("ace-anime-companion");
      const label = document.getElementById("companion-state-label");
      const headline = document.getElementById("companion-headline");
      frame.setAttribute("data-state", valid);
      label.textContent = valid.toUpperCase();
      headline.textContent = customHeadline || STATE_HEADLINES[valid];
    }

    function appendChatBubble(msg) {
      const container = document.getElementById("chat-messages");
      if (document.getElementById("msg-" + msg.message_id)) {
        return;
      }
      const bubble = document.createElement("div");
      bubble.id = "msg-" + msg.message_id;
      bubble.className = "msg-bubble " + (msg.role === "user" ? "msg-user" : "msg-assistant");

      const textNode = document.createElement("div");
      // Always use textContent so user/model HTML strings are safely escaped (WEB21)
      textNode.textContent = msg.text;
      bubble.appendChild(textNode);

      const meta = document.createElement("div");
      meta.className = "msg-meta";
      meta.textContent = (msg.role === "user" ? "Kamu" : "ACE") + " • " + (msg.created_at || "");
      bubble.appendChild(meta);

      container.appendChild(bubble);
      container.scrollTop = container.scrollHeight;
    }

    function prependStoryCard(evt) {
      if (!evt || !evt.story_text || STATE.seenEventIds.has(evt.event_id)) {
        return;
      }
      STATE.seenEventIds.add(evt.event_id);
      if (evt.sequence && evt.sequence > STATE.lastSequence) {
        STATE.lastSequence = evt.sequence;
      }

      const feed = document.getElementById("story-feed");
      const emptyPlaceholder = document.getElementById("story-empty");
      if (emptyPlaceholder) {
        emptyPlaceholder.remove();
      }

      const card = document.createElement("article");
      card.className = "story-card";
      card.id = "story-" + evt.event_id;

      const header = document.createElement("div");
      header.className = "story-card-header";
      const kindSpan = document.createElement("span");
      kindSpan.textContent = (evt.kind || "aktivitas").replace(/_/g, " ").toUpperCase();
      const timeSpan = document.createElement("span");
      timeSpan.textContent = evt.timestamp || "";
      header.appendChild(kindSpan);
      header.appendChild(timeSpan);
      card.appendChild(header);

      const p = document.createElement("p");
      p.className = "story-narrative";
      p.textContent = evt.story_text;
      card.appendChild(p);

      if (Array.isArray(evt.artifact_refs) && evt.artifact_refs.length > 0) {
        const artRow = document.createElement("div");
        evt.artifact_refs.forEach((ref) => {
          const base = String(ref).split("/").pop();
          const link = document.createElement("a");
          link.className = "artifact-chip";
          link.href = "/api/artifacts/" + encodeURIComponent(base);
          link.target = "_blank";
          link.rel = "noopener";
          link.textContent = "Berkas: " + base;
          artRow.appendChild(link);
        });
        card.appendChild(artRow);
      }

      const details = document.createElement("details");
      details.className = "evidence-drawer";
      const summary = document.createElement("summary");
      summary.textContent = "Lihat bukti teknis (" + (evt.summary_code || evt.kind) + ")";
      const pre = document.createElement("pre");
      pre.className = "evidence-pre";
      pre.textContent = JSON.stringify(
        {
          event_id: evt.event_id,
          task_id: evt.task_id,
          status: evt.status,
          model_backend: evt.model_backend,
          verification_passed: evt.verification_passed,
          technical_detail: evt.technical_detail || {},
        },
        null,
        2
      );
      details.appendChild(summary);
      details.appendChild(pre);
      card.appendChild(details);

      feed.prepend(card);
      updateCompanionAvatar(evt.avatar_state || "bekerja", evt.story_text);
      document.getElementById("story-count-badge").textContent = STATE.seenEventIds.size + " cerita tercatat";
    }

    async function refreshStatusAndHistory() {
      try {
        const [stRes, convRes, evRes] = await Promise.all([
          fetch("/api/status"),
          fetch("/api/conversations/" + encodeURIComponent(STATE.conversationId)),
          fetch("/api/events?after=" + STATE.lastSequence),
        ]);
        if (stRes.ok) {
          const st = await stRes.json();
          const modeLabel = st.offline_mode ? "Mode: Offline Lokal" : "Mode: " + String(st.mode || "lokal").toUpperCase();
          document.getElementById("text-mode").textContent = modeLabel;
          document.getElementById("badge-model").textContent = "Model: " + (st.active_backend || "lokal");
          if (st.active_task) {
            STATE.activeTaskId = st.active_task.task_id;
            document.getElementById("active-task-badge").textContent =
              st.active_task.title_id + " [" + st.active_task.status + "]";
          }
          updateCompanionAvatar(st.avatar_state || "mendengar");
        }
        if (convRes.ok) {
          const conv = await convRes.json();
          (conv.messages || []).forEach(appendChatBubble);
        }
        if (evRes.ok) {
          const evData = await evRes.json();
          const events = evData.events || [];
          if (events.length === 0 && STATE.seenEventIds.size === 0) {
            const feed = document.getElementById("story-feed");
            if (!document.getElementById("story-empty")) {
              const empty = document.createElement("p");
              empty.id = "story-empty";
              empty.style.color = "var(--text-secondary)";
              empty.textContent = "Belum ada aktivitas. Kirim pesan di panel Ngobrol dengan ACE untuk memulai!";
              feed.appendChild(empty);
            }
          } else {
            events.forEach(prependStoryCard);
          }
        }
      } catch (err) {
        console.warn("Gagal menyegarkan status:", err);
      }
    }

    async function sendChatMessage(text) {
      const btn = document.getElementById("send-btn");
      btn.disabled = true;
      updateCompanionAvatar("bekerja", "ACE sedang memproses permintaanmu...");
      const clientMsgId = "cmsg_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: STATE.conversationId,
            text: text,
            client_message_id: clientMsgId,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.user_message) appendChatBubble(data.user_message);
          if (data.assistant_message) appendChatBubble(data.assistant_message);
          if (data.task) {
            STATE.activeTaskId = data.task.task_id;
            document.getElementById("active-task-badge").textContent =
              data.task.title_id + " [" + data.task.status + "]";
          }
          await refreshStatusAndHistory();
        }
      } finally {
        btn.disabled = false;
      }
    }

    function submitChatForm(e) {
      e.preventDefault();
      const input = document.getElementById("chat-input");
      const val = input.value.trim();
      if (!val) return;
      input.value = "";
      sendChatMessage(val);
    }

    function sendQuickPrompt(text) {
      sendChatMessage(text);
    }

    async function controlActiveTask(action) {
      if (!STATE.activeTaskId) {
        await sendChatMessage(action === "pause" ? "hentikan dulu" : action === "resume" ? "lanjutkan" : "hentikan tugas");
        return;
      }
      const res = await fetch("/api/tasks/" + encodeURIComponent(STATE.activeTaskId) + "/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: action }),
      });
      if (res.ok) {
        await refreshStatusAndHistory();
      }
    }

    window.addEventListener("DOMContentLoaded", () => {
      refreshStatusAndHistory();
      setInterval(refreshStatusAndHistory, 4000);
    });
  </script>
</body>
</html>
"""


def find_available_port(host: str, preferred_port: int, max_probes: int = 25) -> int:
    """Return `preferred_port` if free on `host`, otherwise probe subsequent ports or OS ephemeral port (`WEB02`)."""
    for offset in range(max_probes):
        candidate = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
                return candidate
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


class ACEWebCore:
    """Shared application state and API dispatcher used by HTTP server and direct test harness."""

    def __init__(self, store: OperationalStore):
        self.store = store
        self.router = ModelRouter(store)
        self.coding = CodingAgentLoop(store)
        self.autonomy = AutonomyOrchestrator(store)
        self.chat_engine = ConversationalEngine(store)

    def get_status_payload(self) -> dict[str, Any]:
        hc = self.router.health_check()
        latest_task = self.store.get_latest_task("conv_utama")
        events = self.store.list_events(limit=25)
        last_evt = events[-1] if events else None
        avatar_state = last_evt["avatar_state"] if last_evt else "mendengar"
        if latest_task:
            if latest_task["status"] in ("PAUSED", "WAITING_FOR_DEPENDENCY"):
                avatar_state = "menunggu"
            elif latest_task["status"] == "LEARNING":
                avatar_state = "belajar"
            elif latest_task["status"] in ("ACTIVE", "VERIFYING"):
                avatar_state = "bekerja"
            elif latest_task["status"] == "COMPLETED":
                avatar_state = "selesai"

        frontier = self.store.list_frontier()
        return {
            "status": "ok",
            "release_version": self.store.get_meta("release_version"),
            "workspace": str(self.store.workspace),
            "mode": hc["mode"],
            "offline_mode": hc["offline_mode"],
            "active_backend": hc["active_backend"],
            "egress_attempts_blocked": hc["egress_attempts_blocked"],
            "avatar_state": avatar_state,
            "active_task": latest_task,
            "worker_consumer_active": self.autonomy.is_worker_consumer_active(),
            "last_heartbeat_at": self.store.get_meta("last_heartbeat_at", ""),
            "frontier_summary": {
                "total": len(frontier),
                "known_and_tested": sum(1 for f in frontier if f["status"] == "KNOWN_AND_TESTED"),
            },
            "gaps_open": len(self.store.list_gaps(status="OPEN")),
            "skills_active": len(self.store.list_skills(active_only=True)),
        }

    def control_task(self, task_id: str, action: str) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if not task:
            raise KeyError(f"Task tidak ditemukan: {task_id}")
        conv_id = task["conversation_id"]
        act = action.strip().lower()
        if act == "pause":
            updated = self.store.update_task(
                task_id,
                status="PAUSED",
                resume_condition="Dijeda oleh pengguna melalui kendali web/CLI.",
                next_action="tunggu_lanjutkan",
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=task_id,
                kind="task_paused",
                status="PAUSED",
                summary_code="task_paused_via_control",
                technical_detail={"reason": "dijeda langsung oleh pengguna"},
            )
            return {"task": updated, "action": "pause"}
        if act in ("stop", "cancel"):
            updated = self.store.update_task(
                task_id,
                status="CANCELLED",
                resume_condition="Dibatalkan oleh pengguna.",
                next_action="dibatalkan",
            )
            self.store.emit_event(
                conversation_id=conv_id,
                task_id=task_id,
                kind="task_paused",
                status="CANCELLED",
                summary_code="task_cancelled_via_control",
                technical_detail={"reason": "dihentikan dan dibatalkan oleh pengguna"},
            )
            return {"task": updated, "action": "stop"}
        if act == "resume":
            if task["status"] in ("PAUSED", "FAILED_WITH_RECOVERY_STATE", "WAITING_FOR_DEPENDENCY", "QUEUED"):
                res = self.coding.execute_coding_task(task_id, domain="expense_tracker")
                return {"task": res["task"], "action": "resume"}
            return {"task": task, "action": "resume"}
        raise ValueError(f"Aksi kendali tidak dikenal: {action}")

    def resolve_artifact(self, artifact_id: str) -> tuple[Path, str] | None:
        safe_name = Path(unquote(artifact_id)).name
        if not safe_name or safe_name in (".", ".."):
            return None
        for root_dir in (self.store.workspace / "projects", self.store.workspace / "artifacts"):
            for match in root_dir.rglob(safe_name):
                if match.is_file():
                    return match, match.read_text(encoding="utf-8", errors="replace")
        return None


def create_http_handler(core: ACEWebCore):
    class ACEHTTPRequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args) -> None:
            pass

        def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _send_html(self, html_text: str, status: int = HTTPStatus.OK) -> None:
            raw = html_text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw) if raw.strip() else {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            qs = parse_qs(parsed.query)

            if path == "/":
                self._send_html(ANIME_WEB_HTML)
                return

            if path == "/api/status":
                self._send_json(core.get_status_payload())
                return

            if path == "/api/conversations":
                conv = core.store.get_conversation("conv_utama")
                self._send_json({"conversations": [conv]})
                return

            if path.startswith("/api/conversations/"):
                conv_id = unquote(path.split("/api/conversations/", 1)[1]) or "conv_utama"
                self._send_json(core.store.get_conversation(conv_id))
                return

            if path == "/api/events":
                after_seq = int((qs.get("after") or ["0"])[0] or "0")
                inc_hb = (qs.get("include_heartbeats") or ["0"])[0] in ("1", "true")
                events = core.store.list_events(after_sequence=after_seq, include_heartbeats=inc_hb)
                accept = self.headers.get("Accept", "")
                if "text/event-stream" in accept or (qs.get("stream") or ["0"])[0] == "1":
                    chunks = []
                    for ev in events:
                        chunks.append(
                            f"id: {ev['sequence']}\nevent: activity\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
                        )
                    if not chunks:
                        chunks.append(": heartbeat\n\n")
                    raw = "".join(chunks).encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                last_seq = events[-1]["sequence"] if events else after_seq
                self._send_json({"events": events, "last_sequence": last_seq})
                return

            if path == "/api/story":
                st = core.get_status_payload()
                events = core.store.list_events(include_heartbeats=False, limit=30)
                cards = [ev for ev in reversed(events) if ev.get("story_text")]
                self._send_json({
                    "avatar_state": st["avatar_state"],
                    "current_story": cards[0]["story_text"] if cards else "ACE siap menerima instruksi.",
                    "cards": cards,
                    "last_heartbeat_at": st["last_heartbeat_at"],
                })
                return

            if path == "/api/tasks":
                self._send_json({"tasks": core.store.list_tasks()})
                return

            if path.startswith("/api/tasks/"):
                task_id = unquote(path.split("/api/tasks/", 1)[1])
                t = core.store.get_task(task_id)
                if not t:
                    self._send_json({"error": "Task tidak ditemukan"}, status=HTTPStatus.NOT_FOUND)
                    return
                t["receipts"] = core.store.list_receipts(task_id)
                t["work_orders"] = core.store.list_work_orders(task_id)
                self._send_json(t)
                return

            if path.startswith("/api/artifacts/"):
                art_id = path.split("/api/artifacts/", 1)[1]
                resolved = core.resolve_artifact(art_id)
                if not resolved:
                    self._send_json({"error": "Artefak tidak ditemukan"}, status=HTTPStatus.NOT_FOUND)
                    return
                file_path, content = resolved
                if (qs.get("format") or [""])[0] == "json":
                    self._send_json({"id": file_path.name, "path": str(file_path), "content": content})
                    return
                raw = content.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return

            if path == "/api/gaps":
                self._send_json({
                    "gaps": core.store.list_gaps(),
                    "frontier": core.store.list_frontier(),
                })
                return

            if path == "/api/skills":
                self._send_json({"skills": core.store.list_skills()})
                return

            if path == "/api/deliverables":
                self._send_json(core.store.export_deliverables_snapshot())
                return

            if path == "/api/experiments":
                self._send_json({"experiments": core.store.list_experiments()})
                return

            self._send_json({"error": f"Route tidak ditemukan: {path}"}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            try:
                body = self._read_json_body()
            except Exception as exc:
                self._send_json({"error": f"JSON tidak valid: {exc}"}, status=HTTPStatus.BAD_REQUEST)
                return

            if path == "/api/chat":
                text = str(body.get("text", "")).strip()
                if not text:
                    self._send_json({"error": "Pesan 'text' tidak boleh kosong"}, status=HTTPStatus.BAD_REQUEST)
                    return
                conv_id = str(body.get("conversation_id") or "conv_utama")
                client_msg_id = body.get("client_message_id")
                res = core.chat_engine.handle_user_message(
                    text,
                    conversation_id=conv_id,
                    client_message_id=str(client_msg_id) if client_msg_id else None,
                )
                events = core.store.list_events(include_heartbeats=False, limit=10)
                res["story_cards"] = [e for e in reversed(events) if e.get("story_text")]
                res["avatar_state"] = core.get_status_payload()["avatar_state"]
                self._send_json(res)
                return

            if path.startswith("/api/tasks/") and path.endswith("/control"):
                mid = path[len("/api/tasks/") : -len("/control")].strip("/")
                action = str(body.get("action", "")).strip()
                try:
                    res = core.control_task(mid, action)
                    self._send_json(res)
                except KeyError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return

            if path == "/api/heartbeat":
                ev = core.store.emit_event(
                    kind="heartbeat",
                    status="ACTIVE",
                    summary_code="daemon_heartbeat",
                    technical_detail={"note": "detak jantung rutin"},
                )
                self._send_json({"heartbeat": ev})
                return

            self._send_json({"error": f"Route POST tidak ditemukan: {path}"}, status=HTTPStatus.NOT_FOUND)

    return ACEHTTPRequestHandler


class ACEWebServer:
    """Manageable localhost ThreadingHTTPServer wrapper for `ace web` and automated tests."""

    def __init__(
        self,
        store: OperationalStore,
        *,
        host: str = "127.0.0.1",
        port: int = 8080,
        allow_lan: bool = False,
    ):
        # Rule WEB18: Refuse non-loopback bind unless allow_lan is explicitly enabled
        if host not in ("127.0.0.1", "localhost", "::1") and not allow_lan:
            raise ValueError(
                f"Pengikatan host '{host}' ditolak demi keamanan lokal. Gunakan 127.0.0.1 atau berikan --allow-lan."
            )
        self.store = store
        self.core = ACEWebCore(store)
        self.host = "127.0.0.1" if host == "localhost" else host
        self.requested_port = int(port)
        self.actual_port = find_available_port(self.host, self.requested_port)
        self.port_fallback_used = self.actual_port != self.requested_port
        handler_cls = create_http_handler(self.core)
        self.httpd = ThreadingHTTPServer((self.host, self.actual_port), handler_cls)
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.actual_port}"

    def start_background(self) -> str:
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def stop(self) -> None:
        if self._thread and self._thread.is_alive():
            self.httpd.shutdown()
            self._thread.join(timeout=3.0)
        self.httpd.server_close()
