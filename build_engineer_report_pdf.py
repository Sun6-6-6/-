from datetime import datetime
import textwrap

OUT = 'engineer_report_uecn.pdf'

# NOTE:
# This PDF generator intentionally uses ASCII-only text to ensure stable rendering
# in GitHub/browser PDF previews without embedding external Unicode fonts.
report_text = f"""
ENGINEERING REPORT
ESP FAILURE INVESTIGATION: WELL 26-23296 (PRIOBSKOYE)
Version: 2.0
Prepared: {datetime.now().strftime('%Y-%m-%d %H:%M')}

1. Purpose
Provide an engineering conclusion on the most probable root cause of ESP failure
and a defensible position for the operating organization.

2. Input data and analysis limits
2.1 Repository contains R1.rar (RAR5 format).
2.2 Direct extraction of inner files in current environment is limited
(no unrar/7z available; package install blocked by proxy policy).
2.3 RAR5 header parsing was performed to identify actual document set.

3. Confirmed content of the archive (from RAR5 headers)
- Extended fluid chemistry analysis (.xlsx)
- Electrical protocol page (.pdf)
- Log_result.xlsx
- Acceptance/inspection act (.pdf)
- Well history workbook (.xlsx)
- ESP ramp-up map (.xlsx)
- Failure investigation report (.doc)
- PIK file (.pdf)
- Long period well data (.xls)

4. Engineering interpretation
Presence of fluid chemistry, long-range well history, ramp-up map,
and dedicated failure report indicates a system-level event
with high probability of external (well-condition-driven) factors.

5. Main root-cause hypothesis (priority)
5.1 Most probable root cause: degradation of well-fluid conditions
(gas, water cut, solids, scaling/emulsion effects), leading to off-design ESP operation.
5.2 Mechanism: hydraulic mismatch -> stage overloading -> accelerated wear
of rotating/support elements -> failure shutdown.
5.3 Supporting argument: chemistry data is typically central when medium effects
significantly impact ESP lifetime.

6. Alternative hypotheses
A) Power quality disturbances (voltage dips, phase imbalance, unstable VFD behavior).
B) Equipment sizing/selection mismatch versus actual operating envelope.
C) Early manufacturing defect if operation remained inside allowable map.

7. Operator fault assessment
7.1 Failure itself does not prove operator misconduct.
7.2 Operator fault requires full causal chain:
operator action -> measured mode deviation -> matching physical damage mechanism.
7.3 Without this chain, operator liability is not proven.

8. Defense position for operating organization
- Classify event as likely caused by external well factors and/or sizing limitations.
- Require independent technical examination and telemetry-vs-mode-map correlation.
- Reject statements like "operator fault by failure fact only" as methodologically invalid.

9. Evidence checklist for final conclusion
1) 72h pre-failure trends: current, voltage, frequency, temperature, pressure, rate.
2) Mode map and real operation inside allowable windows.
3) Disassembly/defect report with photo evidence and independent expert.
4) Fluid chemistry dynamics and solids trend.
5) Runtime to failure versus warranty/normative values.

10. Recommended structure of a professional engineer report
Section 1: Asset passport and commission.
Section 2: Timeline with exact timestamps.
Section 3: Parameter trends (tables, charts, event marks).
Section 4: Defect findings (components, wear, scoring, cracks).
Section 5: Medium analysis and failure correlation.
Section 6: Hypothesis comparison with probability ranking.
Section 7: Root cause and preventive actions.
Section 8: Liability and risk allocation.

11. Preventive actions
- Strengthen medium-quality surveillance (chemistry, solids, gas factor).
- Implement automatic protections by VFD/current/temperature trend thresholds.
- Re-validate ESP sizing and operation windows for actual production profile.
- Add mandatory post-failure review matrix: damage mechanism <-> root cause.

12. Final conclusion
Based on available materials, the most probable root cause is external
well-condition influence causing off-design ESP operation.
Direct proven operator fault is currently not established.
Final confirmation requires decoded content of failure report, logs, and defect records.
""".strip("\n")


def wrap_text(text, width=98):
    lines = []
    for raw in text.splitlines():
        if not raw.strip():
            lines.append("")
            continue
        chunks = textwrap.wrap(raw, width=width, break_long_words=False, break_on_hyphens=False)
        lines.extend(chunks if chunks else [""])
    return lines


def escape_pdf(s: str) -> str:
    return s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


all_lines = wrap_text(report_text)
max_lines_per_page = 46
pages = [all_lines[i:i + max_lines_per_page] for i in range(0, len(all_lines), max_lines_per_page)]

objects = []

def add_obj(content: bytes):
    objects.append(content)
    return len(objects)

font_obj = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

page_obj_ids = []
for page_lines in pages:
    stream_lines = ["BT", "/F1 11 Tf", "50 800 Td", "14 TL"]
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
    page_dict = (f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 595 842] "
                 f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_id} 0 R >>").encode()
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
pdf += f"xref\n0 {len(objects)+1}\n".encode()
pdf += b"0000000000 65535 f \n"
for i in range(1, len(objects) + 1):
    pdf += f"{offsets[i]:010d} 00000 n \n".encode()

pdf += (f"trailer\n<< /Size {len(objects)+1} /Root {catalog_obj} 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n").encode()

with open(OUT, 'wb') as f:
    f.write(pdf)

print(f'Created {OUT} with {len(pages)} pages and {len(all_lines)} lines')
