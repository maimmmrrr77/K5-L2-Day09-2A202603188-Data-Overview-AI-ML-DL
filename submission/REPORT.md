# Báo cáo Day 09 — Nguyễn Thị Ngọc Mai: 2A202603188

## 1. Kết luận trước
- Pipeline kết luận HOLD (mã thoát 10).   
- Đầu vào 224 ảnh, loại 21 ảnh ở cửa vào (01_intake), xuất bản nháp 203 ảnh ra submission/export/clean_v1/.   
- Lý do chính: 0 lỗi bắt buộc còn lại sau khi người duyệt gán 6 ảnh thiếu nhãn, nhưng còn 38/203 ảnh (18.72%) mang cảnh báo chưa được duyệt, vượt ngưỡng Hold 10.00%.   

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

## 2. Lỗi và phân việc

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `DUP_IMAGE_EXACT` | 8 ảnh | Máy | Trùng chính xác từng byte (MD5), máy loại bỏ bản sao tự động và an toàn. |
| `LEAK_TEST` | 5 ảnh | Máy | Trùng ảnh với tập kiểm thử `test/`, bắt buộc loại bỏ để tránh rò rỉ dữ liệu. |
| `BAD_SIZE` | 3 ảnh | Máy | Cạnh ngắn nhỏ hơn ngưỡng tối thiểu (`250px`), vi phạm quy tắc chất lượng ảnh đầu vào. |
| `DUP_IMAGE_NEAR` | 3 ảnh | Máy | Trùng gần đúng qua khoảng cách pHash dưới ngưỡng đã hiệu chỉnh, máy loại tự động. |
| `CORRUPT_IMAGE` | 2 ảnh | Máy | File ảnh hỏng/cắt cụt không thể giải mã (`UnidentifiedImageError`/`OSError`), máy loại bỏ. |
| `BOX_OUT_OF_IMAGE` | 8 dòng | Máy | Lỗi hình học thuần túy, máy tự động cắt (clip) tọa độ box về trong `[0, 1]` an toàn. |
| `DUP_BOX` | 7 dòng | Máy | Hai box cùng lớp chồng lấn quá ngưỡng IoU trên cùng một ảnh, máy xóa dòng lặp phía sau. |
| `BAD_CLASS_ID` | 6 dòng | Máy | ID lớp nằm ngoài phạm vi hợp lệ `0..3` (`93`, `-1`, `7`, `4`), máy xóa dòng lỗi. |
| `BOX_ZERO` | 4 dòng | Máy | Box có chiều rộng hoặc cao bằng 0 (không có diện tích), máy xóa dòng lỗi. |
| `BAD_FORMAT` | 3 dòng | Máy | Dòng nhãn thiếu cột hoặc chứa `nan`/`inf`, không thể khôi phục tọa độ nên máy xóa dòng. |
| `BAD_CLASS_NAME` | 2 dòng | Máy | Tên lớp viết hoa sai quy chuẩn (`Person`, `Bus`), máy chuẩn hóa lại trong `data.yaml`. |
| `MISSING_LABEL_FILE` | 6 ảnh | Người | Ảnh chưa có file nhãn; máy không được phép tự bịa nhãn nên đẩy cho người gán mới. |
| `POSSIBLE_MISSING` | 53 dòng | Người | Model `yolo26l` phát hiện vật thể nhưng thiếu box; có thể model báo giả nên cần người xác nhận. |
| `POSSIBLE_FALSE_POS` | 29 dòng | Người | Box nhãn hiện tại không khớp dự đoán của model; cần người kiểm tra xem có phải nhãn thừa hay model sót. |
| `POSSIBLE_LOOSE_BOX` | 28 dòng | Người | Box cùng lớp nhưng IoU thấp so với model; cần người chỉnh lại độ khít hoặc giữ nguyên. |
| `POSSIBLE_WRONG_CLASS` | 18 dòng | Người | Nghi ngờ gán nhầm lớp (ví dụ `car`/`truck`/`bus`); sửa nhãn ngữ nghĩa thuộc thẩm quyền của người. |
| `EMPTY_LABEL` | 12 ảnh | Người | File nhãn rỗng; cần người phân biệt giữa ảnh nền thật sự hay ảnh bị xóa nhầm hết nhãn. |
| `BOX_TINY` | 6 dòng | Người | Cạnh ngắn box nhỏ hơn ngưỡng pixel quy định; cần người quyết định giữ hay bỏ vật thể quá nhỏ. |
| `CLASS_RARE` | 4 dòng | Máy | Cảnh báo ở vòng 1 do các ID lớp rác (`-1`, `4`, `7`, `93`); tự động biến mất sau khi máy xóa `BAD_CLASS_ID`. |
| `BOX_HUGE` | 3 dòng | Người | Box chiếm gần trọn khung hình (`> 97%` diện tích); cần người kiểm tra xem có bị phình box quá mức không. |

File `05_review_queue.csv` xếp các ảnh lỗi bắt buộc chưa có nhãn (`MISSING_LABEL_FILE`) lên đầu hàng đợi để đảm bảo giải quyết dứt điểm lỗi chặn `Rework` trước, sau đó mới sắp xếp các ảnh cảnh báo ngữ nghĩa theo mức độ ưu tiên và độ tin cậy của model giảm dần[cite: 3, 6]. Với tổng hàng đợi 125 ảnh và ngân sách tối đa 80 ảnh, người hduyệt đã xử lý trọn vẹn 6 ảnh thiếu file nhãn và 74/119 ảnh có cảnh báo ngữ nghĩa; 45 ản cuối hàng đợi chưa được duyệt (trong đó còn 38 ảnh giữ cảnh báo ở vòng kiểm tra cuối, chiếm 18.72%) [cite: 3, 6].

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | 8 | `DUP_IMAGE_NEAR`: `1.00 / 0.50` → `1.00 / 0.67` | Tăng ngưỡng từ `2` lên `8` giúp nâng Recall bắt ảnh trùng gần đúng từ `0.50` lên `0.67` (`F1` tăng `0.67 → 0.80`) mà vẫn giữ Precision `1.00`. Tránh chọn mức `20` vì làm gộp nhầm cụm khiến Recall của `DUP_IMAGE_EXACT` sụt từ `1.00` xuống `0.33`. |
| `second_opinion.conf` | 0.25 | 0.6 | `POSSIBLE_MISSING`: `0.50 / 1.00` → `0.57 / 1.00`<br>`POSSIBLE_WRONG_CLASS`: `0.56 / 0.83` → `0.62 / 0.83` | Nâng ngưỡng tự tin giúp lọc bớt cảnh báo nhiễu (giảm số cảnh báo trên lô thật từ `273` xuống `153`, tăng Precision của cả `MISSING` và `WRONG_CLASS` mà không làm giảm Recall). Không đẩy lên `0.7–0.8` để tránh đánh đổi làm tụt Recall bắt nhãn thiếu (`1.00 → 0.75`). |

Tập `data/calib/` chỉ có 39 ảnh độc lập về bối cảnh nên ở mức `phash_dist = 16`, công cụ đạt đỉnh `F1 = 0.91` (`Precision = 1.00`, `FP = 0`) mà không gây loại nhầm. Tuy nhiên, khi áp dụng sang lô dữ liệu thật `raw/` gồm 224 ảnh cùng chủ đề giao thông/đường phố, ngưỡng `phash_dist` quá lớn có nguy cơ nhận nhầm hai khung hình khác nhau chụp cùng góc đường hoặc chuỗi ảnh liên tiếp là trùng lặp; đồng thời trên `calib/`, việc tăng `second_opinion.conf` từ `0.25` lên `0.6` làm giảm Recall của `POSSIBLE_LOOSE_BOX` từ `0.40` xuống `0.20` (chỉ bắt được `1/5` lỗi box lỏng), cho thấy tối ưu ngưỡng theo F1 của `MISSING`/`WRONG_CLASS` trên 39 ảnh có thể bỏ sót các lỗi box lỏng nhẹ trong thực tế.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
(a) chứng minh gate chặn đúng:
- Khi chạy thử nghiệm với ngân sách người duyệt bằng 0, hệ thống nhận 203/224 ảnh và tự động sửa 35 lỗi cú pháp/hình học ở vòng 1[cite: 3].
- Tuy nhiên, do không có ngân sách người duyệt (`budget = 0`), 6/203 ảnh thiếu file nhãn (`MISSING_LABEL_FILE`) không được gán nhãn bổ sung và vẫn tồn tại ở vòng kiểm tra cuối (QC vòng 3)[cite: 3, 6].
- Cửa chặn (`gate.py`) đã phát hiện còn `n_errors = 6 >= 1`, từ đó đưa ra kết luận `REWORK`, trả về mã thoát `20` (`$LASTEXITCODE = 20`) và chặn không xuất bộ dữ liệu ra thư mục `work/exp_nb` (trả quy trình về bước gán/sửa nhãn)[cite: 6, 10].

(b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).
 
1. Bỏ sót nhãn đối tượng: ở img_0001.jpg, người quân nhân mặc quân phục đứng ở bên phải khung hình hoàn toàn không có bounding box nào bao quanh.   
2. Bỏ sót đối tượng: ở img_0030.jpg, vận động viên thứ hai từ phải sang so với vận động viên đang phát báng không có box bao quanh

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
| biến thể | #ảnh train | số seed | map50 (TB ± độ lệch) | map50_95 (TB ± độ lệch) | precision (TB ± độ lệch) | recall (TB ± độ lệch) |
|---|---|---|---|---|---|---|
| raw | 224 | 2 | 0.726 ± 0.000 | 0.512 ± 0.004 | 0.764 ± 0.061 | 0.649 ± 0.028 |
| clean | 203 | 2 | 0.699 ± 0.025 | 0.486 ± 0.013 | 0.796 ± 0.050 | 0.596 ± 0.049 |

Chênh mAP50 (clean − raw) = **-0.027**.

Độ chênh lệch `mAP50 (clean − raw) = -0.027` có trị tuyệt đối (`0.027`) gần bằng với độ lệch chuẩn giữa các seed của biến thể `clean` (`± 0.025`), đồng thời `mAP50` của `clean` thấp hơn `raw` (`0.699` so với `0.726`) do `recall` giảm (`0.596` so với `0.649`) dù `precision` có cải thiện (`0.796` so với `0.764`). Do đó, không thể kết luận bộ dữ liệu `clean` giúp mô hình tốt hơn `raw`, và sự chênh lệch này chịu tác động mạnh bởi phương sai ngẫu nhiên giữa các seed cũng như đặc thù dữ liệu[cite: 4, 6].
Giả thuyết giải thích và cách kiểm chứng:
1. Rò rỉ dữ liệu test (`LEAK_TEST`) và ảnh trùng lặp trong `raw`: Tập `raw` (224 ảnh) chứa 5 ảnh trùng trực tiếp với tập `test` (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`) cùng 11 ảnh trùng lặp nội bộ (`8 DUP_IMAGE_EXACT` + `3 DUP_IMAGE_NEAR`), khiến mô hình học vẹt các mẫu trùng với tập kiểm thử nên đạt điểm `mAP50` cao giả tạo; khi pipeline loại bỏ 21 ảnh này ở bước Intake, tập `clean` mất lợi thế rò rỉ dữ liệu nên `mAP50` phản ánh đúng năng lực tổng quát hóa thực tế hơn. 
Cách kiểm: Đánh giá lại mô hình `raw` sau khi loại bỏ 5 ảnh rò rỉ khỏi tập `test` (hoặc loại 5 ảnh `LEAK_TEST` khỏi `raw` rồi train lại) để so sánh trên cùng một mặt bằng công bằng.

2. Tồn đọng cảnh báo chưa duyệt (`HOLD`) và sụt giảm kích thước mẫu (`203` vs `224` ảnh): Do ngân sách người duyệt giới hạn ở 80 ảnh, vẫn còn 38/203 ảnh (chủ yếu là cảnh báo thiếu nhãn `POSSIBLE_MISSING`) chưa được xử lý trong `clean_v1`, khiến mô hình học thiếu tín hiệu dương tính (`recall` giảm từ `0.649` xuống `0.596`) và biến động mạnh giữa các seed (`± 0.025`). 
Cách kiểm: Tăng ngân sách duyệt để xử lý nốt 38 ảnh cảnh báo còn lại (đạt trạng thái `RELEASE`) và tăng số lượng seed huấn luyện lên 3–5 seed để giảm phương sai thống kê.

## 6. Quyết định và ghi chú AI
(a) Quyết định cuối và hướng khắc phục để đạt Release:
- Quyết định cuối: `HOLD` - không phát hành chính thức bộ dữ liệu `clean_v1` (chỉ xuất bản nháp để chạy thí nghiệm đối chứng)[cite: 3, 6].
- Để thành Release: Hiện tại toàn bộ lỗi bắt buộc đã bằng `0`, nhưng vẫn còn 38/203 ảnh (`18.72%`) mang cảnh báo chưa được duyệt vượt ngưỡng cho phép `10.00%` (tối đa `20/203 ảnh` ≈ `9.85%`)[cite: 3, 6]. Để chuyển sang `RELEASE`, cần cấp thêm ngân sách người duyệt tối thiểu 18 ảnh nữa (tăng tổng ngân sách từ 80 lên tối thiểu 98 ảnh) để xử lý dứt điểm các cảnh báo còn tồn đọng ở cuối hàng đợi[cite: 3, 6].

(b) Ghi chú dùng AI viết code:
- Prompt chính: Cung cấp nội dung file stub kèm docstring đặc tả đầu vào/đầu ra và danh sách mã lỗi của 4 module (`label_format.py`, `gate.py`, `autofix.py`, `second_opinion.py`), yêu cầu cài đặt đầy đủ logic kiểm tra và xử lý các trường hợp biên[cite: 3, 4, 6].
- Cách bạn kiểm code AI: Đọc đối chiếu từng dòng code với đặc tả docstring và cấu hình `configs/pipeline.yaml`, chạy `pytest` cho từng module riêng lẻ đến khi xanh hết 79/79 test, đồng thời kiểm tra thủ công các ca biên như dòng trống ở giữa file, một dòng dính nhiều lỗi và kiểm chứng kết quả chạy trên lô dữ liệu thật[cite: 3, 4, 6].
- 1 lần AI sai: Ở hàm `label_format.run`, AI giả định `ds.read_label_lines(stem)` trả về danh sách chuỗi (`str`) và dùng `enumerate()` để đếm dòng nên gây lỗi `AttributeError: 'tuple' object has no attribute 'strip'`; thực tế hàm này trả về trực tiếp tuple `(line_no, text)`, đồng thời chữ ký khởi tạo `Issue` cần truyền đúng tham số tên check ở vị trí đầu tiên.


*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
