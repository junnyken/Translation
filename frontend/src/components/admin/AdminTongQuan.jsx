import { useEffect, useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Button from '../ui/Button.jsx'

/**
 * AdminTongQuan — Trang tổng quan Dashboard với KPI cards, biểu đồ mini,
 * và form kích hoạt VIP nhanh.
 */

const NHAN_NGON_NGU = {
  ja: { co: '🇯🇵', ten: 'Tiếng Nhật', tenEn: 'Japanese', mau: '#ef4444' },
  ko: { co: '🇰🇷', ten: 'Tiếng Hàn', tenEn: 'Korean', mau: '#3b82f6' },
  zh: { co: '🇨🇳', ten: 'Tiếng Trung', tenEn: 'Chinese', mau: '#f59e0b' },
  en: { co: '🇬🇧', ten: 'Tiếng Anh', tenEn: 'English', mau: '#10b981' },
}

export default function AdminTongQuan({
  thongKe, ds, tranMacDinh, tranKhachLa, onNap, dangTaiLai, setLoi, setThongBaoOk,
}) {
  const { laEn } = useNgonNguUI()
  const [emailCap, setEmailCap] = useState('')
  const [congLuot, setCongLuot] = useState('100')
  const [tranVip, setTranVip] = useState('')
  const [dangCap, setDangCap] = useState(false)
  const [tuChuaLanh, setTuChuaLanh] = useState(null)
  const [dangChayChuaLanh, setDangChayChuaLanh] = useState(false)

  useEffect(() => {
    let huy = false
    api.layTrangThaiTuChuaLanh()
      .then((d) => { if (!huy && d) setTuChuaLanh(d) })
      .catch(() => {})
    return () => { huy = true }
  }, [thongKe])

  async function xuLyChayTuChuaLanh() {
    setDangChayChuaLanh(true)
    setLoi(null)
    try {
      const kq = await api.chayTuChuaLanhNgay()
      if (kq) setTuChuaLanh(kq)
      setThongBaoOk(
        laEn
          ? 'Self-healing diagnostic completed: freed memory (GC), refreshed AI key cooldowns & verified temp storage.'
          : 'Đã chạy Bác Sĩ Hệ Thống: giải phóng bộ nhớ rác (GC), mở khóa AI hết hạn cách ly & làm sạch vùng đệm!',
      )
    } catch (err) {
      setLoi(String(err?.message || err))
    } finally {
      setDangChayChuaLanh(false)
    }
  }

  const heThong = thongKe?.he_thong || {}
  const bieuDo7Ngay = Array.isArray(thongKe?.bieu_do_7_ngay) ? thongKe.bieu_do_7_ngay : []
  const phanBoNgonNgu = thongKe?.phan_bo_ngon_ngu || {}
  const soKhachVip = (ds || []).filter(
    (u) => (u.so_luot_mua_them || 0) > 0 || (u.tran_hang_ngay_rieng && u.tran_hang_ngay_rieng > tranMacDinh),
  ).length

  const maxTrangNgay = Math.max(1, ...bieuDo7Ngay.map((d) => d.tong || 0))
  const tongChapNgonNgu = Math.max(
    1,
    Object.values(phanBoNgonNgu).reduce((s, v) => s + Number(v || 0), 0),
  )

  async function xuLyCapGoi(e) {
    e.preventDefault()
    if (!emailCap.trim()) return
    setDangCap(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const kq = await api.quanTriCapLuot({
        email: emailCap.trim(),
        congThemLuot: Number(congLuot) || 0,
        tranHangNgayRieng: tranVip === '' ? null : Number(tranVip),
      })
      setThongBaoOk(kq?.thong_diep || `Đã cập nhật gói cho ${emailCap.trim()}`)
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangCap(false)
    }
  }

  return (
    <>
      {/* ── KPI Cards ───────────────────────────────────────────────────── */}
      <div className="admin-luoi-kpi">
        <div className="admin-the-kpi xanh">
          <div className="admin-kpi-dau">
            <span className="admin-kpi-nhan">
              {laEn ? 'Total Accounts' : 'Tổng tài khoản'}
            </span>
            <span className="admin-kpi-icon">👥</span>
          </div>
          <div className="admin-kpi-gia-tri">{thongKe?.tong_nguoi_dung ?? (ds || []).length}</div>
          <div className="admin-kpi-phu">
            {thongKe
              ? `${thongKe.nguoi_dung_hoat_dong} ${laEn ? 'active' : 'hoạt động'} · +${thongKe.nguoi_dung_moi_hom_nay || 0} ${laEn ? 'today' : 'hôm nay'}`
              : `${(ds || []).filter((u) => u.dang_hoat_dong !== false).length} ${laEn ? 'active' : 'hoạt động'}`}
          </div>
        </div>

        <div className="admin-the-kpi cam">
          <div className="admin-kpi-dau">
            <span className="admin-kpi-nhan">
              {laEn ? 'VIP Customers' : 'Khách VIP'}
            </span>
            <span className="admin-kpi-icon">💎</span>
          </div>
          <div className="admin-kpi-gia-tri">{thongKe?.so_khach_vip ?? soKhachVip}</div>
          <div className="admin-kpi-phu">
            {laEn ? 'Remaining' : 'Còn'}{' '}
            <strong>{(thongKe?.tong_luot_tich_luy_con_lai ?? 0).toLocaleString('vi-VN')}</strong>{' '}
            {laEn ? 'pages unused' : 'trang tích luỹ'}
          </div>
        </div>

        <div className="admin-the-kpi do">
          <div className="admin-kpi-dau">
            <span className="admin-kpi-nhan">
              {laEn ? 'Pages Today' : 'Trang dịch hôm nay'}
            </span>
            <span className="admin-kpi-icon">🔥</span>
          </div>
          <div className="admin-kpi-gia-tri">
            {(thongKe?.trang_dich_hom_nay ?? 0).toLocaleString('vi-VN')}
          </div>
          <div className="admin-kpi-phu">
            {laEn ? 'Account' : 'Tài khoản'}: <strong>{thongKe?.trang_tai_khoan_hom_nay ?? 0}</strong>
            {' · '}{laEn ? 'Guest' : 'Khách'}: <strong>{thongKe?.trang_khach_hom_nay ?? 0}</strong>
          </div>
        </div>

        <div className="admin-the-kpi xanh-duong">
          <div className="admin-kpi-dau">
            <span className="admin-kpi-nhan">
              {laEn ? '7-Day Volume' : 'Sản lượng 7 ngày'}
            </span>
            <span className="admin-kpi-icon">📈</span>
          </div>
          <div className="admin-kpi-gia-tri">
            {(thongKe?.trang_dich_7_ngay ?? 0).toLocaleString('vi-VN')}
          </div>
          <div className="admin-kpi-phu">
            {laEn ? 'Avg' : 'TB'}{' '}
            <strong>{Math.round((thongKe?.trang_dich_7_ngay ?? 0) / 7)}</strong>{' '}
            {laEn ? 'pages/day' : 'trang/ngày'}
          </div>
        </div>

        <div className="admin-the-kpi tim">
          <div className="admin-kpi-dau">
            <span className="admin-kpi-nhan">
              {laEn ? 'All-Time Stats' : 'Tổng sản lượng'}
            </span>
            <span className="admin-kpi-icon">📚</span>
          </div>
          <div className="admin-kpi-gia-tri">
            {(thongKe?.trang_dich_toan_thoi_gian ?? 0).toLocaleString('vi-VN')}
          </div>
          <div className="admin-kpi-phu">
            {laEn ? 'pages across' : 'trang trên'}{' '}
            <strong>{(thongKe?.tong_chapter ?? 0).toLocaleString('vi-VN')}</strong> chapter
          </div>
        </div>

        <div className="admin-the-kpi">
          <div className="admin-kpi-dau">
            <span className="admin-kpi-nhan">
              {laEn ? 'Queue & Policy' : 'Hàng đợi & Chính sách'}
            </span>
            <span className="admin-kpi-icon">⚙️</span>
          </div>
          <div className="admin-kpi-gia-tri">
            {tranMacDinh} <small>{laEn ? 'pages/day' : 'trang/ngày'}</small>
          </div>
          <div className="admin-kpi-phu">
            {laEn ? 'Running' : 'Đang xử lý'}: <strong>{thongKe?.viec_dang_chay ?? 0}</strong> job
            {' · '}{laEn ? 'Guest' : 'Khách'}: <strong>{tranKhachLa}</strong> {laEn ? 'pages' : 'trang'}
          </div>
        </div>
      </div>

      {/* ── Quick VIP Activation ────────────────────────────────────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <div>
            <h3>⚡ {laEn ? 'Quick VIP Activation' : 'Kích hoạt VIP nhanh'}</h3>
            <p className="ghi-chu">
              {laEn
                ? 'Select a preset or enter custom credits to activate for a customer.'
                : 'Chọn gói nhanh hoặc nhập số lượt tuỳ ý cho khách hàng.'}
            </p>
          </div>
        </div>
        <div className="admin-khung-than">
          {/* Preset chips */}
          <div className="admin-goi-nhanh">
            {[
              { luot: '100', nhan: '🌱 Khởi Động (+100)' },
              { luot: '550', nhan: '🔥 Cày Truyện (+550)' },
              { luot: '1200', nhan: '👑 Studio (+1.200)' },
              { luot: '6500', nhan: '🏢 Doanh Nghiệp (+6.500)' },
              { luot: '28000', nhan: '🏛️ Enterprise (+28.000)' },
            ].map((g) => (
              <button
                key={g.luot}
                type="button"
                className={`admin-chip-goi ${congLuot === g.luot ? 'dang-chon' : ''}`}
                onClick={() => setCongLuot(g.luot)}
              >
                {g.nhan}
              </button>
            ))}
          </div>

          {/* Form */}
          <form className="admin-form-hang" onSubmit={xuLyCapGoi}>
            <div className="admin-form-nhom" style={{ flex: 2 }}>
              <label>Email {laEn ? 'customer' : 'khách hàng'}</label>
              <input
                type="email"
                list="admin-ds-email"
                placeholder={laEn ? 'customer@gmail.com' : 'khachhang@gmail.com'}
                value={emailCap}
                onChange={(e) => setEmailCap(e.target.value)}
                required
              />
              <datalist id="admin-ds-email">
                {(ds || []).map((u) => (
                  <option key={u.id} value={u.email}>{u.ten_hien || u.email}</option>
                ))}
              </datalist>
            </div>
            <div className="admin-form-nhom" style={{ flex: 1 }}>
              <label>{laEn ? 'Credits to add' : 'Lượt cộng thêm'}</label>
              <input
                type="number"
                placeholder="100"
                value={congLuot}
                onChange={(e) => setCongLuot(e.target.value)}
              />
            </div>
            <div className="admin-form-nhom" style={{ flex: 1 }}>
              <label>{laEn ? 'VIP daily cap' : 'Trần VIP/ngày'}</label>
              <input
                type="number"
                placeholder={`${laEn ? 'Default' : 'Mặc định'}: ${tranMacDinh}`}
                value={tranVip}
                onChange={(e) => setTranVip(e.target.value)}
              />
            </div>
            <Button type="submit" kieu="chinh" disabled={dangCap}>
              {dangCap ? '⏳ …' : `💎 ${laEn ? 'Activate' : 'Kích hoạt'}`}
            </Button>
          </form>
        </div>
      </div>

      {/* ── Mini 7-day chart ────────────────────────────────────────────── */}
      {bieuDo7Ngay.length > 0 && (
        <div className="admin-luoi-bieu-do">
          <div className="admin-khung">
            <div className="admin-khung-dau">
              <div>
                <h3>📊 {laEn ? '7-Day Volume' : 'Sản lượng 7 ngày'}</h3>
                <p className="ghi-chu">
                  {laEn
                    ? 'Purple = Accounts · Amber = Guests'
                    : 'Tím = Tài khoản · Cam = Khách vãng lai'}
                </p>
              </div>
              <div className="admin-chu-thich-bieu-do">
                <span><i className="admin-cham-mau tk" /> {laEn ? 'Accounts' : 'Tài khoản'}</span>
                <span><i className="admin-cham-mau khach" /> {laEn ? 'Guests' : 'Khách'}</span>
              </div>
            </div>
            <div className="admin-khung-than">
              <div className="admin-bieu-do-7ngay">
                {bieuDo7Ngay.map((d) => {
                  const pctTk = Math.round(((d.trang_tai_khoan || 0) / maxTrangNgay) * 100)
                  const pctKh = Math.round(((d.trang_khach || 0) / maxTrangNgay) * 100)
                  return (
                    <div
                      key={d.ngay}
                      className="admin-cot-ngay"
                      title={`${d.nhan}: ${d.tong} trang`}
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

          {/* Language Breakdown mini */}
          <div className="admin-khung">
            <div className="admin-khung-dau">
              <h3>🌏 {laEn ? 'Languages' : 'Ngôn ngữ'}</h3>
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
                      <strong>{soChap} chap ({pct}%)</strong>
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
        </div>
      )}

      {/* ── Trung Tâm Tự Khắc Phục Lỗi 24/7 (Autonomous Self-Healing Doctor) ── */}
      <div className="admin-khung" style={{ marginTop: 18 }}>
        <div className="admin-khung-dau" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              🛡️ {laEn ? '24/7 Autonomous Self-Healing Doctor' : 'Bác Sĩ Hệ Thống Tự Khắc Phục Lỗi 24/7'}
              <span
                style={{
                  fontSize: 11,
                  padding: '3px 9px',
                  borderRadius: 999,
                  background: 'rgba(16, 185, 129, 0.16)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  fontWeight: 700,
                }}
              >
                {laEn ? 'ACTIVE 24/7' : 'ĐANG BẢO VỆ TỰ ĐỘNG'}
              </span>
            </h3>
            <p className="ghi-chu">
              {laEn
                ? 'Automatically detects runtime errors, rotates rate-limited AI keys, repairs malformed JSON, downscales heavy images, and cleans server RAM without waiting for manual fixes.'
                : 'Tự động phát hiện lỗi phát sinh, cách ly khóa AI quá tải 60s để xoay sang khóa khỏe mạnh, tự vá lỗi cú pháp JSON, tự nén ảnh nặng trên Tiện ích và giải phóng RAM máy chủ mà không cần chờ can thiệp thủ công.'}
            </p>
          </div>
          <Button type="button" kieu="chinh" onClick={xuLyChayTuChuaLanh} disabled={dangChayChuaLanh}>
            {dangChayChuaLanh
              ? '⏳ Đang chẩn đoán & sửa...'
              : (laEn ? '🛠️ Run Self-Heal Now' : '🛠️ Chẩn Đoán & Tự Khắc Phục Ngay')}
          </Button>
        </div>

        <div className="admin-khung-than">
          {/* 4 chỉ số tự chữa lành */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(175px, 1fr))', gap: 10, marginBottom: 14 }}>
            <div style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
              <div style={{ fontSize: 12, opacity: 0.8 }}>{laEn ? 'Total Auto-Fixed Incidents' : 'Tổng sự cố đã tự khắc phục'}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#34d399', marginTop: 2 }}>
                {tuChuaLanh?.thong_ke?.tong_so_lan_tu_sua ?? 0}
              </div>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.25)' }}>
              <div style={{ fontSize: 12, opacity: 0.8 }}>{laEn ? 'AI Key Auto-Rotations' : 'Xoay vòng khóa AI & Dự phòng'}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#60a5fa', marginTop: 2 }}>
                {(tuChuaLanh?.thong_ke?.xoay_vong_khoa_ai ?? 0) + (tuChuaLanh?.thong_ke?.du_phong_google_translate ?? 0)}
              </div>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)' }}>
              <div style={{ fontSize: 12, opacity: 0.8 }}>{laEn ? 'Malformed JSON Repaired' : 'Tự cứu bản dịch JSON lỗi'}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fbbf24', marginTop: 2 }}>
                {tuChuaLanh?.thong_ke?.tu_sua_json_ai ?? 0}
              </div>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(168, 85, 247, 0.08)', border: '1px solid rgba(168, 85, 247, 0.25)' }}>
              <div style={{ fontSize: 12, opacity: 0.8 }}>{laEn ? 'RAM & GC Cleanups' : 'Dọn rác bộ nhớ RAM (GC)'}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#c084fc', marginTop: 2 }}>
                {tuChuaLanh?.thong_ke?.don_rac_bo_nho ?? 0}
                {tuChuaLanh?.bo_nho?.rss_mb > 0 && (
                  <span style={{ fontSize: 12, fontWeight: 500, marginLeft: 6, opacity: 0.85 }}>
                    ({tuChuaLanh.bo_nho.rss_mb} MB)
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* 4 lớp lá chắn tự động */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10, marginBottom: 14 }}>
            {(tuChuaLanh?.co_che_bao_ve || []).map((cc) => (
              <div
                key={cc.ma}
                style={{
                  padding: '10px 12px',
                  borderRadius: 10,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                <div style={{ fontWeight: 700, fontSize: 13, color: '#e2e8f0', display: 'flex', justifyContent: 'space-between', gap: 6 }}>
                  <span>✅ {cc.ten}</span>
                </div>
                <div style={{ fontSize: 12, opacity: 0.76, marginTop: 4, lineHeight: 1.45 }}>
                  {cc.mo_ta}
                </div>
              </div>
            ))}
          </div>

          {/* Nhật ký sự cố đã tự động sửa gần đây */}
          {Array.isArray(tuChuaLanh?.su_co_gan_day) && tuChuaLanh.su_co_gan_day.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, opacity: 0.9 }}>
                📋 {laEn ? 'Recent Auto-Repaired Incidents' : 'Nhật ký sự cố đã được hệ thống tự động phát hiện & sửa chữa gần đây'}
              </div>
              <div style={{ maxHeight: 210, overflowY: 'auto', borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)' }}>
                {tuChuaLanh.su_co_gan_day.slice(0, 12).map((sc) => (
                  <div
                    key={sc.id}
                    style={{
                      padding: '8px 12px',
                      borderBottom: '1px solid rgba(255,255,255,0.06)',
                      fontSize: 12,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 2,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                      <strong style={{ color: '#38bdf8' }}>🔧 {sc.thanh_phan}</strong>
                      <span style={{ opacity: 0.65, fontSize: 11 }}>
                        {sc.thoi_gian ? new Date(sc.thoi_gian).toLocaleString('vi-VN') : ''}
                      </span>
                    </div>
                    <div style={{ opacity: 0.85 }}>⚠️ <em>{sc.su_co}</em></div>
                    <div style={{ color: '#34d399' }}>✔ {sc.hanh_dong}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
