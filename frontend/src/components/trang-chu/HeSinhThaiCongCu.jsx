import { useState } from 'react'
import * as api from '../../api'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'

/**
 * E107 — Khối Hệ sinh thái Công cụ Dịch Truyện (Tiện ích Chrome & App Windows)
 * Thiết kế theo phong cách Khung Tranh Truyện Tranh (Manga/Manhwa Panel Aesthetic).
 */
export default function HeSinhThaiCongCu() {
  const [moHuongDanExt, setMoHuongDanExt] = useState(false)
  const [moHuongDanWin, setMoHuongDanWin] = useState(false)
  const [moTaiLieuApi, setMoTaiLieuApi] = useState(false)
  const [tabCode, setTabCode] = useState('python')
  const { laEn } = useNgonNguUI()
  const apiOrigin = api.API_BASE || 'https://translation-api.vibe1.tinhgon.xyz'

  return (
    <section className="manga-ecosystem" aria-labelledby="tieu-de-he-sinh-thai">
      <div className="manga-ecosystem-dau">
        <span className="manga-sfx-badge">
          {laEn ? '★ ALL-IN-ONE MANGA & WEBTOON TRANSLATION SUITE ★' : '★ BỘ CÔNG CỤ ĐỌC & DỊCH TRUYỆN TOÀN DIỆN ★'}
        </span>
        <h2 id="tieu-de-he-sinh-thai">
          {laEn ? 'Bring the Comic World to Every Platform' : 'Đem Thế Giới Truyện Tranh Lên Mọi Nền Tảng'}
        </h2>
        <p className="dan">
          {laEn ? (
            <>Share one single VIP account across <b>Web</b>, <b>Chrome Extension</b>, and <b>Windows App</b>.</>
          ) : (
            <>Dùng chung một tài khoản VIP duy nhất trên cả <b>Web</b>, <b>Tiện ích Chrome</b> và <b>App Windows</b>.</>
          )}
        </p>
      </div>

      <div className="luoi-cong-cu-manga">
        {/* Khung tranh 1: Tiện ích mở rộng Chrome */}
        <article className="khung-tranh-cong-cu panel-ext">
          <div className="bong-thoai-goc">{laEn ? '💬 Read & Translate Live!' : '💬 Đọc tới đâu dịch tới đó!'}</div>
          <div className="dau-khung-cong-cu">
            <span className="icon-cong-cu" aria-hidden="true">🧩</span>
            <div>
              <span className="nhan-phien-ban">{laEn ? 'VERSION v0.3.0 · CHROME / EDGE / BRAVE' : 'PHIÊN BẢN v0.3.0 · CHROME / EDGE / BRAVE'}</span>
              <h3>{laEn ? 'Live Browser Comic & Novel Translator' : 'Tiện Ích Dịch Truyện Trực Tiếp Trên Web'}</h3>
            </div>
          </div>

          <p className="mo-ta-cong-cu">
            {laEn
              ? 'Translate directly on any Manga, Manhwa, Manhua, Webtoon, or Web Novel site — even sites that block right-click or image hotlinking.'
              : 'Dịch trực tiếp trên mọi trang đọc Manga, Manhwa, Manhua, Webtoon và Truyện chữ — vượt qua cả các trang chặn chuột phải hoặc chống tải ảnh.'}
          </p>

          <ul className="ds-tinh-nang-cong-cu">
            <li>
              {laEn ? (
                <>⚡ <b>Client GPU/Canvas 2D Inpainting:</b> Clean 100% original text while preserving bubble borders in 2–4s.</>
              ) : (
                <>⚡ <b>Xoá chữ 2D trên GPU/Canvas máy khách:</b> Sạch 100% chữ gốc, giữ nguyên viền cong bong bóng chỉ trong 2–4 giây.</>
              )}
            </li>
            <li>
              {laEn ? (
                <>🛡️ <b>Anti-Block &amp; Canvas/Novel Bypass:</b> Works on protected comic sites, Canvas readers, and Light Novel text pages.</>
              ) : (
                <>🛡️ <b>Vượt mọi trang chặn dịch:</b> Xử lý cả ảnh chống Hotlink, trang vẽ bằng thẻ Canvas và trang Truyện chữ (Web Novel).</>
              )}
            </li>
            <li>
              {laEn ? (
                <>✏️ <b>Double-Click Bubble Editor:</b> Edit translations, resize text, or re-translate with AI right on the page.</>
              ) : (
                <>✏️ <b>Nhấp đúp sửa bóng thoại tức thì:</b> Sửa câu dịch, phóng to/thu nhỏ chữ hoặc gọi AI dịch lại ngay trên trang.</>
              )}
            </li>
            <li>
              {laEn ? (
                <>🌍 <b>Multi-Target &amp; Genre Fonts:</b> Translate to 🇻🇳 Vietnamese &amp; 🇬🇧 English with 4 genre fonts.</>
              ) : (
                <>🌍 <b>Đa ngôn ngữ &amp; 4 Bộ Font thể loại:</b> Dịch sang 🇻🇳 Tiếng Việt &amp; 🇬🇧 Tiếng Anh Quốc tế.</>
              )}
            </li>
          </ul>

          <div className="chan-khung-cong-cu">
            <a
              href={api.urlTaiTienIchChrome()}
              download="dich-truyen-chrome-extension-v0.3.0.zip"
              className="nut-manga nut-manga-chinh"
            >
              {laEn ? '⬇️ Download Chrome Extension (.ZIP)' : '⬇️ Tải Tiện Ích Chrome (.ZIP)'}
            </a>
            <button
              type="button"
              className="nut-manga nut-manga-phu"
              onClick={() => setMoHuongDanExt((v) => !v)}
            >
              {moHuongDanExt
                ? (laEn ? '▲ Hide guide' : '▲ Ẩn cách cài')
                : (laEn ? '📖 Install in 10 seconds' : '📖 Cách cài trong 10 giây')}
            </button>
          </div>

          {moHuongDanExt && (
            <div className="hop-huong-dan-nhanh">
              <b>{laEn ? 'How to install on Chrome / Edge / Brave:' : 'Cách cài đặt vào Chrome / Edge / Cốc Cốc:'}</b>
              <ol>
                <li>{laEn ? <>Unzip <code>dich-truyen-chrome-extension-v0.3.0.zip</code>.</> : <>Giải nén file <code>dich-truyen-chrome-extension-v0.3.0.zip</code> vừa tải về.</>}</li>
                <li>{laEn ? <>Open <code>chrome://extensions</code> and enable <b>Developer mode</b> at the top right.</> : <>Mở trình duyệt, gõ <code>chrome://extensions</code> và bật công tắc <b>Chế độ nhà phát triển (Developer mode)</b> ở góc phải trên.</>}</li>
                <li>{laEn ? <>Click <b>Load unpacked</b> and select the unzipped folder!</> : <>Bấm <b>Tải tiện ích đã giải nén (Load unpacked)</b> và chọn thư mục vừa giải nén là xong!</>}</li>
              </ol>
            </div>
          )}
        </article>

        {/* Khung tranh 2: App Windows Tự động dịch theo Link & Chia Chapter */}
        <article className="khung-tranh-cong-cu panel-win">
          <div className="bong-thoai-goc bong-thoai-vang">{laEn ? '🚀 Batch 100 Chapters!' : '🚀 Cày 100 Chapter tự động!'}</div>
          <div className="dau-khung-cong-cu">
            <span className="icon-cong-cu" aria-hidden="true">🖥️</span>
            <div>
              <span className="nhan-phien-ban nhan-win">WINDOWS 10 / 11 DESKTOP APP · v1.0</span>
              <h3>{laEn ? 'Windows App: Auto-Crawl URL & Split Chapters' : 'App Windows: Dịch Theo Link & Chia Thư Mục Chapter'}</h3>
            </div>
          </div>

          <p className="mo-ta-cong-cu">
            {laEn
              ? 'Built for Scanlation teams, Comic admins, and Recap creators: paste a series URL to auto-download, translate, and organize chapter folders.'
              : 'Công cụ chuyên dụng cho Nhóm dịch, Chủ web truyện và Người làm video Recap: dán Link là tự tải, dịch và chia thư mục.'}
          </p>

          <ul className="ds-tinh-nang-cong-cu">
            <li>
              {laEn ? (
                <>🔗 <b>Auto Chapter Scanner:</b> Paste 1 series URL → Select auto-translation from <b>Chapter A to Chapter B</b>.</>
              ) : (
                <>🔗 <b>Quét tự động danh sách Chapter:</b> Dán 1 Link bộ truyện → Chọn dịch tự động từ <b>Chapter A đến Chapter B</b>.</>
              )}
            </li>
            <li>
              {laEn ? (
                <>📁 <b>Clean Folder Structure:</b> Automatically saves as <code>Series_Name / Chapter-001 / 001.jpg, 002.jpg...</code></>
              ) : (
                <>📁 <b>Chia sẵn thư mục chuẩn chỉnh:</b> Tự động lưu thành <code>Tên_Truyện / Chapter-001 / 001.jpg, 002.jpg...</code></>
              )}
            </li>
            <li>
              {laEn ? (
                <>🖥️ <b>PC Hardware ID &amp; Quota Sync:</b> Confirms your PC ID and displays remaining daily + VIP pages in real time.</>
              ) : (
                <>🖥️ <b>Xác nhận Mã máy tính &amp; Lượt dịch:</b> Gắn mã máy bảo mật và kiểm tra trực tiếp số lượt còn lại của tài khoản.</>
              )}
            </li>
            <li>
              {laEn ? (
                <>📦 <b>Flexible Export:</b> Outputs high-res image folders and <code>.CBZ</code> archives for Mihon/Tachiyomi.</>
              ) : (
                <>📦 <b>Đóng gói linh hoạt:</b> Xuất cả thư mục ảnh rời chất lượng cao lẫn gói <code>.CBZ</code> đọc trên Mihon/Tachiyomi.</>
              )}
            </li>
          </ul>

          <div className="chan-khung-cong-cu">
            <a
              href={api.urlTaiAppWindows()}
              download="App-Windows-Dich-Truyen-Tu-Dong-v1.0.zip"
              className="nut-manga nut-manga-win"
            >
              {laEn ? '⬇️ Download Windows App (.ZIP)' : '⬇️ Tải App Windows (.ZIP)'}
            </a>
            <button
              type="button"
              className="nut-manga nut-manga-phu"
              onClick={() => setMoHuongDanWin((v) => !v)}
            >
              {moHuongDanWin
                ? (laEn ? '▲ Hide guide' : '▲ Ẩn hướng dẫn')
                : (laEn ? '📖 How to run on Windows' : '📖 Cách chạy trên Windows')}
            </button>
          </div>

          {moHuongDanWin && (
            <div className="hop-huong-dan-nhanh">
              <b>{laEn ? 'How to launch on Windows 10/11:' : 'Cách mở App trên máy tính Windows:'}</b>
              <ol>
                <li>{laEn ? <>Unzip <code>App-Windows-Dich-Truyen-Tu-Dong-v1.0.zip</code> on your PC.</> : <>Giải nén file <code>App-Windows-Dich-Truyen-Tu-Dong-v1.0.zip</code> ra máy tính.</>}</li>
                <li>{laEn ? <>Double-click <code>Chay-App-Dich-Truyen-Windows.bat</code> to open the Manga Studio GUI.</> : <>Nhấp đúp chuột vào file <code>Chay-App-Dich-Truyen-Windows.bat</code> để mở giao diện Manga Studio.</>}</li>
                <li>{laEn ? <>Verify your PC ID / VIP token, paste the comic URL, select chapters, and click <b>Start</b>!</> : <>Xác nhận Mã máy tính / tài khoản VIP, dán Link truyện, chọn Chapter muốn dịch và bấm <b>Bắt đầu</b>!</>}</li>
              </ol>
            </div>
          )}
        </article>
      </div>

      {/* Khung tranh 3 (Full-width): Cổng Developer REST API cho Tool & Web Khách Hàng Kéo Về */}
      <article
        className="khung-tranh-cong-cu"
        style={{
          marginTop: 22,
          border: '2px solid rgba(56, 189, 248, 0.45)',
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.92))',
        }}
      >
        <div className="bong-thoai-goc" style={{ background: '#0284c7', color: '#fff' }}>
          {laEn ? '🔌 B2B / Developer API Ready!' : '🔌 Đấu nối API vào Tool của bạn!'}
        </div>
        <div className="dau-khung-cong-cu">
          <span className="icon-cong-cu" aria-hidden="true">⚡</span>
          <div>
            <span className="nhan-phien-ban" style={{ color: '#38bdf8' }}>
              {laEn
                ? 'DEVELOPER REST API · API KEY (tr_live_...) · JSON + RENDERED PNG'
                : 'CỔNG DEVELOPER REST API · KHOÁ API RIÊNG (tr_live_...) · KÉO ẢNH & JSON TỰ ĐỘNG'}
            </span>
            <h3 style={{ color: '#f8fafc' }}>
              {laEn
                ? 'Customer Tool & Third-Party Website Integration API'
                : 'API Cho Tool Khách Hàng, Web Truyện & Bot Tự Động Kéo Về'}
            </h3>
          </div>
        </div>

        <p className="mo-ta-cong-cu" style={{ color: '#cbd5e1' }}>
          {laEn
            ? 'Building your own comic reader website, WordPress plugin, auto-crawler, or Discord bot? Generate a personal API Key (tr_live_...) in your Account menu and pull translated images + bubble coordinates in a single HTTP call.'
            : 'Bạn có website đọc truyện riêng, plugin WordPress/Madara, tool auto-leech hoặc bot Discord/Telegram? Chỉ cần tạo mã API Key (tr_live_...) trong mục Tài khoản để tool của bạn tự động đẩy ảnh/link lên dịch và kéo ảnh đã ghép chữ hoàn chỉnh về!'}
        </p>

        <ul className="ds-tinh-nang-cong-cu" style={{ color: '#e2e8f0' }}>
          <li>
            {laEn ? (
              <>🔑 <b>Personal API Key (<code>tr_live_...</code>):</b> Never expires after 14 days, revocable anytime, deducts directly from your account quota.</>
            ) : (
              <>🔑 <b>Khoá API cố định (<code>tr_live_...</code>):</b> Không lo hết hạn phiên 14 ngày, tạo/đổi key 1 chạm trong mục <b>Tài khoản</b>, trừ trực tiếp vào số dư lượt của bạn.</>
            )}
          </li>
          <li>
            {laEn ? (
              <>🖼️ <b>1-Call All-in-One Endpoint (<code>POST /api/v1/developer/translate-image</code>):</b> Send an image file or <code>image_url</code> and receive both <code>rendered_image_url</code> (typeset PNG), <code>inpainted_image_url</code>, and full bubble JSON.</>
            ) : (
              <>🖼️ <b>Gọi 1 lệnh lấy trọn bộ (<code>POST /api/v1/developer/translate-image</code>):</b> Gửi file ảnh hoặc <code>image_url</code>, nhận về ngay link tải <b>Ảnh đã ghép chữ hoàn chỉnh</b> + <b>Ảnh đã xoá chữ</b> + <b>JSON toạ độ khung thoại</b>.</>
            )}
          </li>
          <li>
            {laEn ? (
              <>⚡ <b>0.15s SHA-256 Community Cache:</b> Instant response when pulling pages already translated on the network.</>
            ) : (
              <>⚡ <b>Tích hợp Bảng Cache Cộng Đồng SHA-256:</b> Trả kết quả tức thì trong 0.15 giây nếu trang truyện đã từng được dịch trên hệ thống.</>
            )}
          </li>
        </ul>

        <div className="chan-khung-cong-cu">
          <button
            type="button"
            className="nut-manga nut-manga-chinh"
            onClick={() => setMoTaiLieuApi((v) => !v)}
          >
            {moTaiLieuApi
              ? (laEn ? '▲ Hide API Code Examples' : '▲ Ẩn tài liệu & Code mẫu API')
              : (laEn ? '💻 View API Docs & Code Examples' : '💻 Xem Tài Liệu & Code Mẫu Đấu Nối API')}
          </button>
          <a
            href={`${apiOrigin}/docs`}
            target="_blank"
            rel="noreferrer"
            className="nut-manga nut-manga-phu"
          >
            {laEn ? '📘 Open Swagger OpenAPI (/docs) ↗' : '📘 Mở Swagger OpenAPI (/docs) ↗'}
          </a>
        </div>

        {moTaiLieuApi && (
          <div className="hop-huong-dan-nhanh" style={{ marginTop: 14, background: '#090d16', color: '#e2e8f0', border: '1px solid #334155' }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
              {[
                { id: 'python', label: '🐍 Python (Tool / Crawler)' },
                { id: 'nodejs', label: '🟢 Node.js / JS (Web / Bot)' },
                { id: 'curl', label: '💻 cURL / PHP' },
                { id: 'json', label: '📦 JSON Kết quả trả về' },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTabCode(t.id)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: 8,
                    border: tabCode === t.id ? '1px solid #38bdf8' : '1px solid #334155',
                    background: tabCode === t.id ? 'rgba(56, 189, 248, 0.18)' : '#1e293b',
                    color: '#f8fafc',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: 12.5,
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {tabCode === 'python' && (
              <pre style={{ margin: 0, padding: 12, background: '#020617', borderRadius: 8, overflowX: 'auto', fontSize: 12.5 }}>{`import requests

API_KEY = "tr_live_YOUR_API_KEY"  # Lấy trong mục Tài khoản trên Website
ENDPOINT = "${apiOrigin}/api/v1/developer/translate-image"

# Cách 1: Truyền thẳng link ảnh từ web gốc (hệ thống tự vượt chống hotlink)
res = requests.post(
    ENDPOINT,
    headers={"X-Customer-Api-Key": API_KEY},
    data={
        "image_url": "https://uploads.mangadex.org/data/.../page1.jpg",
        "source_lang": "ja",      # ja | ko | zh | en
        "target_lang": "vi",      # vi (Tiếng Việt) | en (Tiếng Anh)
        "engine": "llm_context",  # google_fast | llm_context
        "mode": "day_du",         # day_du = ghép sẵn chữ vào ảnh | chi_chu = chỉ lấy JSON
        "wait": "true"
    }
).json()

# Tải ảnh đã dịch hoàn chỉnh về máy chủ của bạn:
if res.get("rendered_image_url"):
    img_bytes = requests.get(res["rendered_image_url"]).content
    open("trang_da_dich.png", "wb").write(img_bytes)`}</pre>
            )}

            {tabCode === 'nodejs' && (
              <pre style={{ margin: 0, padding: 12, background: '#020617', borderRadius: 8, overflowX: 'auto', fontSize: 12.5 }}>{`const form = new FormData();
form.append("image_url", "https://example.com/raw-chapter/01.jpg");
form.append("source_lang", "ko");
form.append("target_lang", "vi");
form.append("engine", "llm_context");
form.append("mode", "day_du");
form.append("wait", "true");

const res = await fetch("${apiOrigin}/api/v1/developer/translate-image", {
  method: "POST",
  headers: { "X-Customer-Api-Key": "tr_live_YOUR_API_KEY" },
  body: form,
});
const data = await res.json();
console.log("Ảnh đã dịch:", data.rendered_image_url);
console.log("Danh sách bóng thoại:", data.regions);`}</pre>
            )}

            {tabCode === 'curl' && (
              <pre style={{ margin: 0, padding: 12, background: '#020617', borderRadius: 8, overflowX: 'auto', fontSize: 12.5 }}>{`# 1. Dịch ảnh từ file trên máy hoặc link URL:
curl -X POST "${apiOrigin}/api/v1/developer/translate-image" \\
  -H "X-Customer-Api-Key: tr_live_YOUR_API_KEY" \\
  -F "file=@./page01.jpg" \\
  -F "source_lang=ja" \\
  -F "target_lang=vi" \\
  -F "engine=llm_context" \\
  -F "mode=day_du" \\
  -F "wait=true"

# 2. Dịch chương truyện chữ (Web Novel / Light Novel):
curl -X POST "${apiOrigin}/api/v1/developer/translate-text" \\
  -H "X-Customer-Api-Key: tr_live_YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"texts": ["第1話：始まり", "彼は静かに立ち上がった。"], "source_lang": "ja", "target_lang": "vi", "engine": "llm_context"}'`}</pre>
            )}

            {tabCode === 'json' && (
              <pre style={{ margin: 0, padding: 12, background: '#020617', borderRadius: 8, overflowX: 'auto', fontSize: 12.5 }}>{`{
  "status": "completed",
  "completed": true,
  "cached": false,
  "page_id": "6f9c2a10-...",
  "source_lang": "ja",
  "target_lang": "vi",
  "mode": "day_du",
  "rendered_image_url": "${apiOrigin}/api/v1/developer/pages/6f9c2a10-.../rendered-image?api_key=tr_live_...",
  "inpainted_image_url": "${apiOrigin}/api/v1/developer/pages/6f9c2a10-.../inpainted-image?api_key=tr_live_...",
  "regions_count": 2,
  "regions": [
    {
      "order": 1,
      "bbox": { "x": 118.0, "y": 42.0, "w": 164.0, "h": 210.0 },
      "source_text": "いくぞ！",
      "translated_text": "Lên đường thôi!",
      "font_size": 24.0,
      "text_color": "#111827",
      "stroke_color": "#FFFFFF"
    }
  ],
  "quota": {
    "daily_remaining": 9,
    "purchased_remaining": 500,
    "total_usable_pages": 509
  }
}`}</pre>
            )}
          </div>
        )}
      </article>
    </section>
  )
}
