import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import AdminTongQuan from './AdminTongQuan.jsx'
import AdminTaiKhoan from './AdminTaiKhoan.jsx'
import AdminBieuDo from './AdminBieuDo.jsx'
import AdminThanhToan from './AdminThanhToan.jsx'
import AdminCauHinhAi from './AdminCauHinhAi.jsx'
import AdminChapter from './AdminChapter.jsx'
import '../../styles/admin.css'

/**
 * AdminApp — Shell chính của Admin Panel với sidebar + vùng nội dung.
 *
 * Quản lý state trung tâm (danh sách tài khoản, thống kê), truyền xuống cho
 * các trang con. Mỗi trang là một component riêng, chuyển qua state `trangAdmin`.
 */

const CAC_TRANG = [
  { ma: 'tong-quan', nhom: 'chinh', nhan: 'Tổng quan', nhanEn: 'Overview', icon: '📊' },
  { ma: 'tai-khoan', nhom: 'chinh', nhan: 'Tài khoản', nhanEn: 'Accounts', icon: '👥' },
  { ma: 'bieu-do', nhom: 'chinh', nhan: 'Biểu đồ & Phân tích', nhanEn: 'Charts & Analytics', icon: '📈' },
  { ma: 'thanh-toan', nhom: 'chinh', nhan: 'Thanh toán & VietQR', nhanEn: 'Payments & VietQR', icon: '💳' },
  { ma: 'cau-hinh-ai', nhom: 'he-thong', nhan: 'Cấu hình AI', nhanEn: 'AI Config', icon: '🤖' },
  { ma: 'chapter', nhom: 'he-thong', nhan: 'Nhật ký Chapter', nhanEn: 'Chapter Logs', icon: '📚' },
]

const TIEU_DE = Object.fromEntries(CAC_TRANG.map((t) => [t.ma, { vi: t.nhan, en: t.nhanEn }]))

export default function AdminApp({ nguoiDung, onDangXuat, onVeTrangChu }) {
  const { laEn } = useNgonNguUI()
  const [trangAdmin, setTrangAdmin] = useState('tong-quan')
  const [ds, setDs] = useState(null)
  const [thongKe, setThongKe] = useState(null)
  const [loi, setLoi] = useState(null)
  const [thongBaoOk, setThongBaoOk] = useState(null)
  const [dangTaiLai, setDangTaiLai] = useState(false)
  const [moMenuDt, setMoMenuDt] = useState(false)

  const nap = useCallback(async () => {
    setDangTaiLai(true)
    try {
      const danhSach = await api.layDanhSachNguoiDung()
      if (Array.isArray(danhSach)) setDs(danhSach)
      try {
        const tk = await api.layThongKeQuanTri()
        if (tk && typeof tk === 'object' && Array.isArray(tk.nguoi_dung_chi_tiet)) {
          setThongKe(tk)
          setDs(tk.nguoi_dung_chi_tiet)
        }
      } catch {
        // Giữ nguyên danh sách cơ bản từ `/auth/users` nếu `/quan-tri/thong-ke` chưa có
      }
    } catch (e) {
      setLoi(String(e?.message || e))
    } finally {
      setDangTaiLai(false)
    }
  }, [])

  useEffect(() => { nap() }, [nap])

  const tranMacDinh = thongKe?.han_muc_co_tai_khoan ?? 20
  const tranKhachLa = thongKe?.han_muc_khach_la ?? 2
  const heThong = thongKe?.he_thong || {}

  const tieuDeTrang = TIEU_DE[trangAdmin]
    ? (laEn ? TIEU_DE[trangAdmin].en : TIEU_DE[trangAdmin].vi)
    : ''

  const soTaiKhoan = thongKe?.tong_nguoi_dung ?? (ds ? ds.length : null)
  const soDonNap = Array.isArray(thongKe?.don_nap_gan_day) ? thongKe.don_nap_gan_day.length : null
  const soDuyetTay = Number(thongKe?.so_duyet_tay_cho_xu_ly || 0)
  const soChapter = Array.isArray(thongKe?.chapter_gan_day) ? thongKe.chapter_gan_day.length : null
  const soKeyAi = (heThong.deepseek_so_key || 0) + (heThong.du_phong_so_key || (heThong.llm_configured ? 1 : 0))

  function layHuyHieuMenu(ma) {
    if (ma === 'tai-khoan' && soTaiKhoan !== null) return soTaiKhoan
    if (ma === 'thanh-toan') {
      if (soDuyetTay > 0) return `⚠️ ${soDuyetTay}`
      if (soDonNap !== null) return soDonNap
    }
    if (ma === 'cau-hinh-ai' && soKeyAi > 0) return `${soKeyAi} key`
    if (ma === 'chapter' && soChapter !== null) return soChapter
    return null
  }

  function xuLyVeTrangChu(e) {
    if (e) e.preventDefault()
    if (onVeTrangChu) {
      onVeTrangChu()
      return
    }
    if (window.location.pathname !== '/') {
      window.history.pushState({}, '', '/')
    }
    window.location.hash = ''
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }

  const dsTrangHien = CAC_TRANG
  const nhomChinh = dsTrangHien.filter((t) => t.nhom === 'chinh')
  const nhomHeThong = dsTrangHien.filter((t) => t.nhom === 'he-thong')
  const chuCaiDau = String(nguoiDung?.ten_hien || nguoiDung?.email || 'A').trim().charAt(0).toUpperCase()

  return (
    <div className="admin-bo-cuc">
      {/* ── Mobile menu toggle ──────────────────────────────────────────── */}
      <button
        type="button"
        className="admin-nut-menu-dt"
        onClick={() => setMoMenuDt((v) => !v)}
        aria-label="Toggle menu"
      >
        {moMenuDt ? '✕' : '☰'}
      </button>
      <div
        className={`admin-overlay-dt ${moMenuDt ? 'mo' : ''}`}
        onClick={() => setMoMenuDt(false)}
      />

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className={`admin-thanh-ben ${moMenuDt ? 'mo' : ''}`}>
        {/* Branding */}
        <div className="admin-thanh-ben-hieu">
          <div className="admin-hieu-icon">T</div>
          <div className="admin-hieu-chu">
            <strong>
              Translation
              <span className="admin-hieu-badge">ADMIN</span>
            </strong>
            <small>{laEn ? 'Management Console' : 'Trung tâm Quản trị'}</small>
          </div>
        </div>

        {/* Navigation */}
        <nav className="admin-menu">
          <div className="admin-menu-nhan">{laEn ? 'Main Management' : 'Quản trị chính'}</div>
          {nhomChinh.map((t) => {
            const dem = layHuyHieuMenu(t.ma)
            return (
              <button
                key={t.ma}
                type="button"
                className={`admin-menu-muc ${trangAdmin === t.ma ? 'dang-chon' : ''}`}
                onClick={() => { setTrangAdmin(t.ma); setMoMenuDt(false) }}
              >
                <span className="admin-menu-trai">
                  <span className="admin-menu-icon">{t.icon}</span>
                  <span>{laEn ? t.nhanEn : t.nhan}</span>
                </span>
                {dem !== null && <span className="admin-menu-dem">{dem}</span>}
              </button>
            )
          })}

          <div className="admin-phan-cach" />
          <div className="admin-menu-nhan">{laEn ? 'System & AI' : 'Hệ thống & Vận hành'}</div>
          {nhomHeThong.map((t) => {
            const dem = layHuyHieuMenu(t.ma)
            return (
              <button
                key={t.ma}
                type="button"
                className={`admin-menu-muc ${trangAdmin === t.ma ? 'dang-chon' : ''}`}
                onClick={() => { setTrangAdmin(t.ma); setMoMenuDt(false) }}
              >
                <span className="admin-menu-trai">
                  <span className="admin-menu-icon">{t.icon}</span>
                  <span>{laEn ? t.nhanEn : t.nhan}</span>
                </span>
                {dem !== null && <span className="admin-menu-dem">{dem}</span>}
              </button>
            )
          })}
        </nav>

        {/* User info */}
        <div className="admin-nguoi-dung">
          <div className="admin-nd-dau">
            <div className="admin-nd-avatar">{chuCaiDau}</div>
            <div className="admin-nd-info">
              <div className="admin-nd-ten">{nguoiDung.ten_hien || nguoiDung.email}</div>
              <div className="admin-nd-email">{nguoiDung.email}</div>
            </div>
          </div>
          <div className="admin-nd-hanh-dong">
            <a href="/" onClick={xuLyVeTrangChu}>
              ← {laEn ? 'Main Site' : 'Trang chủ'}
            </a>
            <button
              type="button"
              className="admin-nut-chan dang-xuat"
              onClick={onDangXuat}
            >
              {laEn ? 'Sign Out' : 'Đăng xuất'}
            </button>
          </div>
        </div>
      </aside>

      {/* ── Content ─────────────────────────────────────────────────────── */}
      <div className="admin-noi-dung">
        {/* Top bar */}
        <header className="admin-thanh-tren">
          <h1>{tieuDeTrang}</h1>
          <div className="admin-thanh-tren-phai">
            <span className="admin-huy-hieu xanh">
              ● {laEn ? 'Online' : 'Đang hoạt động'}
            </span>
            {heThong.llm_model_name && (
              <span className="admin-huy-hieu tim">🤖 {heThong.llm_model_name}</span>
            )}
            <span className="admin-huy-hieu cam">
              🎯 {laEn
                ? `Quota: ${tranMacDinh}p/day`
                : `Hạn mức: ${tranMacDinh} trang/ngày`}
            </span>
            <Button kieu="phu" onClick={nap} disabled={dangTaiLai}>
              {dangTaiLai
                ? (laEn ? '⏳ Refreshing…' : '⏳ Đang tải…')
                : (laEn ? '🔄 Refresh' : '🔄 Làm mới')}
            </Button>
          </div>
        </header>

        {/* Main content */}
        <main className="admin-ruot">
          {loi && (
            <Alert sac="loi" tieuDe={laEn ? 'Error' : 'Có lỗi'} onDong={() => setLoi(null)}>
              {loi}
            </Alert>
          )}
          {thongBaoOk && (
            <Alert sac="ok" tieuDe={laEn ? 'Done' : 'Thành công'} onDong={() => setThongBaoOk(null)}>
              {thongBaoOk}
            </Alert>
          )}

          {trangAdmin === 'tong-quan' && (
            <AdminTongQuan
              thongKe={thongKe}
              ds={ds}
              tranMacDinh={tranMacDinh}
              tranKhachLa={tranKhachLa}
              onNap={nap}
              dangTaiLai={dangTaiLai}
              setLoi={setLoi}
              setThongBaoOk={setThongBaoOk}
            />
          )}
          {trangAdmin === 'tai-khoan' && (
            <AdminTaiKhoan
              ds={ds}
              thongKe={thongKe}
              toi={nguoiDung}
              tranMacDinh={tranMacDinh}
              onNap={nap}
              setLoi={setLoi}
              setThongBaoOk={setThongBaoOk}
            />
          )}
          {trangAdmin === 'bieu-do' && (
            <AdminBieuDo thongKe={thongKe} tranMacDinh={tranMacDinh} tranKhachLa={tranKhachLa} />
          )}
          {trangAdmin === 'thanh-toan' && (
            <AdminThanhToan
              thongKe={thongKe}
              onNap={nap}
              setLoi={setLoi}
              setThongBaoOk={setThongBaoOk}
            />
          )}
          {trangAdmin === 'cau-hinh-ai' && (
            <AdminCauHinhAi
              thongKe={thongKe}
              onNap={nap}
              setLoi={setLoi}
              setThongBaoOk={setThongBaoOk}
            />
          )}
          {trangAdmin === 'chapter' && <AdminChapter thongKe={thongKe} />}
        </main>
      </div>
    </div>
  )
}
