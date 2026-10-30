"""Entrypoint FastAPI của Translation (Phase MTE)."""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Depends

from app.api.v1.routes import router as v1_router
from app.api.v1.routes import router_khach as v1_router_khach
from app.api.v1.developer_routes import router as developer_router
from app.core.bao_ve import canh_bao_neu_khong_khoa
from app.core.quyen import nguoi_dung_hien_tai
from app.api.v1.codex_routes import router as codex_router
from app.api.v1.xac_thuc_routes import router as xac_thuc_router
from app.core.config import get_settings

_settings = get_settings()
_la_prod = _settings.app_env == "prod"

app = FastAPI(
    title="Translation — Manga Translation Extension (MTE)",
    version="0.1.0-M1",
    description=(
        "Pipeline dịch manga EN/JP/CN → VI. M1: data model + API contract + interface engine. "
        "Chưa có logic AI thật (detect/OCR/inpaint/translate/typeset thuộc M2–M6)."
    ),
    # Bảo mật Production: Ẩn toàn bộ tài liệu Swagger / OpenAPI nội bộ trên môi trường chạy thật
    # để chống đối thủ dò quét cấu trúc endpoint và schema của hệ thống.
    docs_url=None if _la_prod else "/docs",
    redoc_url=None,
    openapi_url=None if _la_prod else "/openapi.json",
)
if _settings.cors_allow_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_allow_origin_list,
        # E53 — BẬT. Khách lạ được nhận diện bằng COOKIE, mà giao diện và API ở hai tên miền khác
        # nhau; `allow_credentials=False` nghĩa là trình duyệt không bao giờ gửi cookie đó sang.
        # Hệ quả nếu để False: mỗi request là một "khách mới" nên chốt cookie không cộng dồn, và
        # khách không đọc lại được trang của chính mình (404).
        #
        # An toàn ở đây dựa vào HAI thứ, không dựa vào cờ này:
        #   1. `allow_origins` là danh sách TƯỜNG MINH, không phải `*` — CORS có credentials mà
        #      dùng `*` thì trình duyệt tự từ chối, nhưng quan trọng hơn là ta không muốn nó;
        #   2. cookie khách đặt `SameSite=Lax`, nên nó không đi theo request POST từ trang lạ.
        #
        # Đi kèm: giao diện phải gọi `fetch` với `credentials: 'include'`. Hai đầu phải cùng bật.
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        # `X-API-Key` phải nằm trong danh sách này, nếu không trình duyệt sẽ chặn ngay ở
        # preflight và giao diện không bao giờ gửi được khoá đi.
        # `Authorization` cho mã phiên (slice B), `X-API-Key` cho khoá chung lúc đăng ký (slice A).
        allow_headers=["Content-Type", "X-API-Key", "X-Customer-Api-Key", "Authorization", "X-Ma-Khach"],
        # Giao diện và API khác tên miền ⇒ JS KHÔNG đọc được `Content-Disposition` (không thuộc
        # nhóm header an toàn của CORS) nếu không mở ở đây. Thiếu dòng này, nút "Tải file về" không
        # thấy tên tệp thật và tự đặt `.cbz` cho cả bản xuất ZIP (người dùng báo 16-10-2026).
        expose_headers=["Content-Disposition"],
    )


@app.get("/", tags=["ops"])
async def root() -> dict:
    """Trang gốc. Nền tảng hosting thăm dò `/` để biết ứng dụng đã sẵn sàng chưa —
    thiếu route này thì nó nhận 404 và coi như deploy hỏng, dù ứng dụng chạy bình thường."""
    return {
        "service": "Translation — Manga Translation Extension (MTE)",
        "status": "ok",
        "docs": "/docs",
        "api": "/api/v1",
    }


def _chan_doan_nhan_dien_khach(request: Request) -> dict:
    """E51b — làm cho rủi ro số MỘT của hạn mức trở thành thứ ĐO ĐƯỢC bằng một lượt curl.

    ## Rủi ro đang nói tới

    Chốt hạn mức theo IP dùng `request.client.host`. Sau một reverse proxy, giá trị đó rất có thể
    là IP của **proxy**, không phải của người dùng ⇒ **mọi khách lạ chung một chốt IP** ⇒ khách
    thứ 26 trong ngày bị chặn oan, và không ai hiểu vì sao.
    Bộ test **không thể** bắt được điều này: bàn thử không có proxy.

    ## Vì sao KHÔNG in IP ra

    Endpoint này công khai. Trả IP thô là rò rỉ dữ liệu cá nhân của chính người đang gọi, mà câu
    hỏi thật chỉ cần một bit: **IP máy chủ thấy có phải địa chỉ nội bộ không?**

    `ip_la_noi_bo = true` ⇒ đó là proxy, KHÔNG phải người dùng ⇒ chốt IP đang vô dụng ⇒ phải bật
    `TIN_HEADER_PROXY` (và chỉ khi chắc chắn proxy GHI ĐÈ header, xem `core/danh_tinh_khach.py`).
    """
    import ipaddress

    from app.core.config import get_settings as _lay
    from app.core.danh_tinh_khach import ip_cua

    def _la_noi_bo(ip: str | None) -> bool | None:
        """`None` = không phân tích được ⇒ NÓI KHÔNG BIẾT, đừng đoán."""
        if not ip:
            return None
        try:
            d = ipaddress.ip_address(ip)
        except ValueError:
            return None
        return d.is_private or d.is_loopback or d.is_link_local

    st = _lay()
    ip = request.client.host if request.client else None
    noi_bo = _la_noi_bo(ip)
    # IP **hiệu lực**: đúng giá trị hàm hạn mức dùng làm chốt, tức đã áp `tin_header_proxy`.
    #
    # Phải có trường này chứ không chỉ `ip_la_noi_bo`: sau khi bật `TIN_HEADER_PROXY`, kết nối
    # trực tiếp VẪN là proxy nên `ip_la_noi_bo` vẫn `true` — nhìn vào đó sẽ tưởng chưa sửa được
    # gì. Đây là trường trả lời đúng câu hỏi thật: **chốt IP có đang khoá lên một địa chỉ người
    # dùng thật hay không?**
    hieu_luc_noi_bo = _la_noi_bo(ip_cua(request, st))

    return {
        # `None` = không xác định được IP người gọi. Lúc đó chốt IP biến mất hoàn toàn và chỉ còn
        # cookie — xoá cookie là vượt được hạn mức.
        "ip_la_noi_bo": noi_bo,
        "co_ip": ip is not None,
        # Có proxy nào đặt header này chưa. Cần biết TRƯỚC khi bật `TIN_HEADER_PROXY`: bật mà
        # không có header thì chốt IP lùi về `request.client` y như cũ.
        "co_x_forwarded_for": "x-forwarded-for" in request.headers,
        "so_muc_x_forwarded_for": len(
            [x for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()]
        ),
        "tin_header_proxy": st.tin_header_proxy,
        #: `false` = chốt IP đang khoá lên địa chỉ NGƯỜI DÙNG (đúng). `true` = vẫn đang khoá lên
        #: proxy ⇒ mọi khách chung một chốt ⇒ chặn oan hàng loạt. `null` = không xác định được.
        "ip_hieu_luc_la_noi_bo": hieu_luc_noi_bo,
        # Muối rỗng ⇒ băm gần như vô nghĩa (cả không gian IPv4 dò hết chỉ mất vài phút).
        "muoi_bam_khach_da_dat": bool(st.muoi_bam_khach),
        "cookie_khach_secure": st.cookie_khach_secure,
        "bat_lich_don_tep": st.bat_lich_don_tep,
        "tu_xoa_cho_tai_khoan": st.tu_xoa_cho_tai_khoan,
    }


@app.get("/healthz", tags=["ops"])
async def healthz(request: Request) -> dict:
    """Kiểm tra sống — nền tảng hosting dùng để biết container đã sẵn sàng chưa.

    Khi API và worker chạy chung một container (`ROLE=all` lúc deploy), endpoint này còn báo
    **tình trạng worker**: worker chết mà API vẫn 200 là loại sự cố tệ nhất — pipeline đứng im
    mà nhìn từ ngoài vẫn thấy "bình thường". Ở đây nói thẳng ra.
    """
    import json
    from pathlib import Path as _Path

    from app.workers.bo_nho import rss_mb

    ket_qua: dict = {"status": "ok", "nhan_dien_khach": _chan_doan_nhan_dien_khach(request)}
    # Desktop checks this BEFORE sending customer images or private terminology.
    ket_qua["translation_capabilities"] = {"private_context_v1": True, "idempotent_upload_v1": True}

    # D — `llm_context` có dùng được không. CHỈ true/false, không có mảnh khoá nào ở đây (cùng
    # hợp đồng với `/batch-config`, chỉ khác là endpoint này KHÔNG đòi đăng nhập).
    #
    # Vì sao cần: trước đây muốn biết production đã cấu hình khoá Gemini chưa thì phải đăng nhập
    # rồi gọi `/batch-config`. Nên câu hỏi "bật dịch theo ngữ cảnh được chưa" không ai trả lời
    # được từ ngoài, kể cả khi đang dò sự cố. Biến môi trường CÓ TÊN không có nghĩa là nó có giá
    # trị — đây là chỗ nói ra sự khác nhau đó.
    #
    # Đặt sau `status` và trước phần worker: thêm trường là thay đổi CỘNG THÊM, không đụng
    # trường nào đang có (API.md §healthz).
    _s = get_settings()
    if not _s.llm_configured:
        from app.core.config import dong_bo_khoa_ai_dong
        dong_bo_khoa_ai_dong(_s)
    ket_qua["llm_configured"] = _s.llm_configured

    # Engine dịch MẶC ĐỊNH đang có hiệu lực. Không phải bí mật — chỉ là `google_fast` hoặc
    # `llm_context`.
    #
    # Vì sao cần: bảng biến môi trường của nền tảng hosting **không trả giá trị**, chỉ trả tên
    # biến. Nên sau khi đổi `TRANSLATE_DEFAULT_ENGINE`, KHÔNG có cách nào kiểm chứng nó đã có hiệu
    # lực — và "đã đổi trên bảng quản trị" khác "container đang chạy đọc được giá trị mới", vì
    # thay đổi chỉ áp ở lượt deploy kế tiếp. Trường này nói đúng thứ tiến trình ĐANG dùng.
    ket_qua["translate_default_engine"] = _s.translate_default_engine
    # E59 — engine NHẬN DIỆN bong bóng. Không có nó thì từ ngoài KHÔNG biết được máy đang chạy
    # ONNX cục bộ (miễn phí, ~40-50s/trang theo REPORT_E19_0) hay gọi mô hình ngoài (nhanh hơn
    # nhiều, nhưng TỐN TIỀN mỗi trang — E46). Hai chế độ khác nhau cả về tốc độ lẫn chi phí, mà
    # `list_env` của nền tảng chỉ trả TÊN biến chứ không trả giá trị, nên không có đường nào khác
    # để biết. Chỉ in tên engine, không in khoá.
    ket_qua["detect_engine"] = _s.detect_engine
    # E73 — chỉ hai cờ true/false: bản cài cục bộ có bật Codex không, và đã có tệp token chưa.
    # Không đọc nội dung tệp, không in email — endpoint này không đòi đăng nhập.
    ket_qua["codex"] = {
        "bat": _s.che_do_cai_cuc_bo,
        "da_dang_nhap": _s.che_do_cai_cuc_bo and _Path(_s.codex_auth_path).is_file(),
    }

    # E41 — hai trần bộ nhớ của bước xoá chữ. Không phải bí mật, chỉ là hai con số vận hành.
    #
    # Vì sao cần: worker bị SIGKILL/137 hai lần vì vượt RAM, và lớp bảo vệ duy nhất là hai trần
    # này (người dùng chốt KHÔNG nâng RAM). Nhưng bảng biến môi trường của nền tảng không trả
    # GIÁ TRỊ, chỉ trả tên biến — nên sau khi hạ trần thì không có cách nào kiểm chứng container
    # đang chạy thật sự đọc được số mới. Trường này nói đúng thứ tiến trình ĐANG dùng, và cũng
    # là tín hiệu tự chứng cho lượt deploy hạ trần.
    ket_qua["inpaint_tran_mpx"] = {
        "ca_trang": _s.inpaint_whole_page_max_mpx,
        "o_cat": _s.inpaint_max_crop_mpx,
    }

    duong_dan = _Path(os.environ.get("WORKER_STATE_FILE", "/tmp/trang-thai-worker.json"))
    try:
        ket_qua["worker"] = json.loads(duong_dan.read_text())
    except Exception:
        # Chạy ở máy nhà thì worker là container riêng, không có file này — không phải lỗi.
        ket_qua["worker"] = {"trang_thai": "khong_ro"}
    # HAI con số của HAI tiến trình, dán nhãn tách bạch.
    #
    # `rss_api_mb` là bộ nhớ của tiến trình đang phục vụ HTTP này. `worker.rss_mb` là của tiến
    # trình worker — thứ thật sự bị OOM killer giết. Trước P3m chỉ có một trường `rss_mb` (của
    # API) và ai nhìn cũng tưởng đó là số của worker: đúng về kỹ thuật, sai về câu hỏi.
    #
    # Giữ luôn `rss_mb` cũ trỏ vào số của API để không phá thứ đang đọc nó (API.md §healthz).
    ket_qua["rss_api_mb"] = ket_qua["rss_mb"] = rss_mb()
    try:
        moc = json.loads(_Path(os.environ.get("WORKER_RSS_FILE", "/tmp/rss-worker.json")).read_text())
        # Kèm `luc` để bên đọc tự đánh giá số này CŨ tới đâu — worker chết thì tệp đứng lại,
        # và một con số đứng yên trông y hệt một con số bình thường nếu không có mốc thời gian.
        ket_qua["worker"] = {**ket_qua["worker"], "rss_mb": moc.get("rss_mb"),
                             "rss_moc": moc.get("moc"), "rss_luc": moc.get("luc")}
    except Exception:
        # Worker chưa chạy bước nặng nào thì chưa có tệp — không phải lỗi, và KHÔNG bịa số 0.
        ket_qua["worker"] = {**ket_qua["worker"], "rss_mb": None}

    # E55 — trạng thái THỰC của worker, suy từ hai nguồn có hai người ghi khác nhau.
    #
    # Vấn đề: nhánh `ROLE=all` của `deploy-start.sh` ghi `starting` MỘT lần rồi chỉ ghi `restarting`
    # khi worker chết. Nên worker chạy tốt hai ngày vẫn báo `starting` — đo được 26-09: `starting`
    # suốt 42 giờ trong khi `rss_moc` chứng minh nó đã chạy xong một bước xoá chữ. Người vận hành
    # không phân biệt được "đang nạp model" với "chạy tốt hai ngày rồi".
    #
    # Shell KHÔNG có cách nào biết worker đã nạp xong model, nên dấu sẵn sàng do CHÍNH worker ghi
    # (`worker_ready_file`). Ở đây chỉ gộp lại, KHÔNG ghi gì — giữ luật một người ghi một tệp.
    #
    # Ba nhánh, thứ tự có ý nghĩa:
    #   1. shell nói `restarting` ⇒ tin shell. Nó vừa QUAN SÁT một lần thoát, đó là bằng chứng
    #      mạnh hơn một dấu sẵn sàng cũ từ lần chạy trước;
    #   2. có dấu sẵn sàng ⇒ `running`. Worker đã tự nói nó nhận được việc;
    #   3. còn lại ⇒ giữ nguyên thứ shell nói.
    #
    # Cố ý KHÔNG sửa trường `trang_thai` cũ: có thứ đang đọc nó (API.md §healthz). Thêm trường mới
    # và để trường cũ nói đúng thứ nó vẫn nói — shell nghĩ gì.
    try:
        san_sang = json.loads(
            _Path(os.environ.get("WORKER_READY_FILE", "/tmp/worker-ready.json")).read_text()
        ).get("san_sang_luc")
    except Exception:
        san_sang = None  # chưa có tệp = worker chưa báo sẵn sàng. KHÔNG đoán là đã sẵn sàng.

    tt_shell = ket_qua["worker"].get("trang_thai")
    ket_qua["worker"] = {
        **ket_qua["worker"],
        "san_sang_luc": san_sang,
        "trang_thai_thuc": (
            tt_shell if tt_shell == "restarting"
            else "running" if san_sang
            else tt_shell
        ),
    }
    return ket_qua


from fastapi.responses import HTMLResponse

_HTML_CHINH_SACH_BAO_MAT = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chính sách quyền riêng tư / Privacy Policy — Manga Translation Studio</title>
  <style>
    :root { --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8; --accent: #f97316; --border: #334155; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.65; padding: 32px 16px; }
    .container { max-width: 880px; margin: 0 auto; background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 32px; box-shadow: 0 20px 40px rgba(0,0,0,0.35); }
    .badge { display: inline-block; background: rgba(249,115,22,0.15); color: var(--accent); border: 1px solid rgba(249,115,22,0.4); padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; margin-bottom: 12px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    h2 { color: var(--accent); font-size: 20px; margin-top: 28px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
    p, li { color: #e2e8f0; font-size: 15px; }
    .muted { color: var(--muted); font-size: 14px; }
    .lang-box { background: rgba(15,23,42,0.55); border: 1px solid var(--border); border-radius: 12px; padding: 20px 24px; margin-top: 24px; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <span class="badge">Chrome Web Store &amp; Web Platform Privacy Policy</span>
    <h1>Chính Sách Quyền Riêng Tư / Privacy Policy</h1>
    <p class="muted">Cập nhật lần cuối / Last updated: 23/10/2026 — Áp dụng cho Website chính thức <strong><a href="https://comic.io.vn">https://comic.io.vn</a></strong> (và địa chỉ dự phòng <code>translation.vibe1.tinhgon.xyz</code>), Tiện ích Chrome <strong>Dịch truyện đang đọc (v0.3.0+)</strong> và Ứng dụng Windows.</p>

    <div class="lang-box">
      <h2>🇻🇳 Phiên bản Tiếng Việt (Vietnamese)</h2>
      <p><strong>1. Cam kết chung:</strong> Tiện ích mở rộng <em>"Dịch truyện đang đọc"</em> và nền tảng <em>Manga Translation Studio</em> chỉ xử lý dữ liệu khi người dùng chủ động yêu cầu dịch trang truyện hoặc văn bản đang đọc.</p>
      <ul>
        <li><strong>Dữ liệu thu thập và xử lý:</strong> Khi bạn bấm nút Dịch (hoặc bật chế độ tự dịch khi cuộn), tiện ích chỉ trích xuất hình ảnh khung truyện hoặc đoạn văn bản truyện trên tab hiện tại để gửi tới máy chủ API dịch thuật (<code>translation-api.vibe1.tinhgon.xyz</code>).</li>
        <li><strong>Lưu trữ cục bộ (Local Storage):</strong> Tiện ích sử dụng <code>chrome.storage.local</code> để lưu cấu hình của bạn (ngôn ngữ nguồn, ngôn ngữ đích, kiểu chữ, mã phiên đăng nhập nếu có).</li>
        <li><strong>Bộ nhớ đệm cộng đồng (Community Cache):</strong> Để tăng tốc độ dịch và tiết kiệm tài nguyên AI, hệ thống lưu trữ bản dịch theo chữ ký định danh một chiều ẩn danh của hình ảnh (+ ngôn ngữ đích), hoàn toàn không gắn với danh tính cá nhân hay lịch sử duyệt web của bạn.</li>
        <li><strong>Không theo dõi &amp; Không bán dữ liệu:</strong> Chúng tôi <strong>KHÔNG</strong> thu thập lịch sử duyệt web, không đọc mật khẩu/thông tin ngân hàng, không chèn quảng cáo và không bán hay chia sẻ dữ liệu người dùng cho bất kỳ bên thứ ba nào vì mục đích quảng cáo.</li>
      </ul>
    </div>

    <div class="lang-box">
      <h2>🇬🇧 English Version (For Chrome Web Store Compliance)</h2>
      <p><strong>1. Core Privacy Principle:</strong> The <em>"Dịch truyện đang đọc" (Manga Translation Studio)</em> Chrome Extension and Web Platform only process data when explicitly triggered by the user to translate comic images or web novel text.</p>
      <ul>
        <li><strong>Data Processed:</strong> When you click Translate (or enable Auto-Translate on scroll), the extension captures only the comic image or story text on the active tab and transmits it securely over HTTPS to our translation server (<code>translation-api.vibe1.tinhgon.xyz</code>) to perform OCR, inpainting, and translation.</li>
        <li><strong>Local Preferences:</strong> We use <code>chrome.storage.local</code> solely to store your user preferences (source language, target language, font style, and optional session token).</li>
        <li><strong>Anonymous Community Cache:</strong> Translated text regions may be cached using an anonymous one-way cryptographic image fingerprint (+ target language) to provide instant translations for subsequent readers. No personal identifiers or browsing URLs are attached to this cache.</li>
        <li><strong>No Tracking or Data Selling:</strong> We do <strong>NOT</strong> collect general browsing history, personal credentials, or payment details. We never sell, rent, or transfer user data to third parties for advertising or analytics.</li>
      </ul>
    </div>
  </div>
</body>
</html>"""


@app.get("/privacy-policy", response_class=HTMLResponse, tags=["ops"])
@app.get("/api/v1/privacy-policy", response_class=HTMLResponse, tags=["ops"])
async def privacy_policy() -> HTMLResponse:
    """Trang Chính sách quyền riêng tư song ngữ Việt - Anh chuẩn Chrome Web Store."""
    return HTMLResponse(content=_HTML_CHINH_SACH_BAO_MAT, status_code=200)


# Router tài khoản KHÔNG đòi đăng nhập (đăng nhập thì lấy đâu ra phiên mà gửi). Riêng
# `/auth/register` tự đòi khoá chung bên trong, để người lạ không tự tạo tài khoản.
app.include_router(xac_thuc_router, prefix="/api/v1")

# Gắn cổng ĐĂNG NHẬP ở tầng ROUTER, không gắn từng endpoint: 65 đường dẫn thì kiểu gì cũng
# quên một cái, và cái bị quên sẽ là cái không ai ngờ tới.
#
# Đây là chỗ slice B thay slice A: trước là một khoá chung (ai cầm khoá làm được mọi thứ với
# chapter của mọi người), giờ là tài khoản riêng + chapter có chủ. Khoá chung KHÔNG còn mở
# được dữ liệu nữa — nó chỉ còn gác cổng đăng ký.
app.include_router(v1_router, dependencies=[Depends(nguoi_dung_hien_tai)])
# E73 — đăng nhập ChatGPT kiểu Codex. Tự trả 404 khi không phải bản cài cục bộ; chỉ quản trị.
app.include_router(codex_router, prefix="/api/v1", dependencies=[Depends(nguoi_dung_hien_tai)])

# E49 — router KHÁCH LẠ: cố ý KHÔNG có `Depends(nguoi_dung_hien_tai)`.
#
# Đây là chỗ duy nhất trong hệ thống mở cho người chưa đăng nhập ngoài `/auth/*`, nên nó phải
# đứng tách ra và nhìn thấy được ngay. Mặc định vẫn là ĐÓNG: endpoint nào không được chuyển
# sang `router_khach` thì vẫn nằm sau cổng đăng nhập ở trên.
#
# Đổi lại, khách lạ bị chặn bằng HẠN MỨC (cookie + IP) chứ không phải bằng đăng nhập —
# xem `core/cong_han_muc.py`.
@app.middleware("http")
async def _cors_developer_api(request: Request, call_next):
    """Mở CORS cho các đường dẫn `/api/v1/developer/*` để website / tool của khách hàng từ mọi
    tên miền đều gọi kéo dữ liệu về được bằng `X-Customer-Api-Key` mà không bị trình duyệt chặn."""
    if request.url.path.startswith("/api/v1/developer"):
        if request.method == "OPTIONS":
            from fastapi.responses import Response as _Resp

            return _Resp(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Customer-Api-Key, X-API-Key",
                    "Access-Control-Max-Age": "86400",
                },
            )
        resp = await call_next(request)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Customer-Api-Key, X-API-Key"
        )
        return resp
    return await call_next(request)


_CHUOI_BOT_DO_QUET_CAM = (
    "sqlmap",
    "nikto",
    "nmap",
    "nuclei",
    "masscan",
    "zgrab",
    "gobuster",
    "dirbuster",
    "wfuzz",
    "ffuf",
    "scrapy",
    "phantomjs",
    "headlesschrome",
    "puppeteer",
    "playwright",
    "selenium",
    "acunetix",
    "nessus",
    "openvas",
)


@app.middleware("http")
async def _header_bao_mat(request: Request, call_next):
    """Header bảo mật và tường lửa chống bot dò quét tự động cho mọi phản hồi của API."""
    ua = (request.headers.get("user-agent") or "").lower()
    if ua and any(bot in ua for bot in _CHUOI_BOT_DO_QUET_CAM):
        from fastapi.responses import JSONResponse as _JSONResp

        return _JSONResp(
            status_code=403,
            content={
                "error": "automated_scanner_blocked",
                "detail": "Hệ thống bảo vệ đã chặn truy cập tự động từ công cụ dò quét.",
            },
        )
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Robots-Tag", "noindex, noarchive, nosnippet")
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


app.include_router(v1_router_khach)
app.include_router(developer_router)

canh_bao_neu_khong_khoa()
