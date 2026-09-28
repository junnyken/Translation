import { useEffect, useState } from 'react'
import * as api from '../../api.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Icon from '../ui/Icon.jsx'

/** Màn đăng nhập — chắn trước toàn bộ ứng dụng (Auth slice B).
 *
 * ## Vì sao có cả đường "tạo tài khoản đầu tiên"
 *
 * Lúc mới bật slice B, hệ thống chưa có tài khoản nào. Không có đường tạo tài khoản ngay trên
 * màn này thì chính chủ hệ thống cũng bị khoá ra ngoài và phải gọi API bằng tay.
 *
 * Đăng ký đòi **khoá chung** (`X-API-Key`, slice A) — nếu không, ai mở được địa chỉ này cũng
 * tự tạo tài khoản. Nên form đăng ký có thêm ô khoá.
 *
 * ## E62 — dựng lại giao diện
 *
 * Bản trước là một `<form>` trần giữa trang trắng: ô nhập dùng kiểu mặc định của trình duyệt
 * (không mang class `.o` như mọi ô nhập khác trong app), không có thẻ, không căn giữa theo chiều
 * dọc nên nó dính vào mép trên của một canvas rộng 1240px. Lượt này cho nó đúng ngôn ngữ thị giác
 * của phần còn lại: một thẻ nổi trên nền ngà, nhịp dọc thật, một hành động chính rõ ràng.
 *
 * Hai thứ sửa được luôn vì đang ở đây, không phải trang trí:
 *
 * * **`onQuayLai`** — E53 cho khách lạ dùng trang chủ mà không cần tài khoản, nhưng bấm "Đăng
 *   nhập" xong thì **không có đường quay lại**: `App` đổi `muonDangNhap` thành `true` và màn này
 *   không hề nhận hàm đảo lại. Người đổi ý chỉ còn cách tải lại trang. Prop là **tuỳ chọn** nên
 *   nơi nào không truyền (các bài test) vẫn không thấy liên kết đó.
 * * **Nút hiện/ẩn mật khẩu** — gõ sai mật khẩu mà không xem lại được là lý do phổ biến nhất của
 *   một lượt đăng nhập hỏng, và ở đây nó còn tốn một lượt gọi máy chủ.
 */
export default function ManDangNhap({ onXong, onQuayLai }) {
  const [che, setChe] = useState('dang-nhap')
  const [email, setEmail] = useState('')
  const [matKhau, setMatKhau] = useState('')
  const [hienMatKhau, setHienMatKhau] = useState(false)
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
      <div className="the-dang-nhap">
        <p className="dau-hieu-san-pham">
          <span className="dau-hieu" aria-hidden="true"><Icon ten="sach" co={18} /></span>
          Dịch truyện tranh
        </p>

        <h1>{dangKy ? 'Tạo tài khoản' : 'Đăng nhập'}</h1>
        {/* Câu dẫn nói ĐÚNG cái lợi đo được của tài khoản: khách lạ bị chặn thêm bởi một chốt
            theo ĐỊA CHỈ MẠNG dùng chung (`khach_ip`, `danh_tinh_khach.py`), tài khoản thì chỉ có
            chốt của riêng mình. Đây là lý do thật để đăng nhập, không phải lời mời suông. */}
        <p className="dan-dang-nhap">
          {dangKy
            ? 'Hạn mức tính riêng cho tài khoản bạn, không dùng chung với người khác cùng mạng.'
            : 'Vào lại để dùng hạn mức riêng của bạn.'}
        </p>

        {daCoTaiKhoan === false && (
          <Alert sac="tin" tieuDe="Chưa có tài khoản nào">
            Đây là tài khoản đầu tiên của hệ thống, nên nó sẽ là tài khoản quản trị. Cần khoá
            chung (biến <code>API_ACCESS_KEY</code> trên máy chủ) để tạo.
          </Alert>
        )}

        <form onSubmit={gui} className="khung-dang-nhap">
          <div className="hang-o">
            <label htmlFor="o-email">Email</label>
            <input
              id="o-email" className="o" type="email" autoComplete="username" required autoFocus
              placeholder="ban@vi-du.com"
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          {dangKy && (
            <div className="hang-o">
              <label htmlFor="o-ten">Tên hiển thị</label>
              <input
                id="o-ten" className="o" value={tenHien}
                onChange={(e) => setTenHien(e.target.value)}
                placeholder="Để trống thì lấy phần trước @"
              />
            </div>
          )}

          <div className="hang-o">
            <label htmlFor="o-mk">Mật khẩu</label>
            {/* Nút hiện/ẩn nằm TRONG ô: để ngoài thì nó đội thêm một dòng và kéo nút chính
                xuống dưới màn trên điện thoại. */}
            <div className="o-co-nut">
              <input
                id="o-mk" className="o" type={hienMatKhau ? 'text' : 'password'} required
                autoComplete={dangKy ? 'new-password' : 'current-password'}
                value={matKhau} onChange={(e) => setMatKhau(e.target.value)}
              />
              <button
                type="button" className="nut-trong-o" onClick={() => setHienMatKhau((v) => !v)}
                aria-label={hienMatKhau ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                aria-pressed={hienMatKhau}
              >
                {hienMatKhau ? 'Ẩn' : 'Hiện'}
              </button>
            </div>
            {dangKy && <p className="ghi-chu">Ít nhất 8 ký tự.</p>}
          </div>

          {/* E52 — ô khoá chung CHỈ hiện cho tài khoản ĐẦU TIÊN.
              Trước E52 nó hiện với mọi lượt tạo tài khoản, và máy chủ cũng luôn đòi — nên người
              lạ không tự đăng ký được, trái §4.1 đặc tả. Nay máy chủ chỉ đòi khoá khi hệ thống
              chưa có tài khoản nào (người đầu tiên thành quản trị), còn lại mở và chặn theo địa
              chỉ mạng. Giữ ô này khi đã có tài khoản là hỏi một thứ máy chủ không dùng tới. */}
          {dangKy && daCoTaiKhoan === false && (
            <div className="hang-o">
              <label htmlFor="o-khoa">Khoá chung của hệ thống</label>
              <input
                id="o-khoa" className="o" type="password" value={khoa}
                onChange={(e) => setKhoa(e.target.value)}
                placeholder="Hỏi người quản trị"
              />
            </div>
          )}

          <Button kieu="chinh" type="submit" disabled={dangGui} dangChay={dangGui}>
            {dangGui ? 'Đang gửi…' : dangKy ? 'Tạo tài khoản' : 'Đăng nhập'}
          </Button>
        </form>

        {loi && <Alert sac="loi" tieuDe="Không vào được">{loi}</Alert>}

        {daCoTaiKhoan !== false && (
          <p className="doi-che">
            <button
              type="button" className="nut-chu"
              onClick={() => { setChe(dangKy ? 'dang-nhap' : 'dang-ky'); setLoi(null) }}
            >
              {dangKy ? 'Đã có tài khoản? Đăng nhập' : 'Chưa có tài khoản? Tạo mới'}
            </button>
          </p>
        )}
      </div>

      {onQuayLai && (
        <p className="chan-dang-nhap">
          <button type="button" className="nut-chu" onClick={onQuayLai}>
            Quay lại trang chủ
          </button>
          {' — dịch thử được ngay, không cần tài khoản.'}
        </p>
      )}
    </div>
  )
}
