import { useEffect, useState } from 'react'
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
  const [thongTinNap, setThongTinNap] = useState(null)
  const [goiChonQr, setGoiChonQr] = useState(null)
  const { laEn } = useNgonNguUI()
  const apiOrigin = api.API_BASE || 'https://translation-api.vibe1.tinhgon.xyz'
  const donGia = thongTinNap?.ty_le_vnd_moi_trang || 500

  useEffect(() => {
    let huy = false
    api.layThongTinNapLuot()
      .then((tt) => { if (!huy) setThongTinNap(tt) })
      .catch(() => {})
    return () => { huy = true }
  }, [])

  function chonGoiDoanhNghiep(goiTinh) {
    setGoiChonQr(goiTinh)
  }

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
              <span className="nhan-phien-ban">{laEn ? 'VERSION v0.3.1 · CHROME / EDGE / BRAVE' : 'PHIÊN BẢN v0.3.1 · CHROME / EDGE / BRAVE'}</span>
              <h3>{laEn ? 'Live Browser Comic & Novel Translator' : 'Tiện Ích Dịch Truyện Trực Tiếp Trên Web'}</h3>
            </div>
          </div>

          <p className="mo-ta-cong-cu">
            {laEn
              ? 'Translate directly on the Manga, Manhwa, Manhua, Webtoon, and Web Novel pages you are reading — for personal reading only.'
              : 'Dịch trực tiếp trên trang Manga, Manhwa, Manhua, Webtoon và Truyện chữ bạn đang đọc — dùng cho việc đọc cá nhân.'}
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
                <>📖 <b>Comics &amp; Web Novels:</b> Works on image-based comic readers and Light Novel text pages.</>
              ) : (
                <>📖 <b>Truyện tranh &amp; Truyện chữ:</b> Dùng được trên trang đọc truyện tranh dạng ảnh và trang Truyện chữ (Web Novel).</>
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
              download="dich-truyen-chrome-extension-v0.3.1.zip"
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
                <li>{laEn ? <>Unzip <code>dich-truyen-chrome-extension-v0.3.1.zip</code>.</> : <>Giải nén file <code>dich-truyen-chrome-extension-v0.3.1.zip</code> vừa tải về.</>}</li>
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
              <span className="nhan-phien-ban nhan-win">WINDOWS 10 / 11 DESKTOP APP · v1.1</span>
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
              download="App-Windows-Dich-Truyen-Tu-Dong-v1.1.zip"
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
                <li>{laEn ? <>Unzip <code>App-Windows-Dich-Truyen-Tu-Dong-v1.1.zip</code> on your PC.</> : <>Giải nén file <code>App-Windows-Dich-Truyen-Tu-Dong-v1.1.zip</code> ra máy tính.</>}</li>
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
            href="#ket-noi-api"
            className="nut-manga nut-manga-phu"
          >
            {laEn ? '📘 Full API Integration Guide ↗' : '📘 Xem Hướng Dẫn Đấu Nối API Chi Tiết ↗'}
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
    open("trang_da_dich.png", "wb").write(img_bytes)

# Cách 2: Đẩy nguyên 1 Chapter (danh sách nhiều URL ảnh) chỉ với 1 lệnh gọi:
chap = requests.post(
    "${apiOrigin}/api/v1/developer/translate-chapter",
    headers={"X-Customer-Api-Key": API_KEY},
    json={
        "chapter_name": "One Piece - Chap 1120",
        "image_urls": ["https://.../01.jpg", "https://.../02.jpg"],
        "source_lang": "ja",
        "target_lang": "vi",
        "engine": "llm_context",
        "mode": "day_du"
    }
).json()
print("Link theo dõi & kéo cả chapter:", chap["poll_chapter_url"])`}</pre>
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

      {/* Khối 4: Bảng Gói Cước Cá Nhân, Nhóm Dịch & Doanh Nghiệp (tạm ẩn theo yêu cầu) */}
      {false && (
      <div style={{ marginTop: 28 }}>
        <div className="manga-ecosystem-dau" style={{ marginBottom: 16 }}>
          <span className="manga-sfx-badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#10b981', borderColor: 'rgba(16, 185, 129, 0.4)' }}>
            {laEn ? '💎 FLEXIBLE QUOTA & B2B ENTERPRISE PLANS' : '💎 BẢNG GÓI CƯỚC CÁ NHÂN, STUDIO & DOANH NGHIỆP (API)'}
          </span>
          <h3 style={{ fontSize: 22, margin: '8px 0 4px' }}>
            {laEn
              ? 'Pay-As-You-Go Quota (Never Expires) & Enterprise API Tiers'
              : 'Lượt Mua Tích Luỹ Không Bao Giờ Hết Hạn — Dùng Chung Web, App & Cổng API'}
          </h3>
          <p className="dan" style={{ fontSize: 14 }}>
            {laEn
              ? '100% automatic 24/7 VietQR top-up. Higher tiers include up to +40% bonus pages and full Developer API access.'
              : 'Nạp tự động 24/7 qua mã VietQR. Gói Doanh nghiệp tặng thêm tới +40% số trang và mở toàn bộ Cổng Developer API (tr_live_...).'}
          </p>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 14,
        }}>
          {[
            {
              ma: 'tieu_chuan',
              nhan: laEn ? 'READER VIP' : 'CÁ NHÂN / VIP',
              ten: laEn ? '550 Pages (+10% Bonus)' : 'Gói Cày Truyện (550 trang)',
              giaVnd: 500 * donGia,
              soTrang: '550 trang (~28 chap)',
              diemManh: laEn
                ? ['+10% bonus pages included', 'Sync Web + Chrome Extension', 'Quota never expires overnight']
                : ['Tặng thêm +10% số trang', 'Dùng trên Web + Tiện ích Chrome', 'Lượt mua không hết hạn qua đêm'],
              noiBat: false,
            },
            {
              ma: 'nhom_dich',
              nhan: laEn ? 'SCANLATION STUDIO' : 'NHÓM DỊCH / STUDIO',
              ten: laEn ? '1,200 Pages (+20% Bonus)' : 'Gói Studio (1.200 trang)',
              giaVnd: 1000 * donGia,
              soTrang: '1.200 trang (~60 chap)',
              diemManh: laEn
                ? ['+20% bonus pages included', 'Windows Batch App + Zip/CBZ/PDF', 'Custom Character Glossary']
                : ['Tặng thêm +20% số trang', 'Mở App Windows cày link tự động', 'Sổ tay nhân vật & Xuất CBZ/ZIP/PDF'],
              noiBat: false,
            },
            {
              ma: 'doanh_nghiep_api',
              nhan: laEn ? '🏢 BUSINESS API PRO' : '🏢 DOANH NGHIỆP / WEB API PRO',
              ten: laEn ? '6,500 Pages (+30% Bonus)' : 'Gói Doanh Nghiệp API (6.500 trang)',
              giaVnd: 5000 * donGia,
              soTrang: '6.500 trang (~325 chap)',
              diemManh: laEn
                ? ['+30% bonus pages', 'Full Developer API Key (tr_live_...)', 'Batch Chapter URL endpoint + Anti-Hotlink']
                : ['Tặng thêm +30% số trang', 'Cấp Khoá Developer API (tr_live_...)', 'Đẩy cả Chapter qua URL + Vượt Hotlink'],
              noiBat: true,
            },
            {
              ma: 'enterprise_scale',
              nhan: laEn ? '🏛️ ENTERPRISE SCALE' : '🏛️ HỆ THỐNG CỔNG TRUYỆN LỚN',
              ten: laEn ? '28,000 Pages (+40% Bonus)' : 'Gói Enterprise (28.000 trang)',
              giaVnd: 20000 * donGia,
              soTrang: '28.000 trang (~1.400 chap)',
              diemManh: laEn
                ? ['+40% bonus pages', 'High-concurrency Worker + SHA-256 Cache', '24/7 Automated Tool & CMS Integration']
                : ['Tặng thêm +40% số trang', 'Luồng Worker đa nhân + Cache SHA-256', 'Đấu nối không giới hạn vào CMS / Web truyện'],
              noiBat: true,
            },
          ].map((g) => (
            <div
              key={g.ma}
              style={{
                borderRadius: 14,
                padding: '18px 16px',
                background: g.noiBat
                  ? 'linear-gradient(160deg, rgba(15, 23, 42, 0.96), rgba(30, 58, 138, 0.88))'
                  : 'var(--nen-the, rgba(15, 23, 42, 0.78))',
                border: g.noiBat ? '2px solid #f97316' : '1px solid var(--vien, #334155)',
                color: '#f8fafc',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <span style={{
                  display: 'inline-block',
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '3px 9px',
                  borderRadius: 999,
                  background: g.noiBat ? 'rgba(249, 115, 22, 0.2)' : 'rgba(148, 163, 184, 0.15)',
                  color: g.noiBat ? '#fb923c' : '#cbd5e1',
                  marginBottom: 8,
                }}>
                  {g.nhan}
                </span>
                <h4 style={{ margin: '0 0 6px', fontSize: 16, color: '#fff' }}>{g.ten}</h4>
                <div style={{ fontSize: 21, fontWeight: 800, color: '#38bdf8', marginBottom: 4 }}>
                  {g.giaVnd.toLocaleString('vi-VN')}đ
                </div>
                <div style={{ fontSize: 12.5, color: '#94a3b8', marginBottom: 12 }}>
                  ⚡ {g.soTrang}
                </div>
                <ul style={{ margin: '0 0 14px', paddingLeft: 18, fontSize: 13, lineHeight: 1.6, color: '#e2e8f0' }}>
                  {g.diemManh.map((dm, idx) => (
                    <li key={idx}>{dm}</li>
                  ))}
                </ul>
              </div>
              <button
                type="button"
                className={g.noiBat ? 'nut-manga nut-manga-chinh' : 'nut-manga nut-manga-phu'}
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => chonGoiDoanhNghiep(g)}
              >
                {laEn ? '💳 Get VietQR Code' : '💳 Chọn Gói & Lấy Mã QR'}
              </button>
            </div>
          ))}
        </div>

        {goiChonQr && (
          <div style={{
            marginTop: 16,
            padding: 18,
            borderRadius: 14,
            background: 'rgba(15, 23, 42, 0.95)',
            border: '2px solid #10b981',
            color: '#f8fafc',
            display: 'flex',
            flexWrap: 'wrap',
            gap: 20,
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ color: '#10b981', fontWeight: 700, fontSize: 14, marginBottom: 4 }}>
                ✅ {laEn ? 'Selected Package:' : 'Đang chọn gói nạp tự động 24/7:'} {goiChonQr.ten}
              </div>
              <p style={{ margin: '0 0 8px', fontSize: 13.5, color: '#cbd5e1' }}>
                {laEn
                  ? 'Scan the VietQR code with your banking app. Your pages are credited automatically within 5–15 seconds after transfer!'
                  : 'Quét mã VietQR bên cạnh bằng ứng dụng Ngân hàng. Hệ thống Webhook sẽ tự động cộng ngay số trang (kèm % khuyến mãi) vào tài khoản của bạn sau 5–15 giây!'}
              </p>
              <div style={{ fontSize: 13, background: '#020617', padding: '10px 12px', borderRadius: 8, border: '1px solid #334155' }}>
                <div>💰 {laEn ? 'Amount:' : 'Số tiền:'} <strong style={{ color: '#38bdf8' }}>{goiChonQr.giaVnd.toLocaleString('vi-VN')} VNĐ</strong> ({goiChonQr.soTrang})</div>
                <div>📝 {laEn ? 'Transfer Memo:' : 'Nội dung chuyển khoản bắt buộc:'} <code style={{ color: '#f97316', fontWeight: 700 }}>{thongTinNap?.noi_dung_chuyen_khoan || 'NAP <EMAIL_CUA_BAN>'}</code></div>
              </div>
            </div>

            {thongTinNap?.ngan_hang_ten && thongTinNap?.ngan_hang_so_tk && (
              <div style={{ background: '#fff', padding: 10, borderRadius: 10, textAlign: 'center' }}>
                <img
                  src={`https://img.vietqr.io/image/${encodeURIComponent(thongTinNap.ngan_hang_ten)}-${encodeURIComponent(thongTinNap.ngan_hang_so_tk)}-compact2.png?amount=${goiChonQr.giaVnd}&addInfo=${encodeURIComponent(thongTinNap.noi_dung_chuyen_khoan)}&accountName=${encodeURIComponent(thongTinNap.ngan_hang_chu_tk || '')}`}
                  alt="VietQR Enterprise"
                  style={{ width: 180, height: 'auto', display: 'block' }}
                />
              </div>
            )}
          </div>
        )}
      </div>
      )}
    </section>
  )
}
