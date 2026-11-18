"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401

CHECK = "label_format"


def run(ds, cfg):
    lf = cfg["label_format"]
    issues = []
    for lp in ds.label_files():
        stem = lp.stem
        size = ds.image_size(stem)              # (W, H) hoặc None
        kept = []                               # (số dòng, lớp, box) các dòng hợp lệ phía trước
        for ln, text in ds.read_label_lines(stem) or []:
            # 1) cú pháp
            try:
                c, x, y, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue(CHECK, ERROR, "BAD_FORMAT", stem, f"sai định dạng: {e}", ln))
                continue
            # 2) BAD_CLASS_ID
            if not (0 <= c < len(ds.classes)):
                issues.append(Issue(CHECK, ERROR, "BAD_CLASS_ID", stem, f"id lớp {c} không hợp lệ", ln))
                continue
            # 3) BOX_ZERO
            if w <= 0 or h <= 0:
                issues.append(Issue(CHECK, ERROR, "BOX_ZERO", stem, "box không có diện tích", ln))
                continue

            box = (x, y, w, h)
            # 4) BOX_OUT_OF_IMAGE
            overflow = max(0.0, -(x - w / 2), (x + w / 2) - 1, -(y - h / 2), (y + h / 2) - 1)
            if overflow > lf["overflow_tol"]:
                issues.append(Issue(CHECK, ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"box tràn ảnh {overflow:.4f}", ln, {"overflow": overflow}))
            # 5) DUP_BOX
            for prev_ln, prev_c, prev_box in kept:
                iou = iou_xywh(prev_box, box)
                if prev_c == c and iou > lf["dup_box_iou"]:
                    issues.append(Issue(CHECK, ERROR, "DUP_BOX", stem,
                                        f"trùng box dòng {prev_ln} (IoU {iou:.2f})", ln))
                    break
            kept.append((ln, c, box))

            # 6) BOX_TINY, BOX_HUGE
            if size:
                short = min(w * size[0], h * size[1])
                if short < lf["min_box_px"]:
                    issues.append(Issue(CHECK, WARN, "BOX_TINY", stem,
                                        f"cạnh ngắn {short:.1f}px < {lf['min_box_px']}px", ln))
            if w * h > lf["max_box_frac"]:
                issues.append(Issue(CHECK, WARN, "BOX_HUGE", stem,
                                    f"box chiếm {w * h:.0%} ảnh", ln))
    return issues