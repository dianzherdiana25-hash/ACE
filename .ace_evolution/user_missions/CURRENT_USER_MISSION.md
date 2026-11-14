# ACE User Mission Work Order: `mission-0001b-dialog-alami`

- **Mission Sequence**: `2`
- **Title**: Dialog Alami & Perbaikan Obrolan Web/Termux (Misi 0001b)
- **Order SHA-256**: `f56a3a347d7dd5e33d1b39dcdf626784ad41c4bbe18366b1d4494024922bd30b`

## 1. Objective
Menjadikan ACE benar-benar mampu mengobrol alami dalam Bahasa Indonesia di Web Studio & CLI (Stage 0-4), menghilangkan balasan kaku/berulang, salah cocok fuzzy, pembajakan intent santai, dan merapikan tampilan chat browser.

## 2. Success Criteria
- Implement real, verified behavior with companion unit tests.

## 3. Target Files
- `code/ace_indo_nlp/morphology.py`
- `code/ace_indo_nlp/lexicon_kb.py`
- `code/ace_indo_nlp/discourse.py`
- `code/ace_indo_nlp/test_morphology.py`
- `code/ace_indo_nlp/test_lexicon_kb.py`
- `code/ace_indo_nlp/test_discourse.py`
- `code/ace_operational/speech_acquisition.py`
- `code/ace_operational/language.py`
- `code/ace_operational/web_server.py`
- `code/ace_operational/test_speech_acquisition.py`

## 4. Strictly Forbidden Custody & Upstream Paths
- `code/ace_autonomy/`
- `code/ace_host_controller/`
- `code/ace_mission/`
- `code/ace_runtime/`
- `docs/UPSTREAM_SOURCES.json`
- `evidence/`
- `tools/`

## 5. Acceptance Verification Commands
- `PYTHONPATH=code /usr/bin/python3 -m unittest discover -s code/ace_indo_nlp -p test_*.py -v`
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_speech_acquisition -v`
- `PYTHONPATH=code /usr/bin/python3 -m unittest ace_operational.test_edition4_acceptance -v`

Then ratify cleanly without clobbering `EVOLUTION_WORK_ORDER.json` via:
```bash
PYTHONPATH=code python3 -m ace_operational.oaie_cli --workspace ".ace_evolution" mission-verify --mission-id "mission-0001b-dialog-alami" --repo-root "."
```
