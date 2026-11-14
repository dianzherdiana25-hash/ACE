#!/bin/bash
MODEL=/workspace/ace-omega/models/Qwen3-30B-A3B-Q4_K_M.gguf
UP=/workspace/tools/llama.cpp/llama-b12316/llama-bench
IK=/workspace/tools/ik-llama/src/build/bin/llama-bench
guard() { # abort if server resident died
  if ! pgrep -f 'port 18080' >/dev/null; then echo "NOTE: 18080 server not running at $1"; fi
  echo "mem.current=$(cat /sys/fs/cgroup/system.slice/sandbox-mcp.service/memory.current) at $1"
}
echo "=== CONTROL b12316 t1 r1"; guard start
$UP -m $MODEL -p 512 -n 128 -t 1 -r 1 2>&1 | tail -6
guard after_control
echo "=== IK PLAIN t1 r1"
$IK -m $MODEL -p 512 -n 128 -t 1 -r 1 2>&1 | tail -6
guard after_ik_plain
echo "=== IK RTR t1 r1"
$IK -m $MODEL -p 512 -n 128 -t 1 -r 1 -rtr 1 2>&1 | tail -6
guard after_ik_rtr
echo "BENCH_ALL_R1_DONE"
