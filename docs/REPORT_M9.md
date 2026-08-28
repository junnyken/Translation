# Báo cáo Mini-Spec M9 — Chạy cả chapter theo mẻ, thử lại có kỷ luật & cổng hạn mức

**Project:** Translation · **Phase:** MTE · **Ngày:** 2026-08-28
**Nền:** M8 `2a92286` (`v0.8-M8`) · giao diện `f753c46` · xoá chữ theo cụm `1bfa2de`

## 1. Summary

Người vận hành nay chạy được **cả chapter bằng một mẻ** thay vì bấm từng trang: chọn cách dịch,
bấm một nút, và nhìn thấy tiến độ thật — bao nhiêu trang xong, trang nào hỏng, trang nào bị chặn
vì hạn mức, đang làm tới trang nào.

Bốn thứ quan trọng hơn "chạy được":

1. **Mẻ không bao giờ báo xong khi còn việc.** Trạng thái mẻ được **suy ra** từ các mục con mỗi
   lần gộp, không có đường nào ghi tay vào nó.
2. **Chỉ thử lại lỗi tạm thời**, có trần, có lùi dần kèm nhiễu. Thiếu font, thiếu model, sai cấu
   hình ⇒ hỏng ngay, không tốn thời gian giả vờ cố gắng.
3. **Hạn mức Gemini được giữ ở mức toàn cục** bằng cửa sổ trượt nguyên tử trong Redis, không phải
   `rate_limit` của Celery (thứ chỉ giới hạn *từng worker*). Hết lượt ⇒ báo `blocked_quota` trung
   thực, **không** xoay khoá cùng project (M5 đã đo: vô ích).
4. **Chạy lại an toàn**: chỉ trang hỏng/bị chặn, không đụng trang đã xong — MD5 ảnh đã canh chữ
   trước và sau khi chạy lại giống hệt nhau.

**2 bảng mới** `batch_run` + `batch_item` (migration `0003_m9`), **7 endpoint** mới, **1 bảng điều
khiển mẻ** trên giao diện. **546 test pass**, tăng 96 test so với M8.

Chạy thật 4 Run bắt buộc trên **truyện tranh thật** (Pepper&Carrot, CC BY-SA) — số liệu ở
`TEST_LOG §M9`. Trong lúc chạy thật, **6 lỗi thật** lộ ra và đã sửa (§7).

## 2. Audit Before Build

8/8 mục của spec §5 có bằng chứng. Điểm đáng chú ý:

| Mục | Kết quả audit |
|---|---|
| Hook trung tâm nối `Job` ↔ `BatchItem` | Mọi task M2–M6 có đúng 3 lối ra (xong / hết giờ / lỗi). Đặt **một** hàm `bao_ket_thuc_buoc()` ở `workers/tasks.py`; task không biết gì về mẻ |
| `Job.retry_count` | Có sẵn từ M1, `int not null default 0`, **chưa từng được dùng**. Không task nào tự thử lại ⇒ không có chuyện hai chính sách thử lại chồng nhau |
| Redis | API và worker dùng **chung** `REDIS_URL` (`redis://redis:6379/0`); AOF **tắt**, chỉ có ảnh chụp mỗi 60s ⇒ trạng thái cổng **không** bền qua khởi động lại. Vì vậy nguồn sự thật của tiến độ đặt ở Postgres, Redis chỉ giữ cửa sổ nhịp 60s |
| Gemini 429 | Cùng mã 429 cho **cả** quá-nhịp lẫn hết-quota ⇒ phải đọc thân phản hồi mới phân biệt được. Không suy diễn "mọi 429 là hết quota" |
| Celery | 5.4.0. `Task.rate_limit` là **per worker instance** (tài liệu chính thức) ⇒ không dùng làm cổng toàn cục. `apply_async(countdown=…)` là cách hẹn giờ thử lại |
| Vòng đời trang | Mỗi trang tiếp tục **từ đúng bước nó đang đứng**; máy trạng thái M1 không cho quay ngược (`translated → detecting` là cạnh không hợp lệ) nên không thể "chạy lại từ đầu" |
| Export M8 | Là job tách biệt, **không** có batch export ẩn ⇒ mẻ tuyệt đối không tự xuất |
| Khoảng trống | Chưa có `BatchRun`/`BatchItem`, chưa có cổng hạn mức toàn cục, chưa có chính sách thử lại/chạy lại/tiến độ thống nhất |

## 3. Design Choice

**Tiến độ nằm ở Postgres, Redis chỉ giữ nhịp.** Worker bị giết (đã gặp thật ở M4 vì hết bộ nhớ)
thì mọi thứ trong bộ nhớ biến mất; tiến độ mẻ thì phải đọc lại được. Redis ở đây AOF tắt nên
không đủ bền để làm nguồn sự thật.

**Không có task nào ngồi chờ.** Worker chạy `--concurrency=1`; một task đứng chờ các task con sẽ
chiếm đúng cái worker duy nhất và mẻ tự khoá chết chính nó. Thay vào đó: xếp việc rồi thoát, mỗi
bước kết thúc thì gọi ngược `on_page_terminal` để đẩy bước/trang kế.

**Cổng nhịp bằng Redis + Lua, không dùng `rate_limit` của Celery.** Hai worker cùng đặt 10
lượt/phút thành 20 lượt/phút đập vào nhà cung cấp. Toàn bộ phép kiểm-rồi-ghi nằm trong một lệnh
Lua nên 40 luồng tranh nhau vẫn chỉ 5 lượt lọt qua (có test). Redis hỏng ⇒ cổng **từ chối**,
không mở toang.

**Ba nhóm lỗi, không phải hai.** Hết quota không thuộc "tạm thời" (thử lại ngay vẫn hỏng) cũng
không thuộc "vĩnh viễn" (quota hồi là chạy được) ⇒ trạng thái riêng `blocked_quota`, chờ người
vận hành bấm chạy lại.

**Không tạo `APIKeyPool`.** M5 đã đo: Gemini tính hạn mức theo **project**, xoay khoá trong cùng
project không tăng được gì — chỉ tạo ảo giác là hệ thống đang xoay xở. Có guardrail test quét
toàn bộ mã để chặn việc lén thêm lại.

**Mẻ không tự xuất chapter.** Tự xuất sau khi dịch có thể phát hành bản còn tràn khung và tước
mất quyền quyết định của người vận hành. Giao diện chỉ dẫn sang bảng xuất sau khi mẻ xong.

**Đặt tên theo tài nguyên** (`batch-runs/{id}`) thay vì hai động từ rời (`run-batch` /
`batch-status`) như phác thảo cũ ở `API.md`: một mẻ có mã riêng, xem lại được, chạy lại được,
dừng được — đó là tài nguyên chứ không phải một lệnh.

## 4. Changed Files

| Tệp | Việc |
|---|---|
| `app/models/enums.py` | + `BatchPipeline`, `BatchStatus`, `BatchItemStatus` |
| `app/models/__init__.py` | + `BatchRun`, `BatchItem` (unique + 2 index) |
| `alembic/versions/0003_m9_batch.py` | migration 2 chiều, drop enum type tường minh |
| `app/services/batch/errors.py` | phân loại lỗi + chính sách thử lại (lùi dần, nhiễu một nửa) |
| `app/services/batch/gate.py` | cổng nhịp Redis + Lua, khoá **băm**, không bao giờ chứa API key |
| `app/services/batch/rollup.py` | luật gộp trạng thái mẻ + chọn bước kế cho từng trang |
| `app/services/batch/dispatch.py` | tạo `Job` rồi đẩy đúng task cũ; hẹn giờ khi thử lại; hỏi broker việc nào còn sống |
| `app/services/batch/orchestrator.py` | tạo/đẩy/nhận kết quả/gộp/thu hồi/chạy lại/dừng |
| `app/services/batch/factory.py` | **chỗ duy nhất** được dựng bộ điều phối từ cấu hình |
| `app/workers/tasks.py` | 1 hàm `bao_ket_thuc_buoc()` + cổng nhịp trước khi gọi LLM |
| `app/api/v1/routes.py` | 7 endpoint mẻ |
| `app/schemas/common.py` | 8 schema mẻ |
| `app/core/config.py` | 9 tuỳ chọn `BATCH_*`/`LLM_*` + `llm_configured` |
| `frontend/src/components/BatchPanel.jsx` | bảng điều khiển mẻ (mới) |
| `frontend/src/api.js`, `App.jsx`, `styles.css` | nối bảng mẻ vào màn dự án |
| `scripts/do_run_m9.py` | đo Run A/B/C/E, lặp lại được |
| `docs/*` | ARCH §10, API §26–32, FEATURES, PLAN, TEST_LOG §M9 |

## 5. New API / DB / State

**DB:** `batch_run` (14 cột) + `batch_item` (13 cột), `unique(batch_run_id, page_id)`,
index `(batch_run_id, status, page_order)` và `(current_job_id)`.
**Không** thêm `APIKeyPool`, **không** thêm `ProviderQuotaState` (Redis đủ cho cửa sổ 60s).

**API:** §26–32 trong `API.md`. 5 endpoint theo đúng hợp đồng mini-spec, **2 endpoint thêm** và
lý do:

| Thêm | Vì sao |
|---|---|
| `GET /batch-config` | §4D buộc giao diện tắt lựa chọn LLM **kèm lý do rõ** khi chưa cấu hình. Không có nó thì giao diện phải đoán, hoặc để người dùng bấm rồi nhận 422. Chỉ trả true/false + các con số |
| `GET /projects/{id}/batch-runs` | Không có nó thì giao diện phải tự nhớ mã mẻ trong trình duyệt; tải lại trang là mất dấu mẻ đang chạy |

**State:** trạng thái mẻ **luôn** suy ra từ mục con (bảng ở `API.md §27`). `Page.status` do M1–M8
làm chủ — mẻ **không bao giờ** ghi vào.

## 6. Tests

**546 pass** (M8: 450). Riêng M9: 90 test + 8 guardrail.

Guardrail canh những thứ "code chạy được" không phát hiện: không `APIKeyPool`, bộ điều phối không
đụng engine nào của M2–M8, mẻ không nhắc tới export, `gate.py` bắt buộc băm khoá, Celery không có
`rate_limit`, mỗi task báo về mẻ ở **cả 3 nhánh** (đếm bằng AST), việc thao tác tay **không** báo
về mẻ, và chỉ **một** chỗ được dựng bộ điều phối.

## 7. Bugs tìm được & đã sửa

Chi tiết + bằng chứng đo: `TEST_LOG §M9.7`. Tóm tắt:

1. **Dò khung hỏng ⇒ mẻ treo 40 phút** — `run_detect_job` chỉ báo về ở nhánh thành công.
2. **Cấu hình thử lại không có tác dụng** — worker dựng `RetryPolicy` bằng tay, quên đọc `.env`.
   Đặt lùi dần 30s, đo được 0,6s.
3. **`next_delay_seconds` chưa từng được gọi** — thử lại gọi lại ngay lập tức.
4. **Bước kế tiếp bị phạt chờ oan** bằng thời gian lùi của lần lỗi trước.
5. **Nhiễu toàn phần cho ra 0,2s** — "có lùi dần" trên giấy, thực tế chờ như không chờ.
6. **Bấm "chạy lại" ngay sau sự cố không cứu được gì** — thu hồi chỉ dựa vào đồng hồ 2400s.
   Sửa: hỏi broker xem việc còn sống thật không.

Lỗi 2–5 đều là "code trông đúng, đọc qua thấy hợp lý" và **chỉ lộ ra khi chạy thật rồi đọc log**.

## 8. Success Criteria — đối chiếu thẳng

| Tiêu chí (spec §8) | Kết quả |
|---|---|
| Ảnh chụp đúng danh sách/thứ tự lúc tạo; trang thêm sau không lọt vào | ✅ Run A |
| Tiến độ phản ánh đúng completed/failed/blocked; không báo xong khi còn việc | ✅ Run A/C, + test gộp trạng thái |
| Lỗi tạm thời thử lại đúng trần, có lùi dần + nhiễu; lỗi vĩnh viễn không thử lại | ✅ Run B (1 lần, chờ 6,9s) |
| Cổng hạn mức toàn cục, không xoay khoá cùng project | ⚠️ ✅ ở mức 1 worker (test 40 luồng + Run C); **chưa** đo nhiều worker thật |
| Hết lượt ⇒ `blocked_quota` minh bạch, không gọi ra nhà cung cấp, không lùi tốn phí trái ý | ✅ Run C — 0 lời gọi ra Gemini trong cả 4 lần |
| Chạy lại chỉ trang hỏng/bị chặn; trang đã xong không đổi/không nhân bản | ✅ Run C/E — MD5 giống hệt Run A |
| Dừng mẻ không làm hỏng việc đang chạy | ✅ test tích hợp (chưa đo trên hệ thật) |
| M1–M8 hồi quy pass; tài liệu cập nhật đủ | ✅ 546 test + hồi quy sống 1 trang lẻ |

## 9. Remaining Limits / Follow-ups

- **Chưa có auth/RBAC** — M9 chỉ hợp với thí điểm một người vận hành trên máy nhà.
- **Cổng nhịp mới đo với 1 worker.** Muốn tuyên bố "giữ đúng hạn mức" ở môi trường nhiều máy thì
  phải đo lại với Redis dùng chung.
- **`LLM_PROJECT_RPM=10` là số dev**, không phải hạn mức Google công bố cho project này.
- **Chưa đo mẻ dài** (10+ trang, chạy hàng giờ).
- **Giao diện chưa bấm thật trên trình duyệt** như M7 đã làm.
- **Dừng mẻ (`cancel`) chưa đo trên hệ thật** — mới có test tích hợp.
- Không tự thử lại khi **chất lượng** kém (OCR/dịch/xoá chữ sai) — đó không phải lỗi hạ tầng;
  vẫn phải sửa tay ở M7.
- **M10** — cổng khai báo phạm vi sử dụng & bản quyền: không lén thêm vào M9.
