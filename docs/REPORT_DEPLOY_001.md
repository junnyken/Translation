# Báo cáo Phase 3A–3C — Push GitHub + Deploy VibeHost

**Ngày:** 2026-08-30/31 · **Phạm vi:** 3A audit · 3B push · 3C deploy + smoke
**Dừng trước:** Phase 3D (Pilot/UAT) — theo quyết định của chủ dự án
**Môi trường:** VibeHost **staging/production-like** (chưa được xác nhận là production chính thức)

## 1. Summary

Đẩy 4 commit local lên GitHub và triển khai lên VibeHost. Trước lượt này, bản hosted chạy mã từ
**29/08 15:49** — cũ hơn E1, E15 phần 2, phần đóng E15 và E1a.

- **Push:** `7ca8af6..45c0af2` → `origin/main`. ✅
- **Deploy:** `translation-api` v20→**v21**, `translation-web` v12→**v13**. ✅
- **Smoke sau deploy:** curl + **Chromium thật 11/11 đạt**. ✅
- **CORS hosted giữ nguyên độ chặt** — không wildcard, không phản chiếu, không credentials.

**Không** phải production-ready: chưa có auth/RBAC/multi-user, và Pilot/UAT chưa chạy.

## 2. Audit Before Run (Phase 3A)

### 2.1 Git

```
branch          : main
worktree        : SẠCH
commit range    : 7ca8af6..45c0af2  (4 commit, 60 tệp, +9.197/−21)
  45c0af2  security(e1a): harden local API and Vite proxy CORS
  fff82d0  docs(e15): close orientation routing and record vertical structural block
  6be69b9  feat(E15 phần 2): giao diện hướng chữ + Run A–D
  5bd3007  feat(E1): tiện ích Chrome mở nhanh Translation
```

### 2.2 Quét bí mật — **PASS**

| Kiểm | Kết quả |
|---|---|
| `git diff --check` | sạch |
| `.env` có bị theo dõi | **không** (`git ls-files` → 0). Tệp khớp mẫu `.env` là `.env.example` — mẫu an toàn |
| Mẫu `AIza…` / `sk-…` / `github_pat_…` | 1 dòng khớp: `backend/tests/test_batch_integration.py:263` |
| Dòng đó là gì | **key GIẢ trong test kiểm chức năng che key**: `assert "AIzaSyD1234567890" not in loi` + `assert "***" in loi`. Có từ `d83c572` (28/08), **không** thuộc dải push |
| Model/onnx/pt trong dải push | **0** |
| `node_modules`, `storage/local`, `test_fixtures/den_trang` | **0** |

### 2.3 Hồi quy trước khi phát hành

| Bộ | Lệnh | Kết quả |
|---|---|---|
| Backend | `cd backend && ../.venv/bin/python -m pytest -q` | **785 thu thập, exit 0**, 0 fail |
| Frontend | `cd frontend && npx vitest run` | **226 pass**, 0 fail |
| Extension | `cd extension && npx vitest run` | **282 pass**, 0 fail |
| Build | `cd frontend && npx vite build` | ✅ `built in 2.17s` |

**Lint chưa phải cổng phát hành** — repo không có ruleset cấu hình; các phát hiện nền vẫn là việc riêng.

### 2.4 Audit triển khai

| Hạng mục | Đo được |
|---|---|
| Nguồn deploy | `sourceType: git-url`, `sourceProvider: github` |
| Push có tự deploy không | **KHÔNG** — sau khi push, `lastDeployedAt` vẫn 29/08 15:49 ⇒ redeploy **thủ công** |
| Topology | **Không có service worker riêng.** Worker chạy chung trong `translation-api` (`ROLE=all`, xem `backend/deploy-start.sh`) |
| Model AI | ✅ có — `backend/Dockerfile` tải `comic-text-detector.onnx` + `lama-manga-dynamic.onnx` từ HuggingFace lúc build |
| Font | ✅ có — 10 tệp trong git kèm OFL |
| CSDL | Postgres managed (`translation-api-db`) + Redis managed — **tách khỏi container**, không mất khi redeploy |
| Tài nguyên api | 1.6 vCPU / 4096 MB (trần 2.6 / 5376 MB) |

**Khoá cấu hình có mặt** (chỉ liệt kê TÊN, không đọc giá trị): `DATABASE_URL`, `CELERY_BROKER_URL`,
`CELERY_RESULT_BACKEND`, `REDIS_URL`, `STORAGE_BACKEND`, `STORAGE_LOCAL_ROOT`, `CTD_WEIGHTS_PATH`,
`INPAINT_WEIGHTS_PATH`, `FONT_DIR`, `DEFAULT_FONT_FAMILY`, `CORS_ALLOW_ORIGINS`, `ROLE`,
`WORKER_STATE_FILE`, `GEMINI_API_KEYS`, `LLM_MODEL_NAME`, `INPAINT_WHOLE_PAGE_MAX_MPX`,
`INPAINT_INTRA_OP_THREADS`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`.

### 2.5 Mốc nền TRƯỚC deploy

```
web  /                    200
web  config.js            __API_BASE__ = https://translation-api.cmc-1.vibenode.matbao.ai
api  /healthz             200 · application/json
api  /api/v1/health       {"status":"ok"}
CORS api:
  https://translation.cmc-1.vibenode.matbao.ai  -> ACAO khớp chính xác
  https://evil.example                          -> (không có ACAO)
  http://localhost:5174                         -> (không có ACAO)
  null                                          -> (không có ACAO)
  wildcard ACAO:*                               -> 0
```

## 3. Deployment (Phase 3B + 3C)

### 3.1 Push

```
Remote  : https://github.com/junnyken/Translation
Branch  : main
Range   : 7ca8af6..45c0af2
Kết quả : 7ca8af6..45c0af2  main -> main   (103 object, 167.44 KiB)
Xác minh: git ls-remote origin main -> 45c0af26b913cd83ea43446218552126cca3bf54
```

⚠️ **Tag CHƯA được đẩy.** `v1.5-E15-closed` và `v1.6-E1a-cors-hardening` vẫn chỉ có ở local —
push branch thực hiện bằng nhập tay tương tác nên phiên tự động không dùng lại được credential.
Cách đẩy nốt:

```bash
cd ~/workspace/projects/Translation
git push origin v1.5-E15-closed v1.6-E1a-cors-hardening
```

### 3.2 Deploy

| Service | Trước | Sau | Thời điểm | Job |
|---|---|---|---|---|
| `translation-api` | v20 (29/08 15:49) | **v21** | 31/08 00:12 | `cmtg2exdn0ede0i5f56kswhpp` — succeeded |
| `translation-web` | v12 (29/08 15:49) | **v13** | 31/08 00:13 | `cmtg2i0oh0efm0i5fajnvxnii` — succeeded |

Cơ chế: `redeploy_project` trên VibeHost (thủ công). Deploy api trước, chờ xong hẳn rồi mới deploy web.

**Rollback có sẵn:** `rollback_project(translation-api, 20)` và `rollback_project(translation-web, 12)`.

### 3.3 Bằng chứng phiên bản đã triển khai

Ứng dụng **không** phơi build SHA — đây là **lỗ hổng quan sát**. Dùng bằng chứng theo tính năng thay thế:

**API** — phân biệt route tồn tại/không tồn tại bằng **thân 404**:

```
/api/v1/khong-he-co-route-nay                 -> {"detail":"Not Found"}          (route KHÔNG có)
/api/v1/pages/{uuid}/orientation-summary      -> {"detail":"page_not_found"}     (route CÓ — E15)
/api/v1/regions/{uuid}/orientation            -> {"detail":"orientation_not_analyzed: vùng này
                                                  chưa được nhận biết hướng chữ"}  (route CÓ — E15)
```

**Web** — bundle mới `/assets/index-CGGZ4XNz.js` (238.952 byte) chứa đủ chuỗi giao diện E15:
`Chữ dọc — đã căn theo cột`, `Chưa xác định hướng chữ`, `Hiện lưới cột chữ`,
`Chữ nghiêng/cách điệu`, `orientation-summary` — mỗi chuỗi 1 lần.

### 3.4 Smoke sau deploy — Chromium thật, **11/11 đạt**

`scripts/do_smoke_hosted.py` dựng một website lạ ở cổng 9999 rồi từ đó gọi API hosted.

| Mục | Kết quả |
|---|---|
| H1 tải qua HTTPS | ✅ |
| H2 `__API_BASE__` trỏ đúng API hosted | ✅ |
| H3 giao diện E11 hiện form tạo chapter | ✅ `Translation \| Dịch truyện tranh sang tiếng Việt \| Chapter \| Tạo chapter` |
| H4 giao diện **đọc được** API chéo nguồn | ✅ 200 `{"status":"ok"}` |
| H5 website lạ đọc `/api/v1/health` | ✅ **CHẶN** — `TypeError: Failed to fetch` |
| H5 website lạ đọc `/healthz` | ✅ **CHẶN** |
| H6 không tràn ngang @ 360/768/1280/1600 | ✅ 4/4 |
| Z1 lỗi JS console | ✅ 0 |

**Ma trận CORS sau deploy (curl):**

| Origin | ACAO |
|---|---|
| `https://translation.cmc-1.vibenode.matbao.ai` | khớp chính xác |
| `https://evil.example` | *(không có)* |
| `http://localhost:5174` | *(không có)* |
| `null` | *(không có)* |
| `https://translation.cmc-1.vibenode.matbao.ai.evil.example` | *(không có)* |

`ACAO: *` → **0**. `Access-Control-Allow-Credentials` → **0**. Không đổi so với trước deploy.

### 3.5 Worker

```
/healthz sau deploy:
{"status":"ok","worker":{"trang_thai":"starting","so_lan_chet":0,
 "ma_thoat_gan_nhat":null,"luc":"2026-08-30T17:12:14Z"}}
```

`luc` khớp đúng thời điểm deploy; `so_lan_chet: 0` ⇒ worker đã bật và **chưa chết lần nào**.

⚠️ **Nhưng `starting` KHÔNG phải bằng chứng worker đang chạy.** Đọc `backend/deploy-start.sh`:
ở `ROLE=all`, script ghi `starting` **đúng một lần** lúc khởi động và chỉ ghi lại khi worker chết
(`restarting`). Nó **không bao giờ** ghi `running`. Nên trạng thái này chỉ chứng minh
"đã bật và chưa sập", **không** chứng minh worker đang tiêu thụ việc.

**Bằng chứng worker thật sự xử lý việc chỉ có được khi chạy Pilot** — chưa có ở phase này.

## 4. Phát hiện — chưa sửa (Phase 3 cấm sửa)

| # | Mức | Phát hiện |
|---|---|---|
| 1 | **P2** | `GEMINI_API_KEYS` trên `translation-api` đang lưu với `isSecret: false` ⇒ giá trị có thể hiện trong dashboard. (Không đọc, không in giá trị.) |
| 2 | **P2** | `STORAGE_BACKEND=local`, `STORAGE_LOCAL_ROOT=/data/storage`. Local có volume `storage_data`; trên VibeHost **chưa xác minh được** có volume tương đương. Nếu không có, redeploy xoá ảnh trang trong khi Postgres managed vẫn giữ bản ghi ⇒ chapter cũ hỏng ảnh. Chủ dự án đã chấp nhận rủi ro này cho lượt deploy hiện tại. |
| 3 | **P3** | Worker state kẹt ở `starting` vĩnh viễn (§3.5) — lỗ hổng quan sát. |
| 4 | **P3** | Ứng dụng không phơi build SHA/version ⇒ phải chứng minh phiên bản gián tiếp qua tính năng. |

## 5. What Passed — chỉ những gì có bằng chứng

- Push đúng dải commit, xác minh bằng `git ls-remote`.
- Quét bí mật sạch; `.env`/model/ảnh riêng tư không lọt vào git.
- Hồi quy đầy đủ xanh (785 / 226 / 282 / build).
- Cả hai service deploy thành công, lên đúng version mới.
- Mã E15 **thật sự** có trên hosted — chứng minh bằng thân 404 và chuỗi bundle.
- CORS hosted chặt như trước deploy, chứng minh bằng **cả curl lẫn Chromium thật**.
- Giao diện không tràn ngang ở 4 cỡ màn hình, 0 lỗi JS.

## 6. What Did Not Pass / Unknown

- **Tag chưa đẩy** — cần một lệnh tay của chủ dự án (§3.2).
- **Worker có tiêu thụ việc không: CHƯA BIẾT.** `starting` không phải bằng chứng. Cần Pilot.
- **LaMa inpaint trên 4GB host: CHƯA ĐO.** M4 từng OOM; hosted chạy API+worker chung container.
- **Persistent storage cho ảnh: CHƯA XÁC MINH.**
- **E15 dựng chữ dọc: vẫn BLOCKED về cấu trúc** (`MangaOCREngine.recognize()` trả `(text, None)`).
- **Tiện ích E1: chưa bấm tay biểu tượng** — môi trường không có display server.
- **Pilot/UAT chưa chạy** — dừng theo quyết định của chủ dự án.

## 7. Remaining Limits

- Đây là môi trường **staging/production-like**, chưa được xác nhận là production chính thức.
- **Không có auth/RBAC/multi-user.** **CORS không phải xác thực** — nó chỉ chặn trang web trong
  trình duyệt; mọi tiến trình gọi thẳng API vẫn được.
- Tiện ích E1: không nhập URL, không quét website, không phủ bản dịch.
- E15: chữ dọc/chữ nghiêng chỉ để **rà soát**, không dựng.
- Lint chưa có cổng phát hành.

## 8. Git / Deploy State

```
Pushed commit  : 45c0af2  (origin/main = 45c0af26b913cd83ea43446218552126cca3bf54)
Tag đã đẩy     : KHÔNG CÓ — v1.5-E15-closed, v1.6-E1a-cors-hardening còn ở local
Deploy hiện tại: translation-api v21 · translation-web v13  (31/08 00:12–00:13)
Rollback       : api -> v20 · web -> v12  (rollback_project có sẵn)
Báo cáo này    : commit LOCAL, KHÔNG push (theo quy tắc §11 của kế hoạch)
```

**Sau khi deploy xong, không có lần push hay deploy nào khác được thực hiện.**
