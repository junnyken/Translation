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

  // Phương án A (International-First): 1 Bảng Giá 5 Gói Chuẩn Quốc Tế (USD hiển thị mặc định, lượt không hết hạn qua đêm)
  // Cổng Developer API (tr_live_...) mở từ Gói Cấp 4 (Studio - $14.99) và Cấp 5 (Unlimited - $19.99) trở lên.
  const DANH_SACH_GOI = [
    {
      ma: 'trial_pack_50',
      maNgan: 'MOI',
      nhan: laEn ? '🌱 LEVEL 1 — TRIAL' : '🌱 CẤP 1 — GÓI TRIAL',
      ten: laEn ? 'Trial Pack (50 Pages)' : 'Gói Trial (50 trang)',
      giaVnd: 19000,
      giaUsd: '1.99',
      chuKy: laEn ? 'never expires' : 'không hết hạn',
      soTrang: 50,
      uocChap: '~2.5 chapters',
      khuyenMai: laEn ? 'Level 1' : 'Cấp 1 (Trial)',
      donGiaVnd: '380đ/trang',
      donGiaUsd: '$0.040/page',
      diemManh: laEn
        ? [
            '50 AI-translated comic pages (never expires overnight)',
            'Unlocks Full Clean + Typeset mode (`day_du`) & 4 Genre Fonts',
            'Use on Web Studio & Chrome Extension in 9 target languages',
          ]
        : [
            '50 trang dịch AI tích luỹ (không bao giờ hết hạn qua đêm)',
            'Mở khoá Xoá chữ Tái tạo nền (`day_du`) & 4 bộ Phông chữ thể loại',
            'Dùng trên Web Studio & Tiện ích Chrome (9 ngôn ngữ)',
          ],
      noiBat: false,
    },
    {
      ma: 'starter_monthly',
      maNgan: 'STARTER',
      nhan: laEn ? '⭐ LEVEL 2 — LITE / STARTER' : '⭐ CẤP 2 — GÓI LITE / STARTER',
      ten: laEn ? 'Lite Pack (200 Pages)' : 'Gói Lite / Starter (200 trang)',
      giaVnd: 49000,
      giaUsd: '4.99',
      chuKy: laEn ? 'never expires' : 'không hết hạn',
      soTrang: 200,
      uocChap: '~10 chapters',
      khuyenMai: laEn ? 'Save 38%' : 'Tiết kiệm 38%',
      donGiaVnd: '245đ/trang',
      donGiaUsd: '$0.025/page',
      diemManh: laEn
        ? [
            '200 permanent AI pages (~10 chapters) — never expires',
            'Full Clean + Typeset mode & Double-click live bubble editor',
            '4 Genre Fonts (Action, Romance, Historical, Classic Comic)',
          ]
        : [
            '200 trang dịch AI tích luỹ (~10 chapter) — không hết hạn',
            'Đầy đủ Xoá chữ + Dàn trang & Nhấp đúp sửa câu trực tiếp',
            '4 bộ Font thể loại (Hành động, Ngôn tình, Cổ trang, Comic)',
          ],
      noiBat: false,
    },
    {
      ma: 'pro_monthly',
      maNgan: 'PRO',
      nhan: laEn ? '🔥 LEVEL 3 — PRO READER' : '🔥 CẤP 3 — GÓI PRO CÀY TRUYỆN',
      ten: laEn ? 'Pro Pack (600 Pages)' : 'Gói Pro Cày Truyện (600 trang)',
      giaVnd: 99000,
      giaUsd: '9.99',
      chuKy: laEn ? 'never expires' : 'không hết hạn',
      soTrang: 600,
      uocChap: '~30 chapters',
      khuyenMai: laEn ? 'Popular' : 'Phổ biến',
      donGiaVnd: '165đ/trang',
      donGiaUsd: '$0.016/page',
      diemManh: laEn
        ? [
            '600 permanent AI pages (~30 chapters) — only $0.016/page',
            'Unlocks Windows App Continuous Multi-Chapter Auto-Crawl',
            'Unlocks Context AI Pro + Character & Pronoun Glossary',
            'Unlocks Batch Archive Upload (.ZIP, .CBZ, .PDF)',
          ]
        : [
            '600 trang tích luỹ vĩnh viễn (~30 chapter) — chỉ 165đ/trang',
            'Mở khoá App Windows tải & dịch liên tục nhiều Chapter',
            'Mở khoá AI Chuẩn Ngữ Cảnh Pro + Từ điển Nhân vật & Xưng hô',
            'Mở khoá tải nguyên tập nén .ZIP, .CBZ, .PDF',
          ],
      noiBat: true,
    },
    {
      ma: 'studio_monthly',
      maNgan: 'STUDIO',
      nhan: laEn ? '💎 LEVEL 4 — STUDIO + API (RECOMMENDED)' : '💎 CẤP 4 — STUDIO + API (ĐỀ XUẤT)',
      ten: laEn ? 'Studio + API (2,000 Pages)' : 'Gói Studio + API (2.000 trang)',
      giaVnd: 199000,
      giaUsd: '14.99',
      chuKy: laEn ? 'never expires' : 'không hết hạn',
      soTrang: 2000,
      uocChap: '~100 chapters',
      khuyenMai: laEn ? 'API + Best Value' : 'Đề xuất + Mở API',
      donGiaVnd: '99đ/trang',
      donGiaUsd: '$0.007/page',
      diemManh: laEn
        ? [
            '2,000 permanent AI pages (~100 chapters) for teams & developers',
            '✅ Unlocks Personal Developer REST API Key (tr_live_...)',
            '✅ Unlocks Layered Photoshop (.PSD) Export & Video Review Studio',
            '✅ Priority Support + Cross-chapter Glossary consistency',
          ]
        : [
            '2.000 trang tích luỹ vĩnh viễn (~100 chapter) — chỉ 99đ/trang',
            '✅ Mở khoá Khoá Developer REST API riêng (tr_live_...)',
            '✅ Mở khoá Xuất file Photoshop (.PSD) tách lớp & Video Review Studio',
            '✅ Hỗ trợ ưu tiên + Đồng bộ thuật ngữ xuyên suốt các chương',
          ],
      noiBat: true,
    },
    {
      ma: 'unlimited_plan',
      maNgan: 'UNLIMITED',
      nhan: laEn ? '🏢 LEVEL 5 — PRO MAX / UNLIMITED API' : '🏢 CẤP 5 — UNLIMITED + FULL API PRO',
      ten: laEn ? 'Unlimited API (5,000 Pages)' : 'Gói Unlimited (5.000 trang + API)',
      giaVnd: 399000,
      giaUsd: '19.99',
      chuKy: laEn ? 'never expires' : 'không hết hạn',
      soTrang: 5000,
      uocChap: '~250 chapters',
      khuyenMai: laEn ? 'Save 90% + Full API' : 'Full API + GPU VIP',
      donGiaVnd: '~79đ/trang',
      donGiaUsd: '$0.004/page',
      diemManh: laEn
        ? [
            '5,000 permanent pages (~250 chapters — only $0.004/page)',
            '✅ Full Developer REST API Key (tr_live_...) + Highest GPU Priority',
            '✅ Unlocks Batch Chapter URL API (translate-chapter, up to 100 ch)',
            '✅ 0.15s High-Speed Image Cache + 1-on-1 Priority Engineering Support',
          ]
        : [
            '5.000 trang tích luỹ vĩnh viễn (~250 chapter — chỉ ~79đ/trang)',
            '✅ Full Khoá Developer REST API (tr_live_...) + Luồng GPU VIP cao nhất',
            '✅ Mở khoá API đẩy cả Chapter qua URL (translate-chapter, tới 100 chap)',
            '✅ Bộ nhớ đệm siêu tốc 0.15s + Hỗ trợ kỹ thuật 1-1 ưu tiên',
          ],
      noiBat: true,
    },
  ]

  const [goiDangChon, setGoiDangChon] = useState(DANH_SACH_GOI[3])

  useEffect(() => {
    setGoiDangChon(DANH_SACH_GOI[3])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

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
            ? '5 clear tiers by page volume & feature level (from $1.99 / 50 pages, API access from Studio $14.99+). Pages never expire overnight — only deducted when you translate. Instant 24/7 activation.'
            : '5 gói nâng cấp rõ ràng theo Số Trang & Cấp Độ Tính Năng (hiển thị chuẩn Quốc tế USD, mở khoá Developer API từ gói Studio trở lên). Lượt mua không bao giờ mất qua đêm — kích hoạt tự động 24/7.'}
        </p>

        {/* Thanh chuyển đổi Tiền tệ: Ưu tiên USD ($ Global) đứng trước */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap', alignItems: 'center' }}>
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

      {/* Tầng miễn phí mỗi ngày */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
        gap: 16,
        marginBottom: 24,
      }}>
        <div style={{
          background: 'rgba(15, 23, 42, 0.9)',
          border: '1px solid rgba(148, 163, 184, 0.28)',
          borderRadius: 14,
          padding: '16px 18px',
          color: '#e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#94a3b8' }}>
              👤 {laEn ? 'GUEST USER (NO SIGN-UP)' : 'KHÁCH VÃNG LAI (KHÔNG CẦN ĐĂNG KÝ)'}
            </div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#ffffff', marginTop: 2 }}>
              {laEn ? 'Free 2 Pages / Day' : 'Miễn phí 2 trang / ngày'}
            </div>
            <div style={{ fontSize: 13, color: '#cbd5e1' }}>
              {laEn ? 'Test translation quality immediately on Web or Extension.' : 'Dùng thử ngay trên Web hoặc Tiện ích Chrome không cần tạo tài khoản.'}
            </div>
          </div>
          <span style={{ fontSize: 22, fontWeight: 800, color: '#94a3b8' }}>
            {tienTe === 'USD' ? '$0' : '0đ'}
          </span>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.92), rgba(15, 23, 42, 0.94))',
          border: '1px solid rgba(129, 140, 248, 0.45)',
          borderRadius: 14,
          padding: '16px 18px',
          color: '#e2e8f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#818cf8' }}>
              ✨ {laEn ? 'FREE REGISTERED ACCOUNT' : 'TÀI KHOẢN ĐĂNG KÝ MIỄN PHÍ'}
            </div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#ffffff', marginTop: 2 }}>
              {laEn ? 'Free 10 Pages / Day' : 'Miễn phí 10 trang / ngày'}
            </div>
            <div style={{ fontSize: 13, color: '#cbd5e1' }}>
              {laEn ? 'Resets automatically at 00:00 GMT+7 every day.' : 'Tự động hồi lại 10 trang mới vào 00:00 mỗi ngày. Chỉ mất 5 giây đăng ký.'}
            </div>
          </div>
          {!nguoiDung && onMoDangNhap ? (
            <button type="button" className="nut-manga nut-manga-chinh" onClick={onMoDangNhap} style={{ whiteSpace: 'nowrap' }}>
              {laEn ? 'Sign Up Free' : 'Đăng ký nhận 10 trang'}
            </button>
          ) : (
            <span style={{ fontSize: 14, fontWeight: 700, color: '#34d399', whiteSpace: 'nowrap' }}>
              ✅ {laEn ? 'Active' : 'Đang kích hoạt'}
            </span>
          )}
        </div>
      </div>

      {/* Lưới gói cước trả phí */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(215px, 1fr))',
        gap: 14,
        marginBottom: 26,
      }}>
        {DANH_SACH_GOI.map((g) => {
          const dangChon = goiDangChon.ma === g.ma
          const hienGia = tienTe === 'USD'
            ? `$${g.giaUsd}`
            : `${g.giaVnd.toLocaleString('vi-VN')}đ`
          const hienDonGia = tienTe === 'USD' ? g.donGiaUsd : g.donGiaVnd
          return (
            <div
              key={g.ma}
              style={{
                borderRadius: 16,
                padding: '20px 16px',
                background: dangChon
                  ? 'linear-gradient(160deg, rgba(15, 23, 42, 0.98), rgba(30, 58, 138, 0.92))'
                  : 'rgba(15, 23, 42, 0.92)',
                border: dangChon
                  ? '2px solid #38bdf8'
                  : (g.noiBat ? '2px solid rgba(249, 115, 22, 0.7)' : '1px solid rgba(148, 163, 184, 0.28)'),
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
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 2 }}>
                  <span style={{ fontSize: 24, fontWeight: 800, color: '#38bdf8' }}>{hienGia}</span>
                  <span style={{ fontSize: 12, color: '#94a3b8' }}>{g.chuKy}</span>
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 12 }}>
                  ⚡ <b>{g.soTrang.toLocaleString('vi-VN')} {laEn ? 'pages' : 'trang'}</b> ({g.uocChap}) · {hienDonGia}
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
