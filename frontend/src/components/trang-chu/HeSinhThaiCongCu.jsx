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
  const { laEn } = useNgonNguUI()

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
    </section>
  )
}
