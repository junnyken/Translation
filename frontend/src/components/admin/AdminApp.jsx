import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import DangNhapChatGPT from '../auth/DangNhapChatGPT.jsx'
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
  { ma: 'tong-quan', nhan: 'Tổng quan', nhanEn: 'Overview', icon: '📊' },
  { ma: 'tai-khoan', nhan: 'Tài khoản', nhanEn: 'Accounts', icon: '👥' },
  { ma: 'bieu-do', nhan: 'Biểu đồ & Phân tích', nhanEn: 'Charts & Analytics', icon: '📈' },
  { ma: 'thanh-toan', nhan: 'Thanh toán & VietQR', nhanEn: 'Payments & VietQR', icon: '💳' },
  { ma: 'cau-hinh-ai', nhan: 'Cấu hình AI', nhanEn: 'AI Config', icon: '🤖' },
  { ma: 'chapter', nhan: 'Nhật ký Chapter', nhanEn: 'Chapter Logs', icon: '📚' },
  { ma: 'codex', nhan: 'ChatGPT Codex', nhanEn: 'ChatGPT Codex', icon: '🔑' },
]

const TIEU_DE = Object.fromEntries(CAC_TRANG.map((t) => [t.ma, { vi: t.nhan, en: t.nhanEn }]))

export default function AdminApp({ nguoiDung, onDangXuat }) {
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

  const tranMacDinh = thongKe?.han_muc_co_tai_khoan ?? 10
  const tranKhachLa = thongKe?.han_muc_khach_la ?? 2
  const heThong = thongKe?.he_thong || {}

  const tieuDeTrang = TIEU_DE[trangAdmin]
    ? (laEn ? TIEU_DE[trangAdmin].en : TIEU_DE[trangAdmin].vi)
    : ''

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
            <strong>Translation</strong>
            <small>Admin Panel</small>
          </div>
        </div>

        {/* Navigation */}
        <nav className="admin-menu">
          <div className="admin-menu-nhan">{laEn ? 'Navigation' : 'Điều hướng'}</div>
          {CAC_TRANG.map((t) => (
            <button
              key={t.ma}
              type="button"
              className={`admin-menu-muc ${trangAdmin === t.ma ? 'dang-chon' : ''}`}
              onClick={() => { setTrangAdmin(t.ma); setMoMenuDt(false) }}
            >
              <span className="admin-menu-icon">{t.icon}</span>
              {laEn ? t.nhanEn : t.nhan}
            </button>
          ))}
        </nav>

        <div className="admin-phan-cach" />

        {/* User info */}
        <div className="admin-nguoi-dung">
          <div className="admin-nd-ten">{nguoiDung.ten_hien || nguoiDung.email}</div>
          <div className="admin-nd-email">{nguoiDung.email}</div>
          <div className="admin-nd-hanh-dong">
            <a href="#" onClick={(e) => { e.preventDefault(); window.location.hash = '' }}>
              ← {laEn ? 'Main Site' : 'Về trang chủ'}
            </a>
            <button type="button" onClick={onDangXuat}>
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
          {trangAdmin === 'codex' && (
            <div className="admin-khung">
              <div className="admin-khung-dau">
                <div>
                  <h3>🔑 {laEn ? 'ChatGPT Codex Login' : 'Đăng nhập ChatGPT Codex'}</h3>
                  <p className="ghi-chu">
                    {laEn
                      ? 'Use your own ChatGPT account for context-aware translation.'
                      : 'Dùng tài khoản ChatGPT của bạn để dịch ngữ cảnh.'}
                  </p>
                </div>
              </div>
              <div className="admin-khung-than">
                <DangNhapChatGPT />
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
