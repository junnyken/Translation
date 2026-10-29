import * as api from '../../api'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'
import ChanTrangManga from './ChanTrangManga'

export default function TrangTienIch({ onQuayLai }) {
  const { laEn } = useNgonNguUI()

  const cardStyle = {
    background: 'linear-gradient(155deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.94))',
    border: '1px solid rgba(148, 163, 184, 0.28)',
    borderRadius: 18,
    padding: '28px 24px',
    color: '#f8fafc',
    boxShadow: '0 18px 40px rgba(2, 6, 23, 0.35)',
  }

  const stepBoxStyle = {
    background: 'rgba(2, 6, 23, 0.65)',
    border: '1px solid rgba(99, 102, 241, 0.35)',
    borderRadius: 14,
    padding: '18px 20px',
    marginTop: 18,
  }

  const featureItemStyle = {
    background: 'rgba(30, 41, 59, 0.75)',
    borderLeft: '4px solid #6366f1',
    borderRadius: 10,
    padding: '10px 14px',
    marginBottom: 10,
    color: '#e2e8f0',
    fontSize: 14,
    lineHeight: 1.55,
  }

  return (
    <main className="than-trang" style={{ maxWidth: 1120, margin: '0 auto', padding: '24px 16px 48px' }}>
      {/* Đầu trang */}
      <div style={{
        textAlign: 'center',
        padding: '28px 20px',
        marginBottom: 28,
        borderRadius: 20,
        background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.95), rgba(15, 23, 42, 0.96))',
        border: '1px solid rgba(129, 140, 248, 0.35)',
        color: '#f8fafc',
        boxShadow: '0 20px 45px rgba(15, 23, 42, 0.3)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
          <span style={{
            display: 'inline-block',
            background: 'linear-gradient(90deg, #ec4899, #8b5cf6)',
            color: '#fff',
            padding: '5px 14px',
            borderRadius: 999,
            fontSize: 12.5,
            fontWeight: 700,
            letterSpacing: '0.03em',
          }}>
            {laEn ? '★ CHROME EXTENSION v0.3.1 & WINDOWS APP v1.1 ★' : '★ BỘ CÔNG CỤ TIỆN ÍCH CHROME v0.3.1 & APP WINDOWS v1.1 ★'}
          </span>
          <a
            href="#"
            onClick={(e) => {
              if (onQuayLai) {
                e.preventDefault()
                onQuayLai()
              }
            }}
            className="nut nut-phu"
          >
            ← {laEn ? 'Back to Translator' : 'Quay về Trang Dịch Truyện'}
          </a>
        </div>

        <h1 style={{ fontSize: 30, margin: '6px 0 10px', color: '#ffffff' }}>
          {laEn
            ? 'Install Chrome Extension & Windows Batch App'
            : 'Tải & Hướng Dẫn Cài Đặt Tiện Ích Chrome / App Windows'}
        </h1>
        <p style={{ maxWidth: 760, margin: '0 auto', fontSize: 15.5, color: '#cbd5e1', lineHeight: 1.6 }}>
          {laEn ? (
            <>Use <b>one single VIP account</b> across <b>comic.io.vn</b>, the <b>Browser Extension</b>, and the <b>Windows Desktop App</b>.</>
          ) : (
            <>Dùng chung <b>một tài khoản VIP duy nhất</b> trên cả <b>Web (comic.io.vn)</b>, <b>Tiện ích Chrome/Edge</b> và <b>App Windows</b>.</>
          )}
        </p>
      </div>

      {/* Lưới 2 công cụ chính */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: 24 }}>
        {/* CỘT 1: TIỆN ÍCH CHROME / EDGE */}
        <section style={cardStyle} aria-labelledby="tieu-de-tien-ich-chrome">
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 14,
              background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 26, flexShrink: 0,
            }}>
              🧩
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#818cf8', letterSpacing: '0.04em' }}>
                {laEn ? 'VERSION v0.3.1 · CHROME / EDGE / BRAVE / COC COC' : 'PHIÊN BẢN v0.3.1 · CHROME / EDGE / BRAVE / CỐC CỐC'}
              </div>
              <h2 id="tieu-de-tien-ich-chrome" style={{ margin: '2px 0 0', fontSize: 22, color: '#ffffff' }}>
                {laEn ? 'Live Browser Comic & Novel Translator' : 'Tiện Ích Dịch Truyện Trực Tiếp Trên Web'}
              </h2>
            </div>
          </div>

          <p style={{ color: '#cbd5e1', fontSize: 14.5, lineHeight: 1.6, marginBottom: 16 }}>
            {laEn
              ? 'Read and translate as you go on the Manga, Manhwa, Manhua, Webtoon, and Web Novel sites you already read — translations are overlaid on the page you are viewing, for personal reading only.'
              : 'Đọc tới đâu dịch tới đó ngay trên trang Manga, Manhwa, Manhua, Webtoon và Truyện chữ bạn đang đọc — bản dịch phủ lên chính trang đang xem, dùng cho việc đọc cá nhân.'}
          </p>

          <div style={{ marginBottom: 18 }}>
            <div style={featureItemStyle}>
              ⚡ <b>{laEn ? '2D Client GPU/Canvas Inpainting:' : 'Xoá chữ 2D trên GPU/Canvas máy khách:'}</b>{' '}
              {laEn
                ? 'Erases 100% of original text inside speech bubbles while keeping curved bubble borders intact in 2–4 seconds.'
                : 'Làm sạch 100% chữ gốc trong lòng bong bóng, giữ nguyên viền cong và tách bong bóng đôi bằng rào chắn Voronoi chỉ trong 2–4 giây.'}
            </div>
            <div style={featureItemStyle}>
              ✏️ <b>{laEn ? 'Double-Click Live Bubble Editor + Brush Inpaint:' : 'Nhấp đúp sửa bóng thoại + 🖌️ Cọ xoá chữ (Brush Inpaint):'}</b>{' '}
              {laEn
                ? 'Double-click any bubble to edit text, toggle solid box fill (⬛), drag bubble position (✥), or paint over leftover original strokes with the Canvas Brush (🖌️).'
                : 'Nhấp đúp vào bất kỳ bóng thoại nào để sửa câu, bật ⬛ Phủ kín hộp, ✥ Kéo vị trí chữ hoặc dùng 🖌️ Cọ vẽ tay tô xoá nét chữ gốc còn sót ngay trên Canvas.'}
            </div>
            <div style={featureItemStyle}>
              🌍 <b>{laEn ? '3 Specialized AI Models (Fast GPU & Self-Learning Pro):' : '3 Bộ máy AI chuyên biệt (⚡ OCR + GPU Nhanh & 🧠 GPU Pro Tự Học):'}</b>{' '}
              {laEn
                ? 'Choose ⚡ OCR + GPU Fast (1 credit/page), ✨ Gemini Cloud (1 credit/page), or 🧠 OCR + GPU Pro for handwritten fonts & permanent self-learning (2 credits/page).'
                : 'Chọn ⚡ OCR + GPU Nhanh (1 lượt/trang · khuyên dùng), ✨ Gemini Cloud (1 lượt/trang) hoặc 🧠 OCR + GPU Pro chuyên trị chữ viết tay & tự học vĩnh viễn các câu bạn sửa (2 lượt/trang).'}
            </div>
          </div>

          <a
            href={api.urlTaiTienIchChrome()}
            download="dich-truyen-chrome-extension-v0.3.1.zip"
            className="nut-manga nut-manga-chinh"
            style={{ width: '100%', justifyContent: 'center', fontSize: 15, padding: '12px 18px' }}
          >
            ⬇️ {laEn ? 'Download Chrome Extension (.ZIP — v0.3.1)' : 'Tải Tiện Ích Chrome / Edge (.ZIP — v0.3.1)'}
          </a>

          {/* Hướng dẫn cài đặt từng bước */}
          <div style={stepBoxStyle}>
            <h3 style={{ margin: '0 0 10px', fontSize: 16, color: '#38bdf8' }}>
              📖 {laEn ? 'Step-by-Step Installation Guide (10 Seconds):' : 'Hướng dẫn cài đặt chi tiết trong 10 giây:'}
            </h3>
            <ol style={{ margin: 0, paddingLeft: 20, color: '#e2e8f0', fontSize: 13.8, lineHeight: 1.75 }}>
              <li>
                {laEn ? (
                  <>Download and unzip <code>dich-truyen-chrome-extension-v0.3.1.zip</code> into a folder on your computer.</>
                ) : (
                  <>Tải file <code>dich-truyen-chrome-extension-v0.3.1.zip</code> về máy và <b>Giải nén (Extract)</b> ra một thư mục.</>
                )}
              </li>
              <li>
                {laEn ? (
                  <>Open Chrome / Edge / Brave, type <code>chrome://extensions</code> in the address bar, and press Enter.</>
                ) : (
                  <>Mở trình duyệt Chrome / Edge / Cốc Cốc, gõ <code>chrome://extensions</code> vào thanh địa chỉ rồi nhấn <b>Enter</b>.</>
                )}
              </li>
              <li>
                {laEn ? (
                  <>Turn ON the <b>Developer mode</b> toggle at the top-right corner.</>
                ) : (
                  <>Bật công tắc <b>Chế độ dành cho nhà phát triển (Developer mode)</b> ở góc trên bên phải màn hình.</>
                )}
              </li>
              <li>
                {laEn ? (
                  <>Click <b>Load unpacked</b> at the top-left and select the unzipped folder. Pin the <b>T</b> icon to your toolbar!</>
                ) : (
                  <>Bấm nút <b>Tải tiện ích đã giải nén (Load unpacked)</b> ở góc trái trên và chọn thư mục vừa giải nén. Ghim biểu tượng chữ <b>T</b> lên thanh trình duyệt để dùng!</>
                )}
              </li>
            </ol>
          </div>

          {/* Bảng phím tắt */}
          <div style={{ ...stepBoxStyle, borderColor: 'rgba(56, 189, 248, 0.35)' }}>
            <h3 style={{ margin: '0 0 10px', fontSize: 15.5, color: '#fbbf24' }}>
              ⌨️ {laEn ? 'Convenient Keyboard Shortcuts on Any Comic Site:' : 'Bảng Phím Tắt Tiện Lợi Khi Đang Đọc Truyện:'}
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13, color: '#e2e8f0' }}>
              <div style={{ background: 'rgba(15,23,42,0.8)', padding: '8px 10px', borderRadius: 8, border: '1px solid #334155' }}>
                <b style={{ color: '#38bdf8' }}>Alt + Q</b>: {laEn ? 'Translate current page' : 'Dịch trang đang xem'}
              </div>
              <div style={{ background: 'rgba(15,23,42,0.8)', padding: '8px 10px', borderRadius: 8, border: '1px solid #334155' }}>
                <b style={{ color: '#38bdf8' }}>Alt + A</b>: {laEn ? 'Translate full chapter' : 'Dịch toàn bộ cả chapter'}
              </div>
              <div style={{ background: 'rgba(15,23,42,0.8)', padding: '8px 10px', borderRadius: 8, border: '1px solid #334155' }}>
                <b style={{ color: '#38bdf8' }}>Alt + W</b>: {laEn ? 'Auto-translate on scroll' : 'Bật/Tắt tự dịch khi cuộn'}
              </div>
              <div style={{ background: 'rgba(15,23,42,0.8)', padding: '8px 10px', borderRadius: 8, border: '1px solid #334155' }}>
                <b style={{ color: '#38bdf8' }}>Alt + S</b>: {laEn ? 'Snip & translate area' : 'Kéo chuột khoanh vùng dịch'}
              </div>
            </div>
          </div>
        </section>

        {/* CỘT 2: APP WINDOWS DESKTOP */}
        <section style={cardStyle} aria-labelledby="tieu-de-app-windows">
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 14,
              background: 'linear-gradient(135deg, #059669, #0d9488)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 26, flexShrink: 0,
            }}>
              🖥️
            </div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#34d399', letterSpacing: '0.04em' }}>
                WINDOWS 10 / 11 DESKTOP APP · v1.1
              </div>
              <h2 id="tieu-de-app-windows" style={{ margin: '2px 0 0', fontSize: 22, color: '#ffffff' }}>
                {laEn ? 'Windows App: Auto-Crawl URL & Split Chapters' : 'App Windows: Dịch Theo Link & Chia Thư Mục Chapter'}
              </h2>
            </div>
          </div>

          <p style={{ color: '#cbd5e1', fontSize: 14.5, lineHeight: 1.6, marginBottom: 16 }}>
            {laEn
              ? 'Designed for Scanlation studios, Comic website owners, and YouTube/TikTok Recap creators: paste a series link to auto-crawl, translate, and organize chapters into folders.'
              : 'Công cụ chuyên dụng cho Nhóm dịch, Chủ web truyện và Người làm video Recap: chỉ cần dán 1 Link bộ truyện là tự động tải, dịch hàng loạt và chia sẵn thư mục từng Chapter.'}
          </p>

          <div style={{ marginBottom: 18 }}>
            <div style={{ ...featureItemStyle, borderLeftColor: '#10b981' }}>
              🔗 <b>{laEn ? 'Auto Chapter Scanner (Chapter A to B):' : 'Quét tự động danh sách Chapter:'}</b>{' '}
              {laEn
                ? 'Paste 1 series URL → Automatically detects all chapters and lets you batch-translate from Chapter A to Chapter B.'
                : 'Dán 1 Link mục lục bộ truyện → Tự động liệt kê toàn bộ danh sách chương để bạn chọn dịch từ Chapter A đến Chapter B.'}
            </div>
            <div style={{ ...featureItemStyle, borderLeftColor: '#10b981' }}>
              📁 <b>{laEn ? 'Clean Chapter Folder Organization:' : 'Chia sẵn thư mục chuẩn chỉnh:'}</b>{' '}
              {laEn
                ? <>Automatically outputs to <code>Downloads/Truyen_Da_Dich/Series_Name/Chapter-001/001.jpg, 002.jpg...</code></>
                : <>Tự động lưu gọn gàng theo cấu trúc <code>Tên_Truyện / Chapter-001 / 001.jpg, 002.jpg...</code> kèm chế độ Resume (bỏ qua trang đã dịch).</>}
            </div>
            <div style={{ ...featureItemStyle, borderLeftColor: '#10b981' }}>
              📦 <b>{laEn ? 'Hardware-Adaptive Parallelism (1–8 Chapters) & Self-Learning AI:' : 'Chạy song song tự động theo cấu hình máy (1–8 Chap) & AI Tự Học:'}</b>{' '}
              {laEn
                ? 'Auto-detects CPU/RAM to translate multiple chapters simultaneously, exports .CBZ/.PDF/Long-Strip, and includes ⚡ OCR + GPU Fast (1 credit/page) + 🧠 OCR + GPU Pro for handwritten text (2 credits/page).'
                : 'Tự nhận diện CPU/RAM để chạy song song nhiều Chapter cùng lúc, xuất .CBZ/.PDF/Long-Strip, tích hợp ⚡ OCR + GPU Nhanh (1 lượt/trang) và 🧠 OCR + GPU Pro tự học chữ viết tay (2 lượt/trang).'}
            </div>
          </div>

          <a
            href={api.urlTaiAppWindows()}
            download="App-Windows-Dich-Truyen-Tu-Dong-v1.1.zip"
            className="nut-manga nut-manga-win"
            style={{ width: '100%', justifyContent: 'center', fontSize: 15, padding: '12px 18px' }}
          >
            ⬇️ {laEn ? 'Download Windows App (.ZIP — v1.1)' : 'Tải App Windows Chia Chapter (.ZIP — v1.1)'}
          </a>

          {/* Hướng dẫn cài đặt App Windows */}
          <div style={{ ...stepBoxStyle, borderColor: 'rgba(16, 185, 129, 0.35)' }}>
            <h3 style={{ margin: '0 0 10px', fontSize: 16, color: '#34d399' }}>
              🚀 {laEn ? 'How to Run on Windows 10 / 11 (3 Simple Steps):' : 'Hướng dẫn khởi chạy trên Windows 10 / 11 (3 bước):'}
            </h3>
            <ol style={{ margin: 0, paddingLeft: 20, color: '#e2e8f0', fontSize: 13.8, lineHeight: 1.75 }}>
              <li>
                {laEn ? (
                  <>Unzip <code>App-Windows-Dich-Truyen-Tu-Dong-v1.1.zip</code> on your Windows PC (requires Python 3.9+ installed).</>
                ) : (
                  <>Giải nén file <code>App-Windows-Dich-Truyen-Tu-Dong-v1.1.zip</code> ra máy tính Windows (máy có cài Python 3.9+ cơ bản).</>
                )}
              </li>
              <li>
                {laEn ? (
                  <>Double-click <code>CHAY-NGAY-DICH-TRUYEN.bat</code> — it automatically checks libraries and opens the Manga Studio GUI.</>
                ) : (
                  <>Nhấp đúp chuột vào file <code>CHAY-NGAY-DICH-TRUYEN.bat</code> (tự động kiểm tra thư viện và mở ngay bàn làm việc Manga Studio).</>
                )}
              </li>
              <li>
                {laEn ? (
                  <>In Section 1, sign in with your VIP Email/Password (or paste your <code>tr_live_...</code> API Key from <b>comic.io.vn</b>).</>
                ) : (
                  <>Ở Khung số 1, đăng nhập bằng <b>Email &amp; Mật khẩu VIP</b> (hoặc dán mã <code>tr_live_...</code> lấy từ <b>comic.io.vn</b>) để đồng bộ số lượt.</>
                )}
              </li>
              <li>
                {laEn ? (
                  <>Paste the comic URL in Section 2 → Click <b>Scan Chapters</b> → Choose Chapter range and click <b>START</b>!</>
                ) : (
                  <>Dán Link truyện vào Khung số 2 → Bấm <b>🔍 Quét danh sách Chapter</b> → Chọn khoảng Chapter và bấm <b>🚀 BẮT ĐẦU TỰ ĐỘNG TẢI &amp; DỊCH</b>!</>
                )}
              </li>
            </ol>
          </div>

          {/* Minh họa cây thư mục xuất ra */}
          <div style={{ ...stepBoxStyle, borderColor: 'rgba(148, 163, 184, 0.25)' }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 15, color: '#cbd5e1' }}>
              🗂️ {laEn ? 'Output Folder Structure on Your PC:' : 'Cấu trúc thư mục xuất ra trên máy tính của bạn:'}
            </h3>
            <pre style={{
              margin: 0, padding: '10px 12px', background: '#020617',
              borderRadius: 8, color: '#34d399', fontSize: 12.5, overflowX: 'auto',
            }}>{`📁 Downloads / Truyen_Da_Dich /
 └── 📁 Solo-Leveling /
      ├── 📁 Chapter-001 /
      │    ├── 🖼️ 001.jpg
      │    ├── 🖼️ 002.jpg
      │    └── 📜 Chapter-001_Webtoon_LongStrip.jpg
      ├── 📦 Chapter-001.cbz
      └── 📕 Chapter-001.pdf`}</pre>
          </div>
        </section>
      </div>

      <div style={{ marginTop: 36 }}>
        <ChanTrangManga />
      </div>
    </main>
  )
}
