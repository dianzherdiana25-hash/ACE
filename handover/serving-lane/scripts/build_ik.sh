#!/bin/bash
set -x
cd /workspace/tools
mkdir -p ik-llama
cd ik-llama
EXPECTED=405b6c45219dbe72e174e7e6c8c11a79d4ac917113972cea3c03190d0ebfcb19
if [ ! -f ik.tar.gz ]; then
  curl -sL -o ik.tar.gz https://github.com/ikawrakow/ik_llama.cpp/archive/7aa7e01482db892b023bb9aace9a40567ab5297a.tar.gz
fi
ls -l ik.tar.gz
ACTUAL=$(sha256sum ik.tar.gz | cut -d' ' -f1)
echo "SHA256_ACTUAL=$ACTUAL"
echo "SHA256_EXPECTED=$EXPECTED"
if [ "$ACTUAL" != "$EXPECTED" ]; then echo "HASH_MISMATCH_ABORT"; exit 2; fi
echo "HASH_OK"
if [ ! -d src ]; then
  mkdir src && tar xzf ik.tar.gz -C src --strip-components=1
fi
head -2 src/LICENSE
if ! command -v cmake >/dev/null; then
  pip3 install --break-system-packages -q cmake 2>&1 | tail -2 || pip3 install --break-system-packages cmake
fi
cmake --version | head -1
cd src
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DGGML_AVX512=ON -DGGML_AVX512_VNNI=ON -DLLAMA_CURL=OFF -DGGML_RPC=OFF 2>&1 | tail -20
cmake --build build -j 4 --target llama-bench llama-cli 2>&1 | tail -20
ls -lh build/bin/
echo "BUILD_DONE"
