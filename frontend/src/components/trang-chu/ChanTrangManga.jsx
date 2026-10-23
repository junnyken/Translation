import * as api from '../../api'

/**
 * E107 — Chân trang (Footer) phong cách Thế Giới Truyện Tranh (Manga / Manhwa Studio).
 * Hiển thị thống nhất ở cuối Trang chủ khách và Không gian làm việc.
 */
export default function ChanTrangManga() {
  const namHienTai = new Date().getFullYear()

  return (
    <footer className="chan-trang-manga" role="contentinfo" aria-label="Chân trang hệ thống">
      <div className="chan-trang-noi-dung">
        {/* Cột 1: Thương hiệu & Sứ mệnh */}
        <div className="cot-chan-trang cot-thuong-hieu">
          <div className="logo-chan-trang">
            <span className="huy-hieu-logo" aria-hidden="true">🎌</span>
            <div>
              <strong>Manga Translation Studio</strong>
              <span className="phu-de-logo">Thế Giới Truyện Tranh Đa Ngôn Ngữ</span>
            </div>
          </div>
          <p className="mo-ta-chan-trang">
            Nền tảng dịch truyện tranh tự động thế hệ mới dành cho độc giả, nhóm dịch và nhà sáng tạo nội dung.
            Xoá sạch chữ gốc trong lòng bong bóng, giữ trọn nét vẽ và căn chữ chuẩn thẩm mỹ scanlation.
          </p>
          <div className="day-the-loai-chan">
            <span>⚔️ Hành động</span>
            <span>🌸 Ngôn tình</span>
            <span>📜 Cổ trang</span>
            <span>💬 Truyện tranh</span>
          </div>
        </div>

        {/* Cột 2: Tải Bộ Công Cụ */}
        <div className="cot-chan-trang">
          <h3>📦 Tải Bộ Công Cụ</h3>
          <ul className="ds-lien-ket-chan">
            <li>
              <a href={api.urlTaiTienIchChrome()} download="dich-truyen-chrome-extension-v0.3.0.zip">
                🧩 Tải Tiện Ích Chrome / Edge (v0.3.0)
              </a>
            </li>
            <li>
              <a href={api.urlTaiAppWindows()} download="App-Windows-Dich-Truyen-Tu-Dong-v1.0.zip">
                🖥️ Tải App Windows Chia Chapter (v1.0)
              </a>
            </li>
            <li>
              <a href="#tieu-de-he-sinh-thai">
                📖 Hướng dẫn cài đặt trong 10 giây
              </a>
            </li>
            <li>
              <a href="#tieu-de-cach-chay">
                ⚡ Quy trình dịch nhanh trên Web
              </a>
            </li>
          </ul>
        </div>

        {/* Cột 3: Công Nghệ & Tính Năng */}
        <div className="cot-chan-trang">
          <h3>✨ Công Nghệ Lõi</h3>
          <ul className="ds-tinh-nang-chan">
            <li>🎯 Flood-Fill 2D &amp; Rào chắn Voronoi tách bong bóng đôi</li>
            <li>⚡ Xoá chữ tốc độ cao trên GPU/Canvas máy khách</li>
            <li>✏️ Nhấp đúp (Double-click) sửa thoại trực tiếp trên ảnh</li>
            <li>🌍 Hỗ trợ dịch Nhật · Hàn · Trung · Anh ➔ Việt &amp; Quốc tế</li>
          </ul>
        </div>

        {/* Cột 4: Tài Khoản & Gói VIP */}
        <div className="cot-chan-trang">
          <h3>💎 Tài Khoản &amp; Gói Cước</h3>
          <ul className="ds-tinh-nang-chan">
            <li>🔄 Đồng bộ 1 tài khoản trên Web, Extension &amp; App Windows</li>
            <li>🏦 Nạp lượt tự động 24/7 qua mã VietQR ngân hàng</li>
            <li>🛡️ Lượt mua tích luỹ không bao giờ hết hạn qua đêm</li>
            <li>📂 Hỗ trợ xuất ảnh PNG/JPG rời, gói .CBZ, .ZIP &amp; .PDF</li>
          </ul>
        </div>
      </div>

      <div className="chan-trang-day">
        <span>© {namHienTai} Manga Translation Studio · Phiên bản v0.3.0</span>
        <span className="cham-ngan" aria-hidden="true">•</span>
        <span>Hỗ trợ: Manga (Nhật) · Manhwa (Hàn) · Manhua (Trung) · Comic (Anh)</span>
      </div>
    </footer>
  )
}
