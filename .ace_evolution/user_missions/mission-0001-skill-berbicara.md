# ACE User Mission Work Order: `mission-0001-skill-berbicara`

- **Mission Sequence**: `1`
- **Title**: Misi Pengguna 0001: Skill Berbicara Bertahap 4 Tahap (Teks & Memori)
- **Order SHA-256**: `59a29baa324e0027a1813b16e5bab94ede6d612feb0d300c266c5d696d4629e8`

## 1. Objective
Implementasi penguasaan keterampilan berbicara Bahasa Indonesia 4 tahap (Fonotaktik/Suku Kata -> Kata Pertama & Leksikon Persisten SQLite -> Frasa Telegrafik 2-3 Kata -> Ujaran Kontekstual Terverifikasi) beserta ujian holdout antartahap, dapat diajari kata baru lewat chat, dan terintegrasi ke ConversationalEngine, AutonomousEngine, StoryProjector, serta Web UI tanpa regresi.

## 2. Success Criteria
- Kurikulum 4 tahap progresif + ujian holdout antartahap nyata tanpa stub
- Leksikon kata persisten di OperationalStore SQLite & bisa diajari kata baru via chat
- Integrasi ke ConversationalEngine, ContinuousAutonomousEngine, StoryProjector, dan ACEWebCore
- Zero regresi audit statis dan seluruh acceptance test Edition 4 serta test_speech_acquisition lulus

## 3. Target Files
- `code/ace_operational/speech_acquisition.py`
- `code/ace_operational/test_speech_acquisition.py`
- `code/ace_operational/language.py`
- `code/ace_operational/autonomous_engine.py`
- `code/ace_operational/web_server.py`
- `code/ace_operational/story_projector.py`

## 4. Strictly Forbidden Custody & Upstream Paths
- `code/ace_autonomy/`
- `code/ace_host_controller/`
- `code/ace_mission/`
- `code/ace_runtime/`
- `docs/UPSTREAM_SOURCES.json`
- `evidence/`
- `tools/`

## 5. Acceptance Verification Commands
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_speech_acquisition -v`
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_edition4_acceptance -v`

Then ratify cleanly without clobbering `EVOLUTION_WORK_ORDER.json` via:
```bash
PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace ".ace_evolution" mission-verify --mission-id "mission-0001-skill-berbicara" --repo-root "."
```
