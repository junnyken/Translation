import { useEffect, useState } from 'react'
import * as api from '../../api.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'

/** Màn đăng nhập — chắn trước toàn bộ ứng dụng (Auth slice B).
 *
 * ## Vì sao có cả đường "tạo tài khoản đầu tiên"
 *
 * Lúc mới bật slice B, hệ thống chưa có tài khoản nào. Không có đường tạo tài khoản ngay trên
 * màn này thì chính chủ hệ thống cũng bị khoá ra ngoài và phải gọi API bằng tay.
 *
 * Đăng ký đòi **khoá chung** (`X-API-Key`, slice A) — nếu không, ai mở được địa chỉ này cũng
 * tự tạo tài khoản. Nên form đăng ký có thêm ô khoá.
 */
export default function ManDangNhap({ onXong }) {
  const [che, setChe] = useState('dang-nhap')
  const [email, setEmail] = useState('')
  const [matKhau, setMatKhau] = useState('')
  const [tenHien, setTenHien] = useState('')
  const [khoa, setKhoa] = useState(api.docKhoa())
  const [dangGui, setDangGui] = useState(false)
  const [loi, setLoi] = useState(null)
  // `null` = chưa hỏi xong. Không đoán bừa là "đã có tài khoản" trong lúc chờ: đoán sai thì
  // người đầu tiên nhìn thấy màn đăng nhập mà không có đường nào tạo tài khoản.
  const [daCoTaiKhoan, setDaCoTaiKhoan] = useState(null)

  useEffect(() => {
    let huy = false
    api.coTaiKhoanChua()
      .then((r) => { if (!huy) { setDaCoTaiKhoan(r.da_co); if (!r.da_co) setChe('dang-ky') } })
      .catch(() => { if (!huy) setDaCoTaiKhoan(true) })
    return () => { huy = true }
  }, [])

  async function gui(e) {
    e.preventDefault()
    setDangGui(true); setLoi(null)
    try {
      if (che === 'dang-ky') {
        if (khoa.trim()) api.luuKhoa(khoa)
        await api.dangKy(email.trim(), tenHien.trim(), matKhau)
      }
      // Đăng ký xong thì đăng nhập luôn — bắt người ta gõ lại đúng thứ vừa gõ là vô nghĩa.
      const nguoi = await api.dangNhap(email.trim(), matKhau)
      onXong(nguoi)
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangGui(false)
    }
  }

  const dangKy = che === 'dang-ky'
  return (
    <div className="man-dang-nhap">
      <h1>{dangKy ? 'Tạo tài khoản' : 'Đăng nhập'}</h1>
      {daCoTaiKhoan === false && (
        <Alert sac="tin" tieuDe="Chưa có tài khoản nào">
          Đây là tài khoản đầu tiên của hệ thống, nên nó sẽ là tài khoản quản trị. Cần khoá
          chung (biến <code>API_ACCESS_KEY</code> trên máy chủ) để tạo.
        </Alert>
      )}
      <form onSubmit={gui} className="khung-dang-nhap">
        <label htmlFor="o-email">Email</label>
        <input
          id="o-email" type="email" autoComplete="username" required autoFocus
          value={email} onChange={(e) => setEmail(e.target.value)}
        />

        {dangKy && (
          <>
            <label htmlFor="o-ten">Tên hiển thị</label>
            <input
              id="o-ten" value={tenHien} onChange={(e) => setTenHien(e.target.value)}
              placeholder="Để trống thì lấy phần trước @"
            />
          </>
        )}

        <label htmlFor="o-mk">Mật khẩu</label>
        <input
          id="o-mk" type="password" required
          autoComplete={dangKy ? 'new-password' : 'current-password'}
          value={matKhau} onChange={(e) => setMatKhau(e.target.value)}
        />
        {dangKy && <p className="ghi-chu">Ít nhất 8 ký tự.</p>}

        {dangKy && (
          <>
            <label htmlFor="o-khoa">Khoá chung của hệ thống</label>
            <input
              id="o-khoa" type="password" value={khoa}
              onChange={(e) => setKhoa(e.target.value)}
              placeholder="Hỏi người quản trị"
            />
          </>
        )}

        <Button kieu="chinh" type="submit" disabled={dangGui}>
          {dangGui ? 'Đang gửi…' : dangKy ? 'Tạo tài khoản' : 'Đăng nhập'}
        </Button>
      </form>

      {loi && <Alert sac="loi" tieuDe="Không vào được">{loi}</Alert>}

      {daCoTaiKhoan !== false && (
        <p className="ghi-chu">
          <button
            type="button" className="nut-chu"
            onClick={() => { setChe(dangKy ? 'dang-nhap' : 'dang-ky'); setLoi(null) }}
          >
            {dangKy ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Tạo mới'}
          </button>
        </p>
      )}
    </div>
  )
}
