import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Icon from '../ui/Icon.jsx'

const MIEN_EMAIL_CHINH_THONG_CLIENT = new Set([
  'gmail.com', 'googlemail.com',
  'outlook.com', 'hotmail.com', 'live.com', 'msn.com', 'outlook.com.vn', 'hotmail.com.vn',
  'icloud.com', 'me.com', 'mac.com',
  'yahoo.com', 'yahoo.com.vn', 'ymail.com', 'rocketmail.com',
  'proton.me', 'protonmail.com', 'pm.me',
  'zoho.com', 'zohomail.com', 'yandex.com', 'gmx.com', 'aol.com',
  'matbao.com', 'matbao.vn', 'fpt.com', 'fpt.com.vn', 'viettel.com.vn', 'vnpt.vn',
])

const DUOI_TO_CHUC_CHO_PHEP_CLIENT = ['.edu.vn', '.gov.vn', '.ac.vn', '.org.vn', '.edu']

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
  if ((local.match(/\./g) || []).length > 3) {
    return laEn
      ? 'Email contains too many dots in the username.'
      : 'Địa chỉ email có quá nhiều dấu chấm bất thường.'
  }
  if (domain.endsWith('.local') || ['vi-du.com', 'example.com', 'x.com', 'b.com', 'c.com'].includes(domain)) {
    return null
  }
  const hopLe =
    MIEN_EMAIL_CHINH_THONG_CLIENT.has(domain) ||
    DUOI_TO_CHUC_CHO_PHEP_CLIENT.some((duoi) => domain.endsWith(duoi))
  if (!hopLe) {
    return laEn
      ? `Domain '@${domain}' is not supported (10-minute / temporary emails are blocked). Please use Gmail, Outlook/Hotmail, iCloud, Yahoo, ProtonMail, or an educational (.edu.vn) email.`
      : `Tên miền '@${domain}' không được hỗ trợ (chặn triệt để mail 10 phút / tên miền ảo). Vui lòng dùng Gmail (@gmail.com), Outlook/Hotmail, iCloud, Yahoo, ProtonMail hoặc email trường học (.edu.vn).`
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
  const [emailChoXacNhan, setEmailChoXacNhan] = useState(null)

  // Cloudflare Turnstile (Verify you are human)
  const [turnstileSiteKey, setTurnstileSiteKey] = useState('1x00000000000000000000AA')
  const [yeuCauXacNhanEmail, setYeuCauXacNhanEmail] = useState(true)
  const [cfToken, setCfToken] = useState('')
  const turnstileRef = useRef(null)
  const widgetIdRef = useRef(null)

  useEffect(() => {
    let huy = false
    api.coTaiKhoanChua()
      .then((r) => { if (!huy) { setDaCoTaiKhoan(r.da_co); if (!r.da_co) setChe('dang-ky') } })
      .catch(() => { if (!huy) setDaCoTaiKhoan(true) })
    return () => { huy = true }
  }, [])

  useEffect(() => {
    if (typeof api.layThachThucBot !== 'function') return
    api.layThachThucBot()
      .then((r) => {
        if (r?.turnstile_site_key) setTurnstileSiteKey(r.turnstile_site_key)
        if (typeof r?.yeu_cau_xac_nhan_email === 'boolean') {
          setYeuCauXacNhanEmail(r.yeu_cau_xac_nhan_email)
        }
      })
      .catch(() => {})
  }, [])

  const khoiTaoTurnstile = useCallback(() => {
    if (!turnstileRef.current || !window.turnstile) return
    try {
      if (widgetIdRef.current !== null) {
        window.turnstile.remove(widgetIdRef.current)
        widgetIdRef.current = null
      }
      setCfToken('')
      widgetIdRef.current = window.turnstile.render(turnstileRef.current, {
        sitekey: turnstileSiteKey,
        theme: 'light',
        callback: (token) => setCfToken(token || ''),
        'expired-callback': () => setCfToken(''),
        'error-callback': () => setCfToken(''),
      })
    } catch {
      // Bỏ qua trong môi trường test jsdom
    }
  }, [turnstileSiteKey])

  useEffect(() => {
    if (che !== 'dang-ky' || daCoTaiKhoan === false || emailChoXacNhan) return undefined
    if (window.turnstile) {
      khoiTaoTurnstile()
      return undefined
    }
    const idScript = 'cf-turnstile-script'
    let script = document.getElementById(idScript)
    const onLoad = () => khoiTaoTurnstile()
    if (!script) {
      script = document.createElement('script')
      script.id = idScript
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
      script.async = true
      script.defer = true
      script.addEventListener('load', onLoad)
      document.head.appendChild(script)
    } else {
      script.addEventListener('load', onLoad)
    }
    return () => {
      script?.removeEventListener('load', onLoad)
    }
  }, [che, daCoTaiKhoan, emailChoXacNhan, khoiTaoTurnstile])

  const dangKy = che === 'dang-ky'
  const loiEmailSpam = dangKy ? kiemEmailHopLeClient(email, laEn) : null
  const canChongBot = dangKy && daCoTaiKhoan !== false

  async function gui(e) {
    e.preventDefault()
    if (dangKy && loiEmailSpam) {
      setLoi(loiEmailSpam)
      return
    }
    if (canChongBot && !cfToken) {
      setLoi(
        laEn
          ? 'Please complete the Cloudflare security verification (Verify you are human) first.'
          : 'Vui lòng tích hoàn thành xác thực bảo mật Cloudflare (Verify you are human) trước khi tạo tài khoản.',
      )
      return
    }
    setDangGui(true); setLoi(null)
    try {
      if (che === 'dang-ky') {
        if (khoa.trim()) api.luuKhoa(khoa)
        const nguoiMoi = await api.dangKy(email.trim(), tenHien.trim(), matKhau, {
          cf_turnstile_token: cfToken || null,
        })
        if (nguoiMoi && nguoiMoi.dang_hoat_dong === false) {
          setEmailChoXacNhan(nguoiMoi.email || email.trim())
          return
        }
      }
      const nguoi = await api.dangNhap(email.trim(), matKhau)
      onXong(nguoi)
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
      if (dangKy && window.turnstile && widgetIdRef.current !== null) {
        try {
          window.turnstile.reset(widgetIdRef.current)
          setCfToken('')
        } catch {}
      }
    } finally {
      setDangGui(false)
    }
  }

  if (emailChoXacNhan) {
    return (
      <div className="man-dang-nhap">
        <div className="the-dang-nhap">
          <p className="dau-hieu-san-pham">
            <span className="dau-hieu" aria-hidden="true"><Icon ten="sach" co={20} /></span>
            {laEn ? 'Comic Translator' : 'Dịch truyện tranh'}
          </p>

          <h1>📩 {laEn ? 'Confirm Your Email' : 'Xác nhận qua Email'}</h1>
          <Alert sac="ok" tieuDe={laEn ? 'Verification link sent!' : 'Đã gửi liên kết kích hoạt tài khoản!'}>
            {laEn ? (
              <>
                We have sent a confirmation email to <strong>{emailChoXacNhan}</strong>. Please open your inbox (or Spam/Promotions folder) and <strong>click the verification link</strong> to activate and sign in to your account.
              </>
            ) : (
              <>
                Hệ thống đã gửi một thư xác nhận tới <strong>{emailChoXacNhan}</strong>. Vui lòng mở hộp thư đến (hoặc mục Thư rác / Quảng cáo) và <strong>bấm vào liên kết xác nhận trong email</strong> để kích hoạt tài khoản.
              </>
            )}
          </Alert>

          <p className="ghi-chu" style={{ marginTop: 8 }}>
            {laEn
              ? 'Once you click the link in your email, you will be automatically signed in to https://comic.io.vn.'
              : 'Ngay sau khi bấm vào liên kết trong email, bạn sẽ được tự động đăng nhập thẳng vào trang làm việc.'}
          </p>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 12 }}>
            <Button
              kieu="chinh"
              type="button"
              onClick={() => {
                setEmailChoXacNhan(null)
                setChe('dang-nhap')
              }}
            >
              {laEn ? 'Already confirmed? Sign In' : 'Đã bấm xác nhận? Đăng nhập ngay'}
            </Button>
            <Button
              kieu="ghost"
              type="button"
              onClick={() => setEmailChoXacNhan(null)}
            >
              {laEn ? 'Resend / Change Email' : 'Gửi lại hoặc đổi Email'}
            </Button>
          </div>
        </div>
      </div>
    )
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
                ? 'Requires a real email confirmation link & Cloudflare security check.'
                : 'Yêu cầu xác thực Cloudflare & bấm liên kết xác nhận gửi về hộp thư Email thật của bạn.')
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
                  ? '✓ Official email provider accepted — a confirmation link will be sent to this inbox'
                  : '✓ Nhà cung cấp email hợp lệ — hệ thống sẽ gửi liên kết xác nhận về hộp thư này'}
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
            <div className="khung-xac-thuc-bot" role="group" aria-label="Cloudflare Security Check">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--mo)' }}>
                  ☁️ {laEn ? 'Cloudflare Bot Protection:' : 'Xác thực chống Bot (Cloudflare Turnstile):'}
                </span>
                {yeuCauXacNhanEmail && (
                  <span className="huy-hieu-chong-bot">
                    📧 {laEn ? 'Email Link Required' : 'Xác nhận qua Mail'}
                  </span>
                )}
              </div>
              <div ref={turnstileRef} style={{ minHeight: 65, display: 'flex', justifyContent: 'center' }} />
            </div>
          )}

          <Button
            kieu="chinh"
            type="submit"
            disabled={dangGui || Boolean(loiEmailSpam) || (canChongBot && !cfToken)}
            dangChay={dangGui}
          >
            {dangGui
              ? (laEn ? 'Sending…' : 'Đang gửi…')
              : dangKy
                ? (yeuCauXacNhanEmail
                    ? (laEn ? 'Send Confirmation Email' : 'Gửi Email xác nhận & Tạo tài khoản')
                    : (laEn ? 'Create Account' : 'Tạo tài khoản'))
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
