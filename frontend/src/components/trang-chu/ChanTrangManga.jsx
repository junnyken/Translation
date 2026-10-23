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
              ? 'Next-generation automatic comic & novel translation platform for readers, scanlation teams, and content creators. Clean bubble text inpainting, intact artwork, and scanlation-grade typesetting.'
              : 'Nền tảng dịch truyện tranh tự động thế hệ mới dành cho độc giả, nhóm dịch và nhà sáng tạo nội dung. Xoá sạch chữ gốc trong lòng bong bóng, giữ trọn nét vẽ và căn chữ chuẩn thẩm mỹ scanlation.'}
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
          <h3>📦 {laEn ? 'Download Toolkit' : 'Tải Bộ Công Cụ'}</h3>
          <ul className="ds-lien-ket-chan">
            <li>
              <a href={api.urlTaiTienIchChrome()} download="dich-truyen-chrome-extension-v0.3.0.zip">
                🧩 {laEn ? 'Chrome / Edge Extension (v0.3.0)' : 'Tải Tiện Ích Chrome / Edge (v0.3.0)'}
              </a>
            </li>
            <li>
              <a href={api.urlTaiAppWindows()} download="App-Windows-Dich-Truyen-Tu-Dong-v1.0.zip">
                🖥️ {laEn ? 'Windows Batch Chapter App (v1.0)' : 'Tải App Windows Chia Chapter (v1.0)'}
              </a>
            </li>
            <li>
              <a href="#tieu-de-he-sinh-thai">
                📖 {laEn ? '10-Second Setup Guide' : 'Hướng dẫn cài đặt trong 10 giây'}
              </a>
            </li>
            <li>
              <a href="#tieu-de-cach-chay">
                ⚡ {laEn ? 'Fast Web Translation Workflow' : 'Quy trình dịch nhanh trên Web'}
              </a>
            </li>
          </ul>
        </div>

        {/* Cột 3: Công Nghệ & Tính Năng */}
        <div className="cot-chan-trang">
          <h3>✨ {laEn ? 'Core Technology' : 'Công Nghệ Lõi'}</h3>
          <ul className="ds-tinh-nang-chan">
            <li>🎯 {laEn ? '2D Flood-Fill & Voronoi Double-Bubble Split' : 'Flood-Fill 2D & Rào chắn Voronoi tách bong bóng đôi'}</li>
            <li>⚡ {laEn ? 'High-Speed Client GPU/Canvas Inpainting' : 'Xoá chữ tốc độ cao trên GPU/Canvas máy khách'}</li>
            <li>✏️ {laEn ? 'Double-Click Live Speech Bubble Editor' : 'Nhấp đúp (Double-click) sửa thoại trực tiếp trên ảnh'}</li>
            <li>🌍 {laEn ? 'JP · KR · ZH · EN ➔ Vietnamese & Global English' : 'Hỗ trợ dịch Nhật · Hàn · Trung · Anh ➔ Việt & Quốc tế'}</li>
          </ul>
        </div>

        {/* Cột 4: Tài Khoản & Gói VIP */}
        <div className="cot-chan-trang">
          <h3>💎 {laEn ? 'Accounts & VIP Plans' : 'Tài Khoản & Gói Cước'}</h3>
          <ul className="ds-tinh-nang-chan">
            <li>🔄 {laEn ? 'Sync 1 Account across Web, Extension & Windows App' : 'Đồng bộ 1 tài khoản trên Web, Extension & App Windows'}</li>
            <li>🏦 {laEn ? '24/7 Instant Top-up via Bank QR Code' : 'Nạp lượt tự động 24/7 qua mã VietQR ngân hàng'}</li>
            <li>🛡️ {laEn ? 'Purchased Quota Never Expires Overnight' : 'Lượt mua tích luỹ không bao giờ hết hạn qua đêm'}</li>
            <li>📂 {laEn ? 'Export High-Res PNG/JPG, .CBZ, .ZIP & .PDF' : 'Hỗ trợ xuất ảnh PNG/JPG rời, gói .CBZ, .ZIP & .PDF'}</li>
          </ul>
        </div>
      </div>

      <div className="chan-trang-day">
        <span>© {namHienTai} Manga Translation Studio · {laEn ? 'Version v0.3.0' : 'Phiên bản v0.3.0'}</span>
        <span className="cham-ngan" aria-hidden="true">•</span>
        <span>{laEn ? 'Supported: Manga (JP) · Manhwa (KR) · Manhua (ZH) · Comic (EN) · Web Novel' : 'Hỗ trợ: Manga (Nhật) · Manhwa (Hàn) · Manhua (Trung) · Comic (Anh) · Truyện chữ'}</span>
      </div>
    </footer>
  )
}
