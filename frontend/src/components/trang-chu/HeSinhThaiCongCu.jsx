import { useState } from 'react'
import * as api from '../../api'

/**
 * E107 — Khối Hệ sinh thái Công cụ Dịch Truyện (Tiện ích Chrome & App Windows)
 * Thiết kế theo phong cách Khung Tranh Truyện Tranh (Manga/Manhwa Panel Aesthetic).
 */
export default function HeSinhThaiCongCu() {
  const [moHuongDanExt, setMoHuongDanExt] = useState(false)
  const [moHuongDanWin, setMoHuongDanWin] = useState(false)

  return (
    <section className="manga-ecosystem" aria-labelledby="tieu-de-he-sinh-thai">
      <div className="manga-ecosystem-dau">
        <span className="manga-sfx-badge">★ BỘ CÔNG CỤ ĐỌC &amp; DỊCH TRUYỆN TOÀN DIỆN ★</span>
        <h2 id="tieu-de-he-sinh-thai">Đem Thế Giới Truyện Tranh Lên Mọi Nền Tảng</h2>
        <p className="dan">
          Dùng chung một tài khoản VIP duy nhất trên cả <b>Web</b>, <b>Tiện ích Chrome</b> và <b>App Windows</b>.
        </p>
      </div>

      <div className="luoi-cong-cu-manga">
        {/* Khung tranh 1: Tiện ích mở rộng Chrome */}
        <article className="khung-tranh-cong-cu panel-ext">
          <div className="bong-thoai-goc">💬 Đọc tới đâu dịch tới đó!</div>
          <div className="dau-khung-cong-cu">
            <span className="icon-cong-cu" aria-hidden="true">🧩</span>
            <div>
              <span className="nhan-phien-ban">PHIÊN BẢN v0.3.0 · CHROME / EDGE / BRAVE</span>
              <h3>Tiện Ích Dịch Truyện Trực Tiếp Trên Web</h3>
            </div>
          </div>

          <p className="mo-ta-cong-cu">
            Dịch trực tiếp trên mọi trang đọc Manga, Manhwa, Manhua, Webtoon mà không cần tải ảnh về máy.
          </p>

          <ul className="ds-tinh-nang-cong-cu">
            <li>⚡ <b>Xoá chữ 2D trên GPU/Canvas máy khách:</b> Sạch 100% chữ gốc, giữ nguyên viền cong bong bóng chỉ trong 2–4 giây.</li>
            <li>✏️ <b>Nhấp đúp sửa bóng thoại tức thì:</b> Sửa câu dịch, phóng to/thu nhỏ chữ hoặc gọi AI dịch lại ngay trên trang.</li>
            <li>🔤 <b>4 Bộ Font chuẩn thể loại:</b> ⚔️ Hành động · 💬 Truyện tranh · 🌸 Ngôn tình · 📜 Cổ trang.</li>
            <li>🌍 <b>Đa ngôn ngữ đích:</b> Dịch sang 🇻🇳 Tiếng Việt &amp; 🇬🇧 Tiếng Anh Quốc tế.</li>
          </ul>

          <div className="chan-khung-cong-cu">
            <a
              href={api.urlTaiTienIchChrome()}
              download="dich-truyen-chrome-extension-v0.3.0.zip"
              className="nut-manga nut-manga-chinh"
            >
              ⬇️ Tải Tiện Ích Chrome (.ZIP)
            </a>
            <button
              type="button"
              className="nut-manga nut-manga-phu"
              onClick={() => setMoHuongDanExt((v) => !v)}
            >
              {moHuongDanExt ? '▲ Ẩn cách cài' : '📖 Cách cài trong 10 giây'}
            </button>
          </div>

          {moHuongDanExt && (
            <div className="hop-huong-dan-nhanh">
              <b>Cách cài đặt vào Chrome / Edge / Cốc Cốc:</b>
              <ol>
                <li>Giải nén file <code>dich-truyen-chrome-extension-v0.3.0.zip</code> vừa tải về.</li>
                <li>Mở trình duyệt, gõ <code>chrome://extensions</code> và bật công tắc <b>Chế độ nhà phát triển (Developer mode)</b> ở góc phải trên.</li>
                <li>Bấm <b>Tải tiện ích đã giải nén (Load unpacked)</b> và chọn thư mục vừa giải nén là xong!</li>
              </ol>
            </div>
          )}
        </article>

        {/* Khung tranh 2: App Windows Tự động dịch theo Link & Chia Chapter */}
        <article className="khung-tranh-cong-cu panel-win">
          <div className="bong-thoai-goc bong-thoai-vang">🚀 Cày 100 Chapter tự động!</div>
          <div className="dau-khung-cong-cu">
            <span className="icon-cong-cu" aria-hidden="true">🖥️</span>
            <div>
              <span className="nhan-phien-ban nhan-win">WINDOWS 10 / 11 DESKTOP APP · v1.0</span>
              <h3>App Windows: Dịch Theo Link &amp; Chia Thư Mục Chapter</h3>
            </div>
          </div>

          <p className="mo-ta-cong-cu">
            Công cụ chuyên dụng cho Nhóm dịch, Chủ web truyện và Người làm video Recap: dán Link là tự tải, dịch và chia thư mục.
          </p>

          <ul className="ds-tinh-nang-cong-cu">
            <li>🔗 <b>Quét tự động danh sách Chapter:</b> Dán 1 Link bộ truyện → Chọn dịch tự động từ <b>Chapter A đến Chapter B</b>.</li>
            <li>📁 <b>Chia sẵn thư mục chuẩn chỉnh:</b> Tự động lưu thành <code>Tên_Truyện / Chapter-001 / 001.jpg, 002.jpg...</code></li>
            <li>🛡️ <b>Vượt chặn Hotlink &amp; Tự động tiếp tục (Resume):</b> Mất mạng hay tắt máy mở lại tự chạy tiếp từ trang đang dở.</li>
            <li>📦 <b>Đóng gói linh hoạt:</b> Xuất cả thư mục ảnh rời chất lượng cao lẫn gói <code>.CBZ</code> đọc trên Mihon/Tachiyomi.</li>
          </ul>

          <div className="chan-khung-cong-cu">
            <a
              href={api.urlTaiAppWindows()}
              download="App-Windows-Dich-Truyen-Tu-Dong-v1.0.zip"
              className="nut-manga nut-manga-win"
            >
              ⬇️ Tải App Windows (.ZIP)
            </a>
            <button
              type="button"
              className="nut-manga nut-manga-phu"
              onClick={() => setMoHuongDanWin((v) => !v)}
            >
              {moHuongDanWin ? '▲ Ẩn hướng dẫn' : '📖 Cách chạy trên Windows'}
            </button>
          </div>

          {moHuongDanWin && (
            <div className="hop-huong-dan-nhanh">
              <b>Cách mở App trên máy tính Windows:</b>
              <ol>
                <li>Giải nén file <code>App-Windows-Dich-Truyen-Tu-Dong-v1.0.zip</code> ra máy tính.</li>
                <li>Nhấp đúp chuột vào file <code>Chay-App-Dich-Truyen-Windows.bat</code> để mở giao diện Manga Studio.</li>
                <li>Đăng nhập tài khoản VIP, dán Link truyện, chọn Chapter muốn dịch và bấm <b>Bắt đầu</b>!</li>
              </ol>
            </div>
          )}
        </article>
      </div>
    </section>
  )
}
