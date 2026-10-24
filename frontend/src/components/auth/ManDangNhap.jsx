import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Icon from '../ui/Icon.jsx'

const MIEN_EMAIL_RAC_CLIENT = new Set([
  '10minutemail.com', '10minutemail.net', '10minutemail.org', '10mail.org', '10minmail.com',
  '20minutemail.com', 'temp-mail.org', 'temp-mail.io', 'tempmail.com', 'tempmail.net',
  'tempmail.org', 'tempmail.plus', 'tempmail.io', 'tempmailo.com', 'tempail.com',
  'tmpmail.net', 'tmpmail.org', 'tmails.net', 'mytemp.email', 'guerrillamail.com',
  'guerrillamail.net', 'guerrillamail.org', 'sharklasers.com', 'grr.la', 'pokemail.net',
  'yopmail.com', 'yopmail.fr', 'yopmail.net', 'mailinator.com', 'mailinator.net',
  'trashmail.com', 'trashmail.net', 'trashmail.org', 'getnada.com', 'nada.email',
  'dropmail.me', 'maildrop.cc', 'throwawaymail.com', 'dispostable.com', 'mailnesia.com',
  'mohmal.com', 'mohmal.in', 'emailondeck.com', 'fakeinbox.com', 'fakemail.net',
  'emailfake.com', 'generator.email', 'crazymailing.com', 'smailpro.com', 'burnermail.io',
  'inboxkitten.com', 'mailsac.com', 'harakirimail.com', 'vn10p.com', 'mail1s.com',
  '1secmail.com', '1secmail.org', '1secmail.net', 'linshiyouxiang.net', 'moakt.com',
])

const TU_KHOA_RAC_CLIENT = [
  '10min', 'tempmail', 'temp-mail', 'trashmail', 'throwaway', 'guerrillamail',
  'mailinator', 'yopmail', 'fakeinbox', 'fakemail', 'burnermail', '1secmail',
  'maildrop', 'dispostable', 'harakirimail', 'smailpro', 'emailfake', 'mohmal',
]

export function kiemEmailHopLeClient(rawEmail, laEn = false) {
  const chuan = (rawEmail || '').trim().toLowerCase()
  if (!chuan) return null
  if (!chuan.includes('@')) {
    return laEn ? 'Please enter a valid email address.' : 'Vui lòng nhập địa chỉ email hợp lệ.'
  }
  const [local, domain] = chuan.split('@')
  if (!local || !domain || !domain.includes('.')) {
    return laEn
      ? 'Invalid email format (e.g., name@gmail.com).'
      : 'Địa chỉ email chưa đúng định dạng (ví dụ: ten@gmail.com).'
  }
  if (local.includes('+')) {
    return laEn
      ? 'Plus (+) alias emails are not allowed. Please use your primary email address.'
      : 'Không hỗ trợ tạo tài khoản bằng email phụ chứa dấu cộng (+). Vui lòng dùng email chính.'
  }
  if ((local.match(/\./g) || []).length > 4) {
    return laEn
      ? 'Email contains too many dots in the username.'
      : 'Địa chỉ email có quá nhiều dấu chấm bất thường.'
  }
  if (
    MIEN_EMAIL_RAC_CLIENT.has(domain) ||
    TU_KHOA_RAC_CLIENT.some((kw) => domain.includes(kw)) ||
    ['.tk', '.ml', '.ga', '.cf', '.gq'].some((tld) => domain.endsWith(tld))
  ) {
    return laEn
      ? 'Disposable / 10-minute emails are blocked. Please use a real email (Gmail, Outlook, Yahoo, iCloud, or work/school email).'
      : 'Hệ thống chặn email tạm thời (mail 10 phút / tên miền ảo). Vui lòng dùng email thật (Gmail, Outlook, Yahoo, iCloud...).'
  }
  return null
}

/** Màn đăng nhập — chắn trước toàn bộ ứng dụng (Auth slice B). */
export default function ManDangNhap({ onXong, onQuayLai }) {
  const { laEn } = useNgonNguUI()
  const [che, setChe] = useState('dang-nhap')
  const [email, setEmail] = useState('')
  const [matKhau, setMatKhau] = useState('')
  const [hienMatKhau, setHienMatKhau] = useState(false)
  const [tenHien, setTenHien] = useState('')
  const [khoa, setKhoa] = useState(api.docKhoa())
  const [dangGui, setDangGui] = useState(false)
  const [loi, setLoi] = useState(null)
  const [daCoTaiKhoan, setDaCoTaiKhoan] = useState(null)

  // Xác thực chống Bot (Anti-Robot + Mã bảo mật) khi tạo tài khoản mới
  const [khongPhaiBot, setKhongPhaiBot] = useState(false)
  const [thachThuc, setThachThuc] = useState(null)
  const [dapAnChon, setDapAnChon] = useState('')
  const [dangTaiThachThuc, setDangTaiThachThuc] = useState(false)

  const taiMoiThachThuc = useCallback(() => {
    if (typeof api.layThachThucBot !== 'function') return
    setDangTaiThachThuc(true)
    setDapAnChon('')
    api.layThachThucBot()
      .then((r) => {
        if (r && r.ma_thach_thuc) setThachThuc(r)
      })
      .catch(() => {
        setThachThuc(null)
      })
      .finally(() => setDangTaiThachThuc(false))
  }, [])

  useEffect(() => {
    let huy = false
    api.coTaiKhoanChua()
      .then((r) => { if (!huy) { setDaCoTaiKhoan(r.da_co); if (!r.da_co) setChe('dang-ky') } })
      .catch(() => { if (!huy) setDaCoTaiKhoan(true) })
    return () => { huy = true }
  }, [])

  useEffect(() => {
    if (che === 'dang-ky' && daCoTaiKhoan !== false) {
      taiMoiThachThuc()
    }
  }, [che, daCoTaiKhoan, taiMoiThachThuc])

  const dangKy = che === 'dang-ky'
  const loiEmailSpam = dangKy ? kiemEmailHopLeClient(email, laEn) : null
  const canChongBot = dangKy && daCoTaiKhoan !== false
  const daVuotThachThuc = !canChongBot || (
    khongPhaiBot && (!thachThuc || dapAnChon === thachThuc.ma_xac_nhan_hien_thi)
  )

  async function gui(e) {
    e.preventDefault()
    if (dangKy && loiEmailSpam) {
      setLoi(loiEmailSpam)
      return
    }
    if (canChongBot && !khongPhaiBot) {
      setLoi(
        laEn
          ? 'Please check "I am not a Robot" before creating an account.'
          : 'Vui lòng tích chọn "Tôi không phải là Robot" trước khi tạo tài khoản.',
      )
      return
    }
    if (canChongBot && thachThuc && dapAnChon !== thachThuc.ma_xac_nhan_hien_thi) {
      setLoi(
        laEn
          ? `Please select the matching security verification code (${thachThuc.ma_xac_nhan_hien_thi}).`
          : `Vui lòng bấm chọn đúng mã xác thực bảo mật (${thachThuc.ma_xac_nhan_hien_thi}).`,
      )
      return
    }
    setDangGui(true); setLoi(null)
    try {
      if (che === 'dang-ky') {
        if (khoa.trim()) api.luuKhoa(khoa)
        await api.dangKy(email.trim(), tenHien.trim(), matKhau, {
          ma_thach_thuc: thachThuc?.ma_thach_thuc || null,
          dap_an_thach_thuc: dapAnChon || null,
          xac_nhan_khong_phai_bot: Boolean(khongPhaiBot),
        })
      }
      // Đăng ký xong thì đăng nhập luôn — bắt người ta gõ lại đúng thứ vừa gõ là vô nghĩa.
      const nguoi = await api.dangNhap(email.trim(), matKhau)
      onXong(nguoi)
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
      if (dangKy) taiMoiThachThuc()
    } finally {
      setDangGui(false)
    }
  }

  return (
    <div className="man-dang-nhap">
      <div className="the-dang-nhap">
        <p className="dau-hieu-san-pham">
          <span className="dau-hieu" aria-hidden="true"><Icon ten="sach" co={20} /></span>
          {laEn ? 'Comic Translator' : 'Dịch truyện tranh'}
        </p>

        <h1>{dangKy ? (laEn ? 'Create Account' : 'Tạo tài khoản') : (laEn ? 'Sign In' : 'Đăng nhập')}</h1>
        <p className="dan-dang-nhap">
          {dangKy
            ? (laEn
                ? 'Get your own dedicated 20 pages/day quota, independent of shared network limits.'
                : 'Hạn mức tính riêng cho tài khoản bạn, không dùng chung với người khác cùng mạng.')
            : (laEn
                ? 'Sign in to use your dedicated account quota and manage chapters.'
                : 'Vào lại để dùng hạn mức riêng của bạn.')}
        </p>

        {daCoTaiKhoan === false && (
          <Alert sac="tin" tieuDe={laEn ? 'No accounts yet' : 'Chưa có tài khoản nào'}>
            {laEn ? (
              <>This is the first account in the system and will become the administrator. Requires the system access key (<code>API_ACCESS_KEY</code>).</>
            ) : (
              <>Đây là tài khoản đầu tiên của hệ thống, nên nó sẽ là tài khoản quản trị. Cần khoá chung (biến <code>API_ACCESS_KEY</code> trên máy chủ) để tạo.</>
            )}
          </Alert>
        )}

        <form onSubmit={gui} className="khung-dang-nhap">
          <div className="hang-o">
            <label htmlFor="o-email">Email</label>
            <input
              id="o-email" className="o" type="email" autoComplete="username" required autoFocus
              placeholder={laEn ? 'you@gmail.com' : 'ban@gmail.com'}
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
            {dangKy && loiEmailSpam && (
              <p className="ghi-chu" style={{ color: 'var(--loi)', fontWeight: 600 }}>
                ⚠️ {loiEmailSpam}
              </p>
            )}
            {dangKy && !loiEmailSpam && email.includes('@') && email.split('@')[1]?.includes('.') && (
              <p className="ghi-chu" style={{ color: 'var(--ok)', fontWeight: 600 }}>
                {laEn
                  ? '✓ Valid email domain (10-minute / disposable emails are blocked)'
                  : '✓ Tên miền email hợp lệ (Hệ thống tự động chặn mail 10 phút / mail rác)'}
              </p>
            )}
          </div>

          {dangKy && (
            <div className="hang-o">
              <label htmlFor="o-ten">{laEn ? 'Display Name' : 'Tên hiển thị'}</label>
              <input
                id="o-ten" className="o" value={tenHien}
                onChange={(e) => setTenHien(e.target.value)}
                placeholder={laEn ? 'Leave blank to use part before @' : 'Để trống thì lấy phần trước @'}
              />
            </div>
          )}

          <div className="hang-o">
            <label htmlFor="o-mk">{laEn ? 'Password' : 'Mật khẩu'}</label>
            <div className="o-co-nut">
              <input
                id="o-mk" className="o" type={hienMatKhau ? 'text' : 'password'} required
                autoComplete={dangKy ? 'new-password' : 'current-password'}
                value={matKhau} onChange={(e) => setMatKhau(e.target.value)}
              />
              <button
                type="button" className="nut-trong-o" onClick={() => setHienMatKhau((v) => !v)}
                aria-label={hienMatKhau ? (laEn ? 'Hide password' : 'Ẩn mật khẩu') : (laEn ? 'Show password' : 'Hiện mật khẩu')}
                aria-pressed={hienMatKhau}
              >
                {hienMatKhau ? (laEn ? 'Hide' : 'Ẩn') : (laEn ? 'Show' : 'Hiện')}
              </button>
            </div>
            {dangKy && <p className="ghi-chu">{laEn ? 'At least 8 characters.' : 'Ít nhất 8 ký tự.'}</p>}
          </div>

          {dangKy && daCoTaiKhoan === false && (
            <div className="hang-o">
              <label htmlFor="o-khoa">{laEn ? 'System Access Key' : 'Khoá chung của hệ thống'}</label>
              <input
                id="o-khoa" className="o" type="password" value={khoa}
                onChange={(e) => setKhoa(e.target.value)}
                placeholder={laEn ? 'Ask system administrator' : 'Hỏi người quản trị'}
              />
            </div>
          )}

          {canChongBot && (
            <div className="khung-xac-thuc-bot" role="group" aria-label={laEn ? 'Anti-Bot Security Verification' : 'Xác thực chống Robot'}>
              <label className="hang-tick-bot">
                <input
                  type="checkbox"
                  checked={khongPhaiBot}
                  onChange={(e) => setKhongPhaiBot(e.target.checked)}
                />
                <span>
                  <strong>{laEn ? 'I am not a Robot' : 'Tôi không phải là Robot'}</strong>
                  <small>
                    {laEn
                      ? 'Confirm human registration & non-disposable email'
                      : 'Xác nhận người dùng thật & không dùng mail 10 phút'}
                  </small>
                </span>
                <span className="huy-hieu-chong-bot" aria-hidden="true">🛡️ Anti-Spam</span>
              </label>

              {thachThuc && (
                <div className="buoc-chon-ma-bot">
                  <div className="dau-chon-ma-bot">
                    <span>
                      {laEn ? 'Click security code' : 'Bấm chọn đúng mã bảo mật'}:{' '}
                      <strong className="ma-goc-bot">{thachThuc.ma_xac_nhan_hien_thi}</strong>
                    </span>
                    <button
                      type="button"
                      className="nut-chu"
                      style={{ fontSize: 12 }}
                      disabled={dangTaiThachThuc}
                      onClick={taiMoiThachThuc}
                    >
                      🔄 {laEn ? 'Refresh' : 'Đổi mã'}
                    </button>
                  </div>
                  <div className="luoi-ma-bot" role="radiogroup" aria-label={laEn ? 'Select security code' : 'Chọn mã bảo mật'}>
                    {(thachThuc.lua_chon || []).map((ma) => {
                      const dangChon = dapAnChon === ma
                      return (
                        <button
                          key={ma}
                          type="button"
                          role="radio"
                          aria-checked={dangChon}
                          className={`nut-ma-bot ${dangChon ? 'dang-chon' : ''}`}
                          onClick={() => {
                            setDapAnChon(ma)
                            if (!khongPhaiBot) setKhongPhaiBot(true)
                          }}
                        >
                          {ma}
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          <Button
            kieu="chinh"
            type="submit"
            disabled={dangGui || Boolean(loiEmailSpam) || (canChongBot && !daVuotThachThuc)}
            dangChay={dangGui}
          >
            {dangGui
              ? (laEn ? 'Submitting…' : 'Đang gửi…')
              : dangKy
                ? (laEn ? 'Verify & Create Account' : 'Xác nhận & Tạo tài khoản')
                : (laEn ? 'Sign In' : 'Đăng nhập')}
          </Button>
        </form>

        {loi && <Alert sac="loi" tieuDe={laEn ? 'Sign-in Error' : 'Không vào được'}>{loi}</Alert>}

        {daCoTaiKhoan !== false && (
          <p className="doi-che">
            <button
              type="button" className="nut-chu"
              onClick={() => { setChe(dangKy ? 'dang-nhap' : 'dang-ky'); setLoi(null) }}
            >
              {dangKy
                ? (laEn ? 'Already have an account? Sign in' : 'Đã có tài khoản? Đăng nhập')
                : (laEn ? 'New here? Create an account' : 'Chưa có tài khoản? Tạo mới')}
            </button>
          </p>
        )}
      </div>

      {onQuayLai && (
        <p className="chan-dang-nhap">
          <button type="button" className="nut-chu" onClick={onQuayLai}>
            {laEn ? 'Back to Home' : 'Quay lại trang chủ'}
          </button>
          {laEn
            ? ' — try translating immediately without an account.'
            : ' — dịch thử được ngay, không cần tài khoản.'}
        </p>
      )}
    </div>
  )
}
