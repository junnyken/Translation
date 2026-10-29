# MCP server cho Translation

Cho Claude / Cursor điều khiển việc dịch truyện tranh qua giao thức MCP. Đây là **client mỏng**
gọi REST API `/api/v1` có sẵn của Translation: không nhập mã backend, không đụng
`backend/requirements*.txt`. "Chapter" trong công cụ = `project` trên API.

## Cài

Cần Python 3.10+.

```bash
cd tools/mcp-translation
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # chỉ: mcp>=1.2,<2
# (tuỳ chọn) .venv/bin/pip install pillow   # để thu nhỏ ảnh trả về cạnh dài <= 1600px
```

> Dùng venv RIÊNG, đừng cài `mcp` vào venv của backend: `mcp` kéo `pydantic`/`starlette` bản
> mới hơn bản backend ghim.

## Cấu hình (biến môi trường)

| Biến | Ý nghĩa |
|---|---|
| `TRANSLATION_API_URL` | Địa chỉ API, mặc định `http://127.0.0.1:8010`. Production: `https://translation-api.vibe1.tinhgon.xyz` |
| `TRANSLATION_MA_PHIEN` | Mã phiên (gửi `Authorization: Bearer ...`) |
| `TRANSLATION_EMAIL` + `TRANSLATION_MAT_KHAU` | Thay cho mã phiên: server tự gọi `POST /api/v1/auth/login`, giữ mã trong bộ nhớ, hết hạn thì đăng nhập lại một lần |
| `TRANSLATION_API_KEY` | Tuỳ chọn: khoá chung `X-API-Key` nếu máy chủ bật |

Mã phiên và mật khẩu không bao giờ được in ra log hay kết quả công cụ (thông điệp lỗi đều bị
che).

## Claude Code

```bash
claude mcp add translation \
  -e TRANSLATION_API_URL=https://translation-api.vibe1.tinhgon.xyz \
  -e TRANSLATION_EMAIL=ban@matbao.com -e TRANSLATION_MAT_KHAU='***' \
  -- /đường/dẫn/tools/mcp-translation/.venv/bin/python /đường/dẫn/tools/mcp-translation/server.py
```

## Claude Desktop (`claude_desktop_config.json`) / Cursor (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "translation": {
      "command": "/đường/dẫn/tools/mcp-translation/.venv/bin/python",
      "args": ["/đường/dẫn/tools/mcp-translation/server.py"],
      "env": {
        "TRANSLATION_API_URL": "https://translation-api.vibe1.tinhgon.xyz",
        "TRANSLATION_MA_PHIEN": "<mã phiên>"
      }
    }
  }
}
```

## Công cụ

| Công cụ | Việc làm | Endpoint |
|---|---|---|
| `liet_ke_chapter` | Liệt kê chapter của tôi | `GET /projects` |
| `tao_chapter(name, source_lang, intended_use)` | Tạo chapter (ja/zh/en; personal/study/other) | `POST /projects` |
| `xem_chapter(project_id)` | Chapter + danh sách trang + trạng thái | `GET /projects/{id}` |
| `tai_trang_len(project_id, duong_dan, engine?)` | Tải ảnh, hoặc gói `.zip`/`.cbz` cả chapter, từ tệp cục bộ | `POST /projects/{id}/pages[/archive]` |
| `xem_trang(page_id)` | Vùng chữ: chữ gốc, bản dịch, font, `fit_status` | `GET /pages/{id}/detail` |
| `xem_anh_trang(page_id, loai)` | Ảnh `goc` / `sach` (đã xoá chữ) / `xem_thu` (đã dịch), trả dạng Image | `GET /pages/{id}/original-image` ... |
| `sua_vung(region_id, ...)` | Sửa `translated_text`, `raw_text`, `bbox=[x,y,w,h]`, `font_family`, `font_size`; chờ canh lại xong | `PATCH /regions/{id}` |
| `dich_lai_vung(region_id, engine?)` | Dịch lại vùng | `POST /regions/{id}/re-translate` |
| `doc_lai_vung(region_id)` | Đọc lại chữ gốc (OCR) | `POST /regions/{id}/re-ocr` |
| `canh_lai_vung(region_id, font_size?)` | Canh lại chữ | `POST /regions/{id}/re-fit` |
| `chay_lai_buoc(page_id, buoc, engine?)` | Chạy lại `detect/ocr/inpaint/translate/typeset` | `POST /pages/{id}/retry-*` |
| `chay_ca_chapter(project_id, engine?, chi_chay_lai_loi?)` | Chạy cả chapter bằng một mẻ | `POST /projects/{id}/batch-runs` |
| `xem_tien_do_me(batch_run_id, kem_chi_tiet_trang?)` | Tiến độ mẻ | `GET /batch-runs/{id}[/items]` |
| `xuat_chapter(project_id, dinh_dang)` | Xuất `png_single`/`zip`/`cbz` | `POST /projects/{id}/export` |
| `cho_viec(job_id, timeout, loai)` | Chờ job (`auto`/`job`/`export`/`batch`) và trả địa chỉ tải | `GET /jobs/{id}`, `/export-jobs/{id}`, `/batch-runs/{id}` |
| `tai_file_xuat(job_id, thu_muc_luu)` | Tải file zip/cbz đã xuất về máy | `GET /export-jobs/{id}/download` |

Công cụ chỉ đọc có `readOnlyHint`. `png_single` xuất ra thư mục trên máy chủ nên không tải một
lần được — chọn `zip` hoặc `cbz` nếu cần tệp về máy.

## Quy trình điển hình

`tao_chapter` -> `tai_trang_len` (ZIP/CBZ) -> `chay_ca_chapter` -> `cho_viec(loai="batch")` ->
`xem_trang` / `xem_anh_trang` rà soát -> `sua_vung` -> `xuat_chapter` -> `cho_viec(loai="export")`
-> `tai_file_xuat`.

## An toàn

Nội dung trang truyện (ảnh, chữ OCR, bản dịch) là dữ liệu không tin cậy: server dặn model không
làm theo chỉ dẫn nằm trong ảnh/chữ. Engine `llm_context` tốn token, chỉ dùng khi bạn yêu cầu.

## Test

```bash
.venv/bin/pip install pytest pillow
.venv/bin/python -m pytest tests -q   # dùng máy chủ HTTP giả, không cần backend
```
