"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    opinion_cfg = cfg["second_opinion"]
    conf_min = opinion_cfg["conf"]
    min_area_px = opinion_cfg["min_area_px"]
    fp_conf = opinion_cfg["fp_conf"]
    iou_missing = opinion_cfg["iou_missing"]
    iou_match = opinion_cfg["iou_match"]
    iou_loose = opinion_cfg["iou_loose"]

    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    issues = []
    for p in ds.image_files():
        stem = p.stem
        label_lines = ds.read_label_lines(stem)
        if label_lines is None or stem not in preds:
            continue

        labels = ds.valid_boxes(stem)
        image_size = ds.image_size(stem)
        if image_size is None:
            continue
        image_width, image_height = image_size

        primary_predictions = []
        fp_predictions = []
        for row in preds.get(stem, []):
            try:
                pred_class, pred_conf, cx, cy, width, height = row
                pred_conf = float(pred_conf)
                pred_box = (float(cx), float(cy), float(width), float(height))
                pred_class = int(pred_class)
            except (TypeError, ValueError, OverflowError):
                continue

            if pred_conf >= fp_conf:
                fp_predictions.append((pred_box, pred_conf))
            if pred_conf < conf_min:
                continue
            area_px = width * image_width * height * image_height
            if area_px >= min_area_px:
                primary_predictions.append((pred_class, pred_conf, pred_box))

        for pred_class, pred_conf, pred_box in primary_predictions:
            candidates = []
            for label in labels:
                label_class, cx, cy, width, height = label
                iou = iou_xywh(pred_box, (cx, cy, width, height))
                if iou >= iou_missing:
                    candidates.append((label_class, iou))

            if not candidates:
                issues.append(Issue(
                    "second_opinion",
                    WARN,
                    "POSSIBLE_MISSING",
                    stem,
                    "model phát hiện vật thể không có nhãn tương ứng",
                    extra={"conf": pred_conf},
                ))
                continue

            same_class = [iou for label_class, iou in candidates if label_class == pred_class]
            if same_class:
                best_same = max(same_class)
                if best_same < iou_loose:
                    issues.append(Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_LOOSE_BOX",
                        stem,
                        "box cùng lớp lệch hoặc lỏng so với dự đoán model",
                        extra={"conf": pred_conf, "iou": best_same},
                    ))
                continue

            different_class = [iou for label_class, iou in candidates if label_class != pred_class]
            if different_class:
                best_different = max(different_class)
                if best_different >= iou_match:
                    issues.append(Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_WRONG_CLASS",
                        stem,
                        "nhãn có thể sai lớp so với dự đoán model",
                        extra={"conf": pred_conf, "iou": best_different},
                    ))

        for line_number, text in label_lines:
            try:
                label = parse_yolo_line(text)
            except (ValueError, OverflowError):
                continue

            label_class, cx, cy, width, height = label
            if not 0 <= label_class < len(ds.classes):
                continue

            label_box = (cx, cy, width, height)
            best_iou = max(
                (iou_xywh(label_box, pred_box) for pred_box, _ in fp_predictions),
                default=0.0,
            )
            if best_iou < iou_missing:
                issues.append(Issue(
                    "second_opinion",
                    WARN,
                    "POSSIBLE_FALSE_POS",
                    stem,
                    "nhãn không khớp dự đoán nào của model",
                    line=line_number,
                    extra={"iou": best_iou},
                ))

    return issues
