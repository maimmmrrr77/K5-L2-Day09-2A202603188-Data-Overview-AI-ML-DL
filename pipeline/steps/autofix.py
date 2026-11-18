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

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line


def fix(ds, issues, cfg):
    fixes = []
    errors = [issue for issue in issues if issue.severity == ERROR]

    remove_codes = {"CORRUPT_IMAGE", "BAD_SIZE", "LEAK_TEST"}
    remove_issues = {}
    for issue in errors:
        if issue.code.startswith("DUP_IMAGE_") or issue.code in remove_codes:
            remove_issues.setdefault(issue.image, issue)

    removed_images = set()
    for stem, issue in remove_issues.items():
        image_path = ds.image_path(stem)
        label_path = ds.label_path(stem)
        existing_paths = [p for p in (image_path, label_path) if p is not None and p.exists()]
        if not existing_paths:
            continue
        before = ", ".join(p.name for p in existing_paths)
        for path in existing_paths:
            path.unlink()
        removed_images.add(stem)
        fixes.append({
            "image": stem,
            "line": None,
            "action": "remove_image",
            "before": before,
            "after": "",
        })

    needs_label_images = set()
    for issue in errors:
        if issue.code != "MISSING_LABEL_FILE" or issue.image in removed_images:
            continue
        if issue.image in needs_label_images:
            continue
        if ds.image_path(issue.image) is None or ds.label_path(issue.image).exists():
            continue
        needs_label_images.add(issue.image)
        fixes.append({
            "image": issue.image,
            "line": None,
            "action": "needs_label",
            "before": "(không có file)",
            "after": "chuyển người gán",
        })

    if any(issue.code == "BAD_CLASS_NAME" for issue in errors):
        yaml_path = ds.yaml_path
        before_text = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""
        data = yaml.safe_load(before_text) if before_text else {}
        if not isinstance(data, dict):
            data = {}
        data["names"] = dict(enumerate(cfg["classes"]))
        after_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        if before_text != after_text:
            yaml_path.write_text(after_text, encoding="utf-8")
            fixes.append({
                "image": "data.yaml",
                "line": None,
                "action": "rename_classes",
                "before": before_text,
                "after": after_text,
            })

    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    line_issues = defaultdict(dict)
    for issue in errors:
        if issue.image in removed_images or issue.line is None:
            continue
        if issue.code in drop_codes:
            line_issues[issue.image][issue.line] = "drop_line"
        elif issue.code == "BOX_OUT_OF_IMAGE":
            line_issues[issue.image].setdefault(issue.line, "clip_box")

    for stem, actions in line_issues.items():
        label_path = ds.label_path(stem)
        if not label_path.exists():
            continue

        original_text = label_path.read_text(encoding="utf-8")
        original_lines = original_text.splitlines(keepends=True)
        rewritten_lines = []
        file_fixes = []

        for line_number, raw_line in enumerate(original_lines, 1):
            action = actions.get(line_number)
            if action is None:
                rewritten_lines.append(raw_line)
                continue

            line_text = raw_line.rstrip("\r\n")
            if action == "drop_line":
                file_fixes.append({
                    "image": stem,
                    "line": line_number,
                    "action": "drop_line",
                    "before": line_text,
                    "after": "",
                })
                continue

            class_id, cx, cy, width, height = parse_yolo_line(line_text)
            left = max(cx - width / 2, 0.0)
            right = min(cx + width / 2, 1.0)
            top = max(cy - height / 2, 0.0)
            bottom = min(cy + height / 2, 1.0)
            if right <= left or bottom <= top:
                file_fixes.append({
                    "image": stem,
                    "line": line_number,
                    "action": "drop_line",
                    "before": line_text,
                    "after": "",
                })
                continue

            clipped = (
                class_id,
                (left + right) / 2,
                (top + bottom) / 2,
                right - left,
                bottom - top,
            )
            after = " ".join(
                [str(clipped[0])] + [format(value, ".12g") for value in clipped[1:]]
            )
            ending = raw_line[len(line_text):]
            rewritten_lines.append(after + ending)
            file_fixes.append({
                "image": stem,
                "line": line_number,
                "action": "clip_box",
                "before": line_text,
                "after": after,
            })

        if file_fixes:
            label_path.write_text("".join(rewritten_lines), encoding="utf-8")
            fixes.extend(file_fixes)

    return fixes
