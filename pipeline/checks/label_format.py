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


def _check_file(ds, stem, cfg):
    """Kiểm mọi dòng của một file nhãn. Trả về list[Issue] theo thứ tự dòng."""
    lf = cfg["label_format"]
    tol, min_px = lf["overflow_tol"], lf["min_box_px"]
    max_frac, dup_iou = lf["max_box_frac"], lf["dup_box_iou"]
    n_cls = len(ds.classes)
    size = ds.image_size(stem)                 # None nếu không mở được ảnh (vd. nhãn mồ côi) -> bỏ qua BOX_TINY
    issues, kept = [], []                      # kept: (số dòng, lớp, box) các dòng hợp lệ phía TRƯỚC, để bắt DUP_BOX

    for ln, text in ds.read_label_lines(stem) or []:      # số dòng gốc, đã bỏ dòng trống
        # 1) cú pháp: không được làm script chết với dòng hỏng
        try:
            c, x, y, w, h = parse_yolo_line(text)
        except ValueError as e:
            issues.append(Issue(CHECK, ERROR, "BAD_FORMAT", stem, f"dòng không đúng 5 cột số: {e}", ln, {"text": text.strip()[:60]}))
            continue
        # 2) id lớp
        if not 0 <= c < n_cls:
            issues.append(Issue(CHECK, ERROR, "BAD_CLASS_ID", stem, f"id lớp {c} ngoài 0..{n_cls - 1}", ln, {"id": c}))
            continue
        # 3) box rỗng
        if w <= 0 or h <= 0:
            issues.append(Issue(CHECK, ERROR, "BOX_ZERO", stem, f"box không có diện tích (w={w}, h={h})", ln))
            continue
        box = (x, y, w, h)
        # 4) tràn ảnh: mức tràn lớn nhất trên 4 mép
        overflow = max(0.0, -(x - w / 2), (x + w / 2) - 1.0, -(y - h / 2), (y + h / 2) - 1.0)
        if overflow > tol:
            issues.append(Issue(CHECK, ERROR, "BOX_OUT_OF_IMAGE", stem, f"box tràn ảnh {overflow:.4f} (> {tol})", ln,
                                {"overflow": round(overflow, 6)}))
        # 5) box lặp: cùng lớp với một dòng TRƯỚC, IoU > ngưỡng -> báo ở dòng SAU
        for prev_ln, prev_c, prev_box in kept:
            iou = iou_xywh(prev_box, box)
            if prev_c == c and iou > dup_iou:
                issues.append(Issue(CHECK, ERROR, "DUP_BOX", stem, f"trùng box dòng {prev_ln} (IoU {iou:.2f})", ln,
                                    {"of_line": prev_ln, "iou": round(iou, 4)}))
                break                          # mỗi dòng báo DUP_BOX tối đa một lần
        kept.append((ln, c, box))
        # 6) cảnh báo (người xem): box quá nhỏ / quá to
        if size:
            short = min(w * size[0], h * size[1])
            if short < min_px:
                issues.append(Issue(CHECK, WARN, "BOX_TINY", stem, f"cạnh ngắn {short:.1f}px < {min_px}px", ln, {"short_px": round(short, 1)}))
        if w * h > max_frac:
            issues.append(Issue(CHECK, WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.0%} ảnh (> {max_frac:.0%})", ln, {"frac": round(w * h, 4)}))
    return issues


def run(ds, cfg):
    issues = []
    for lp in ds.label_files():                # sắp xếp theo tên -> báo cáo tái lập được
        issues.extend(_check_file(ds, lp.stem, cfg))
    return issues
