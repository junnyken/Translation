import { useNgonNguUI } from '../../lib/ngon-ngu-ui'

export default function ChinhSachBaoMat({ onQuayLai }) {
  const { laEn } = useNgonNguUI()

  return (
    <main className="than-trang" style={{ maxWidth: 920, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{
        background: 'var(--nen-the, #1e293b)',
        border: '1px solid var(--vien, #334155)',
        borderRadius: 16,
        padding: '28px 24px',
        boxShadow: '0 16px 36px rgba(0,0,0,0.22)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <span style={{
            display: 'inline-block',
            background: 'rgba(249,115,22,0.15)',
            color: '#f97316',
            border: '1px solid rgba(249,115,22,0.4)',
            padding: '4px 12px',
            borderRadius: 999,
            fontSize: 13,
            fontWeight: 600,
          }}>
            🛡️ Chrome Web Store &amp; Platform Privacy Policy
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
            ← {laEn ? 'Back to Home' : 'Quay về Trang chủ'}
          </a>
        </div>

        <h1 style={{ marginTop: 14, marginBottom: 6 }}>
          {laEn ? 'Privacy Policy / Chính Sách Quyền Riêng Tư' : 'Chính Sách Quyền Riêng Tư / Privacy Policy'}
        </h1>
        <p style={{ opacity: 0.78, fontSize: 14, marginBottom: 20 }}>
          {laEn
            ? 'Last updated: October 23, 2026 — Applies to Manga Translation Studio (https://comic.io.vn & translation.vibe1.tinhgon.xyz), Chrome Extension (v0.3.0+), and Windows App.'
            : 'Cập nhật lần cuối: 23/10/2026 — Áp dụng cho Website chính thức https://comic.io.vn (và địa chỉ dự phòng translation.vibe1.tinhgon.xyz), Tiện ích Chrome Dịch truyện đang đọc (v0.3.0+) và Ứng dụng Windows.'}
        </p>

        <section style={{
          background: 'rgba(15,23,42,0.45)',
          border: '1px solid var(--vien, #334155)',
          borderRadius: 12,
          padding: '18px 20px',
          marginBottom: 20,
        }}>
          <h2 style={{ color: '#f97316', fontSize: 19, marginTop: 0 }}>🇻🇳 Phiên bản Tiếng Việt (Vietnamese)</h2>
          <p>
            <strong>1. Nguyên tắc cốt lõi:</strong> Tiện ích mở rộng <em>&ldquo;Dịch truyện đang đọc&rdquo;</em> và nền tảng <em>Manga Translation Studio</em> chỉ xử lý dữ liệu khi người dùng chủ động bấm nút Dịch hoặc bật chế độ tự dịch khi cuộn trang.
          </p>
          <ul style={{ lineHeight: 1.7, paddingLeft: 20 }}>
            <li>
              <strong>Dữ liệu được xử lý:</strong> Khi bạn yêu cầu dịch, tiện ích chỉ trích xuất ảnh khung truyện hoặc đoạn văn bản truyện trên tab đang đọc và gửi qua kết nối mã hoá HTTPS tới máy chủ dịch thuật (<code>translation-api.vibe1.tinhgon.xyz</code>) để nhận diện chữ (OCR), xoá chữ gốc và dịch thuật.
            </li>
            <li>
              <strong>Lưu trữ cấu hình cục bộ:</strong> Tiện ích sử dụng <code>chrome.storage.local</code> chỉ để lưu tuỳ chọn của bạn (ngôn ngữ nguồn, ngôn ngữ đích Việt/Anh, kiểu phông chữ, và mã phiên đăng nhập nếu có).
            </li>
            <li>
              <strong>Bộ nhớ đệm Cộng đồng ẩn danh (Anonymous Community Cache):</strong> Để trả kết quả tức thì (0.15 giây) và tiết kiệm tài nguyên AI, hệ thống lưu bản dịch theo chữ ký định danh một chiều của bức ảnh kèm ngôn ngữ đích. Bộ nhớ đệm này hoàn toàn ẩn danh, không lưu danh tính hay lịch sử duyệt web của người dùng.
            </li>
            <li>
              <strong>Cam kết không theo dõi &amp; không bán dữ liệu:</strong> Chúng tôi <strong>KHÔNG</strong> thu thập lịch sử duyệt web, không đọc thông tin cá nhân/mật khẩu, không chèn quảng cáo và tuyệt đối không bán hoặc chia sẻ dữ liệu người dùng cho bên thứ ba.
            </li>
          </ul>
        </section>

        <section style={{
          background: 'rgba(15,23,42,0.45)',
          border: '1px solid var(--vien, #334155)',
          borderRadius: 12,
          padding: '18px 20px',
        }}>
          <h2 style={{ color: '#f97316', fontSize: 19, marginTop: 0 }}>🇬🇧 English Version (Chrome Web Store User Data Privacy)</h2>
          <p>
            <strong>1. Core Privacy Principle:</strong> The <em>&ldquo;Dịch truyện đang đọc&rdquo; (Manga Translation Studio)</em> Chrome Extension and Web Platform only process data when explicitly invoked by the user to translate comic images or web novel text.
          </p>
          <ul style={{ lineHeight: 1.7, paddingLeft: 20 }}>
            <li>
              <strong>Data Processed:</strong> When you click Translate (or enable Auto-Translate on scroll), the extension captures only the comic image or story text on the active tab and transmits it securely over HTTPS to our translation server (<code>translation-api.vibe1.tinhgon.xyz</code>) to perform OCR, inpainting, and translation.
            </li>
            <li>
              <strong>Local Preferences:</strong> We use <code>chrome.storage.local</code> solely to store your user preferences (source language, target language, font style, and optional session token).
            </li>
            <li>
              <strong>Anonymous Community Cache:</strong> Translated regions are cached using an anonymous one-way cryptographic image fingerprint (+ target language) to deliver instant translations for subsequent readers. No personal identifiers or browsing URLs are attached to this cache.
            </li>
            <li>
              <strong>No Tracking or Data Selling:</strong> We do <strong>NOT</strong> collect general browsing history, personal credentials, or financial details. We never sell, rent, or transfer user data to third parties for advertising or analytics.
            </li>
          </ul>
        </section>
      </div>
    </main>
  )
}
