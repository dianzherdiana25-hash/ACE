#!/bin/bash
BIN=/workspace/tools/llama.cpp/llama-b12316/llama-cli
MODEL=/workspace/ace-omega/models/Qwen3-30B-A3B-Q4_K_M.gguf
cd /workspace/tools
PROMPT="The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. Repeat the previous sentence ten times, exactly as written, one per line:"
run() {
  name=$1; shift
  echo "=== SPEC $name"
  /usr/bin/time -v $BIN -m $MODEL -p "$PROMPT" -n 128 -t 1 --seed 42 --temp 0 --no-display-prompt "$@" > spec_${name}.txt 2> spec_${name}.err
  grep -E 'eval time|prompt eval time' spec_${name}.err | head -4
  # generated text is stdout
  sha256sum spec_${name}.txt
  grep -E 'Elapsed|Maximum resident' spec_${name}.err
}
run none --spec-type none
run ngram_simple --spec-type ngram-simple
run ngram_mod --spec-type ngram-mod
echo "SPEC_DONE"
