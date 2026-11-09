#!/usr/bin/env python3
"""
ACE Mobile Web Dashboard (Termux Native)
----------------------------------------
Lightweight, pure Python HTTP dashboard running at http://localhost:8080.
Accessible from any mobile browser on Android without installing extra packages.
Displays real-time evolution telemetry, discovered primitives, Merkle chain status, and live research logs.
"""
from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
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


def get_dashboard_data() -> dict:
    heartbeat = load_json(REPO_ROOT / "checkpoints" / "self_dev" / "daemon_heartbeat.json")
    research_state = load_json(REPO_ROOT / "checkpoints" / "self_dev" / "v03_researcher_state.json")
    primitives = load_json(REPO_ROOT / "checkpoints" / "self_dev" / "primitives_library.json")
    
    # Read last 30 log lines
    log_file = REPO_ROOT / "checkpoints" / "self_dev" / "daemon.log"
    log_lines = []
    if log_file.exists():
        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
            log_lines = lines[-35:]
        except Exception:
            pass

    return {
        "heartbeat": heartbeat,
        "research_state": research_state,
        "primitives": primitives,
        "log_lines": log_lines,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ACE Autonomous Evolution Dashboard</title>
    <style>
        :root {
            --bg: #0d1117;
            --card-bg: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --accent: #58a6ff;
            --green: #3fb950;
            --yellow: #d29922;
            --red: #f85149;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 12px;
            box-sizing: border-box;
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 16px;
        }
        .title {
            font-size: 1.25rem;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .badge {
            font-size: 0.75rem;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 600;
            background: #238636;
            color: #fff;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-bottom: 16px;
        }
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px;
        }
        .card-label {
            font-size: 0.75rem;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        .card-val {
            font-size: 1.3rem;
            font-weight: 700;
            color: #fff;
        }
        .section-title {
            font-size: 1rem;
            font-weight: 600;
            color: #fff;
            margin: 16px 0 8px 0;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .prim-box {
            background: #090d13;
            border: 1px solid #21262d;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 8px;
            font-family: monospace;
            font-size: 0.85rem;
        }
        .prim-name {
            color: var(--accent);
            font-weight: 600;
        }
        .prim-code {
            color: #7ee787;
            margin-top: 4px;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .log-box {
            background: #05070a;
            border: 1px solid #21262d;
            border-radius: 6px;
            padding: 10px;
            height: 240px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.75rem;
            color: #8b949e;
            white-space: pre-wrap;
        }
        .pulse {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--green);
            display: inline-block;
            box-shadow: 0 0 8px var(--green);
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="title">
            <span class="pulse"></span> ACE Auto-Evolution
        </div>
        <div class="badge" id="healthBadge">ONLINE</div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="card-label">Siklus Selesai</div>
            <div class="card-val" id="cycleCount">-</div>
        </div>
        <div class="card">
            <div class="card-label">Throughput / Jam</div>
            <div class="card-val" id="throughput">-</div>
        </div>
        <div class="card">
            <div class="card-label">Penggunaan RAM</div>
            <div class="card-val" id="ramUsage">-</div>
        </div>
        <div class="card">
            <div class="card-label">Penggunaan CPU</div>
            <div class="card-val" id="cpuUsage">-</div>
        </div>
    </div>

    <div class="section-title">🧬 Primitif Baru yang Ditemukan ACE</div>
    <div id="primitivesList">
        <div style="color: #8b949e; font-size: 0.85rem;">Memuat daftar primitif...</div>
    </div>

    <div class="section-title">📜 Log Riset Langsung (Real-time Stream)</div>
    <div class="log-box" id="logBox">Memuat stream log...</div>

    <script>
        async function updateDashboard() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                const hb = data.heartbeat || {};
                const stats = hb.resource_stats || {};
                const rstate = data.research_state || {};
                
                document.getElementById('cycleCount').textContent = hb.last_cycle_id || rstate.completed_cycles || '0';
                document.getElementById('throughput').textContent = (hb.cycle_throughput_per_hour || 0).toFixed(1);
                document.getElementById('ramUsage').textContent = (stats.rss_memory_mb || 0).toFixed(1) + ' MB';
                document.getElementById('cpuUsage').textContent = (stats.cpu_percent || 0).toFixed(1) + '%';
                
                // Primitives
                const prims = data.primitives || {};
                const primKeys = Object.keys(prims);
                const primContainer = document.getElementById('primitivesList');
                if (primKeys.length === 0) {
                    primContainer.innerHTML = '<div style="color: #8b949e; font-size: 0.85rem;">Belum ada primitif yang disimpan.</div>';
                } else {
                    primContainer.innerHTML = primKeys.map(k => {
                        const p = prims[k];
                        return `
                            <div class="prim-box">
                                <span class="prim-name">${p.name || k}</span> (Kompresi: ${p.compression_value || '1.0'}x)
                                <div class="prim-code">${p.source_code || p.expression_body || ''}</div>
                            </div>
                        `;
                    }).join('');
                }

                // Logs
                const logBox = document.getElementById('logBox');
                const logs = data.log_lines || [];
                logBox.textContent = logs.join('\\n');
                logBox.scrollTop = logBox.scrollHeight;

            } catch (e) {
                console.error("Dashboard poll error:", e);
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
        # Mute normal HTTP access logs to keep terminal quiet
        pass


def run_dashboard(port: int = PORT):
    print(f"\n🚀 [ACE Mobile Dashboard] Aktif di: http://localhost:{port}")
    print("   Buka browser di HP Anda untuk melihat grafik & log real-time.\n")
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    run_dashboard()
