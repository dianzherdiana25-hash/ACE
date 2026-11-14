#!/bin/bash
BIN=/workspace/tools/ik-llama/src/build/bin/llama-bench
MODEL=/workspace/ace-omega/models/Qwen3-30B-A3B-Q4_K_M.gguf
cd /workspace/tools/ik-llama
echo "=== IK HELP (repack/spec flags)"
$BIN --help 2>&1 | grep -i -E 'rtr|repack|flash|mmap' | head
echo "=== IK PLAIN t1 r1"
$BIN -m $MODEL -p 512 -n 128 -t 1 -r 1 2>&1 | tail -8
echo "=== IK RTR t1 r1"
$BIN -m $MODEL -p 512 -n 128 -t 1 -r 1 -rtr 2>&1 | tail -8
echo "BENCH_IK_R1_DONE"
