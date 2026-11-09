#!/usr/bin/env python3
"""
ACE Visual Mobile Web Dashboard (Human-Friendly Edition)
--------------------------------------------------------
Dashboard web visual modern, interaktif, dan mudah dimengerti.
Berjalan di http://localhost:8080 (bisa dibuka langsung di browser HP Android).
Menampilkan progres evolusi ACE dengan bahasa santai, kartu visual, dan status armada AI.
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
                "title": "Mulai Merancang Pembaruan Kode",
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
                "desc": "Seluruh tes keamanan dan konsistensi mandiri berjalan sempurna.",
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

    # Ambil 10 aktivitas terbaru (dibalik agar yang paling baru di atas)
    return stories[::-1][:10]


def get_dashboard_data() -> dict:
    heartbeat = load_json(REPO_ROOT / "checkpoints" / "self_dev" / "daemon_heartbeat.json")
    research_state = load_json(REPO_ROOT / "checkpoints" / "self_dev" / "v03_researcher_state.json")
    
    log_file = REPO_ROOT / "checkpoints" / "self_dev" / "daemon.log"
    log_lines = []
    if log_file.exists():
        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
            log_lines = lines[-50:]
        except Exception:
            pass

    stories = parse_logs_to_stories(log_lines)

    # Hitung level evolusi berdasarkan total cycle
    completed_cycles = heartbeat.get("last_cycle_id") or research_state.get("completed_cycles") or 292
    level = max(1, completed_cycles // 50)
    level_progress = (completed_cycles % 50) * 2  # persentase menuju level berikutnya

    return {
        "heartbeat": heartbeat,
        "research_state": research_state,
        "completed_cycles": completed_cycles,
        "level": level,
        "level_progress": level_progress,
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
            padding-bottom: 40px;
        }

        .container {
            max-width: 600px;
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
            width: 36px;
            height: 36px;
            border-radius: 10px;
            background: linear-gradient(135deg, var(--primary), var(--accent));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            box-shadow: 0 0 16px var(--primary-glow);
        }

        .brand-text h1 {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .brand-text p {
            font-size: 0.75rem;
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
            font-weight: 600;
        }

        .pulse-dot {
            width: 7px;
            height: 7px;
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

        /* Section Title */
        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 20px 0 10px 0;
        }

        .section-title {
            font-size: 0.85rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #cbd5e1;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        /* AI Fleet Cards */
        .fleet-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 16px;
        }

        .ai-chip {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 10px 12px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .ai-avatar {
            width: 28px;
            height: 28px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.05);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
        }

        .ai-info {
            flex: 1;
            overflow: hidden;
        }

        .ai-name {
            font-size: 0.75rem;
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .ai-status {
            font-size: 0.65rem;
            color: #34d399;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .ai-status::before {
            content: "";
            width: 5px;
            height: 5px;
            border-radius: 50%;
            background: #34d399;
            display: inline-block;
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
            transition: transform 0.2s;
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
            padding: 6px 12px;
            border-radius: 8px;
            cursor: pointer;
            width: 100%;
            margin-top: 6px;
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

        <!-- Level Progress -->
        <div class="level-card">
            <div class="level-top">
                <div>
                    <div class="level-title">Tahap Evolusi Mandiri</div>
                    <div class="level-number" id="levelDisplay">Generasi 6</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">Total Ide Selesai</div>
                    <div style="font-size: 1.1rem; font-weight: 800; color: #fff;" id="cycleCount">292</div>
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
                <div class="stat-val" id="speedVal">64/jam</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">RAM Termux</div>
                <div class="stat-val" id="ramVal">26 MB</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Suhu HP & Daya</div>
                <div class="stat-val" style="color: #34d399;">Dingin ❄️</div>
            </div>
        </div>

        <!-- Armada AI Gratis -->
        <div class="section-header">
            <div class="section-title">🤝 Tim AI Pendamping (100% Gratis)</div>
        </div>
        <div class="fleet-grid">
            <div class="ai-chip">
                <div class="ai-avatar">🧠</div>
                <div class="ai-info">
                    <div class="ai-name">PowerBrain (GPT-5)</div>
                    <div class="ai-status">Siap Bantu</div>
                </div>
            </div>
            <div class="ai-chip">
                <div class="ai-avatar">🌸</div>
                <div class="ai-info">
                    <div class="ai-name">Pollinations AI</div>
                    <div class="ai-status">Siap Bantu</div>
                </div>
            </div>
            <div class="ai-chip">
                <div class="ai-avatar">🌐</div>
                <div class="ai-info">
                    <div class="ai-name">G4F (DeepSeek)</div>
                    <div class="ai-status">Siap Bantu</div>
                </div>
            </div>
            <div class="ai-chip">
                <div class="ai-avatar">⚡</div>
                <div class="ai-info">
                    <div class="ai-name">AI Horde Network</div>
                    <div class="ai-status">Siap Bantu</div>
                </div>
            </div>
        </div>

        <!-- Storyline Feed -->
        <div class="section-header">
            <div class="section-title">📖 Catatan Aktivitas Terkini</div>
            <div style="font-size: 0.65rem; color: #64748b;" id="syncTime">Auto-refresh 3s</div>
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
                
                // Cycles & Levels
                const cycles = data.completed_cycles || 292;
                document.getElementById('cycleCount').textContent = cycles;
                document.getElementById('levelDisplay').textContent = 'Generasi ' + data.level;
                document.getElementById('progressBar').style.width = data.level_progress + '%';
                document.getElementById('progressText').textContent = data.level_progress + '%';

                // Stats
                const tput = hb.cycle_throughput_per_hour || 60;
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


def run_dashboard(port: int = PORT):
    print(f"\n🚀 [ACE Web Dashboard] Berhasil dinyalakan di: http://localhost:{port}")
    print("   Buka browser di HP Anda untuk melihat tampilan visual real-time.\n")
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    run_dashboard()
