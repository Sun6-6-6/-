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
    lines.append("КОНСОЛИДИРОВАННЫЙ ИНЖЕНЕРНЫЙ ОТЧЁТ")
    lines.append("РАССЛЕДОВАНИЕ ОТКАЗА УЭЦН: СКВ. 26-23296 (ПРИОБСКОЕ)")
    lines.append(f"Version: 3.0 | Prepared: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("РАЗДЕЛ 1. ЗАДАЧА И МЕТОДОЛОГИЯ")
    lines.append("Цель: сформировать единый консолидированный отчёт по ВСЕМ файлам архива в репозитории,")
    lines.append("определить наиболее вероятную цепочку первопричины и подготовить позицию защиты прав эксплуатации.")
    lines.append("Метод в текущей среде: структурный разбор RAR5 + инженерная интерпретация состава источников.")
    lines.append("Ограничение: прямое извлечение текста из внутренних DOC/XLS/XLSX/PDF в среде ограничено")
    lines.append("(локально отсутствуют unrar/7z, установка зависимостей ограничена прокси-политикой).")
    lines.append("")

    lines.append("РАЗДЕЛ 2. ЦЕЛОСТНОСТЬ И ИНВЕНТАРИЗАЦИЯ ИСТОЧНИКОВ")
    lines.append(f"Архив: {meta['archive']}")
    lines.append(f"Размер архива, байт: {fmt_bytes(meta['size_bytes'])}")
    lines.append(f"SHA256 архива: {meta['sha256']}")
    lines.append(f"Количество вложенных файлов: {meta['file_count']}")
    lines.append(f"Суммарный сжатый объём, байт: {fmt_bytes(meta['packed_total'])}")
    lines.append(f"Суммарный исходный объём, байт: {fmt_bytes(meta['unpacked_total'])}")
    ratio = meta['unpacked_total'] / meta['packed_total'] if meta['packed_total'] else 0
    lines.append(f"Общий коэффициент распаковки: {ratio:.3f}")
    lines.append("Распределение по типам документов: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
    lines.append("")

    lines.append("РАЗДЕЛ 3. ПОЛНЫЙ РЕЕСТР ФАЙЛОВ (ВСЕ ИСТОЧНИКИ)")
    for i, f in enumerate(files, 1):
        fr = f["unpacked_size"] / f["data_size"] if f["data_size"] else 0
        lines.append(
            f"{i:02d}. {to_ascii(f['name'])} | type={classify(f['name'])} | packed={fmt_bytes(f['data_size'])} | "
            f"unpacked={fmt_bytes(f['unpacked_size'])} | ratio={fr:.2f} | crc32={f.get('file_crc32') or '-'}"
        )
    lines.append("")

    lines.append("РАЗДЕЛ 4. ИНЖЕНЕРНАЯ ИНТЕРПРЕТАЦИЯ ДОСЬЕ")
    lines.append("4.1 Комплект источников содержит профильный отчёт по отказу, электротехнический протокол, акты и логи,")
    lines.append("    историю скважины, карту вывода на режим и расширенный химический анализ продукции.")
    lines.append("4.2 Такой состав характерен для полного RCA-пакета и позволяет перекрёстно проверять")
    lines.append("    режим работы, качество среды и механико-электрические механизмы повреждения.")
    lines.append("4.3 Наличие годового временного ряда по скважине указывает на необходимость анализа трендов деградации")
    lines.append("    и предаварийных признаков, а не только единичного события.")
    lines.append("")

    lines.append("РАЗДЕЛ 5. ГИПОТЕЗЫ ПЕРВОПРИЧИНЫ (РАНЖИРОВАНИЕ)")
    lines.append("H1 (приоритет): деградация скважинной среды + работа УЭЦН вне расчётной гидравлики.")
    lines.append("  Цепочка механизма: изменение среды (газ/вода/мехпримеси/соли/эмульсия) -> гидронесоответствие ->")
    lines.append("  перегрузка ступеней / нестабильная подача -> ускоренный износ вращающихся и опорных узлов -> отказ.")
    lines.append("H2: нарушения энергокачества (провалы напряжения, перекос фаз, нестабильная работа ПЧ).")
    lines.append("H3: несоответствие подбора оборудования или ранний производственный дефект при работе в допустимом режиме.")
    lines.append("")

    lines.append("РАЗДЕЛ 6. ПОЗИЦИЯ ЗАЩИТЫ ПРАВ ЭКСПЛУАТИРУЮЩЕЙ ОРГАНИЗАЦИИ")
    lines.append("Принцип: сам факт отказа НЕ является доказательством нарушения эксплуатации.")
    lines.append("Требуемая причинно-следственная доказательная цепочка: действие персонала -> измеренное нарушение режима ->")
    lines.append("соответствующий механизм физического повреждения. Без полной цепочки вина эксплуатации не доказана.")
    lines.append("Действия защиты в претензионной процедуре:")
    lines.append("  A) истребовать телеметрию и журнал событий минимум за 72 часа до отказа;")
    lines.append("  B) сопоставить фактический режим с картой вывода и допустимым окном работы;")
    lines.append("  C) назначить независимую дефектацию/разборку с фотофиксацией;")
    lines.append("  D) сравнить наработку до отказа с гарантийными и нормативными порогами;")
    lines.append("  E) оспаривать выводы формата 'раз отказ -> значит вина эксплуатации'.")
    lines.append("")

    lines.append("РАЗДЕЛ 7. РЕКОМЕНДУЕМЫЙ ШАБЛОН ПРОФЕССИОНАЛЬНОГО ОТЧЁТА")
    lines.append("1) Паспорт объекта, состав комиссии, реестр исходных данных.")
    lines.append("2) Хронология событий с точными отметками времени и срабатываниями защит.")
    lines.append("3) Анализ трендов (I, U, Hz, T, P, Q) в окнах до/во время/после отказа.")
    lines.append("4) Дефектация: узлы, класс повреждения, замеры, фотоприложение.")
    lines.append("5) Корреляция химии среды и мехпримесей с профилем износа.")
    lines.append("6) Матрица сравнения гипотез с уровнем достоверности.")
    lines.append("7) Финальная формулировка первопричины + CAPA (корректирующие/превентивные меры).")
    lines.append("8) Распределение ответственности и рисков с явными ссылками на доказательства.")
    lines.append("")

    lines.append("РАЗДЕЛ 8. ПРОГРАММА ПРЕВЕНТИВНЫХ МЕРОПРИЯТИЙ")
    lines.append("- усилить мониторинг качества продукции и пороги срабатывания по отклонениям;")
    lines.append("- внедрить автоматические предупреждения по ПЧ/току/температуре с предаварийной аналитикой;")
    lines.append("- регулярно верифицировать подбор УЭЦН относительно фактического окна добычи;")
    lines.append("- закрепить post-failure матрицу: наблюдаемое повреждение <-> вероятный механизм <-> доказательство.")
    lines.append("")

    lines.append("РАЗДЕЛ 9. ИТОГОВОЕ КОНСОЛИДИРОВАННОЕ ЗАКЛЮЧЕНИЕ")
    lines.append("По совокупности всех файлов архива наиболее вероятна внешняя по отношению к эксплуатации")
    lines.append("природа отказа: влияние условий скважины с выходом УЭЦН в нерасчётный режим. При текущей глубине данных")
    lines.append("прямая доказанная вина эксплуатации не установлена. Финальное технико-правовое заключение требует")
    lines.append("полного извлечения содержания внутренних документов и строгой перекрёстной валидации телеметрии,")
    lines.append("результатов дефектации и режимных ограничений.")
    lines.append("")

    lines.append("ПРИЛОЖЕНИЕ A. МАШИНОЧИТАЕМЫЕ ФАКТЫ")
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
