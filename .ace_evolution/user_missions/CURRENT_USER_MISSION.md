# ACE User Mission Work Order: `mission-0002-memori-jangka-panjang`

- **Mission Sequence**: `3`
- **Title**: Memori Jangka Panjang ACE (Episodik, Semantik, Prosedural & Lupa Terukur)
- **Order SHA-256**: `b51c5720365476c0be253c1764c05773fca9b3ac7105ba78af0507707ae020a5`

## 1. Objective
Menghubungkan CognitiveMemory (OMEGA-07) secara penuh ke ConversationalEngine, CodingAgentLoop/task episodes, Story Projector, dan Web Studio (CLI & HTTP) agar ACE mengingat fakta pengguna, preferensi, peristiwa tugas berbasis bukti terjangkar, menangani konflik/ralat (supersede), melindungi data privat, serta melupakan ingatan secara jujur melalui tombstone teraudit.

## 2. Success Criteria
- Integrasi nyata CognitiveMemory append-only hash-chained di OperationalStore workspace (episodic, semantic, procedural) yang bertahan lintas restart.
- Perintah Bahasa Indonesia eksplisit & tangkapan percakapan alami: simpan memori, tanya ingatan (bounded recall), koreksi/konflik (supersede), lupa jujur (tombstone), dan audit integritas memori.
- Pencatatan episodik & prosedural tugas dengan provenance evidence terjangkar dan deteksi negative_transfer_risk.
- Panel & API Memori Jangka Panjang di Web Studio (/api/memory, /api/memory/recall, /api/memory/forget) dengan perlindungan record privat.
- Zero regresi seluruh tes bahasa, acceptance Edition 4, OMEGA-07 memory, dan AST RealRepoAuditor.

## 3. Target Files
- `code/ace_operational/memory_bridge.py`
- `code/ace_operational/test_memory_bridge.py`
- `code/ace_operational/language.py`
- `code/ace_operational/story_projector.py`
- `code/ace_operational/web_server.py`

## 4. Strictly Forbidden Custody & Upstream Paths
- `code/ace_autonomy/`
- `code/ace_host_controller/`
- `code/ace_mission/`
- `code/ace_runtime/`
- `docs/UPSTREAM_SOURCES.json`
- `evidence/`
- `tools/`

## 5. Acceptance Verification Commands
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_memory_bridge -v`
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_cognitive_memory -v`
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_speech_acquisition -v`
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_edition4_acceptance -v`
- `/usr/bin/python3 tools/verify_sources.py`

Then ratify cleanly without clobbering `EVOLUTION_WORK_ORDER.json` via:
```bash
PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace ".ace_evolution" mission-verify --mission-id "mission-0002-memori-jangka-panjang" --repo-root "."
```
