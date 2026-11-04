import { useEffect, useState } from 'react'
import * as api from '../../api'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'
import ChanTrangManga from './ChanTrangManga'

export default function TrangBangGia({ nguoiDung, onQuayLai, onMoDangNhap }) {
  const { lang, laEn } = useNgonNguUI()
  const [thongTinNap, setThongTinNap] = useState(null)
  const [emailNhapTay, setEmailNhapTay] = useState(nguoiDung?.email || '')
  const [daChepNoiDung, setDaChepNoiDung] = useState(false)
  const [dangXacNhan, setDangXacNhan] = useState(false)
  const [ketQuaDon, setKetQuaDon] = useState(null)
  const [loiXacNhan, setLoiXacNhan] = useState('')
  const [tienTe, setTienTe] = useState('USD')
  const [chuKyGoi, setChuKyGoi] = useState('THANG')

  const laNam = chuKyGoi === 'NAM'

  // Bảng Giá Chuẩn Quốc Tế 4 Gói (Theo Tháng / Năm) kèm Mỏ Neo Giá (Price Anchoring) & Ưu Đãi Lần Đầu (-50% OFF)
  // Cổng Developer API (tr_live_...) mở từ Gói thứ 3 (Standard/Studio - $9.99/mo) và Gói thứ 4 (Pro Max - $19.99/mo).
  const DANH_SACH_GOI = [
    {
      ma: laNam ? 'starter_yearly' : 'starter_monthly',
      maNgan: laNam ? 'STARTYR' : 'STARTER',
      nhan: laEn ? '🎁 FIRST-TIME OFFER (-50%)' : '🎁 ƯU ĐÃI LẦN ĐẦU (-50%)',
      ten: laEn
        ? (laNam ? 'Starter Yearly (3,600 Credits)' : 'Starter (300 Credits)')
        : (laNam ? 'Gói Starter Năm (3.600 Credits)' : 'Gói Starter (300 Credits / tháng)'),
      giaGocVnd: laNam ? 708000 : 99000,
      giaVnd: laNam ? 450000 : 49000,
      giaGocUsd: laNam ? '4.99' : '5.99',
      giaUsd: laNam ? '29.99' : '2.99',
      giaHienUsd: laNam ? '2.49' : '2.99',
      chuKy: laEn ? '/ month' : '/ tháng',
      phuChuKy: laNam
        ? (laEn ? 'Billed $29.99 yearly (Save 50%)' : 'Thanh toán 450k/năm (~37k/tháng · Giảm 50%)')
        : (laEn ? '🔥 50% OFF First Month (200 + 100 Bonus Credits)' : '🔥 Giảm 50% tháng đầu (200 + Tặng 100 Credits)'),
      soTrang: laNam ? 3600 : 300,
      uocChap: laNam ? '~180 chapters' : '~15 chapters',
      khuyenMai: laEn ? '50% OFF' : 'Giảm 50%',
      donGiaVnd: laNam ? '125đ/credit' : '163đ/credit',
      donGiaUsd: laNam ? '$0.0083/credit' : '$0.010/credit',
      diemManh: laEn
        ? [
            `${laNam ? '3,600 Credits / year' : '300 Credits / month'} (1 Credit = 1 Page · Rollover included)`,
            'Unlocks Full Clean + Typeset mode (`day_du`) & 4 Genre Fonts',
            'Use on Web Studio & Chrome Extension in 9 target languages',
          ]
        : [
            `${laNam ? '3.600 Credits / năm' : '300 Credits / tháng'} (1 Credit = 1 Trang · Cộng dồn khi gia hạn)`,
            'Mở khoá Xoá chữ Tái tạo nền (`day_du`) & 4 bộ Phông chữ thể loại',
            'Dùng trên Web Studio & Tiện ích Chrome (9 ngôn ngữ)',
          ],
      noiBat: false,
    },
    {
      ma: laNam ? 'pro_yearly' : 'pro_monthly',
      maNgan: laNam ? 'LITEYR' : 'PRO',
      nhan: laEn ? '⭐ LITE / READER' : '⭐ GÓI LITE / ĐỌC TRUYỆN',
      ten: laEn
        ? (laNam ? 'Lite Yearly (9,600 Credits)' : 'Lite Monthly (800 Credits)')
        : (laNam ? 'Gói Lite Năm (9.600 Credits)' : 'Gói Lite (800 Credits / tháng)'),
      giaGocVnd: laNam ? 1428000 : 149000,
      giaVnd: laNam ? 890000 : 99000,
      giaGocUsd: laNam ? '7.99' : '8.99',
      giaUsd: laNam ? '53.99' : '5.99',
      giaHienUsd: laNam ? '4.49' : '5.99',
      chuKy: laEn ? '/ month' : '/ tháng',
      phuChuKy: laNam
        ? (laEn ? 'Billed $53.99 yearly (Save 25%)' : 'Thanh toán 890k/năm (~74k/tháng · Giảm 25%)')
        : (laEn ? 'Billed monthly (30 days)' : 'Thanh toán hàng tháng (30 ngày)'),
      soTrang: laNam ? 9600 : 800,
      uocChap: laNam ? '~480 chapters' : '~40 chapters',
      khuyenMai: laNam ? (laEn ? 'Save 25%' : 'Tiết kiệm 25%') : (laEn ? '800 Credits' : '800 Credits'),
      donGiaVnd: laNam ? '92đ/credit' : '123đ/credit',
      donGiaUsd: laNam ? '$0.0056/credit' : '$0.0075/credit',
      diemManh: laEn
        ? [
            `${laNam ? '9,600 Credits / year' : '800 Credits / month'} (~40 chapters/mo · Rollover included)`,
            'Unlocks Windows App Continuous Multi-Chapter Auto-Crawl',
            'Unlocks Context AI Pro + Character & Pronoun Glossary',
            'Unlocks Batch Archive Upload (.ZIP, .CBZ, .PDF)',
          ]
        : [
            `${laNam ? '9.600 Credits / năm' : '800 Credits / tháng'} (~40 chapter/tháng · Cộng dồn khi gia hạn)`,
            'Mở khoá App Windows tải & dịch liên tục nhiều Chapter',
            'Mở khoá AI Chuẩn Ngữ Cảnh Pro + Từ điển Nhân vật & Xưng hô',
            'Mở khoá tải nguyên tập nén .ZIP, .CBZ, .PDF',
          ],
      noiBat: false,
    },
    {
      ma: laNam ? 'studio_yearly' : 'studio_monthly',
      maNgan: laNam ? 'STUDIOYR' : 'STUDIO',
      nhan: laEn ? '💎 STANDARD / STUDIO + API (BEST VALUE)' : '💎 TIÊU CHUẨN / STUDIO + API (ĐỀ XUẤT)',
      ten: laEn
        ? (laNam ? 'Standard + API Yearly (36,000 Credits)' : 'Standard + API (3,000 Credits)')
        : (laNam ? 'Gói Tiêu Chuẩn + API Năm (36.000 Credits)' : 'Gói Tiêu Chuẩn + API (3.000 Credits)'),
      giaGocVnd: laNam ? 2988000 : 399000,
      giaVnd: laNam ? 1790000 : 199000,
      giaGocUsd: laNam ? '14.99' : '19.99',
      giaUsd: laNam ? '89.99' : '9.99',
      giaHienUsd: laNam ? '7.49' : '9.99',
      chuKy: laEn ? '/ month' : '/ tháng',
      phuChuKy: laNam
        ? (laEn ? 'Billed $89.99 yearly (Save 50%)' : 'Thanh toán 1.790k/năm (~149k/tháng · Giảm 50%)')
        : (laEn ? '⚡ Only +$4 over Lite for 3.7x Credits + Free API!' : '⚡ Chỉ thêm $4 so với Lite nhưng nhận gấp 3.7 lần Credits + Mở API!'),
      soTrang: laNam ? 36000 : 3000,
      uocChap: laNam ? '~1,800 chapters' : '~150 chapters',
      khuyenMai: laEn ? 'Recommended + API' : 'Đề xuất + Mở API',
      donGiaVnd: laNam ? '49đ/credit' : '66đ/credit',
      donGiaUsd: laNam ? '$0.0025/credit' : '$0.0033/credit',
      diemManh: laEn
        ? [
            `${laNam ? '36,000 Credits / year' : '3,000 Credits / month'} (3.7x Lite credits for just +$4/mo!)`,
            '✅ Unlocks Personal Developer REST API Key (tr_live_...)',
            '✅ Unlocks Layered Photoshop (.PSD) Export & Video Review Studio',
            '✅ Priority Support + Cross-chapter Glossary consistency',
          ]
        : [
            `${laNam ? '36.000 Credits / năm' : '3.000 Credits / tháng'} (Gấp 3.7 lần gói Lite dù chỉ chênh $4!)`,
            '✅ Mở khoá Khoá Developer REST API riêng (tr_live_...)',
            '✅ Mở khoá Xuất file Photoshop (.PSD) tách lớp & Video Review Studio',
            '✅ Hỗ trợ ưu tiên + Đồng bộ thuật ngữ xuyên suốt các chương',
          ],
      noiBat: true,
    },
    {
      ma: laNam ? 'unlimited_yearly' : 'unlimited_plan',
      maNgan: laNam ? 'MAXYR' : 'UNLIMITED',
      nhan: laEn ? '🏢 PRO MAX / UNLIMITED API' : '🏢 GÓI PRO MAX / FULL API',
      ten: laEn
        ? (laNam ? 'Pro Max API Yearly (120,000 Credits)' : 'Pro Max API (10,000 Credits)')
        : (laNam ? 'Gói Pro Max API Năm (120.000 Credits)' : 'Gói Pro Max (10.000 Credits)'),
      giaGocVnd: laNam ? 5988000 : 799000,
      giaVnd: laNam ? 3590000 : 399000,
      giaGocUsd: laNam ? '29.99' : '39.99',
      giaUsd: laNam ? '179.99' : '19.99',
      giaHienUsd: laNam ? '14.99' : '19.99',
      chuKy: laEn ? '/ month' : '/ tháng',
      phuChuKy: laNam
        ? (laEn ? 'Billed $179.99 yearly (Save 50%)' : 'Thanh toán 3.590k/năm (~299k/tháng · Giảm 50%)')
        : (laEn ? '50% OFF Anchor Deal (10,000 Credits + VIP GPU)' : 'Ưu đãi giảm 50% (10.000 Credits + Luồng GPU VIP)'),
      soTrang: laNam ? 120000 : 10000,
      uocChap: laNam ? '~6,000 chapters' : '~500 chapters',
      khuyenMai: laEn ? '50% OFF + VIP API' : 'Giảm 50% + VIP API',
      donGiaVnd: laNam ? '29đ/credit' : '39đ/credit',
      donGiaUsd: laNam ? '$0.0015/credit' : '$0.0020/credit',
      diemManh: laEn
        ? [
            `${laNam ? '120,000 Credits / year' : '10,000 Credits / month'} (only $0.002/credit — 5 pages per cent!)`,
            '✅ Full Developer REST API Key (tr_live_...) + Highest GPU Priority',
            '✅ Unlocks Batch Chapter URL API (translate-chapter, up to 100 ch)',
            '✅ 0.15s High-Speed Image Cache + 1-on-1 Priority Engineering Support',
          ]
        : [
            `${laNam ? '120.000 Credits / năm' : '10.000 Credits / tháng'} (~500 chapter/tháng — chỉ 39đ/credit!)`,
            '✅ Full Khoá Developer REST API (tr_live_...) + Luồng GPU VIP cao nhất',
            '✅ Mở khoá API đẩy cả Chapter qua URL (translate-chapter, tới 100 chap)',
            '✅ Bộ nhớ đệm siêu tốc 0.15s + Hỗ trợ kỹ thuật 1-1 ưu tiên',
          ],
      noiBat: true,
    },
  ]

  const [goiDangChon, setGoiDangChon] = useState(DANH_SACH_GOI[2])

  useEffect(() => {
    setGoiDangChon(DANH_SACH_GOI[2])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang, chuKyGoi])

  const [daNhanThanhToanTuDong, setDaNhanThanhToanTuDong] = useState(null)

  useEffect(() => {
    let huy = false
    api.layThongTinNapLuot()
      .then((tt) => {
        if (!huy) setThongTinNap(tt)
      })
      .catch(() => {})
    return () => { huy = true }
  }, [])

  // Tự động kiểm tra định kỳ 5 giây/lần khi khách đang ở trang Bảng giá để phát hiện
  // ngay khoảnh khắc Webhook VietQR / PayPal IPN / Admin vừa cộng lượt thành công.
  useEffect(() => {
    if (!nguoiDung) return undefined
    let huy = false
    const luotBanDau = Number(thongTinNap?.so_luot_mua_them ?? -1)
    if (luotBanDau < 0) return undefined
    const timer = setInterval(async () => {
      try {
        const ttMoi = await api.layThongTinNapLuot()
        if (huy || !ttMoi) return
        const luotMoi = Number(ttMoi.so_luot_mua_them || 0)
        if (luotMoi > luotBanDau) {
          setThongTinNap(ttMoi)
          setDaNhanThanhToanTuDong({
            congThem: luotMoi - luotBanDau,
            tongMoi: luotMoi,
          })
        }
      } catch {
        // Bỏ qua lỗi mạng tạm thời khi polling
      }
    }, 5000)
    return () => {
      huy = true
      clearInterval(timer)
    }
  }, [nguoiDung, thongTinNap?.so_luot_mua_them])

  useEffect(() => {
    if (nguoiDung?.email) setEmailNhapTay(nguoiDung.email)
  }, [nguoiDung?.email])

  const emailHienTai = (nguoiDung?.email || emailNhapTay || '').trim()
  const maGoiNgan = goiDangChon.maNgan || 'PRO'
  const noiDungChuyenKhoan = emailHienTai
    ? `NAP ${maGoiNgan} ${emailHienTai}`
    : `NAP ${maGoiNgan} <EMAIL_CUA_BAN>`

  const nganHangTen = thongTinNap?.ngan_hang_ten || ''
  const nganHangSoTk = thongTinNap?.ngan_hang_so_tk || ''
  const nganHangChuTk = thongTinNap?.ngan_hang_chu_tk || ''
  const paypalEmail = (thongTinNap?.paypal_email || '').trim()
  const rapidapiUrl = (thongTinNap?.rapidapi_url || 'https://rapidapi.com/thientrieu753/api/ai-comic-manga-webtoon-translator').trim()
  const urlQr = nganHangTen && nganHangSoTk
    ? `https://img.vietqr.io/image/${encodeURIComponent(nganHangTen)}-${encodeURIComponent(nganHangSoTk)}-compact2.png?amount=${goiDangChon.giaVnd}&addInfo=${encodeURIComponent(noiDungChuyenKhoan)}&accountName=${encodeURIComponent(nganHangChuTk)}`
    : ''

  const notifyUrlPayPal = 'https://translation-api.vibe1.tinhgon.xyz/api/v1/nap-luot/paypal-ipn'
  const customPayPal = `${emailHienTai}|${goiDangChon.ma}`

  const urlPayPal = (() => {
    if (!paypalEmail) return ''
    if (/paypal\.me\//i.test(paypalEmail)) {
      const clean = paypalEmail.replace(/^https?:\/\//i, '').replace(/\/+$/, '')
      return `https://${clean}/${goiDangChon.giaUsd}USD`
    }
    if (paypalEmail.includes('@')) {
      const returnUrl = 'https://comic.io.vn/#bang-gia'
      return `https://www.paypal.com/cgi-bin/webscr?cmd=_xclick&business=${encodeURIComponent(paypalEmail)}&item_name=${encodeURIComponent(`${goiDangChon.ten} (${noiDungChuyenKhoan})`)}&item_number=${encodeURIComponent(goiDangChon.ma)}&custom=${encodeURIComponent(customPayPal)}&notify_url=${encodeURIComponent(notifyUrlPayPal)}&return=${encodeURIComponent(returnUrl)}&cancel_return=${encodeURIComponent(returnUrl)}&no_shipping=1&amount=${encodeURIComponent(goiDangChon.giaUsd)}&currency_code=USD`
    }
    return `https://paypal.me/${encodeURIComponent(paypalEmail)}/${goiDangChon.giaUsd}USD`
  })()

  function saoChepNoiDung() {
    navigator.clipboard?.writeText(noiDungChuyenKhoan)
    setDaChepNoiDung(true)
    setTimeout(() => setDaChepNoiDung(false), 2000)
  }

  async function bamXacNhanDaChuyenKhoan() {
    if (!nguoiDung) {
      if (onMoDangNhap) onMoDangNhap()
      return
    }
    setDangXacNhan(true)
    setLoiXacNhan('')
    try {
      const kq = await api.xacNhanChuyenKhoanGoi({
        ma_goi: goiDangChon.ma,
        ten_goi: goiDangChon.ten,
        so_tien_vnd: goiDangChon.giaVnd,
        so_trang: goiDangChon.soTrang,
        noi_dung_chuyen_khoan: noiDungChuyenKhoan,
      })
      setKetQuaDon(kq)
      const ttMoi = await api.layThongTinNapLuot().catch(() => null)
      if (ttMoi) setThongTinNap(ttMoi)
    } catch (err) {
      setLoiXacNhan(err?.message || 'Không thể gửi xác nhận lúc này.')
    } finally {
      setDangXacNhan(false)
    }
  }

  return (
    <main className="than-trang" style={{ maxWidth: 1180, margin: '0 auto', padding: '24px 16px 48px' }}>
      {/* Hero Banner */}
      <div style={{
        textAlign: 'center',
        padding: '28px 22px',
        marginBottom: 24,
        borderRadius: 20,
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(6, 78, 59, 0.9))',
        border: '1px solid rgba(16, 185, 129, 0.45)',
        color: '#f8fafc',
        boxShadow: '0 20px 45px rgba(2, 6, 23, 0.35)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
          <span style={{
            display: 'inline-block',
            background: 'rgba(16, 185, 129, 0.2)',
            color: '#34d399',
            border: '1px solid rgba(16, 185, 129, 0.45)',
            padding: '5px 14px',
            borderRadius: 999,
            fontSize: 12.5,
            fontWeight: 700,
          }}>
            💎 {laEn ? 'GLOBAL & VIETNAM PRICING (USD / VND)' : 'BẢNG GIÁ GÓI CƯỚC VIỆT NAM & QUỐC TẾ (VNĐ / USD)'}
          </span>
          <a
            href="#"
            onClick={(e) => {
              if (onQuayLai) {
                e.preventDefault()
                onQuayLai()
              }
            }}
            className="nut nut-phu"
          >
            ← {laEn ? 'Back to Translator' : 'Quay về Trang Dịch Truyện'}
          </a>
        </div>

        <h1 style={{ fontSize: 28, margin: '4px 0 10px', color: '#ffffff' }}>
          {laEn
            ? 'Up to 60% Cheaper Than Western Tools — Shared Across Web, Extension, App & API'
            : 'Chi Phí Siêu Tối Ưu — Dùng Chung Cho Web, Tiện Ích Chrome, App Windows & API'}
        </h1>
        <p style={{ maxWidth: 820, margin: '0 auto 18px', fontSize: 15, color: '#cbd5e1', lineHeight: 1.6 }}>
          {laEn
            ? '4 simple Monthly & Yearly plans with round credit quotas (300 / 800 / 3,000 / 10,000 Credits, 1 Credit = 1 Page). Developer API (tr_live_...) unlocked from Standard/Studio ($9.99/mo) & Pro Max ($19.99/mo). Unused credits roll over when renewed on time!'
            : '4 gói Tháng & Năm tinh gọn với số lượng Credits tròn trịa (300 / 800 / 3.000 / 10.000 Credits, 1 Credit = 1 Trang). Mở khoá Developer API (tr_live_...) từ gói Tiêu Chuẩn / Studio ($9.99/tháng) trở lên. Bảo lưu cộng dồn số dư nếu gia hạn trước hạn!'}
        </p>

        {/* Thanh chuyển đổi Chu kỳ (Monthly | Yearly -25%) và Tiền tệ (USD | VNĐ) */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ display: 'inline-flex', background: 'rgba(2, 6, 23, 0.65)', padding: 4, borderRadius: 999, border: '1px solid rgba(16, 185, 129, 0.45)' }}>
            <button
              type="button"
              onClick={() => setChuKyGoi('THANG')}
              style={{
                border: 'none',
                borderRadius: 999,
                padding: '7px 16px',
                fontSize: 13,
                fontWeight: 800,
                cursor: 'pointer',
                background: chuKyGoi === 'THANG' ? '#10b981' : 'transparent',
                color: chuKyGoi === 'THANG' ? '#052e16' : '#e2e8f0',
              }}
            >
              📅 {laEn ? 'Monthly' : 'Hàng tháng'}
            </button>
            <button
              type="button"
              onClick={() => setChuKyGoi('NAM')}
              style={{
                border: 'none',
                borderRadius: 999,
                padding: '7px 16px',
                fontSize: 13,
                fontWeight: 800,
                cursor: 'pointer',
                background: chuKyGoi === 'NAM' ? '#10b981' : 'transparent',
                color: chuKyGoi === 'NAM' ? '#052e16' : '#e2e8f0',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span>✨ {laEn ? 'Yearly' : 'Hàng năm'}</span>
              <span style={{
                background: '#f97316',
                color: '#fff',
                fontSize: 10.5,
                padding: '1px 6px',
                borderRadius: 999,
                fontWeight: 800,
              }}>
                {laEn ? 'Save 25%' : 'Tiết kiệm 25%'}
              </span>
            </button>
          </div>

          <div style={{ display: 'inline-flex', background: 'rgba(2, 6, 23, 0.65)', padding: 4, borderRadius: 999, border: '1px solid rgba(148,163,184,0.3)' }}>
            <button
              type="button"
              onClick={() => setTienTe('USD')}
              style={{
                border: 'none',
                borderRadius: 999,
                padding: '7px 14px',
                fontSize: 13,
                fontWeight: 800,
                cursor: 'pointer',
                background: tienTe === 'USD' ? '#38bdf8' : 'transparent',
                color: tienTe === 'USD' ? '#0f172a' : '#e2e8f0',
              }}
            >
              🌍 USD ($ Global)
            </button>
            <button
              type="button"
              onClick={() => setTienTe('VND')}
              style={{
                border: 'none',
                borderRadius: 999,
                padding: '7px 14px',
                fontSize: 13,
                fontWeight: 800,
                cursor: 'pointer',
                background: tienTe === 'VND' ? '#38bdf8' : 'transparent',
                color: tienTe === 'VND' ? '#0f172a' : '#e2e8f0',
              }}
            >
              🇻🇳 VNĐ (VietQR)
            </button>
          </div>
        </div>
      </div>

      {/* Lưới 4 gói cước trả phí (Hiển thị đúng 4 cột cân đối trên Desktop, kèm Giá gốc gạch ngang làm Mỏ neo) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(245px, 1fr))',
        gap: 16,
        marginBottom: 26,
      }}>
        {DANH_SACH_GOI.map((g) => {
          const dangChon = goiDangChon.ma === g.ma
          const hienGia = tienTe === 'USD'
            ? `$${g.giaHienUsd || g.giaUsd}`
            : `${g.giaVnd.toLocaleString('vi-VN')}đ`
          const hienGiaGoc = tienTe === 'USD'
            ? (g.giaGocUsd ? `$${g.giaGocUsd}` : '')
            : (g.giaGocVnd ? `${g.giaGocVnd.toLocaleString('vi-VN')}đ` : '')
          const hienDonGia = tienTe === 'USD' ? g.donGiaUsd : g.donGiaVnd
          const laMoNeoChinh = g.ma.includes('studio')
          return (
            <div
              key={g.ma}
              style={{
                borderRadius: 16,
                padding: '20px 16px',
                position: 'relative',
                background: dangChon
                  ? 'linear-gradient(160deg, rgba(15, 23, 42, 0.98), rgba(30, 58, 138, 0.92))'
                  : (laMoNeoChinh
                      ? 'linear-gradient(160deg, rgba(6, 78, 59, 0.45), rgba(15, 23, 42, 0.96))'
                      : 'rgba(15, 23, 42, 0.92)'),
                border: dangChon
                  ? '2px solid #38bdf8'
                  : (laMoNeoChinh
                      ? '2px solid #10b981'
                      : (g.noiBat ? '2px solid rgba(249, 115, 22, 0.7)' : '1px solid rgba(148, 163, 184, 0.28)')),
                color: '#f8fafc',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                boxShadow: dangChon ? '0 12px 30px rgba(56, 189, 248, 0.22)' : '0 8px 20px rgba(2, 6, 23, 0.25)',
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                  <span style={{
                    display: 'inline-block',
                    fontSize: 10.5,
                    fontWeight: 800,
                    padding: '3px 8px',
                    borderRadius: 999,
                    background: g.noiBat ? 'rgba(249, 115, 22, 0.2)' : 'rgba(148, 163, 184, 0.16)',
                    color: g.noiBat ? '#fb923c' : '#cbd5e1',
                  }}>
                    {g.nhan}
                  </span>
                  <span style={{
                    fontSize: 11,
                    fontWeight: 800,
                    color: '#34d399',
                    background: 'rgba(16, 185, 129, 0.16)',
                    padding: '2px 7px',
                    borderRadius: 999,
                  }}>
                    {g.khuyenMai}
                  </span>
                </div>

                <h2 style={{ margin: '0 0 6px', fontSize: 16.5, color: '#ffffff' }}>{g.ten}</h2>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 2, flexWrap: 'wrap' }}>
                  {hienGiaGoc && (
                    <span style={{
                      fontSize: 14,
                      fontWeight: 700,
                      color: '#64748b',
                      textDecoration: 'line-through',
                    }}>
                      {hienGiaGoc}
                    </span>
                  )}
                  <span style={{ fontSize: 24, fontWeight: 800, color: '#38bdf8' }}>{hienGia}</span>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>
                    {tienTe === 'USD' ? g.chuKy : (g.ma.includes('yearly') ? '/ năm' : '/ tháng')}
                  </span>
                </div>
                {g.phuChuKy && (
                  <div style={{ fontSize: 11.5, color: '#34d399', marginBottom: 4 }}>
                    {g.phuChuKy}
                  </div>
                )}
                <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 12 }}>
                  ⚡ <b>{g.soTrang.toLocaleString('vi-VN')} {laEn ? 'Credits (pages)' : 'Credits (trang)'}</b> ({g.uocChap}) · {hienDonGia}
                </div>

                <ul style={{ margin: '0 0 16px', paddingLeft: 18, fontSize: 12.8, lineHeight: 1.6, color: '#e2e8f0' }}>
                  {g.diemManh.map((dm, idx) => (
                    <li key={idx} style={{ marginBottom: 4 }}>{dm}</li>
                  ))}
                </ul>
              </div>

              <button
                type="button"
                className={dangChon ? 'nut-manga nut-manga-win' : (g.noiBat ? 'nut-manga nut-manga-chinh' : 'nut-manga nut-manga-phu')}
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => {
                  setGoiDangChon(g)
                  document.getElementById('khung-thanh-toan-qr')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
                }}
              >
                {dangChon
                  ? (laEn ? '✅ Selected below' : '✅ Đang chọn gói này')
                  : (laEn ? '💳 Select Plan' : '💳 Chọn Gói & Thanh Toán')}
              </button>
            </div>
          )
        })}
      </div>

      {/* Khung thanh toán 24/7 */}
      <section
        id="khung-thanh-toan-qr"
        style={{
          padding: '24px 22px',
          borderRadius: 18,
          background: 'linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 0.96))',
          border: '2px solid #10b981',
          color: '#f8fafc',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 24,
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 18px 40px rgba(16, 185, 129, 0.15)',
        }}
      >
        <div style={{ flex: '1 1 380px' }}>
          <div style={{ color: '#34d399', fontWeight: 800, fontSize: 15, marginBottom: 6 }}>
            ⚡ {laEn ? '24/7 AUTOMATIC ACTIVATION:' : 'THANH TOÁN & KÍCH HOẠT TỰ ĐỘNG 24/7:'} {goiDangChon.ten} ({tienTe === 'USD' ? `$${goiDangChon.giaUsd} USD` : `${goiDangChon.giaVnd.toLocaleString('vi-VN')} VNĐ`})
          </div>
          <p style={{ margin: '0 0 12px', fontSize: 14, color: '#cbd5e1', lineHeight: 1.6 }}>
            {laEn
              ? 'Scan the VietQR code or complete transfer below. Our automated webhook credits your account within 5–15 seconds!'
              : 'Quét mã VietQR bên phải hoặc chuyển khoản theo đúng nội dung bên dưới. Hệ thống Webhook sẽ tự động cộng ngay số trang vào tài khoản của bạn chỉ sau 5–15 giây!'}
          </p>

          {!nguoiDung && (
            <div style={{ marginBottom: 12 }}>
              <label htmlFor="o-email-nap" style={{ display: 'block', fontSize: 13, fontWeight: 700, color: '#fbbf24', marginBottom: 4 }}>
                📧 {laEn ? 'Enter your Account Email to generate your personal payment memo:' : 'Nhập Email tài khoản của bạn để mã QR tự điền đúng nội dung:'}
              </label>
              <input
                id="o-email-nap"
                type="email"
                value={emailNhapTay}
                onChange={(e) => setEmailNhapTay(e.target.value)}
                placeholder="vi-du@gmail.com"
                style={{
                  width: '100%',
                  maxWidth: 420,
                  padding: '9px 12px',
                  borderRadius: 8,
                  border: '1px solid #38bdf8',
                  background: '#0f172a',
                  color: '#fff',
                  fontSize: 14,
                }}
              />
            </div>
          )}

          <div style={{
            fontSize: 13.8,
            background: '#090d16',
            padding: '14px 16px',
            borderRadius: 12,
            border: '1px solid #334155',
            lineHeight: 1.75,
          }}>
            <div>
              🏦 {laEn ? 'Bank / Gateway:' : 'Ngân hàng:'} <b>{nganHangTen || 'VietQR / International Transfer'}</b>
              {nganHangSoTk ? <> · STK: <b style={{ color: '#38bdf8' }}>{nganHangSoTk}</b></> : null}
              {nganHangChuTk ? <> ({nganHangChuTk})</> : null}
            </div>
            <div>
              💰 {laEn ? 'Amount:' : 'Số tiền:'}{' '}
              <strong style={{ color: '#38bdf8', fontSize: 16 }}>
                {tienTe === 'USD'
                  ? `$${goiDangChon.giaUsd} USD (${goiDangChon.giaVnd.toLocaleString('vi-VN')} VNĐ)`
                  : `${goiDangChon.giaVnd.toLocaleString('vi-VN')} VNĐ ($${goiDangChon.giaUsd})`}
              </strong>{' '}
              ({laEn ? 'Receive' : 'Nhận'} <b>{goiDangChon.soTrang.toLocaleString('vi-VN')} {laEn ? 'pages' : 'trang'}</b>)
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 4 }}>
              <span>
                📝 {laEn ? 'Required Memo:' : 'Nội dung chuyển khoản bắt buộc:'}{' '}
                <code style={{ color: '#f97316', fontWeight: 800, fontSize: 15, background: 'rgba(249,115,22,0.12)', padding: '2px 8px', borderRadius: 6 }}>
                  {noiDungChuyenKhoan}
                </code>
              </span>
              <button
                type="button"
                onClick={saoChepNoiDung}
                style={{
                  padding: '4px 10px',
                  borderRadius: 6,
                  border: '1px solid #475569',
                  background: daChepNoiDung ? '#059669' : '#1e293b',
                  color: '#fff',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {daChepNoiDung ? (laEn ? '✅ Copied' : '✅ Đã chép') : (laEn ? '📋 Copy Memo' : '📋 Sao chép nội dung')}
              </button>
            </div>
          </div>

          <div style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
            {urlPayPal && (
              <a
                href={urlPayPal}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => {
                  if (nguoiDung) {
                    api.xacNhanChuyenKhoanGoi({
                      ma_goi: goiDangChon.ma,
                      ten_goi: goiDangChon.ten,
                      so_tien_vnd: goiDangChon.giaVnd,
                      so_trang: goiDangChon.soTrang,
                      noi_dung_chuyen_khoan: `PAYPAL $${goiDangChon.giaUsd} ${noiDungChuyenKhoan}`,
                    }).then((kq) => setKetQuaDon(kq)).catch(() => {})
                  }
                }}
                style={{
                  padding: '12px 20px',
                  borderRadius: 10,
                  border: '1px solid #38bdf8',
                  background: 'linear-gradient(135deg, #003087, #0070ba)',
                  color: '#ffffff',
                  fontSize: 14.5,
                  fontWeight: 800,
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  boxShadow: '0 8px 20px rgba(0, 112, 186, 0.35)',
                }}
              >
                🅿️ {laEn ? `Pay $${goiDangChon.giaUsd} USD via PayPal` : `Thanh toán $${goiDangChon.giaUsd} USD qua PayPal`} ↗
              </a>
            )}
            <button
              type="button"
              disabled={dangXacNhan}
              onClick={bamXacNhanDaChuyenKhoan}
              style={{
                padding: '12px 20px',
                borderRadius: 10,
                border: '1px solid #34d399',
                background: 'linear-gradient(135deg, #059669, #10b981)',
                color: '#ffffff',
                fontSize: 14.5,
                fontWeight: 800,
                cursor: dangXacNhan ? 'wait' : 'pointer',
                boxShadow: '0 8px 20px rgba(16, 185, 129, 0.35)',
              }}
            >
              {dangXacNhan
                ? (laEn ? '⏳ Recording & activating plan...' : '⏳ Đang ghi nhận & kích hoạt gói...')
                : (nguoiDung
                  ? (laEn
                      ? `✅ I have paid ${tienTe === 'USD' ? `$${goiDangChon.giaUsd}` : `${goiDangChon.giaVnd.toLocaleString('vi-VN')}đ`} — Activate Now`
                      : `✅ Tôi đã chuyển khoản ${goiDangChon.giaVnd.toLocaleString('vi-VN')}đ — Nhận Gói Ngay`)
                  : (laEn
                      ? '🔐 Sign In to Confirm Payment & Activate Plan'
                      : '🔐 Đăng nhập để Xác nhận Chuyển khoản & Nhận Gói Ngay'))}
            </button>
            <a
              href={rapidapiUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                padding: '11px 16px',
                borderRadius: 10,
                border: '1px solid rgba(148, 163, 184, 0.4)',
                background: 'rgba(30, 41, 59, 0.85)',
                color: '#e2e8f0',
                fontSize: 13.5,
                fontWeight: 700,
                textDecoration: 'none',
              }}
            >
              ⚡ {laEn ? 'Subscribe B2B API on RapidAPI Hub ↗' : 'Thuê API Quốc tế qua RapidAPI Hub ↗'}
            </a>
          </div>

          {daNhanThanhToanTuDong && (
            <div style={{
              marginTop: 12,
              padding: '14px 16px',
              borderRadius: 12,
              background: 'rgba(16, 185, 129, 0.24)',
              border: '2px solid #34d399',
              color: '#ecfdf5',
              fontSize: 14.5,
              fontWeight: 700,
              lineHeight: 1.65,
            }}>
              🎉 {laEn
                ? `PAYMENT CONFIRMED AUTOMATICALLY! +${daNhanThanhToanTuDong.congThem.toLocaleString('vi-VN')} pages added. New balance: ${daNhanThanhToanTuDong.tongMoi.toLocaleString('vi-VN')} pages.`
                : `ĐÃ NHẬN THANH TOÁN & NÂNG CẤP GÓI TỰ ĐỘNG THÀNH CÔNG! Hệ thống vừa cộng thêm +${daNhanThanhToanTuDong.congThem.toLocaleString('vi-VN')} trang. Số dư tích luỹ hiện tại: ${daNhanThanhToanTuDong.tongMoi.toLocaleString('vi-VN')} trang.`}
            </div>
          )}

          {loiXacNhan && (
            <div style={{
              marginTop: 10,
              padding: '10px 14px',
              borderRadius: 10,
              background: 'rgba(239, 68, 68, 0.16)',
              border: '1px solid rgba(248, 113, 113, 0.5)',
              color: '#fca5a5',
              fontSize: 13.5,
            }}>
              ⚠️ {loiXacNhan}
            </div>
          )}

          {ketQuaDon && (
            <div style={{
              marginTop: 12,
              padding: '14px 16px',
              borderRadius: 12,
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid #34d399',
              color: '#ecfdf5',
              fontSize: 13.8,
              lineHeight: 1.65,
            }}>
              <div style={{ fontWeight: 800, color: '#34d399', fontSize: 15 }}>
                🎉 {ketQuaDon.trang_thai === 'da_cong_tu_dong' || ketQuaDon.trang_thai === 'da_xac_nhan'
                  ? `ĐÃ KÍCH HOẠT GÓI THÀNH CÔNG (+${ketQuaDon.so_trang_cong.toLocaleString('vi-VN')} trang)!`
                  : 'ĐÃ GHI NHẬN ĐƠN CHUYỂN KHOẢN CỦA BẠN!'}
              </div>
              <div>
                • Mã đơn: <b>{ketQuaDon.ma_don}</b> · Gói: <b>{ketQuaDon.ten_goi}</b> ({ketQuaDon.so_tien_vnd.toLocaleString('vi-VN')}đ)
              </div>
              <div>
                • Tài khoản: <b>{ketQuaDon.email}</b> · Số trang tích luỹ hiện có:{' '}
                <b style={{ color: '#38bdf8' }}>{(thongTinNap?.so_luot_mua_them ?? ketQuaDon.so_trang_cong).toLocaleString('vi-VN')} trang</b>
              </div>
            </div>
          )}
        </div>

        {urlQr && (
          <div style={{
            background: '#ffffff',
            padding: 12,
            borderRadius: 14,
            textAlign: 'center',
            boxShadow: '0 10px 25px rgba(0,0,0,0.4)',
            margin: '0 auto',
          }}>
            <img
              src={urlQr}
              alt={`VietQR ${goiDangChon.ten}`}
              style={{ width: 210, height: 'auto', display: 'block', borderRadius: 8 }}
            />
            <div style={{ color: '#0f172a', fontWeight: 700, fontSize: 12, marginTop: 6 }}>
              {laEn ? 'Scan with Banking App (VietQR)' : 'Quét mã bằng App Ngân hàng'}
            </div>
          </div>
        )}
      </section>

      <div style={{ marginTop: 36 }}>
        <ChanTrangManga />
      </div>
    </main>
  )
}
