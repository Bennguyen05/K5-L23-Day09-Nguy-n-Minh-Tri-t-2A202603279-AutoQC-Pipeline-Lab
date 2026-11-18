"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    thr = cfg["gate"]["warn_ratio_hold"]
    stems = set(image_stems)
    reviewed = set(reviewed)

    # (1) lỗi bắt buộc: đếm TẤT CẢ, không bỏ qua ảnh đã duyệt, kể cả lỗi data.yaml
    n_errors = sum(1 for i in issues if i.severity == ERROR)

    # (2) TODO: tập hợp các ẢNH còn cảnh báo:
    warn_imgs = {i.image for i in issues
        if i.severity == WARN and i.image in stems and i.image not in reviewed}

    # (3) tỉ lệ, tránh chia cho 0 khi không có ảnh
    n_images = len(stems)
    ratio = round(len(warn_imgs) / n_images, 4) if n_images else 0

    # (4) quyết định
    if n_errors > 0:
        decision = "Rework"
        reasons = [f"còn {n_errors} lỗi bắt buộc: phải sửa trước khi phát hành"]
    elif ratio >= thr:
        decision = "Hold"
        reasons = [f"{len(warn_imgs)}/{n_images} ảnh ({ratio:.1%}) còn cảnh báo chưa duyệt >= ngưỡng {thr:.0%}"]
    else:
        decision = "Release"
        reasons = [f"0 lỗi bắt buộc; {len(warn_imgs)}/{n_images} ảnh ({ratio:.1%}) còn cảnh báo < ngưỡng {thr:.0%}"]

    return dict(decision=decision, n_errors=n_errors, n_warn_images=len(warn_imgs),
                n_images=n_images, warn_ratio=ratio, reasons=reasons)
