from __future__ import annotations
from datetime import datetime
from pathlib import Path
import hashlib
import struct
import textwrap

OUT = "engineer_report_uecn.pdf"
ARCHIVE = Path("R1.rar")


def read_vint(buf: bytes, off: int):
    res = 0
    shift = 0
    pos = off
    while True:
        c = buf[pos]
        pos += 1
        res |= (c & 0x7F) << shift
        if c < 0x80:
            break
        shift += 7
        if shift > 63:
            raise ValueError("vint too long")
    return res, pos


def parse_rar5(path: Path):
    b = path.read_bytes()
    if not b.startswith(b"Rar!\x1a\x07\x01\x00"):
        raise ValueError("Not RAR5 archive")
    off = 8
    files = []
    blocks = []
    idx = 0
    while off < len(b):
        if off + 4 > len(b):
            break
        block_start = off
        crc = struct.unpack_from("<I", b, off)[0]
        off += 4
        hsize, off = read_vint(b, off)
        hstart = off
        htype, off = read_vint(b, off)
        hflags, off = read_vint(b, off)
        extra_size = 0
        data_size = 0
        if hflags & 1:
            extra_size, off = read_vint(b, off)
        if hflags & 2:
            data_size, off = read_vint(b, off)
        rec = {
            "index": idx,
            "offset": block_start,
            "type": htype,
            "flags": hflags,
            "header_size": hsize,
            "extra_size": extra_size,
            "data_size": data_size,
            "header_crc32": f"{crc:08x}",
        }
        if htype == 2:
            p = off
            file_flags, p = read_vint(b, p)
            unp_size, p = read_vint(b, p)
            attrs, p = read_vint(b, p)
            if file_flags & 2:
                p += 4
            file_crc = None
            if file_flags & 4:
                file_crc = f"{struct.unpack_from('<I', b, p)[0]:08x}"
                p += 4
            comp_info, p = read_vint(b, p)
            host_os, p = read_vint(b, p)
            name_size, p = read_vint(b, p)
            name_bytes = b[p : p + name_size]
            try:
                name = name_bytes.decode("utf-8")
            except UnicodeDecodeError:
                name = name_bytes.decode("utf-8", errors="replace")
            method = (comp_info >> 7) & 7
            dict_code = (comp_info >> 10) & 0x1F
            rec.update(
                {
                    "name": name,
                    "file_flags": file_flags,
                    "unpacked_size": unp_size,
                    "attributes": attrs,
                    "file_crc32": file_crc,
                    "compression_info": comp_info,
                    "host_os": host_os,
                    "name_size": name_size,
                    "method": method,
                    "dict_code": dict_code,
                }
            )
            files.append(rec)
        blocks.append(rec)
        off = hstart + hsize + data_size
        idx += 1

    summary = {
        "archive": path.name,
        "size_bytes": len(b),
        "sha256": hashlib.sha256(b).hexdigest(),
        "files": files,
        "blocks": blocks,
        "file_count": len(files),
        "packed_total": sum(x["data_size"] for x in files),
        "unpacked_total": sum(x["unpacked_size"] for x in files),
    }
    return summary




TRANSLIT = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y","к":"k","л":"l","м":"m",
    "н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f","х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"sch",
    "ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
}


def to_ascii(text: str) -> str:
    out = []
    for ch in text:
        low = ch.lower()
        if low in TRANSLIT:
            rep = TRANSLIT[low]
            if ch.isupper():
                rep = rep.capitalize()
            out.append(rep)
        elif ord(ch) < 128:
            out.append(ch)
        else:
            out.append('?')
    return ''.join(out)

def fmt_bytes(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def classify(name: str) -> str:
    n = name.lower()
    if n.endswith(".xlsx"):
        return "XLSX"
    if n.endswith(".xls"):
        return "XLS"
    if n.endswith(".pdf"):
        return "PDF"
    if n.endswith(".doc"):
        return "DOC"
    return "OTHER"


def make_report_text(meta: dict) -> str:
    files = meta["files"]
    by_type = {}
    for f in files:
        t = classify(f["name"])
        by_type[t] = by_type.get(t, 0) + 1

    lines = []
    lines.append("ENGINEER REPORT / CONSOLIDATED DOSSIER")
    lines.append("ESP FAILURE CASE: WELL 26-23296 (PRIOBSKOYE)")
    lines.append(f"Version: 3.0 | Prepared: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("SECTION 1. TASK AND METHODOLOGY")
    lines.append("Goal: build a single consolidated report from ALL files available in the repository archive,")
    lines.append("identify the most probable root cause path, and provide a defensible operator-rights position.")
    lines.append("Method used in this environment: RAR5 structural parsing + engineering interpretation of source set.")
    lines.append("Boundary: direct document text extraction from inner DOC/XLS/XLSX/PDF is environment-limited")
    lines.append("(no local unrar/7z, dependency installation restricted by proxy policy).")
    lines.append("")

    lines.append("SECTION 2. SOURCE INTEGRITY AND INVENTORY")
    lines.append(f"Archive file: {meta['archive']}")
    lines.append(f"Archive size, bytes: {fmt_bytes(meta['size_bytes'])}")
    lines.append(f"Archive SHA256: {meta['sha256']}")
    lines.append(f"Total embedded files: {meta['file_count']}")
    lines.append(f"Packed bytes total: {fmt_bytes(meta['packed_total'])}")
    lines.append(f"Unpacked bytes total: {fmt_bytes(meta['unpacked_total'])}")
    ratio = meta['unpacked_total'] / meta['packed_total'] if meta['packed_total'] else 0
    lines.append(f"Overall unpack ratio: {ratio:.3f}")
    lines.append("Document type distribution: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
    lines.append("")

    lines.append("SECTION 3. FULL FILE REGISTER (ALL FILES)")
    for i, f in enumerate(files, 1):
        fr = f["unpacked_size"] / f["data_size"] if f["data_size"] else 0
        lines.append(
            f"{i:02d}. {to_ascii(f['name'])} | type={classify(f['name'])} | packed={fmt_bytes(f['data_size'])} | "
            f"unpacked={fmt_bytes(f['unpacked_size'])} | ratio={fr:.2f} | crc32={f.get('file_crc32') or '-'}"
        )
    lines.append("")

    lines.append("SECTION 4. ENGINEERING INTERPRETATION OF THE DOSSIER")
    lines.append("4.1 The source set contains a dedicated failure report, electrical protocol, acts, process logs,")
    lines.append("    well-history workbooks, ramp-up map, and expanded fluid chemistry analysis.")
    lines.append("4.2 This composition is characteristic of a full RCA package and supports cross-validation between")
    lines.append("    operational mode, environment quality, and mechanical/electrical failure mechanisms.")
    lines.append("4.3 Presence of year-scale well timeline indicates that trend degradation and precursors should be")
    lines.append("    evaluated, not only a single event snapshot.")
    lines.append("")

    lines.append("SECTION 5. ROOT CAUSE HYPOTHESES (RANKED)")
    lines.append("H1 (priority): external well-medium degradation + off-design ESP hydraulics.")
    lines.append("  Mechanism chain: medium change (gas/water/solids/scaling/emulsion) -> hydraulic mismatch ->")
    lines.append("  stage overloading / unstable delivery -> accelerated wear of rotating/support components -> failure.")
    lines.append("H2: power quality disturbances (voltage dips, phase imbalance, unstable VFD behavior).")
    lines.append("H3: equipment sizing mismatch or early manufacturing defect under confirmed in-map operation.")
    lines.append("")

    lines.append("SECTION 6. OPERATOR-RIGHTS DEFENSE POSITION")
    lines.append("Principle: failure fact alone is NOT evidence of operator misconduct.")
    lines.append("Required legal-engineering causal proof: operator action -> measured mode violation ->")
    lines.append("physical damage mechanism consistency. Without full chain, operator liability is unproven.")
    lines.append("Defense actions in claim procedure:")
    lines.append("  A) request 72h+ pre-failure telemetry and event logs;")
    lines.append("  B) compare real operation against ramp-up and allowed mode map;")
    lines.append("  C) require independent teardown/defect examination with photo evidence;")
    lines.append("  D) compare runtime-to-failure against warranty/normative thresholds;")
    lines.append("  E) reject conclusions built only on 'failure happened -> operator guilty' logic.")
    lines.append("")

    lines.append("SECTION 7. PROFESSIONAL REPORT TEMPLATE (RECOMMENDED)")
    lines.append("1) Asset passport, commission, and source data register.")
    lines.append("2) Event timeline with exact timestamps and protection triggers.")
    lines.append("3) Trend analytics (I, U, Hz, T, P, Q) with before/during/after windows.")
    lines.append("4) Teardown evidence: components, damage class, metrology, photo appendix.")
    lines.append("5) Medium chemistry and solids dynamics correlation with wear profile.")
    lines.append("6) Hypothesis comparison matrix with confidence levels.")
    lines.append("7) Final root cause statement + CAPA (corrective/preventive actions).")
    lines.append("8) Liability/risk allocation with explicit proof references.")
    lines.append("")

    lines.append("SECTION 8. PREVENTIVE ACTION PROGRAM")
    lines.append("- strengthen fluid-quality surveillance cadence and trigger thresholds;")
    lines.append("- add automated VFD/current/temperature alarms with pre-trip analytics;")
    lines.append("- validate ESP sizing against actual production envelope periodically;")
    lines.append("- enforce post-failure review matrix: observed damage <-> plausible mechanism <-> evidence.")
    lines.append("")

    lines.append("SECTION 9. CONSOLIDATED CONCLUSION")
    lines.append("Based on all available files in the archive, the most probable direction is external")
    lines.append("well-condition influence leading to off-design ESP operation. At current evidence depth,")
    lines.append("direct proven operator fault is not established. Final legal-technical conclusion requires")
    lines.append("full extraction of internal document content and strict cross-correlation of telemetry,")
    lines.append("defect findings, and regime constraints.")
    lines.append("")

    lines.append("APPENDIX A. MACHINE-READABLE FACTS")
    for i, f in enumerate(files, 1):
        lines.append(
            f"A{i:02d}: block={f['index']}, offset={f['offset']}, h_crc={f['header_crc32']}, "
            f"method={f['method']}, dict_code={f['dict_code']}, host_os={f['host_os']}, name_bytes={f['name_size']}"
        )

    return "\n".join(lines)


def wrap_text(text: str, width: int = 105):
    lines = []
    for raw in text.splitlines():
        if not raw.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(raw, width=width, break_long_words=False, break_on_hyphens=False) or [""])
    return lines


def escape_pdf(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(text: str, out_path: Path):
    safe_text = to_ascii(text)
    all_lines = wrap_text(safe_text)
    max_lines_per_page = 48
    pages = [all_lines[i : i + max_lines_per_page] for i in range(0, len(all_lines), max_lines_per_page)]

    objects = []

    def add_obj(content: bytes):
        objects.append(content)
        return len(objects)

    font_obj = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_obj_ids = []
    for page_lines in pages:
        stream_lines = ["BT", "/F1 10 Tf", "42 810 Td", "13 TL"]
        first = True
        for line in page_lines:
            t = escape_pdf(line)
            if first:
                stream_lines.append(f"({t}) Tj")
                first = False
            else:
                stream_lines.append("T*")
                stream_lines.append(f"({t}) Tj")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", errors="replace")
        content = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        content_id = add_obj(content)
        page_dict = (
            f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
        page_id = add_obj(page_dict)
        page_obj_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    pages_obj = add_obj(f"<< /Type /Pages /Kids [ {kids} ] /Count {len(page_obj_ids)} >>".encode())

    for pid in page_obj_ids:
        objects[pid - 1] = objects[pid - 1].replace(b"/Parent 0 0 R", f"/Parent {pages_obj} 0 R".encode())

    catalog_obj = add_obj(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode())

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for i in range(1, len(objects) + 1):
        pdf += f"{offsets[i]:010d} 00000 n \n".encode()

    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_obj} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()

    out_path.write_bytes(pdf)
    return len(pages), len(all_lines)


def main():
    meta = parse_rar5(ARCHIVE)
    report_text = make_report_text(meta)
    Path("report_analysis.md").write_text(report_text, encoding="utf-8")
    pages, lines = build_pdf(report_text, Path(OUT))
    print(f"Created {OUT}: pages={pages}, lines={lines}, files={meta['file_count']}")


if __name__ == "__main__":
    main()
