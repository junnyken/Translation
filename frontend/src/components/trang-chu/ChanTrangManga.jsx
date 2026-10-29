import * as api from '../../api'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'

/**
 * E107 — Chân trang (Footer) phong cách Thế Giới Truyện Tranh (Manga / Manhwa Studio).
 * Hiển thị thống nhất ở cuối Trang chủ khách và Không gian làm việc.
 */
export default function ChanTrangManga() {
  const namHienTai = new Date().getFullYear()
  const { laEn } = useNgonNguUI()

  return (
    <footer className="chan-trang-manga" role="contentinfo" aria-label={laEn ? 'System footer' : 'Chân trang hệ thống'}>
      <div className="chan-trang-noi-dung">
        {/* Cột 1: Thương hiệu & Sứ mệnh */}
        <div className="cot-chan-trang cot-thuong-hieu">
          <div className="logo-chan-trang">
            <span className="huy-hieu-logo" aria-hidden="true">🎌</span>
            <div>
              <strong>Manga Translation Studio</strong>
              <span className="phu-de-logo">{laEn ? 'Multilingual Comic & Novel World' : 'Thế Giới Truyện Tranh Đa Ngôn Ngữ'}</span>
            </div>
          </div>
          <p className="mo-ta-chan-trang">
            {laEn
              ? 'Next-generation automatic comic & novel translation platform for readers, scanlation teams, and content creators. Smart background reconstruction, intact artwork, and studio-grade typesetting.'
              : 'Nền tảng dịch truyện tranh tự động thế hệ mới dành cho độc giả, nhóm dịch và nhà sáng tạo nội dung. Tái tạo nền sạch tự nhiên, giữ trọn nét vẽ và dàn chữ chuẩn thẩm mỹ xuất bản.'}
          </p>
          <div className="day-the-loai-chan">
            <span>⚔️ {laEn ? 'Action' : 'Hành động'}</span>
            <span>🌸 {laEn ? 'Romance' : 'Ngôn tình'}</span>
            <span>📜 {laEn ? 'Historical' : 'Cổ trang'}</span>
            <span>💬 {laEn ? 'Classic Comic' : 'Truyện tranh'}</span>
          </div>
        </div>

        {/* Cột 2: Tải Bộ Công Cụ */}
        <div className="cot-chan-trang">
          <h3>📦 {laEn ? 'Ecosystem & Pages' : 'Hệ Sinh Thái & Trang Chuyên Biệt'}</h3>
          <ul className="ds-lien-ket-chan">
            <li>
              <a href="#tien-ich">
                🧩 {laEn ? 'Install Chrome Extension & Windows App' : 'Trang Cài Tiện Ích Chrome & App Windows'}
              </a>
            </li>
            <li>
              <a href="#ket-noi-api">
                ⚡ {laEn ? 'Developer REST API Integration' : 'Trang Hướng Dẫn Kết Nối API (tr_live_...)'}
              </a>
            </li>
            {false && (
              <li>
                <a href="#bang-gia">
                  💎 {laEn ? 'Pricing & Enterprise API Plans' : 'Trang Bảng Giá & Gói Cước Doanh Nghiệp'}
                </a>
              </li>
            )}
            <li>
              <a href="#privacy-policy">
                🛡️ {laEn ? 'Privacy Policy (/privacy-policy)' : 'Chính sách quyền riêng tư (/privacy-policy)'}
              </a>
            </li>
          </ul>
        </div>

        {/* Cột 3: Công Nghệ & Tính Năng */}
        <div className="cot-chan-trang">
          <h3>✨ {laEn ? 'Core Technology' : 'Công Nghệ Độc Quyền'}</h3>
          <ul className="ds-tinh-nang-chan">
            <li>🎯 {laEn ? 'Smart Background Reconstruction & Multi-Dialog Layout' : 'Tái tạo nền thông minh & Tự động căn chỉnh vùng thoại'}</li>
            <li>⚡ {laEn ? 'High-Speed Hardware-Accelerated Processing' : 'Xử lý hình ảnh tăng tốc phần cứng siêu tốc'}</li>
            <li>✏️ {laEn ? 'Double-Click Live Text Editor on Page' : 'Nhấp đúp (Double-click) chỉnh sửa câu dịch trực tiếp trên ảnh'}</li>
            <li>🌍 {laEn ? 'JP · KR · ZH · EN ➔ Vietnamese & Global English' : 'Hỗ trợ dịch Nhật · Hàn · Trung · Anh ➔ Việt & Quốc tế'}</li>
          </ul>
        </div>

        {/* Cột 4: Tài Khoản & Quyền Lợi */}
        <div className="cot-chan-trang">
          <h3>💎 {laEn ? 'Accounts & Benefits' : 'Tài Khoản & Quyền Lợi'}</h3>
          <ul className="ds-tinh-nang-chan">
            <li>🔄 {laEn ? 'Sync 1 Account across Web, Extension & Windows App' : 'Đồng bộ 1 tài khoản trên Web, Extension & App Windows'}</li>
            <li>🎁 {laEn ? 'Free 10 Pages/Day for Every Registered Account' : 'Tặng miễn phí 10 trang/ngày cho tài khoản đăng ký'}</li>
            <li>🛡️ {laEn ? 'Purchased Quota Never Expires Overnight' : 'Lượt tích luỹ không bao giờ hết hạn qua đêm'}</li>
            <li>📂 {laEn ? 'Export High-Res PNG/JPG, .CBZ, .ZIP & .PDF' : 'Hỗ trợ xuất ảnh PNG/JPG rời, gói .CBZ, .ZIP & .PDF'}</li>
          </ul>
        </div>
      </div>

      <div className="chan-trang-day">
        <span>
          © {namHienTai} <a href="https://comic.io.vn" style={{ color: 'inherit', fontWeight: 700, textDecoration: 'none' }}>comic.io.vn</a> — Manga Translation Studio · {laEn ? 'Version v0.3.0' : 'Phiên bản v0.3.0'}
        </span>
        <span className="cham-ngan" aria-hidden="true">•</span>
        <span>{laEn ? 'Supported: Manga (JP) · Manhwa (KR) · Manhua (ZH) · Comic (EN) · Web Novel' : 'Hỗ trợ: Manga (Nhật) · Manhwa (Hàn) · Manhua (Trung) · Comic (Anh) · Truyện chữ'}</span>
        <span className="cham-ngan" aria-hidden="true">•</span>
        <a href="#privacy-policy" style={{ color: '#f97316', fontWeight: 600 }}>
          🛡️ {laEn ? 'Privacy Policy' : 'Chính sách quyền riêng tư (/privacy-policy)'}
        </a>
      </div>
    </footer>
  )
}
