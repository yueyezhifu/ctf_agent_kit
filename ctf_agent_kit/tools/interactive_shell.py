"""pwntools 风格持久交互 shell / 远程连接骨架（P1，对标 EnIGMA IATs）。

pwn/rev 题刚需：与远程服务保持长连接，支持 recvuntil/sendline 等
pwntools 语义的交互原语。纯标准库 socket 实现，支持本地进程与 TCP 远端。
"""

from __future__ import annotations

import re
import socket
import subprocess
import threading
import time
from typing import Optional, Union


class TubeClosed(Exception):
    """连接已关闭。"""


class InteractiveShell:
    """持久交互通道基类：buffered recv / sendline / recvuntil。

    语义对齐 pwntools tube：
    - ``recvuntil(delim)``  读到分隔符为止（含分隔符）
    - ``sendline(data)``    发送一行
    - ``recvline()``        读一行
    - ``interactive()``     进入人工接管模式（骨架：透传 stdin/stdout）
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self._buffer = bytearray()
        self._closed = False

    # -- 底层读写（子类实现） ----------------------------------------------

    def _read(self, n: int = 4096) -> bytes:
        raise NotImplementedError

    def _write(self, data: bytes) -> None:
        raise NotImplementedError

    # -- pwntools 风格原语 ---------------------------------------------------

    def recv(self, n: int = 4096, timeout: Optional[float] = None) -> bytes:
        """读至多 n 字节（先消费缓冲区）。"""
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        while len(self._buffer) < n:
            if self._closed:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            chunk = self._read(n - len(self._buffer))
            if not chunk:
                self._closed = True
                break
            self._buffer.extend(chunk)
        out = bytes(self._buffer[:n])
        del self._buffer[:n]
        return out

    def recvuntil(self, delim: bytes, timeout: Optional[float] = None,
                  drop: bool = False) -> bytes:
        """读到分隔符为止；EOF/超时抛 TubeClosed 或返回已读内容。"""
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        while True:
            idx = self._buffer.find(delim)
            if idx >= 0:
                end = idx + len(delim)
                out = bytes(self._buffer[:end])
                del self._buffer[:end]
                return out[:-len(delim)] if drop else out
            if self._closed:
                raise TubeClosed("连接已关闭，缓冲区剩余: " + repr(bytes(self._buffer)))
            if time.monotonic() >= deadline:
                raise TimeoutError(f"recvuntil 超时，等待 {delim!r}")
            chunk = self._read()
            if not chunk:
                self._closed = True
            else:
                self._buffer.extend(chunk)

    def recvline(self, timeout: Optional[float] = None) -> bytes:
        return self.recvuntil(b"\n", timeout=timeout)

    def send(self, data: Union[bytes, str]) -> None:
        if isinstance(data, str):
            data = data.encode()
        if self._closed:
            raise TubeClosed("连接已关闭")
        self._write(data)

    def sendline(self, data: Union[bytes, str] = b"") -> None:
        if isinstance(data, str):
            data = data.encode()
        self.send(data + b"\n")

    def sendlineafter(self, delim: bytes, data: Union[bytes, str],
                      timeout: Optional[float] = None) -> bytes:
        """先 recvuntil 再 sendline，返回收到的内容（pwntools 同款）。"""
        received = self.recvuntil(delim, timeout=timeout)
        self.sendline(data)
        return received

    def interactive(self) -> None:  # pragma: no cover - 需要人工终端
        """人工接管模式骨架：双向透传，直到用户输入 Ctrl+]。"""
        raise NotImplementedError("骨架版本不支持人工接管，请用脚本化收发")

    def close(self) -> None:
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed


class RemoteShell(InteractiveShell):
    """TCP 远程服务持久连接（nc 的 pwntools 版）。"""

    def __init__(self, host: str, port: int, timeout: float = 10.0,
                 tls: bool = False) -> None:
        super().__init__(timeout)
        self.host, self.port = host, port
        sock = socket.create_connection((host, port), timeout=timeout)
        if tls:
            import ssl
            sock = ssl.create_default_context().wrap_socket(
                sock, server_hostname=host)
        self._sock = sock
        self._sock.settimeout(timeout)

    def _read(self, n: int = 4096) -> bytes:
        try:
            return self._sock.recv(n)
        except socket.timeout:
            return b""

    def _write(self, data: bytes) -> None:
        self._sock.sendall(data)

    def close(self) -> None:
        super().close()
        try:
            self._sock.close()
        except OSError:
            pass


class LocalProcessShell(InteractiveShell):
    """本地进程交互（如调试本地 vuln 二进制）。"""

    def __init__(self, argv: list, timeout: float = 10.0) -> None:
        super().__init__(timeout)
        self._proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0)
        self._lock = threading.Lock()

    def _read(self, n: int = 4096) -> bytes:
        if self._proc.stdout is None or self._proc.poll() is not None:
            return b""
        with self._lock:
            return self._proc.stdout.read1(n) if hasattr(
                self._proc.stdout, "read1") else self._proc.stdout.read(n)

    def _write(self, data: bytes) -> None:
        if self._proc.stdin is None:
            raise TubeClosed("进程 stdin 不可用")
        self._proc.stdin.write(data)
        self._proc.stdin.flush()

    def close(self) -> None:
        super().close()
        if self._proc.poll() is None:
            self._proc.terminate()


# -- 便捷构造函数（pwntools 风格命名） ---------------------------------------

def remote(host: str, port: int, timeout: float = 10.0, tls: bool = False) -> RemoteShell:
    return RemoteShell(host, port, timeout=timeout, tls=tls)


def process(argv: list, timeout: float = 10.0) -> LocalProcessShell:
    return LocalProcessShell(argv, timeout=timeout)


def regex_search(data: bytes, pattern: str) -> Optional[bytes]:
    """在工具输出中正则提取（辅助 flag/地址抽取）。"""
    m = re.search(pattern.encode() if isinstance(pattern, str) else pattern, data)
    return m.group(0) if m else None
