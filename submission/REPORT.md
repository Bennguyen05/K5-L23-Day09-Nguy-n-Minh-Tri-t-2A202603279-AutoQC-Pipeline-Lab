# Báo cáo Day 09 — Nguyễn Minh Triết, 2A202603279

## 1. Kết luận trước
Pipeline kết luận **HOLD** (mã thoát 10). Vào **224** ảnh → bước 1 loại **22** → **202** ảnh vào QC; sau sửa tự động và người duyệt (mô phỏng, 80/80 ảnh ngân sách) còn **0 lỗi bắt buộc**, nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa có người xem, ≥ ngưỡng 10% (`08_summary.json`). Dataset `clean_v1` (202 ảnh) đã xuất nhưng chỉ là **bản nháp, chưa được phát hành**. Lý do chính: hàng đợi duyệt có 125 ảnh mà ngân sách chỉ 80; 45 ảnh không ai xem.

## 2. Lỗi và phân việc
Nguồn: `01_intake` (mẫu số 224 ảnh) và `02_error_list_v1` (mẫu số 202 ảnh). "Ảnh" = số ảnh khác nhau; "dòng" = số dòng nhãn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| CORRUPT_IMAGE / BAD_SIZE | 2 / 3 ảnh (/224) | máy (loại ở cửa vào) | ảnh không mở được / cạnh < 250 px: không dùng được, quy tắc rõ ràng |
| DUP_IMAGE_EXACT / DUP_IMAGE_NEAR | 8 / 4 ảnh (/224) | máy (loại) | trùng làm lệch phân bố, md5 + phash ≤ 12 |
| LEAK_TEST | 5 ảnh (/224) | máy (loại) | trùng ảnh test/val → điểm test bị thổi phồng |
| BAD_CLASS_ID / BAD_FORMAT / BOX_ZERO / DUP_BOX | 6 / 3 / 4 / 7 dòng (/202 ảnh) | máy: `drop_line` (20 fix) | dòng không thể hiểu được hoặc lặp: xoá an toàn, có log trước → sau |
| BOX_OUT_OF_IMAGE | 8 dòng (8 ảnh) | máy: `clip_box` (8 fix) | cắt về [0,1], giữ lớp; box nằm hẳn ngoài ảnh thì xoá |
| BAD_CLASS_NAME | 2 issue (data.yaml: `Person`, `Bus`) | máy: `rename_classes` (1 fix) | names phải đúng `cfg.classes` |
| MISSING_LABEL_FILE | 6 ảnh | **người** (`needs_label`) | máy không được bịa nhãn; file rỗng = "ảnh nền", khác "chưa gán" |
| POSSIBLE_MISSING | 53 (52 ảnh) | người | model lớn thấy vật mà nhãn không có: có thể model sai |
| POSSIBLE_LOOSE_BOX | 28 (24 ảnh) | người | box lỏng/lệch: cần mắt người vẽ lại |
| POSSIBLE_FALSE_POS | 25 dòng (24 ảnh) | người | box nhãn không khớp vật nào model thấy |
| POSSIBLE_WRONG_CLASS | 18 (18 ảnh) | người | car/truck/bus dễ nhầm, chỉ người phân xử được |
| EMPTY_LABEL / BOX_TINY / BOX_HUGE / CLASS_RARE | 12 / 6 dòng (4 ảnh) / 3 / 4 (cấp dataset) | người | ảnh nền hay thiếu nhãn? vật quá nhỏ/quá to có đúng guideline? |

Sau sửa tự động (`04_error_list_v2`): còn 6 lỗi bắt buộc (đúng 6 ảnh chưa có nhãn), EMPTY_LABEL tăng 12 → 15 (3 file chỉ toàn dòng hỏng thành rỗng sau `drop_line`) — tác dụng phụ của autofix, cần người xem.

**Hàng đợi** (`05_review_queue.csv`, 125 ảnh): điểm = tổng trọng số mã lỗi × (1 + conf). Đầu hàng là img_0020 (11,5: vừa bị máy xoá dòng, vừa MISSING + WRONG_CLASS conf 0,95), tiếp theo 6 ảnh `NEEDS_LABEL` (trọng số 10: không có người thì chắc chắn Rework). Ảnh thứ 80 có điểm 3,34, thứ 81 là 3,33: ngưỡng cắt rơi giữa các ảnh chỉ có 1–2 cảnh báo. Với 80 ảnh, người xử lý **94/123** cảnh báo ngữ nghĩa (74/103 ảnh có cảnh báo ngữ nghĩa); 45 ảnh còn lại không ai xem, 38 ảnh trong đó vẫn còn cảnh báo ở v3 (theo số cảnh báo: 16 LOOSE_BOX, 11 FALSE_POS, 6 BOX_TINY, 4 EMPTY_LABEL, 3 BOX_HUGE, 2 MISSING).

## 3. Calibration (2 ngưỡng)
Nguồn: `submission/calibration/calibration_report.md` (calib 39 ảnh).

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **12** | NEAR: 1,00 / 0,50 → 1,00 / 0,67 (EXACT giữ 1,00 / 1,00) | lỗi này **xoá ảnh** nên ưu tiên precision. Trên raw, cặp trùng thật nằm ở 0, 2, 6, 10; cặp ảnh **khác nhau** gần nhất ở 16. Chọn 12: bắt hết cặp ≤ 10, còn biên 4 bit. |
| `second_opinion.conf` | 0.25 | **0.6** | MISSING: 0,50 / 1,00 → 0,57 / 1,00; WRONG_CLASS: 0,56 / 0,83 → 0,62 / 0,83; LOOSE_BOX: 0,29 / 0,40 → 0,20 / 0,20 | chỉ cảnh báo nên giữ **recall MISSING = 1,00**; 0,6 là giá trị cao nhất còn giữ được điều đó (0,7: recall 0,88). Đổi lại mất recall LOOSE_BOX (2 → 1/5) |

**Chỗ calibration đánh lừa:**
1. Trên calib, `phash_dist = 16` cho F1 NEAR cao nhất (0,91). Nhưng trên raw có **9 ảnh** cách ảnh khác đúng 16 bit; mở xem (img_0011 vs img_0008: tennis vs trượt tuyết; img_0177 vs img_0113: lướt sóng vs người ngồi bàn) thì hoàn toàn khác nhau. Chọn 16 sẽ xoá nhầm 9 ảnh tốt (chạy thử: loại ở bước 1 tăng từ 22 lên 31). Calib chỉ có 6 ảnh gần trùng nên không thấy được FP này.
2. `conf = 0,8` là giá trị duy nhất cho **Release** trên raw (16/202 = 7,9% ảnh còn cảnh báo), nhưng recall MISSING trên calib tụt 1,00 → 0,75: hàng đợi "vừa" vì checker mù hơn chứ dữ liệu không sạch hơn. Mình không chọn giá trị này. Ngoài ra FALSE_POS (precision 0,36) không phụ thuộc `conf` (dùng `fp_conf` cố định), nên tăng `conf` cũng không giảm được nhóm cảnh báo này.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` → kết luận **REWORK**, mã thoát **20**: "còn 6 lỗi bắt buộc" (6 `MISSING_LABEL_FILE` trong `work/rep_nb/07_error_list_v3.csv`), 112/202 ảnh còn cảnh báo; log in "KHÔNG xuất: còn lỗi bắt buộc" và thư mục `work/exp_nb/clean_v1` **không tồn tại**. Test `test_error_cannot_be_hidden_by_reviewed` kiểm thêm: lỗi bắt buộc không bị ẩn kể cả ở ảnh đã duyệt.

**Tự nhìn thấy (viz_labels.py):** img_0020 xe buýt bị gán `truck` (máy cờ WRONG_CLASS, IoU 0,94); img_0160 bãi đỗ dày đặc xe tải chỉ gán vài box (thiếu nhãn hàng loạt); img_0018 một box `person` phủ 97% ảnh (BOX_HUGE + LOOSE_BOX).

**(b) Điểm mù:**
1. **Ảnh trùng biến đổi mạnh:** calib_037 và calib_038 là bản gần trùng cố ý nhưng cách gốc 16 và 18 bit, nằm đúng vùng của các cặp ảnh khác nhau trên raw (16–18). Không có `phash_dist` nào bắt được chúng mà không xoá nhầm ảnh tốt (recall NEAR kẹt ở 0,67).
2. **Box lỏng nhẹ:** recall LOOSE_BOX trên calib chỉ 1/5 ở conf 0,6 (box phóng 1,45–1,58 lần). Model phải tự tin ≥ 0,6 về đúng vật đó thì mới cờ được; box lỏng ít hơn (IoU ≥ 0,5) thì không bao giờ bị cờ.
3. **Nhầm lớp mà model lớn cũng nhầm** (car/truck/bus): second_opinion chỉ so với yolo26l; 1/6 WRONG_CLASS trên calib bị bỏ sót, và nếu model đồng ý với nhãn sai thì không có cảnh báo nào.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Chưa chạy.** Bài này dừng ở phần lõi (`make check-core`); chưa train trên Colab. Khi train cần lưu ý: `raw` chứa 5 ảnh rò rỉ test nên mAP của `raw` có thể bị thổi phồng; `clean_v1` là bản Hold (38 ảnh còn cảnh báo chưa duyệt).

## 6. Quyết định và ghi chú AI
**(a)** Quyết định: **Hold** — không phát hành `clean_v1`. Để thành Release cần đưa tỉ lệ ảnh còn cảnh báo chưa duyệt xuống < 10%, tức xem thêm **ít nhất 18** trong 38 ảnh còn cảnh báo (≈ 98 ảnh duyệt thay vì 80), ưu tiên các ảnh có cảnh báo LOOSE_BOX (16) và FALSE_POS (11). Không được đạt Release bằng cách nâng `conf` (mục 3). Nếu người duyệt bỏ sót ảnh `NEEDS_LABEL` thì kết luận chuyển thành Rework.

**(b) Dùng AI (Claude):**
- Đọc guideline và hướng dẫn thao tác trên powershell, tôi tự thực hiện các thao tác
- Gợi ý sửa lỗi và viết bản nháp report, tôi tự điền các phần còn trống
