import { useEffect, useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Button from '../ui/Button.jsx'

/**
 * AdminThanhToan — Quản lý VietQR (VNĐ), PayPal Quốc tế (USD), Chợ RapidAPI B2B & lịch sử đơn nạp.
 */
export default function AdminThanhToan({ thongKe, onNap, setLoi, setThongBaoOk }) {
  const { laEn } = useNgonNguUI()

  // VietQR Bank + PayPal + RapidAPI config
  const [nhTen, setNhTen] = useState(thongKe?.ngan_hang_ten || '')
  const [nhSoTk, setNhSoTk] = useState(thongKe?.ngan_hang_so_tk || '')
  const [nhChuTk, setNhChuTk] = useState(thongKe?.ngan_hang_chu_tk || '')
  const [paypalEmail, setPaypalEmail] = useState(thongKe?.paypal_email || '')
  const [paypalClientId, setPaypalClientId] = useState(thongKe?.paypal_client_id || '')
  const [rapidapiUrl, setRapidapiUrl] = useState(thongKe?.rapidapi_url || '')
  const [dangLuuNh, setDangLuuNh] = useState(false)
  const [dangLam, setDangLam] = useState(null)

  useEffect(() => {
    if (!thongKe) return
    setNhTen(thongKe.ngan_hang_ten || '')
    setNhSoTk(thongKe.ngan_hang_so_tk || '')
    setNhChuTk(thongKe.ngan_hang_chu_tk || '')
    setPaypalEmail(thongKe.paypal_email || '')
    setPaypalClientId(thongKe.paypal_client_id || '')
    setRapidapiUrl(thongKe.rapidapi_url || '')
  }, [thongKe])

  const donNapGanDay = Array.isArray(thongKe?.don_nap_gan_day) ? thongKe.don_nap_gan_day : []

  async function xuLyLuuNganHang(e) {
    e.preventDefault()
    setDangLuuNh(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const kq = await api.quanTriCapLuot({
        email: '',
        nganHangTen: nhTen.trim(),
        nganHangSoTk: nhSoTk.trim(),
        nganHangChuTk: nhChuTk.trim(),
        paypalEmail: paypalEmail.trim(),
        paypalClientId: paypalClientId.trim(),
        rapidapiUrl: rapidapiUrl.trim(),
      })
      setThongBaoOk(
        kq?.thong_diep ||
          (laEn ? 'Payment & RapidAPI config saved.' : 'Đã lưu cấu hình VietQR, PayPal & RapidAPI.'),
      )
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLuuNh(false)
    }
  }

  async function lam(id, viec) {
    setDangLam(id)
    setLoi(null)
    setThongBaoOk(null)
    try {
      await viec()
      await onNap()
    } catch (e) {
      setLoi(String(e?.message || e).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLam(null)
    }
  }

  return (
    <>
      {/* ── VietQR Bank Config ─────────────────────────────────────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <div>
            <h3>
              🏦 {laEn
                ? 'VietQR Bank Configuration'
                : 'Cấu hình Mã QR Ngân hàng (VietQR)'}
            </h3>
            <p className="ghi-chu">
              {nhTen && nhSoTk
                ? `${laEn ? 'Active' : 'Đang bật'}: ${nhTen} — ${nhSoTk} (${nhChuTk})`
                : (laEn ? 'Not configured yet' : 'Chưa cài số tài khoản')}
            </p>
          </div>
        </div>
        <div className="admin-khung-than">
          <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 12px' }}>
            Webhook: <code>{typeof window !== 'undefined' ? `${window.location.origin}/api/v1/nap-luot/webhook` : '/api/v1/nap-luot/webhook'}</code>
          </p>
          <form className="admin-form-hang" onSubmit={xuLyLuuNganHang}>
            <div className="admin-form-nhom">
              <label>{laEn ? 'Bank Code' : 'Mã NH'}</label>
              <input
                type="text"
                placeholder="ACB, MB, VCB..."
                value={nhTen}
                onChange={(e) => setNhTen(e.target.value)}
              />
            </div>
            <div className="admin-form-nhom">
              <label>{laEn ? 'Account Number' : 'Số tài khoản'}</label>
              <input
                type="text"
                placeholder={laEn ? 'Receiving account number' : 'Số tài khoản nhận tiền'}
                value={nhSoTk}
                onChange={(e) => setNhSoTk(e.target.value)}
              />
            </div>
            <div className="admin-form-nhom">
              <label>{laEn ? 'Account Holder' : 'Chủ TK'}</label>
              <input
                type="text"
                placeholder={laEn ? 'ACCOUNT HOLDER NAME' : 'TÊN CHỦ TÀI KHOẢN'}
                value={nhChuTk}
                onChange={(e) => setNhChuTk(e.target.value)}
              />
            </div>
            <Button type="submit" kieu="chinh" disabled={dangLuuNh}>
              {dangLuuNh ? '⏳…' : `💾 ${laEn ? 'Save All Gateways' : 'Lưu VietQR & PayPal'}`}
            </Button>
          </form>

          {/* ── PayPal USD & RapidAPI Hub Configuration ─────────────────── */}
          <div style={{ marginTop: 18, paddingTop: 16, borderTop: '1px dashed rgba(148,163,184,0.25)' }}>
            <h4 style={{ margin: '0 0 10px', fontSize: 14, color: '#38bdf8' }}>
              🌍 {laEn ? 'Global USD Checkout (PayPal) & RapidAPI Hub B2B' : 'Cổng Thanh Toán Quốc Tế PayPal (USD) & Chợ RapidAPI B2B'}
            </h4>
            <form className="admin-form-hang" onSubmit={xuLyLuuNganHang}>
              <div className="admin-form-nhom" style={{ flex: '1 1 240px' }}>
                <label>🅿️ {laEn ? 'PayPal.Me Username or Email' : 'Link PayPal.Me hoặc Email PayPal'}</label>
                <input
                  type="text"
                  placeholder="paypal.me/tenban hoặc business@gmail.com"
                  value={paypalEmail}
                  onChange={(e) => setPaypalEmail(e.target.value)}
                />
              </div>
              <div className="admin-form-nhom" style={{ flex: '1 1 220px' }}>
                <label>🔑 {laEn ? 'PayPal Client ID (Optional)' : 'PayPal Client ID (Tuỳ chọn)'}</label>
                <input
                  type="text"
                  placeholder="Live Client ID (nếu dùng Smart Buttons)"
                  value={paypalClientId}
                  onChange={(e) => setPaypalClientId(e.target.value)}
                />
              </div>
              <div className="admin-form-nhom" style={{ flex: '1 1 260px' }}>
                <label>⚡ {laEn ? 'RapidAPI Listing URL' : 'Link API trên chợ RapidAPI'}</label>
                <input
                  type="text"
                  placeholder="https://rapidapi.com/your-org/api/ai-comic-translator"
                  value={rapidapiUrl}
                  onChange={(e) => setRapidapiUrl(e.target.value)}
                />
              </div>
              <Button type="submit" kieu="phu" disabled={dangLuuNh}>
                {dangLuuNh ? '⏳…' : `💾 ${laEn ? 'Save Global Config' : 'Lưu PayPal & RapidAPI'}`}
              </Button>
            </form>
            <div style={{ marginTop: 10, fontSize: 12.5, color: '#94a3b8', display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'center' }}>
              <span>
                📦 File OpenAPI 3.0 nạp lên RapidAPI Studio:{' '}
                <a href="/tai-ve/openapi-rapidapi.json" download="openapi-rapidapi.json" style={{ color: '#34d399', fontWeight: 700 }}>
                  ⬇️ Tải openapi-rapidapi.json
                </a>
              </span>
              <span>
                🔗 Base URL điền trên RapidAPI:{' '}
                <code style={{ color: '#f8fafc' }}>https://translation-api.vibe1.tinhgon.xyz</code>
              </span>
              <span>
                🔐 Header bảo mật RapidAPI:{' '}
                <code style={{ color: '#fbbf24' }}>X-Customer-Api-Key: tr_live_...</code>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Transfer Orders ────────────────────────────────────────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <h3>
            📋 {laEn
              ? `Transfer History (${donNapGanDay.length})`
              : `Lịch sử Đơn Chuyển Khoản (${donNapGanDay.length})`}
          </h3>
        </div>
        {donNapGanDay.length === 0 ? (
          <div className="admin-khung-than" style={{ textAlign: 'center', padding: 32, color: '#94a3b8' }}>
            {laEn ? 'No transfer orders yet.' : 'Chưa có đơn chuyển khoản nào.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="admin-bang">
              <thead>
                <tr>
                  <th>{laEn ? 'Order ID' : 'Mã đơn'}</th>
                  <th>{laEn ? 'Customer' : 'Khách hàng'}</th>
                  <th>{laEn ? 'Package' : 'Gói'}</th>
                  <th>{laEn ? 'Amount' : 'Số tiền'}</th>
                  <th>{laEn ? 'Pages' : 'Trang'}</th>
                  <th>{laEn ? 'Memo' : 'Nội dung CK'}</th>
                  <th>{laEn ? 'Status' : 'Trạng thái'}</th>
                  <th>{laEn ? 'Actions' : 'Thao tác'}</th>
                </tr>
              </thead>
              <tbody>
                {donNapGanDay.map((don) => (
                  <tr key={don.ma_don}>
                    <td><code>{don.ma_don}</code></td>
                    <td><strong>{don.email}</strong></td>
                    <td>{don.ten_goi}</td>
                    <td><strong>{Number(don.so_tien_vnd || 0).toLocaleString('vi-VN')}đ</strong></td>
                    <td>+{Number(don.so_trang_cong || 0).toLocaleString('vi-VN')}</td>
                    <td><code>{don.noi_dung_chuyen_khoan || don.noi_dung_ck}</code></td>
                    <td>
                      {don.trang_thai === 'da_xac_nhan' && (
                        <span className="admin-don-tt da-xac-nhan">✅ {laEn ? 'Confirmed' : 'Đã khớp'}</span>
                      )}
                      {don.trang_thai === 'da_cong_tu_dong' && (
                        <span className="admin-don-tt tu-dong">⚡ {laEn ? 'Auto-credited' : 'Tự động'}</span>
                      )}
                      {don.trang_thai === 'cho_duyet' && (
                        <span className="admin-don-tt cho-duyet">⏳ {laEn ? 'Pending' : 'Chờ duyệt'}</span>
                      )}
                      {don.trang_thai === 'da_thu_hoi' && (
                        <span className="admin-don-tt thu-hoi">⛔ {laEn ? 'Revoked' : 'Đã thu hồi'}</span>
                      )}
                    </td>
                    <td>
                      <div className="admin-hang-cong-cu">
                        {don.trang_thai !== 'da_xac_nhan' && (
                          <Button
                            kieu="chinh"
                            disabled={dangLam === don.ma_don}
                            onClick={() =>
                              lam(don.ma_don, () =>
                                api.quanTriDuyetDonNap({ ma_don: don.ma_don, hanh_dong: 'xac_nhan' }),
                              )
                            }
                          >
                            ✅ {laEn ? 'Confirm' : 'Xác nhận'}
                          </Button>
                        )}
                        {don.trang_thai !== 'da_thu_hoi' && (
                          <Button
                            kieu="phu"
                            disabled={dangLam === don.ma_don}
                            onClick={() =>
                              lam(don.ma_don, () =>
                                api.quanTriDuyetDonNap({ ma_don: don.ma_don, hanh_dong: 'thu_hoi' }),
                              )
                            }
                          >
                            {laEn ? 'Revoke' : 'Thu hồi'}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
