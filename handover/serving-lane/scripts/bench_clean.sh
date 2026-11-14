#!/bin/bash
MODEL=/workspace/ace-omega/models/Qwen3-30B-A3B-Q4_K_M.gguf
UP=/workspace/tools/llama.cpp/llama-b12316/llama-bench
IK=/workspace/tools/ik-llama/src/build/bin/llama-bench
LOG=/workspace/tools/ik_bench_clean.log
: > $LOG
snap() { echo "[$1] $(date +%H:%M:%S) MemAvail=$(grep MemAvailable /proc/meminfo) other_model_procs=$(pgrep -c -f 'gguf' || true)" >> $LOG; }
run() { label=$1; shift; snap before_$label; echo "=== CELL $label : $*" >> $LOG; "$@" >> $LOG 2>&1; echo "=== END $label rc=$?" >> $LOG; snap after_$label; }
run control_b12316 $UP -m $MODEL -p 512 -n 128 -t 1 -r 1
run ik_plain $IK -m $MODEL -p 512 -n 128 -t 1 -r 1
run ik_rtr $IK -m $MODEL -p 512 -n 128 -t 1 -r 1 -rtr 1
echo "BENCH_CLEAN_DONE" >> $LOG
