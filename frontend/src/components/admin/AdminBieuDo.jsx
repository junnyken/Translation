import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'

/**
 * AdminBieuDo — Biểu đồ sản lượng 7 ngày và phân bổ ngôn ngữ (full page).
 */

const NHAN_NGON_NGU = {
  ja: { co: '🇯🇵', ten: 'Tiếng Nhật (Manga)', tenEn: 'Japanese (Manga)', mau: '#ef4444' },
  ko: { co: '🇰🇷', ten: 'Tiếng Hàn (Manhwa)', tenEn: 'Korean (Manhwa)', mau: '#3b82f6' },
  zh: { co: '🇨🇳', ten: 'Tiếng Trung (Manhua)', tenEn: 'Chinese (Manhua)', mau: '#f59e0b' },
  en: { co: '🇬🇧', ten: 'Tiếng Anh (Comic)', tenEn: 'English (Comic)', mau: '#10b981' },
}

export default function AdminBieuDo({ thongKe, tranMacDinh, tranKhachLa }) {
  const { laEn } = useNgonNguUI()

  const bieuDo7Ngay = Array.isArray(thongKe?.bieu_do_7_ngay) ? thongKe.bieu_do_7_ngay : []
  const phanBoNgonNgu = thongKe?.phan_bo_ngon_ngu || {}
  const maxTrangNgay = Math.max(1, ...bieuDo7Ngay.map((d) => d.tong || 0))
  const tongChapNgonNgu = Math.max(
    1,
    Object.values(phanBoNgonNgu).reduce((s, v) => s + Number(v || 0), 0),
  )

  if (bieuDo7Ngay.length === 0) {
    return (
      <div className="admin-khung">
        <div className="admin-khung-than" style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>
          {laEn ? 'No chart data available yet.' : 'Chưa có dữ liệu biểu đồ.'}
        </div>
      </div>
    )
  }

  return (
    <>
      {/* ── 7-Day Bar Chart (Large) ───────────────────────────────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <div>
            <h3>📊 {laEn ? '7-Day Translation Volume' : 'Biểu đồ Sản lượng Dịch 7 Ngày'}</h3>
            <p className="ghi-chu">
              {laEn
                ? 'Purple = Registered Accounts · Amber = Guest Visitors'
                : 'Màu tím = Tài khoản đã đăng ký · Màu cam = Khách vãng lai dùng thử'}
            </p>
          </div>
          <div className="admin-chu-thich-bieu-do">
            <span><i className="admin-cham-mau tk" /> {laEn ? 'Accounts' : 'Tài khoản'}</span>
            <span><i className="admin-cham-mau khach" /> {laEn ? 'Guests' : 'Khách'}</span>
          </div>
        </div>
        <div className="admin-khung-than">
          <div className="admin-bieu-do-7ngay" style={{ height: 280 }}>
            {bieuDo7Ngay.map((d) => {
              const pctTk = Math.round(((d.trang_tai_khoan || 0) / maxTrangNgay) * 100)
              const pctKh = Math.round(((d.trang_khach || 0) / maxTrangNgay) * 100)
              return (
                <div
                  key={d.ngay}
                  className="admin-cot-ngay"
                  title={`${d.nhan}: ${laEn ? 'Total' : 'Tổng'} ${d.tong} ${laEn ? 'pages' : 'trang'} (${laEn ? 'Account' : 'TK'}: ${d.trang_tai_khoan}, ${laEn ? 'Guest' : 'Khách'}: ${d.trang_khach})`}
                >
                  <span className="admin-cot-so">{d.tong || 0}</span>
                  <div className="admin-cot-than">
                    {pctKh > 0 && (
                      <div
                        className="admin-cot-phan khach"
                        style={{ height: `${Math.max(6, pctKh)}%` }}
                      />
                    )}
                    {pctTk > 0 && (
                      <div
                        className="admin-cot-phan tk"
                        style={{ height: `${Math.max(6, pctTk)}%` }}
                      />
                    )}
                    {d.tong === 0 && <div className="admin-cot-phan rong" />}
                  </div>
                  <span className="admin-cot-nhan">{d.nhan}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── Language Breakdown ─────────────────────────────────────────── */}
      <div className="admin-luoi-bieu-do">
        <div className="admin-khung">
          <div className="admin-khung-dau">
            <h3>🌏 {laEn ? 'Language Distribution' : 'Phân bổ Ngôn ngữ Truyện'}</h3>
          </div>
          <div className="admin-khung-than">
            {['ja', 'ko', 'zh', 'en'].map((ma) => {
              const info = NHAN_NGON_NGU[ma]
              const soChap = Number(phanBoNgonNgu[ma] || 0)
              const pct = thongKe?.tong_chapter
                ? Math.round((soChap / tongChapNgonNgu) * 100)
                : 0
              return (
                <div key={ma} className="admin-dong-nn">
                  <div className="admin-dong-nn-dau">
                    <span>{info.co} {laEn ? info.tenEn : info.ten}</span>
                    <strong>{soChap.toLocaleString('vi-VN')} chap ({pct}%)</strong>
                  </div>
                  <div className="admin-thanh-nn-nen">
                    <div
                      className="admin-thanh-nn-ruot"
                      style={{
                        width: `${Math.max(soChap > 0 ? 4 : 0, pct)}%`,
                        background: info.mau,
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Policy Summary */}
        <div className="admin-khung">
          <div className="admin-khung-dau">
            <h3>🛡️ {laEn ? 'Policy & System Info' : 'Chính sách & Thông số'}</h3>
          </div>
          <div className="admin-khung-than">
            <div className="admin-chinh-sach">
              <span>✅ <b>{laEn ? 'Anti-Spam' : 'Chống Spam'}:</b> {laEn ? 'Gmail, Outlook, iCloud, Yahoo, Proton only' : 'Chỉ nhận Gmail, Outlook, iCloud, Yahoo, Proton'}</span>
              <span>🛡️ <b>{laEn ? 'Anti-Bot' : 'Chống Bot'}:</b> Cloudflare Turnstile {laEn ? 'enabled' : 'đang bật'}</span>
              <span>🎯 <b>{laEn ? 'New Account' : 'Tài khoản mới'}:</b> <b>{tranMacDinh} {laEn ? 'pages/day' : 'trang/ngày'}</b> (Reset 0h00 VN)</span>
              <span>👤 <b>{laEn ? 'Guest Limit' : 'Khách vãng lai'}:</b> <b>{tranKhachLa} {laEn ? 'pages/day' : 'trang/ngày'}</b></span>
              <span>📊 <b>{laEn ? 'Total Pages' : 'Tổng trang đã dịch'}:</b> <b>{(thongKe?.trang_dich_toan_thoi_gian ?? 0).toLocaleString('vi-VN')}</b></span>
              <span>📚 <b>{laEn ? 'Total Chapters' : 'Tổng chapter'}:</b> <b>{(thongKe?.tong_chapter ?? 0).toLocaleString('vi-VN')}</b></span>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
