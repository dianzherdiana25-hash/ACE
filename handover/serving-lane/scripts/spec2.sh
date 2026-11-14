#!/bin/bash
BIN=/workspace/tools/llama.cpp/llama-b12316/llama-cli
MODEL=/workspace/ace-omega/models/Qwen3-30B-A3B-Q4_K_M.gguf
cd /workspace/tools
PROMPT="The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. Repeat the previous sentence ten times, exactly as written, one per line:"
run() {
  name=$1; shift
  echo "=== SPEC $name : $*"
  start=$(date +%s.%N)
  $BIN -m $MODEL -p "$PROMPT" -n 128 -t 1 --seed 42 --temp 0 --no-display-prompt "$@" > spec_${name}.txt 2> spec_${name}.err
  echo "rc=$?"
  end=$(date +%s.%N)
  echo "wall=$(echo "$end - $start" | bc)"
  grep -E 'prompt eval time|eval time' spec_${name}.err | tail -3
  echo "out_sha256:"; sha256sum spec_${name}.txt; wc -c spec_${name}.txt
}
run none --spec-type none
run ngram_simple --spec-type ngram-simple
run ngram_mod --spec-type ngram-mod
echo "SPEC2_DONE"
