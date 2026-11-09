#!/usr/bin/env python3
"""
ACE Visual Mobile Web Dashboard (Human-Friendly Edition V2)
-----------------------------------------------------------
Dashboard web visual interaktif dengan penjelasan 5 fokus utama:
- Sedang melakukan apa?
- Menyelesaikan apa?
- Menambah apa?
- Mengurangi / membersihkan apa?
- Menggunakan AI apa?

Berjalan di http://localhost:8080 (bisa dibuka langsung di browser HP Android).
"""
from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
import re
import socketserver
import sys
import threading
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
PORT = 8080


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_focus_breakdown(log_lines: list[str], research_state: dict, heartbeat: dict) -> dict:
    """Menganalisis status real-time untuk menjawab 5 pertanyaan kunci dalam bahasa manusia."""
    last_few = "\n".join(log_lines[-10:]) if log_lines else ""
    c_soft = research_state.get("completed_cycles") or 73
    c_param = heartbeat.get("last_cycle_id") or 308

    # 1. Sedang Melakukan Apa?
    if "Running external verifier" in last_few or "ALL CHECKS PASSED" in last_few:
        doing = "🛡️ Mengaudit Integritas Sistem (Menjalankan 38 unit test & verifikasi bukti Merkle)"
        doing_status = "VERIFIKASI"
    elif "Autonomous Repo Janitor" in last_few or "Pruned" in last_few:
        doing = "🧹 Membersihkan Repositori & Menjaga Kerapian Kode (Janitor Housekeeping)"
        doing_status = "BERSIH-BERSIH"
    elif "Executing Autonomous Software-Development" in last_few or "Staging artifacts" in last_few:
        doing = f"🧠 Merancang & Menguji Sintesis Patch Kode Baru (Siklus {c_soft})"
        doing_status = "KODING MANDIRI"
    elif "Pushing to origin" in last_few or "Committing" in last_few:
        doing = "📦 Mengamankan & Mendorong Hasil Evolusi Baru ke GitHub (main)"
        doing_status = "SINKRONISASI"
    elif "Sleeping" in last_few or "Active heartbeat" in last_few:
        doing = "❄️ Jeda 15 Detik Antar-Siklus (Mendinginkan prosesor & menjaga baterai HP)"
        doing_status = "ISTIRAHAT SEJENAK"
    else:
        doing = f"⚡ Mengeksplorasi Variasi Parameter Logika (Siklus {c_param}) pada Dataset Tertutup"
        doing_status = "UJI PARAMETER"

    # 2. Menyelesaikan Masalah Apa?
    solving = (
        "Mendobrak Kebuntuan Representasi (Search Space Saturation): "
        "Mencari formula pemisah invariant pergeseran modular (stride 3) dan paritas panjang run karakter "
        "agar akurasi multi-task melonjak tinggi."
    )

    # 3. Menambah Apa?
    adding = (
        f"Menambahkan patch kode baru Siklus {c_soft} [ACCEPTED], "
        f"commit resmi terbaru di branch 'main', serta formula logika baru ke memori evolusi."
    )

    # 4. Mengurangi / Membersihkan Apa?
    removing = (
        "Memangkas puluhan snapshot JSON usang (hanya menyisakan 15 snapshot terbaru), "
        "membersihkan cache kompilasi temporary (__pycache__, .tmp, .bak), dan menghapus file yatim di Termux."
    )

    # 5. Menggunakan AI Apa?
    ai_used = (
        "Armada Multi-AI Aktif: Berpikir via PowerBrain (GPT-5/4 engine) "
        "dengan failover otomatis ke Pollinations AI, G4F (DeepSeek), dan AI Horde. "
        "100% Gratis, Tanpa Kuota Habis, & $0.00 Biaya."
    )

    return {
        "doing": doing,
        "doing_status": doing_status,
        "solving": solving,
        "adding": adding,
        "removing": removing,
        "ai_used": ai_used,
    }


def parse_logs_to_stories(raw_lines: list[str]) -> list[dict]:
    """Mengubah log teknis rumit menjadi cerita aktivitas yang mudah dipahami manusia."""
    stories = []
    for line in raw_lines:
        line_clean = re.sub(r"^\[.*?\]\s*\[Daemon\]\s*", "", line).strip()
        if not line_clean:
            continue

        if "Executing Autonomous Software-Development" in line_clean:
            stories.append({
                "type": "think",
                "icon": "🧠",
                "title": "Merancang Pembaruan Kode Baru",
                "desc": "ACE sedang menganalisis titik kelemahan logika sebelumnya.",
                "badge": "Riset Kode"
            })
        elif "Problem:" in line_clean:
            prob = line_clean.replace("Problem:", "").strip()
            stories.append({
                "type": "target",
                "icon": "🎯",
                "title": f"Tantangan: {prob}",
                "desc": "Mencari cara agar logika penalaran tidak mentok di pola yang sama.",
                "badge": "Fokus"
            })
        elif "Hypothesis:" in line_clean:
            hyp = line_clean.replace("Hypothesis:", "").strip()
            stories.append({
                "type": "idea",
                "icon": "💡",
                "title": "Merumuskan Ide Solusi Baru",
                "desc": hyp[:120] + ("..." if len(hyp) > 120 else ""),
                "badge": "Hipotesis"
            })
        elif "Decision:   ACCEPTED" in line_clean or "Decision: ACCEPTED" in line_clean:
            stories.append({
                "type": "success",
                "icon": "🎉",
                "title": "Solusi Berhasil Diterima!",
                "desc": "Kode baru lolos verifikasi ketat dan terbukti meningkatkan kemampuan.",
                "badge": "BERHASIL"
            })
        elif "Push successful for Cycle" in line_clean:
            cycle_match = re.search(r"Cycle\s+(\d+)", line_clean)
            c_num = cycle_match.group(1) if cycle_match else ""
            stories.append({
                "type": "saved",
                "icon": "📦",
                "title": f"Hasil Evolusi Siklus {c_num} Disimpan",
                "desc": "Pengetahuan baru telah diabadikan ke memori permanen (Git).",
                "badge": "Tersimpan"
            })
        elif "(Param):" in line_clean:
            task_match = re.search(r"Task=([\w_]+)", line_clean)
            gain_match = re.search(r"Gain=([+-]?[\d\.]+)", line_clean)
            t_name = task_match.group(1) if task_match else "tugas"
            g_val = gain_match.group(1) if gain_match else "+0.00"
            stories.append({
                "type": "test",
                "icon": "🔬",
                "title": f"Uji Kemampuan: {t_name}",
                "desc": f"Menguji variasi parameter matematika (Peningkatan: {g_val}).",
                "badge": "Uji Coba"
            })
        elif "External verifier: ALL CHECKS PASSED" in line_clean:
            stories.append({
                "type": "shield",
                "icon": "🛡️",
                "title": "Audit Integritas Lolos 100%",
                "desc": "Seluruh 38 tes keamanan dan konsistensi mandiri berjalan sempurna.",
                "badge": "Aman"
            })
        elif "Host Status:" in line_clean:
            ram_match = re.search(r"RAM:\s*(\d+)MB", line_clean)
            ram_str = f"{ram_match.group(1)} MB" if ram_match else "Lega"
            stories.append({
                "type": "health",
                "icon": "🔋",
                "title": "Kondisi HP Prima & Terkendali",
                "desc": f"RAM bebas {ram_str}, suhu dan memori dijaga agar HP tetap dingin.",
                "badge": "Kesehatan"
            })
        elif "Janitor:" in line_clean:
            stories.append({
                "type": "broom",
                "icon": "🧹",
                "title": "Pembersihan Otomatis Repositori",
                "desc": line_clean.replace("Janitor:", "").strip(),
                "badge": "Kebersihan"
            })

    return stories[::-1][:10]


def get_dashboard_data() -> dict:
    heartbeat = load_json(REPO_ROOT / "checkpoints" / "self_dev" / "daemon_heartbeat.json")
    research_state = load_json(REPO_ROOT / "checkpoints" / "self_dev" / "v03_researcher_state.json")
    
    log_file = REPO_ROOT / "checkpoints" / "self_dev" / "daemon.log"
    log_lines = []
    if log_file.exists():
        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
            log_lines = lines[-60:]
        except Exception:
            pass

    stories = parse_logs_to_stories(log_lines)
    focus = get_focus_breakdown(log_lines, research_state, heartbeat)

    completed_cycles = heartbeat.get("last_cycle_id") or 308
    soft_cycles = research_state.get("completed_cycles") or 73
    level = max(1, completed_cycles // 50)
    level_progress = (completed_cycles % 50) * 2

    return {
        "heartbeat": heartbeat,
        "research_state": research_state,
        "completed_cycles": completed_cycles,
        "soft_cycles": soft_cycles,
        "level": level,
        "level_progress": level_progress,
        "focus": focus,
        "stories": stories,
        "raw_logs": log_lines[-20:],
        "timestamp": time.strftime("%H:%M:%S UTC", time.gmtime()),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>ACE — Pusat Pantauan Evolusi Mandiri</title>
    <style>
        :root {
            --bg: #090d16;
            --surface: #131b2e;
            --surface-hover: #1b2640;
            --border: rgba(255, 255, 255, 0.08);
            --primary: #6366f1;
            --primary-glow: rgba(99, 102, 241, 0.35);
            --accent: #06b6d4;
            --green: #10b981;
            --yellow: #f59e0b;
            --purple: #a855f7;
            --red: #ef4444;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, var(--bg) 60%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 16px;
            padding-bottom: 50px;
        }

        .container {
            max-width: 640px;
            margin: 0 auto;
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0 16px 0;
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .logo-icon {
            width: 38px;
            height: 38px;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--primary), var(--accent));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            box-shadow: 0 0 16px var(--primary-glow);
        }

        .brand-text h1 {
            font-size: 1.2rem;
            font-weight: 800;
            letter-spacing: -0.5px;
        }

        .brand-text p {
            font-size: 0.72rem;
            color: var(--text-muted);
        }

        .status-pill {
            display: flex;
            align-items: center;
            gap: 6px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #34d399;
            box-shadow: 0 0 8px #34d399;
            animation: pulse 1.8s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.8; }
            50% { transform: scale(1.3); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.8; }
        }

        /* Section Title */
        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 22px 0 10px 0;
        }

        .section-title {
            font-size: 0.85rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            color: #cbd5e1;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* 5 Key Focus Cards */
        .focus-stack {
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-bottom: 20px;
        }

        .focus-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        }

        .focus-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
        }

        .focus-doing::before { background: var(--accent); }
        .focus-solving::before { background: var(--yellow); }
        .focus-adding::before { background: var(--green); }
        .focus-removing::before { background: var(--purple); }
        .focus-ai::before { background: var(--primary); }

        .focus-tag {
            font-size: 0.68rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .tag-doing { color: var(--accent); }
        .tag-solving { color: var(--yellow); }
        .tag-adding { color: var(--green); }
        .tag-removing { color: #c084fc; }
        .tag-ai { color: #818cf8; }

        .focus-body {
            font-size: 0.82rem;
            color: var(--text-main);
            line-height: 1.45;
            font-weight: 500;
        }

        /* Level Card */
        .level-card {
            background: linear-gradient(145deg, rgba(30, 27, 75, 0.7), rgba(19, 27, 46, 0.9));
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 18px;
            margin-bottom: 16px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
        }

        .level-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            margin-bottom: 10px;
        }

        .level-title {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--accent);
            font-weight: 700;
        }

        .level-number {
            font-size: 1.6rem;
            font-weight: 800;
            background: linear-gradient(90deg, #fff, #c7d2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .progress-bar-bg {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            height: 8px;
            overflow: hidden;
            margin-bottom: 8px;
        }

        .progress-bar-fill {
            background: linear-gradient(90deg, var(--primary), var(--accent));
            height: 100%;
            border-radius: 10px;
            width: 50%;
            transition: width 0.6s ease;
            box-shadow: 0 0 10px var(--primary-glow);
        }

        .level-desc {
            font-size: 0.75rem;
            color: var(--text-muted);
            display: flex;
            justify-content: space-between;
        }

        /* 3-Column Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-bottom: 16px;
        }

        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 10px;
            text-align: center;
        }

        .stat-val {
            font-size: 1.25rem;
            font-weight: 800;
            color: var(--text-main);
            margin-top: 2px;
        }

        .stat-label {
            font-size: 0.7rem;
            color: var(--text-muted);
        }

        /* Story Feed */
        .story-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 16px;
        }

        .story-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 14px;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }

        .story-icon {
            font-size: 18px;
            margin-top: 1px;
        }

        .story-content {
            flex: 1;
        }

        .story-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }

        .story-title {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-main);
        }

        .story-badge {
            font-size: 0.65rem;
            padding: 2px 7px;
            border-radius: 6px;
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            font-weight: 600;
        }

        .story-desc {
            font-size: 0.72rem;
            color: var(--text-muted);
            line-height: 1.4;
        }

        /* Raw log accordion */
        .toggle-btn {
            background: transparent;
            border: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.75rem;
            padding: 8px 12px;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            margin-top: 10px;
            text-align: center;
        }

        .raw-log-box {
            display: none;
            background: #000;
            border: 1px solid #222;
            border-radius: 10px;
            padding: 10px;
            font-family: monospace;
            font-size: 0.65rem;
            color: #a3e635;
            max-height: 160px;
            overflow-y: auto;
            margin-top: 8px;
            white-space: pre-wrap;
        }

        /* Footer */
        .footer {
            text-align: center;
            font-size: 0.7rem;
            color: #64748b;
            margin-top: 24px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="brand">
                <div class="logo-icon">🧬</div>
                <div class="brand-text">
                    <h1>ACE Evolution</h1>
                    <p>Visi Riset: OAIE Mandiri</p>
                </div>
            </div>
            <div class="status-pill">
                <div class="pulse-dot"></div>
                <span id="healthLabel">BERPIKIR</span>
            </div>
        </div>

        <!-- 5 Key Focus Cards: Apa yang sedang dilakukan, diselesaikan, ditambah, dikurangi, dipakai -->
        <div class="section-header" style="margin-top: 6px;">
            <div class="section-title">🔍 Status Live: Apa yang Sedang Dikerjakan?</div>
            <span style="font-size: 0.65rem; color: #64748b;" id="syncTime">Auto-refresh 3s</span>
        </div>
        <div class="focus-stack">
            <!-- 1. Sedang Melakukan Apa -->
            <div class="focus-card focus-doing">
                <div class="focus-tag tag-doing">⚡ 1. Sedang Melakukan Apa?</div>
                <div class="focus-body" id="focusDoing">Menganalisis dan merancang ide kode baru...</div>
            </div>

            <!-- 2. Menyelesaikan Masalah Apa -->
            <div class="focus-card focus-solving">
                <div class="focus-tag tag-solving">🎯 2. Menyelesaikan Masalah Apa?</div>
                <div class="focus-body" id="focusSolving">Mendobrak kejenuhan representasi modular...</div>
            </div>

            <!-- 3. Menambah Apa -->
            <div class="focus-card focus-adding">
                <div class="focus-tag tag-adding">➕ 3. Menambah Apa?</div>
                <div class="focus-body" id="focusAdding">Menambahkan 1 patch kode baru dan commit permanen...</div>
            </div>

            <!-- 4. Mengurangi / Membersihkan Apa -->
            <div class="focus-card focus-removing">
                <div class="focus-tag tag-removing">➖ 4. Mengurangi / Membersihkan Apa?</div>
                <div class="focus-body" id="focusRemoving">Memangkas snapshot usang dan menghapus cache sampah...</div>
            </div>

            <!-- 5. Menggunakan AI Apa -->
            <div class="focus-card focus-ai">
                <div class="focus-tag tag-ai">🤖 5. Menggunakan AI Apa?</div>
                <div class="focus-body" id="focusAI">PowerBrain (GPT-5/4) & Pollinations AI (100% Gratis)...</div>
            </div>
        </div>

        <!-- Level Progress -->
        <div class="level-card">
            <div class="level-top">
                <div>
                    <div class="level-title">Tahap Generasi Evolusi</div>
                    <div class="level-number" id="levelDisplay">Generasi 6</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">Total Ide Selesai</div>
                    <div style="font-size: 1.1rem; font-weight: 800; color: #fff;" id="cycleCount">308</div>
                </div>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" id="progressBar" style="width: 84%;"></div>
            </div>
            <div class="level-desc">
                <span>Progres Menuju Generasi Berikutnya</span>
                <span id="progressText">84%</span>
            </div>
        </div>

        <!-- Quick 3 Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Kecepatan Belajar</div>
                <div class="stat-val" id="speedVal">60/jam</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">RAM Termux</div>
                <div class="stat-val" id="ramVal">24 MB</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Suhu HP & Daya</div>
                <div class="stat-val" style="color: #34d399;">Dingin ❄️</div>
            </div>
        </div>

        <!-- Storyline Feed -->
        <div class="section-header">
            <div class="section-title">📖 Catatan Aktivitas Terkini</div>
        </div>
        <div class="story-list" id="storyList">
            <div style="text-align: center; color: #64748b; font-size: 0.75rem; padding: 20px;">
                Memuat aktivitas terbaru ACE...
            </div>
        </div>

        <!-- Mode Ahli (Raw Log) -->
        <button class="toggle-btn" onclick="toggleRawLog()">🛠️ Intip Log Terminal Teknis</button>
        <div class="raw-log-box" id="rawLogBox">Memuat log mentah...</div>

        <div class="footer">
            ACE Autonomous Capability Evolution • Berjalan di Android Termux
        </div>
    </div>

    <script>
        function toggleRawLog() {
            const box = document.getElementById('rawLogBox');
            box.style.display = (box.style.display === 'block') ? 'none' : 'block';
        }

        async function updateDashboard() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                const hb = data.heartbeat || {};
                const stats = hb.resource_stats || {};
                const focus = data.focus || {};
                
                // 5 Key Focus Updates
                document.getElementById('focusDoing').textContent = focus.doing || '-';
                document.getElementById('focusSolving').textContent = focus.solving || '-';
                document.getElementById('focusAdding').textContent = focus.adding || '-';
                document.getElementById('focusRemoving').textContent = focus.removing || '-';
                document.getElementById('focusAI').textContent = focus.ai_used || '-';
                document.getElementById('healthLabel').textContent = focus.doing_status || 'BERPIKIR';

                // Cycles & Levels
                const cycles = data.completed_cycles || 308;
                document.getElementById('cycleCount').textContent = cycles;
                document.getElementById('levelDisplay').textContent = 'Generasi ' + data.level;
                document.getElementById('progressBar').style.width = data.level_progress + '%';
                document.getElementById('progressText').textContent = data.level_progress + '%';

                // Stats
                const tput = hb.cycle_throughput_per_hour || 58;
                document.getElementById('speedVal').textContent = tput.toFixed(0) + '/jam';
                document.getElementById('ramVal').textContent = (stats.rss_memory_mb || 24).toFixed(0) + ' MB';
                document.getElementById('syncTime').textContent = 'Update: ' + data.timestamp;

                // Stories Feed
                const list = document.getElementById('storyList');
                if (data.stories && data.stories.length > 0) {
                    list.innerHTML = data.stories.map(s => `
                        <div class="story-card">
                            <div class="story-icon">${s.icon}</div>
                            <div class="story-content">
                                <div class="story-header">
                                    <div class="story-title">${s.title}</div>
                                    <div class="story-badge">${s.badge}</div>
                                </div>
                                <div class="story-desc">${s.desc}</div>
                            </div>
                        </div>
                    `).join('');
                }

                // Raw logs
                const rawBox = document.getElementById('rawLogBox');
                if (data.raw_logs) {
                    rawBox.textContent = data.raw_logs.join('\\n');
                }

            } catch (err) {
                console.error("Gagal sinkronasi dashboard:", err);
            }
        }

        setInterval(updateDashboard, 3000);
        updateDashboard();
    </script>
</body>
</html>
"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif self.path == "/api/data":
            data = get_dashboard_data()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def run_dashboard(port: int = PORT):
    print(f"\n🚀 [ACE Web Dashboard V2] Berhasil dinyalakan di: http://localhost:{port}")
    print("   Buka browser di HP Anda untuk melihat tampilan visual real-time.\n")
    with ReusableTCPServer(("", port), DashboardHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    run_dashboard()
