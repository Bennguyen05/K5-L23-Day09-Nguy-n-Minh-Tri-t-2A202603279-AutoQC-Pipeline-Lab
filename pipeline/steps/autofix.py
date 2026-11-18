"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _clip(text):
    """Cắt box về trong [0,1]. Trả về dòng mới, hoặc None nếu box không còn diện tích."""
    c, x, y, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, x - w / 2), min(1.0, x + w / 2)
    y1, y2 = max(0.0, y - h / 2), min(1.0, y + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    nx, ny, nw, nh = (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1
    return f"{c} {nx:.6f} {ny:.6f} {nw:.6f} {nh:.6f}"


def _remove_image(ds, stem):
    p = ds.image_path(stem)
    if p is not None:
        p.unlink()
    ds.label_path(stem).unlink(missing_ok=True)


def _fix_lines(ds, stem, line_codes):
    """Sửa MỘT file nhãn. line_codes = {số dòng gốc: {các mã lỗi}}. Ghi file một lần."""
    p = ds.label_path(stem)
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8").splitlines()     # giữ cả dòng trống -> số dòng không lệch
    out, fixes = [], []
    for ln, text in enumerate(raw, 1):
        codes = line_codes.get(ln, set())
        if codes & DROP_CODES:                            # xoá thắng cắt
            fixes.append(dict(image=stem, line=ln, action="drop_line", before=text, after=""))
            continue
        if codes & CLIP_CODES:
            try:
                new = _clip(text)
            except ValueError:
                new = None
            if new is None:                               # nằm hẳn ngoài ảnh -> xoá
                fixes.append(dict(image=stem, line=ln, action="drop_line", before=text, after=""))
                continue
            fixes.append(dict(image=stem, line=ln, action="clip_box", before=text, after=new))
            out.append(new)
            continue
        out.append(text)                                  # dòng không lỗi: giữ nguyên
    if fixes:
        p.write_text("".join(line + "\n" for line in out), encoding="utf-8")
    return fixes


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]   # WARN là việc của người: không đụng
    fixes = []

    # (1) xoá ảnh trùng / rò rỉ / hỏng / sai cỡ
    removed = set()
    for i in errors:
        if i.code in REMOVE_CODES and i.image not in removed:
            if ds.image_path(i.image) is None and not ds.label_path(i.image).exists():
                continue
            _remove_image(ds, i.image)
            removed.add(i.image)
            fixes.append(dict(image=i.image, line="", action="remove_image",
                              before=i.code, after="(đã xoá ảnh + nhãn)"))

    # (2) data.yaml: ghi lại names đúng danh sách dự án (1 lần dù nhiều issue)
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) if ds.yaml_path.exists() else {}
        data = data or {}
        before = data.get("names")
        data["names"] = {k: name for k, name in enumerate(cfg["classes"])}
        ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append(dict(image="data.yaml", line="", action="rename_classes",
                          before=str(before), after=str(cfg["classes"])))

    # (3) ảnh chưa có nhãn: KHÔNG tạo file, chuyển người gán
    for stem in sorted({i.image for i in errors if i.code == "MISSING_LABEL_FILE"} - removed):
        if ds.image_path(stem) is not None and not ds.label_path(stem).exists():
            fixes.append(dict(image=stem, line="", action="needs_label",
                              before="(không có file)", after="chuyển người gán"))

    # (4) lỗi theo dòng: gom theo file, rồi sửa mỗi file một lần
    per_file = defaultdict(lambda: defaultdict(set))
    for i in errors:
        if i.line is not None and i.code in DROP_CODES | CLIP_CODES and i.image not in removed:
            per_file[i.image][int(i.line)].add(i.code)
    for stem in sorted(per_file):
        fixes.extend(_fix_lines(ds, stem, per_file[stem]))
    return fixes