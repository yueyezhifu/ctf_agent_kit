#!/bin/sh
# 示例题启动脚本：纯本地题无需起服务，仅准备环境。
# 远程服务题在此启动服务进程（如 socat / flask / 二进制服务）。
set -eu
echo "[example_caesar] challenge ready. ciphertext at /challenge/ciphertext.txt"
# 保持容器存活（服务题换成启动真实服务）
exec tail -f /dev/null
