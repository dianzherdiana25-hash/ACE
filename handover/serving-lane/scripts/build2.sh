#!/bin/bash
set -x
export PATH=/tmp/.local/bin:$PATH
cmake --version | head -1
cd /workspace/tools/ik-llama/src
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_AVX512=ON -DGGML_AVX512_VNNI=ON -DLLAMA_CURL=OFF -DGGML_RPC=OFF 2>&1 | tail -25
cmake --build build -j 4 --target llama-bench llama-cli 2>&1 | tail -15
ls -lh build/bin/
./build/bin/llama-bench --help 2>&1 | head -30
echo "BUILD2_DONE"
