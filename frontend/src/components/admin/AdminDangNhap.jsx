import { useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'

/**
 * AdminDangNhap — Trang đăng nhập riêng cho Admin Panel.
 *
 * Hiển thị khi truy cập `#admin` mà chưa đăng nhập hoặc không có quyền quản trị.
 * Sau khi đăng nhập thành công VÀ xác nhận là quản trị, gọi `onXong(nguoiDung)`.
 */
export default function AdminDangNhap({ onXong, onVeTrangChu }) {
  const { laEn } = useNgonNguUI()
  const [email, setEmail] = useState('')
  const [matKhau, setMatKhau] = useState('')
  const [dangGui, setDangGui] = useState(false)
  const [loi, setLoi] = useState(null)

  async function guiDangNhap(e) {
    e.preventDefault()
    if (!email.trim() || !matKhau) return
    setDangGui(true)
    setLoi(null)
    try {
      const nguoiDung = await api.dangNhap(email.trim(), matKhau)
      if (!nguoiDung.la_quan_tri) {
        setLoi(
          laEn
            ? 'This account does not have admin privileges.'
            : 'Tài khoản này không có quyền quản trị.',
        )
        setDangGui(false)
        return
      }
      onXong(nguoiDung)
    } catch (err) {
      setLoi(String(err?.cauNguoiDoc ?? err?.message ?? err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangGui(false)
    }
  }

  return (
    <div className="admin-dang-nhap">
      <div className="admin-dang-nhap-hop">
        {/* Logo / Branding */}
        <div className="admin-dang-nhap-hieu">
          <div className="admin-hieu-icon">T</div>
          <h1>Translation Admin</h1>
          <p>{laEn ? 'Sign in to continue to admin panel' : 'Đăng nhập để vào trang quản trị'}</p>
        </div>

        {/* Error */}
        {loi && <div className="admin-dang-nhap-loi">⚠️ {loi}</div>}

        {/* Form */}
        <form className="admin-dang-nhap-form" onSubmit={guiDangNhap}>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={laEn ? 'admin@example.com' : 'admin@example.com'}
              autoComplete="email"
              required
              autoFocus
            />
          </label>
          <label>
            {laEn ? 'Password' : 'Mật khẩu'}
            <input
              type="password"
              value={matKhau}
              onChange={(e) => setMatKhau(e.target.value)}
              placeholder={laEn ? 'Enter password' : 'Nhập mật khẩu'}
              autoComplete="current-password"
              required
            />
          </label>
          <button
            type="submit"
            className="nut nut-chinh"
            disabled={dangGui}
            style={{ width: '100%', padding: '10px', fontSize: 14, marginTop: 4 }}
          >
            {dangGui
              ? (laEn ? '⏳ Signing in…' : '⏳ Đang đăng nhập…')
              : (laEn ? 'Sign In' : 'Đăng nhập')}
          </button>
        </form>

        {/* Footer link */}
        <div className="admin-dang-nhap-chan">
          <a
            href="/"
            onClick={(e) => {
              e.preventDefault()
              if (onVeTrangChu) {
                onVeTrangChu()
              } else {
                if (window.location.pathname !== '/') window.history.pushState({}, '', '/')
                window.location.hash = ''
                window.dispatchEvent(new HashChangeEvent('hashchange'))
              }
            }}
          >
            ← {laEn ? 'Back to main site' : 'Về trang chủ'}
          </a>
        </div>
      </div>
    </div>
  )
}
