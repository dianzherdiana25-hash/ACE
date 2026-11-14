#!/bin/bash
# Perplexity multiple-choice card runner (SSH door, outside MCP cgroup).
# Usage: run_ppl_card.sh <label> <gguf> <datadir> <threads> <outdir>
set -uo pipefail
LABEL=$1; GGUF=$2; DATA=$3; THR=$4; OUT=$5
PPL=/workspace/tools/llama.cpp/llama-b12316/llama-perplexity
mkdir -p "$OUT"
echo "=== PPL CARD label=$LABEL gguf=$GGUF data=$DATA threads=$THR start=$(date -Is)" | tee "$OUT/card.log"
sha256sum "$GGUF" | tee -a "$OUT/card.log"
for T in arc_easy arc_challenge hellaswag; do
  echo "--- task $T $(date -Is)" | tee -a "$OUT/card.log"
  /usr/bin/time -v "$PPL" -m "$GGUF" --multiple-choice -f "$DATA/$T.bin" -c 1024 -b 512 -t "$THR" > "$OUT/$T.log" 2>&1
  echo "rc=$? $T" | tee -a "$OUT/card.log"
  grep -E "Final result|Random chance" "$OUT/$T.log" | tee -a "$OUT/card.log"
done
echo "--- task winogrande $(date -Is)" | tee -a "$OUT/card.log"
/usr/bin/time -v "$PPL" -m "$GGUF" --winogrande -f "$DATA/winogrande.csv" -c 1024 -b 512 -t "$THR" > "$OUT/winogrande.log" 2>&1
echo "rc=$? winogrande" | tee -a "$OUT/card.log"
grep -E "Final Winogrande" "$OUT/winogrande.log" | tee -a "$OUT/card.log"
echo "=== PPL CARD DONE label=$LABEL end=$(date -Is)" | tee -a "$OUT/card.log"
