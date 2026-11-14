#!/bin/bash
# sqlite-vec trial runner (SSH door). Starts the nomic embedding server,
# runs trial.py --embed, kills the server. One small load (~0.4 GB).
set -uo pipefail
ROOT=/workspace/tools/sqlite-vec-intake
SRV=/workspace/tools/llama.cpp/llama-b12316/llama-server
MODEL=/workspace/ace-omega/models-embed/nomic-embed-text-v1.5.Q8_0.gguf
mkdir -p "$ROOT/results"
"$SRV" -m "$MODEL" --embedding --pooling mean -t 4 -np 4 -c 2048 --host 127.0.0.1 --port 18082 > "$ROOT/results/server.log" 2>&1 &
SPID=$!
trap "kill $SPID 2>/dev/null" EXIT
for i in $(seq 1 60); do curl -s http://127.0.0.1:18082/health | grep -q ok && break; sleep 2; done
curl -s http://127.0.0.1:18082/health; echo
cd "$ROOT"
./venv/bin/python trial.py --chunks chunks.jsonl --queries queries.jsonl --db "$ROOT/results/trial.db" --emb-cache "$ROOT/results/embeddings.jsonl" --server http://127.0.0.1:18082 --embed --out "$ROOT/results/results.json" 2>&1 | tee "$ROOT/results/trial.log"
echo "TRIAL_RUNNER_DONE"
