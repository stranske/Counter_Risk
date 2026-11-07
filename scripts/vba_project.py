"""Read CFB stream chains and MS-OVBA compressed source, without text scanning.

Read-only: executable project creation/import is delegated to Excel. Parsing
source does not establish compilation or successful macro execution.
"""

from __future__ import annotations

import re
import struct

SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
END = 0xFFFFFFFE
FREE = 0xFFFFFFFF


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


class CompoundFile:
    """Read bounded FAT and mini-FAT chains and the directory storage tree."""

    def __init__(self, data: bytes):
        self.data = data
        if len(data) < 512 or data[:8] != SIGNATURE or data[28:30] != b"\xfe\xff":
            raise ValueError("Invalid CFB header")
        version, shift = _u16(data, 26), _u16(data, 30)
        if (version, shift) not in {(3, 9), (4, 12)} or _u16(data, 32) != 6:
            raise ValueError("Invalid CFB version/sector size")
        self.size = 1 << shift
        if len(data) % self.size:
            raise ValueError("Truncated CFB sectors")
        self.count = len(data) // self.size - 1
        difat = list(struct.unpack_from("<109I", data, 76))
        sector = _u32(data, 68)
        seen = set()
        for _ in range(_u32(data, 72)):
            if sector in seen:
                raise ValueError("Cyclic DIFAT")
            seen.add(sector)
            values = struct.unpack(f"<{self.size // 4}I", self.sector(sector))
            difat.extend(values[:-1])
            sector = values[-1]
        fat_sectors = [value for value in difat if value != FREE]
        if len(fat_sectors) != _u32(data, 44) or not fat_sectors:
            raise ValueError("Invalid CFB FAT")
        fat_bytes = b"".join(self.sector(value) for value in fat_sectors)
        self.fat = struct.unpack(f"<{len(fat_bytes) // 4}I", fat_bytes)
        directory = self.chain(_u32(data, 48), self.fat, self.sector)
        self.entries = [directory[pos : pos + 128] for pos in range(0, len(directory), 128)]
        if not self.entries or self.entries[0][66] != 5:
            raise ValueError("Invalid CFB root directory")
        root = self.entries[0]
        self.mini_stream = self.chain(_u32(root, 116), self.fat, self.sector)[
            : self.entry_size(root)
        ]
        mini_fat = self.chain(_u32(data, 60), self.fat, self.sector)
        if len(mini_fat) != _u32(data, 64) * self.size:
            raise ValueError("Invalid mini-FAT length")
        self.mini_fat = struct.unpack(f"<{len(mini_fat) // 4}I", mini_fat)
        self.streams: dict[str, bytes] = {}
        visited: set[int] = set()

        def walk(index: int, prefix: str) -> None:
            if index == FREE:
                return
            if index >= len(self.entries) or index in visited:
                raise ValueError("Invalid CFB directory tree")
            visited.add(index)
            entry = self.entries[index]
            length = _u16(entry, 64)
            if length < 2 or length > 64 or length % 2:
                raise ValueError("Invalid CFB directory name")
            name = entry[: length - 2].decode("utf-16le")
            walk(_u32(entry, 68), prefix)
            path = prefix + name
            kind = entry[66]
            if kind == 1:
                walk(_u32(entry, 76), path + "/")
            elif kind == 2:
                size = self.entry_size(entry)
                if size < 4096:
                    content = self.chain(_u32(entry, 116), self.mini_fat, self.mini_sector)
                else:
                    content = self.chain(_u32(entry, 116), self.fat, self.sector)
                if len(content) < size or path in self.streams:
                    raise ValueError("Invalid CFB stream size/name")
                self.streams[path] = content[:size]
            else:
                raise ValueError("Invalid CFB directory type")
            walk(_u32(entry, 72), prefix)

        walk(_u32(root, 76), "")

    @staticmethod
    def entry_size(entry: bytes) -> int:
        return struct.unpack_from("<Q", entry, 120)[0]

    def sector(self, index: int) -> bytes:
        if index >= self.count:
            raise ValueError("CFB sector outside file")
        return self.data[(index + 1) * self.size : (index + 2) * self.size]

    def mini_sector(self, index: int) -> bytes:
        content = self.mini_stream[index * 64 : (index + 1) * 64]
        if len(content) != 64:
            raise ValueError("Mini sector outside root stream")
        return content

    @staticmethod
    def chain(index, table, read) -> bytes:
        parts = []
        seen = set()
        while index != END:
            if index >= len(table) or index in seen:
                raise ValueError("Invalid or cyclic CFB chain")
            seen.add(index)
            parts.append(read(index))
            index = table[index]
        return b"".join(parts)


def decompress(data: bytes) -> bytes:
    """Decode MS-OVBA 2.4.1 compressed containers, rejecting truncated tokens."""
    if not data or data[0] != 1:
        raise ValueError("Invalid MS-OVBA compressed container")
    pos = 1
    output = bytearray()
    while pos < len(data):
        if pos + 2 > len(data):
            raise ValueError("Truncated compression header")
        header = _u16(data, pos)
        end = pos + (header & 0xFFF) + 3
        if (header >> 12) & 7 != 3 or end > len(data):
            raise ValueError("Invalid compression chunk")
        pos += 2
        start = len(output)
        if not header & 0x8000:
            if end - pos != 4096:
                raise ValueError("Invalid raw compression chunk")
            output.extend(data[pos:end])
            pos = end
            continue
        while pos < end:
            flags = data[pos]
            pos += 1
            for bit in range(8):
                if pos >= end:
                    break
                if flags & (1 << bit):
                    if pos + 2 > end:
                        raise ValueError("Truncated copy token")
                    token = _u16(data, pos)
                    pos += 2
                    bits = max(4, (len(output) - start - 1).bit_length())
                    length_bits = 16 - bits
                    length = (token & ((1 << length_bits) - 1)) + 3
                    offset = (token >> length_bits) + 1
                    if offset > len(output) - start:
                        raise ValueError("Invalid copy offset")
                    for _ in range(length):
                        output.append(output[-offset])
                else:
                    output.append(data[pos])
                    pos += 1
                if len(output) - start > 4096:
                    raise ValueError("Oversized decompressed chunk")
        if len(output) > 32 * 1024 * 1024:
            raise ValueError("Project exceeds source size limit")
    return bytes(output)


def project_modules(data: bytes) -> dict[str, str]:
    """Read declared module names, stream names and text offsets from VBA/dir."""
    try:
        streams = CompoundFile(data).streams
        if not {"PROJECT", "VBA/dir", "VBA/_VBA_PROJECT"} <= streams.keys():
            raise ValueError("Missing required VBA project streams")
        directory = decompress(streams["VBA/dir"])
        # PROJECTSYSKIND / PROJECTLCID / PROJECTLCIDINVOKE precede CODEPAGE.
        pos = 0
        codepage = None
        # Traverse sized directory records, including the exceptional VERSION record.
        count = None
        while pos < len(directory):
            kind, size = struct.unpack_from("<HI", directory, pos)
            pos += 6
            payload = directory[pos : pos + size]
            if len(payload) != size:
                raise ValueError("Truncated VBA dir record")
            if kind == 3:
                codepage = _u16(payload, 0)
            if kind == 0xF:
                if size != 2:
                    raise ValueError("Invalid PROJECTMODULES")
                count = _u16(payload, 0)
                pos += size
                break
            pos += size + (2 if kind == 9 else 0)
        if codepage is None or count is None or count == 0:
            raise ValueError("Missing VBA codepage/module inventory")
        encoding = f"cp{codepage}"
        result = {}
        name = stream = None
        offset = None
        for _ in range(count):
            while True:
                kind, size = struct.unpack_from("<HI", directory, pos)
                pos += 6
                value = directory[pos : pos + size]
                if len(value) != size:
                    raise ValueError("Truncated module record")
                pos += size
                if kind == 0x19:
                    name = value.decode(encoding)
                elif kind == 0x1A:
                    stream = value.decode(encoding)
                elif kind == 0x31:
                    offset = _u32(value, 0)
                elif kind == 0x2B:
                    break
            if name is None or stream is None or offset is None or name in result:
                raise ValueError("Incomplete/duplicate module inventory")
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                raise ValueError("Unsupported VBA module name")
            source = decompress(streams[f"VBA/{stream}"][offset:]).decode(encoding)
            source = source.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
            if f'Attribute VB_Name = "{name}"' not in source:
                raise ValueError("Module name/source mismatch")
            result[name] = source
            name = stream = offset = None
        return result
    except (KeyError, struct.error, UnicodeError, LookupError, IndexError) as exc:
        raise ValueError(f"Malformed VBA project: {exc}") from exc
