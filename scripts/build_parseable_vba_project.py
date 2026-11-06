#!/usr/bin/env python3
"""Build a CFB/MS-OVBA project that ``project_modules`` can read.

This is a CI/parser stand-in for environments without Windows Excel. It does
not claim Excel compilation or macro execution. Prefer
``scripts/create_vba_project.py`` on Windows when producing executable workbooks.
"""

from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.vba_project import SIGNATURE, CompoundFile, decompress, project_modules

END = 0xFFFFFFFE
FREE = 0xFFFFFFFF
FAT_SECT = 0xFFFFFFFD
SECTOR = 512
MINI = 64
CUTOFF = 4096


def compress(data: bytes) -> bytes:
    """Literal-only MS-OVBA compressor with chunks small enough for the size field."""
    out = bytearray([1])
    max_chunk = 2048
    i = 0
    while i < len(data):
        chunk = data[i : i + max_chunk]
        i += len(chunk)
        payload = bytearray()
        j = 0
        while j < len(chunk):
            block = chunk[j : j + 8]
            payload.append(0)
            payload.extend(block)
            j += 8
        size_field = len(payload) - 1
        if size_field > 0xFFF:
            raise ValueError("compressed chunk exceeds MS-OVBA size field")
        header = 0x8000 | (0x3 << 12) | size_field
        out.extend(struct.pack("<H", header))
        out.extend(payload)
    return bytes(out)


def _record(kind: int, payload: bytes, version_extra: bytes = b"") -> bytes:
    return struct.pack("<HI", kind, len(payload)) + payload + version_extra


def build_dir(module_name: str, stream_name: str, codepage: int = 1252) -> bytes:
    enc = f"cp{codepage}"
    name_b = module_name.encode(enc)
    stream_b = stream_name.encode(enc)
    name_w = module_name.encode("utf-16le")
    stream_w = stream_name.encode("utf-16le")
    return b"".join(
        [
            _record(0x01, struct.pack("<I", 1)),
            _record(0x02, struct.pack("<I", 0x0409)),
            _record(0x14, struct.pack("<I", 0x0409)),
            _record(0x03, struct.pack("<H", codepage)),
            _record(0x04, b"VBAProject"),
            _record(0x05, b""),
            _record(0x40, b""),
            _record(0x06, b""),
            _record(0x3D, b""),
            _record(0x07, struct.pack("<I", 0)),
            _record(0x08, struct.pack("<I", 0)),
            _record(0x09, struct.pack("<I", 0x527A1F51), b"\x00\x00"),
            _record(0x0C, b""),
            _record(0x3C, b""),
            _record(0x0F, struct.pack("<H", 1)),
            _record(0x13, struct.pack("<H", 0xFFFF)),
            _record(0x19, name_b),
            _record(0x47, name_w),
            _record(0x1A, stream_b),
            _record(0x32, stream_w),
            _record(0x1C, b""),
            _record(0x48, b""),
            _record(0x31, struct.pack("<I", 0)),
            _record(0x1E, struct.pack("<I", 0)),
            _record(0x2C, struct.pack("<H", 0xB6FF)),
            _record(0x21, b""),
            _record(0x2B, b""),
            _record(0x10, b""),
        ]
    )


def _dir_entry(
    name: str,
    kind: int,
    *,
    left: int = FREE,
    right: int = FREE,
    child: int = FREE,
    start: int = 0,
    size: int = 0,
    color: int = 1,
) -> bytes:
    entry = bytearray(128)
    encoded = name.encode("utf-16le") + b"\x00\x00"
    if len(encoded) > 64:
        raise ValueError(f"directory name too long: {name}")
    entry[: len(encoded)] = encoded
    entry[64:66] = struct.pack("<H", len(encoded))
    entry[66] = kind
    entry[67] = color
    entry[68:72] = struct.pack("<I", left)
    entry[72:76] = struct.pack("<I", right)
    entry[76:80] = struct.pack("<I", child)
    entry[116:120] = struct.pack("<I", start)
    entry[120:128] = struct.pack("<Q", size)
    return bytes(entry)


def write_cfb(streams: dict[str, bytes]) -> bytes:
    """Serialize named streams into a version-3 512-byte-sector CFB."""
    mini_items = []
    fat_items = []
    for path, data in streams.items():
        (mini_items if len(data) < CUTOFF else fat_items).append((path, data))

    mini_data = bytearray()
    mini_fat: list[int] = []
    mini_starts: dict[str, tuple[int, int]] = {}
    for path, data in mini_items:
        if not data:
            mini_starts[path] = (END, 0)
            continue
        start = len(mini_fat)
        padded = data + b"\x00" * ((MINI - len(data) % MINI) % MINI)
        count = len(padded) // MINI
        for index in range(count):
            mini_fat.append(start + index + 1 if index + 1 < count else END)
            mini_data.extend(padded[index * MINI : (index + 1) * MINI])
        mini_starts[path] = (start, len(data))
    while mini_fat and len(mini_fat) % (SECTOR // 4):
        mini_fat.append(FREE)
    mini_fat_bytes = struct.pack(f"<{len(mini_fat)}I", *mini_fat) if mini_fat else b""

    vba_children = sorted(path.split("/", 1)[1] for path in streams if path.startswith("VBA/"))
    root_level: list[str] = []
    if vba_children:
        root_level.append("VBA")
    root_level.extend(sorted(path for path in streams if "/" not in path))

    entries: list[bytes] = [_dir_entry("Root Entry", 5)]
    node_indices: dict[str, int] = {}
    for name in root_level:
        node_indices[name] = len(entries)
        if name == "VBA":
            entries.append(_dir_entry("VBA", 1))
        else:
            start, size = mini_starts.get(name, (0, len(streams[name])))
            entries.append(_dir_entry(name, 2, start=start, size=size))
    for child in vba_children:
        path = f"VBA/{child}"
        node_indices[path] = len(entries)
        start, size = mini_starts.get(path, (0, len(streams[path])))
        entries.append(_dir_entry(child, 2, start=start, size=size))

    def patch(index: int, **fields: int) -> None:
        entry = bytearray(entries[index])
        if "left" in fields:
            entry[68:72] = struct.pack("<I", fields["left"])
        if "right" in fields:
            entry[72:76] = struct.pack("<I", fields["right"])
        if "child" in fields:
            entry[76:80] = struct.pack("<I", fields["child"])
        if "start" in fields:
            entry[116:120] = struct.pack("<I", fields["start"])
        if "size" in fields:
            entry[120:128] = struct.pack("<Q", fields["size"])
        entries[index] = bytes(entry)

    if root_level:
        patch(0, child=node_indices[root_level[0]])
        for index, name in enumerate(root_level):
            entry_index = node_indices[name]
            right = node_indices[root_level[index + 1]] if index + 1 < len(root_level) else FREE
            patch(entry_index, left=FREE, right=right)
            if name == "VBA" and vba_children:
                patch(entry_index, child=node_indices[f"VBA/{vba_children[0]}"])
        for index, child in enumerate(vba_children):
            entry_index = node_indices[f"VBA/{child}"]
            right = (
                node_indices[f"VBA/{vba_children[index + 1]}"]
                if index + 1 < len(vba_children)
                else FREE
            )
            patch(entry_index, left=FREE, right=right)

    dir_bytes = b"".join(entries)
    dir_bytes += b"\x00" * ((SECTOR - len(dir_bytes) % SECTOR) % SECTOR)
    dir_sectors_count = len(dir_bytes) // SECTOR

    fat_stream_data = {
        path: data + b"\x00" * ((SECTOR - len(data) % SECTOR) % SECTOR) for path, data in fat_items
    }
    mini_stream_padded = bytes(mini_data)
    if mini_stream_padded:
        mini_stream_padded += b"\x00" * ((SECTOR - len(mini_stream_padded) % SECTOR) % SECTOR)

    sector_payloads: list[bytes] = []
    allocations: dict[str, int] = {}

    def alloc_blob(label: str, blob: bytes) -> int:
        start = len(sector_payloads)
        for offset in range(0, len(blob), SECTOR):
            sector_payloads.append(blob[offset : offset + SECTOR])
        allocations[label] = start
        return start

    mini_start = alloc_blob("mini", mini_stream_padded) if mini_stream_padded else END
    mini_fat_start = alloc_blob("minifat", mini_fat_bytes) if mini_fat_bytes else END
    dir_start = alloc_blob("dir", dir_bytes)
    for path, blob in fat_stream_data.items():
        alloc_blob(path, blob)

    if mini_stream_padded:
        patch(0, start=mini_start, size=len(mini_data))
    for path, data in fat_items:
        patch(node_indices[path], start=allocations[path], size=len(data))

    dir_bytes = b"".join(entries)
    dir_bytes += b"\x00" * ((SECTOR - len(dir_bytes) % SECTOR) % SECTOR)
    for index in range(dir_sectors_count):
        sector_payloads[allocations["dir"] + index] = dir_bytes[
            index * SECTOR : (index + 1) * SECTOR
        ]

    n_data_sectors = len(sector_payloads)
    fat_sector_count = 1
    while True:
        total = n_data_sectors + fat_sector_count
        needed = (total + (SECTOR // 4) - 1) // (SECTOR // 4)
        if needed <= fat_sector_count:
            fat_sector_count = needed
            break
        fat_sector_count = needed

    fat_start = n_data_sectors
    total_sectors = n_data_sectors + fat_sector_count
    fat = [FREE] * (fat_sector_count * (SECTOR // 4))

    def link_range(start: int, count: int) -> None:
        for index in range(count):
            fat[start + index] = start + index + 1 if index + 1 < count else END

    if mini_stream_padded:
        link_range(mini_start, len(mini_stream_padded) // SECTOR)
    if mini_fat_bytes:
        link_range(mini_fat_start, len(mini_fat_bytes) // SECTOR)
    link_range(dir_start, dir_sectors_count)
    for path, blob in fat_stream_data.items():
        link_range(allocations[path], len(blob) // SECTOR)
    for index in range(fat_sector_count):
        fat[fat_start + index] = FAT_SECT

    header = bytearray(SECTOR)
    header[0:8] = SIGNATURE
    header[24:26] = struct.pack("<H", 0x003E)
    header[26:28] = struct.pack("<H", 3)
    header[28:30] = b"\xfe\xff"
    header[30:32] = struct.pack("<H", 9)
    header[32:34] = struct.pack("<H", 6)
    header[44:48] = struct.pack("<I", fat_sector_count)
    header[48:52] = struct.pack("<I", dir_start)
    header[56:60] = struct.pack("<I", CUTOFF)
    header[60:64] = struct.pack("<I", mini_fat_start if mini_fat_bytes else END)
    header[64:68] = struct.pack("<I", len(mini_fat_bytes) // SECTOR if mini_fat_bytes else 0)
    header[68:72] = struct.pack("<I", END)
    header[72:76] = struct.pack("<I", 0)
    difat = [FREE] * 109
    for index in range(fat_sector_count):
        difat[index] = fat_start + index
    for index, value in enumerate(difat):
        header[76 + 4 * index : 80 + 4 * index] = struct.pack("<I", value)

    out = bytearray(header)
    out.extend(b"".join(sector_payloads))
    out.extend(struct.pack(f"<{len(fat)}I", *fat))
    if len(out) != SECTOR * (1 + total_sectors):
        raise ValueError("CFB size mismatch")
    return bytes(out)


def build_runnerlaunch_project(bas_path: Path, fixture_path: Path) -> bytes:
    source = bas_path.read_text(encoding="utf-8")
    if not source.endswith("\n"):
        source += "\n"
    stored = source.replace("\n", "\r\n").encode("cp1252")
    if decompress(compress(stored)) != stored:
        raise ValueError("compressor round-trip failed")
    fixture_streams = CompoundFile(fixture_path.read_bytes()).streams
    project = write_cfb(
        {
            "PROJECT": (
                'ID="{00000000-0000-0000-0000-000000000000}"\r\n'
                "Module=RunnerLaunch\r\n"
                'Name="VBAProject"\r\n'
                'HelpContextID="0"\r\n'
                'VersionCompatible32="393222000"\r\n\r\n'
                "[Host Extender Info]\r\n"
                "&H00000001={3832D640-CF90-11CF-8E43-00A0C911005A};VBE;&H00000000\r\n"
            ).encode("cp1252"),
            "PROJECTwm": b"\x00\x00",
            "VBA/dir": compress(build_dir("RunnerLaunch", "RunnerLaunch")),
            "VBA/_VBA_PROJECT": fixture_streams["VBA/_VBA_PROJECT"],
            "VBA/RunnerLaunch": compress(stored),
        }
    )
    modules = project_modules(project)
    if modules.get("RunnerLaunch") != source:
        raise ValueError("built project RunnerLaunch does not match source")
    return project


def replace_workbook_vba(workbook_path: Path, project: bytes) -> None:
    tmp_path = workbook_path.with_suffix(workbook_path.suffix + ".tmp")
    with (
        zipfile.ZipFile(workbook_path, "r") as source,
        zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            data = project if info.filename == "xl/vbaProject.bin" else source.read(info.filename)
            target.writestr(info, data)
    tmp_path.replace(workbook_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bas-path", type=Path, default=Path("assets/vba/RunnerLaunch.bas"))
    parser.add_argument("--project-path", type=Path, default=Path("assets/vba/vbaProject.bin"))
    parser.add_argument(
        "--fixture-path", type=Path, default=Path("tests/fixtures/vba/excel_saved.bin")
    )
    parser.add_argument(
        "--workbook",
        action="append",
        type=Path,
        default=None,
        help="Workbook whose xl/vbaProject.bin should be replaced (repeatable).",
    )
    args = parser.parse_args(argv)
    workbooks = args.workbook or [
        Path("Runner.xlsm"),
        Path("assets/templates/counter_risk_template.xlsm"),
    ]
    project = build_runnerlaunch_project(args.bas_path, args.fixture_path)
    args.project_path.write_bytes(project)
    for workbook in workbooks:
        replace_workbook_vba(workbook, project)
        print(f"Updated {workbook}")
    print(f"Wrote parseable project to {args.project_path} ({len(project)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
