"""gdb 交互式调试会话骨架（P1，对标 EnIGMA 交互式工具）。

pwn/rev 题刚需：通过 gdb 的 machine interface 模式（gdb --interpreter=mi2）
维持一个持久调试会话，支持下发命令、读取输出、断点/单步/查看内存等原语。
纯标准库 subprocess 实现。
"""

from __future__ import annotations

import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import List, Optional


@dataclass
class GdbResponse:
    """一次 gdb 命令的返回。"""

    command: str
    output: str
    stopped: bool = False          # 是否触发了 stop（断点/信号）
    stop_reason: str = ""          # 如 breakpoint-hit / signal-received
    signal: str = ""               # 如 SIGSEGV
    frame: str = ""                # 停止位置


class GdbSession:
    """持久 gdb 会话（MI2 模式 + console 命令透传）。

    用法::

        gdb = GdbSession("./vuln")
        gdb.execute("break main")
        gdb.execute("run")
        resp = gdb.execute("info registers")
        gdb.close()
    """

    def __init__(self, binary: str, gdb_path: str = "gdb",
                 startup_timeout: float = 15.0) -> None:
        self.binary = binary
        self._proc = subprocess.Popen(
            [gdb_path, "--interpreter=mi2", "--quiet", binary],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0)
        self._queue: "Queue[str]" = Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()
        self._closed = False
        self.history: List[GdbResponse] = []
        # 等待 (gdb) 提示符出现
        self._wait_prompt(startup_timeout)

    # -- 输出泵 -------------------------------------------------------------

    def _pump(self) -> None:
        assert self._proc.stdout is not None
        while True:
            line = self._proc.stdout.readline()
            if not line:
                break
            self._queue.put(line.decode(errors="replace").rstrip("\n"))

    def _wait_prompt(self, timeout: float) -> List[str]:
        """收集输出直到 (gdb) 提示符或超时。"""
        lines: List[str] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self._queue.get(timeout=0.2)
            except Empty:
                continue
            if line.strip() == "(gdb)":
                break
            lines.append(line)
        return lines

    # -- 命令执行 -------------------------------------------------------------

    def execute(self, command: str, timeout: float = 30.0) -> GdbResponse:
        """下发一条命令（支持 gdb console 命令与 MI 命令），解析结构化结果。"""
        if self._closed:
            raise RuntimeError("gdb 会话已关闭")
        assert self._proc.stdin is not None
        # console 命令统一走 interpreter-exec，保证输出回到 MI 流里
        if command.startswith("-"):
            mi_cmd = command
        else:
            escaped = command.replace("\\", "\\\\").replace('"', '\\"')
            mi_cmd = f'-interpreter-exec console "{escaped}"'
        self._proc.stdin.write(mi_cmd.encode() + b"\n")
        self._proc.stdin.flush()
        lines = self._wait_prompt(timeout)
        resp = self._parse(command, lines)
        self.history.append(resp)
        return resp

    @staticmethod
    def _parse(command: str, lines: List[str]) -> GdbResponse:
        text_parts: List[str] = []
        resp = GdbResponse(command=command, output="")
        for line in lines:
            if line.startswith('~"'):          # console 流输出
                text_parts.append(GdbSession._unescape(line[2:-1]))
            elif line.startswith("&"):
                continue                        # log 流，忽略
            elif line.startswith("*stopped"):
                resp.stopped = True
                m = re.search(r'reason="([^"]+)"', line)
                if m:
                    resp.stop_reason = m.group(1)
                m = re.search(r'signal-name="([^"]+)"', line)
                if m:
                    resp.signal = m.group(1)
                m = re.search(r'func="([^"]+)"', line)
                if m:
                    resp.frame = m.group(1)
        resp.output = "".join(text_parts)
        return resp

    @staticmethod
    def _unescape(s: str) -> str:
        return (s.replace("\\n", "\n").replace("\\t", "\t")
                 .replace('\\"', '"').replace("\\\\", "\\"))

    # -- 常用原语（语义化封装） ------------------------------------------------

    def break_at(self, location: str) -> GdbResponse:
        return self.execute(f"break {location}")

    def run(self, args: str = "") -> GdbResponse:
        return self.execute(f"run {args}".strip())

    def continue_(self) -> GdbResponse:
        return self.execute("continue")

    def stepi(self) -> GdbResponse:
        return self.execute("stepi")

    def registers(self) -> GdbResponse:
        return self.execute("info registers")

    def read_memory(self, address: str, size: int = 64) -> GdbResponse:
        return self.execute(f"x/{size}bx {address}")

    def disassemble(self, func: str = "") -> GdbResponse:
        return self.execute(f"disassemble {func}".strip())

    def backtrace(self) -> GdbResponse:
        return self.execute("bt")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.execute("quit")
        except Exception:
            pass
        if self._proc.poll() is None:
            self._proc.terminate()
