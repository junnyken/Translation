import { useEffect, useMemo, useState } from 'react'
import * as api from '../../api'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'
import ChanTrangManga from './ChanTrangManga'

const REVIEW_STATUSES = new Set(['needs_manual_review', 'underpaid', 'expired_late_payment'])

function dinhDangUsdTuCents(cents) {
  const n = Math.max(0, Number(cents) || 0)
  return (n / 100).toFixed(2)
}

export default function TrangBangGia({ nguoiDung, onQuayLai, onMoDangNhap }) {
  const { lang, laEn } = useNgonNguUI()
  const [thongTinNap, setThongTinNap] = useState(null)
  const [donHienTai, setDonHienTai] = useState(null)
  const [daChepMaDon, setDaChepMaDon] = useState(false)
  const [dangTaoDon, setDangTaoDon] = useState(false)
  const [dangChuyenCong, setDangChuyenCong] = useState('') // 'stripe' | 'paypal' | ''
  const [loiThanhToan, setLoiThanhToan] = useState('')
  const [thongBaoThanhToan, setThongBaoThanhToan] = useState('')
  const [tienTe, setTienTe] = useState('USD')
  const [chuKyGoi, setChuKyGoi] = useState('THANG')

  const laNam = chuKyGoi === 'NAM'
  const daTungNap = Boolean(thongTinNap?.da_tung_nap)

  // Map giá trực tiếp từ nguồn duy nhất của máy chủ (`GET /api/v1/thanh-toan/bang-gia`)
  const mapGoiMayChu = useMemo(() => {
    const m = new Map()
    const ds = Array.isArray(thongTinNap?.goi_goi_y) ? thongTinNap.goi_goi_y : []
    for (const item of ds) {
      if (item?.ma) m.set(item.ma, item)
    }
    return m
  }, [thongTinNap?.goi_goi_y])

  // Bảng Giá 4 Gói (Theo Tháng / Năm) — giá thực tế luôn đọc từ `mapGoiMayChu` khi có phản hồi máy chủ
  const DANH_SACH_GOI = useMemo(() => {
    const layGia = (ma, fallbackVnd, fallbackGocVnd, fallbackUsdCents, fallbackGocUsdCents, fallbackTrang) => {
      const sv = mapGoiMayChu.get(ma)
      const giaVnd = sv ? Number(sv.so_tien_vnd) : fallbackVnd
      const giaGocVnd = sv ? Number(sv.gia_goc_vnd || sv.so_tien_vnd) : fallbackGocVnd
      const usdCents = sv ? Number(sv.so_tien_usd_cents) : fallbackUsdCents
      const gocUsdCents = sv ? Number(sv.gia_goc_usd_cents || sv.so_tien_usd_cents) : fallbackGocUsdCents
      const soTrang = sv ? Number(sv.so_trang) : fallbackTrang
      const giaUsd = dinhDangUsdTuCents(usdCents)
      const giaGocUsd = dinhDangUsdTuCents(gocUsdCents)
      const giaHienUsd = laNam ? (usdCents / 100 / 12).toFixed(2) : giaUsd
      const giaHienGocUsd = laNam ? (gocUsdCents / 100 / 12).toFixed(2) : giaGocUsd
      return { giaVnd, giaGocVnd, giaUsd, giaGocUsd, giaHienUsd, giaHienGocUsd, soTrang }
    }

    const maStarter = laNam ? 'starter_yearly' : 'starter_monthly'
    const gStarter = layGia(
      maStarter,
      daTungNap ? (laNam ? 708000 : 89000) : (laNam ? 450000 : 49000),
      laNam ? 708000 : 89000,
      daTungNap ? (laNam ? 5988 : 649) : (laNam ? 2999 : 399),
      laNam ? 5988 : 649,
      laNam ? 3600 : 300,
    )

    const maPro = laNam ? 'pro_yearly' : 'pro_monthly'
    const gPro = layGia(
      maPro,
      daTungNap ? (laNam ? 1428000 : 149000) : (laNam ? 890000 : 99000),
      laNam ? 1428000 : 149000,
      daTungNap ? (laNam ? 9588 : 999) : (laNam ? 5399 : 699),
      laNam ? 9588 : 999,
      laNam ? 9600 : 800,
    )

    const maStudio = laNam ? 'studio_yearly' : 'studio_monthly'
    const gStudio = layGia(
      maStudio,
      daTungNap ? (laNam ? 2988000 : 389000) : (laNam ? 1790000 : 199000),
      laNam ? 2988000 : 389000,
      daTungNap ? (laNam ? 17988 : 1999) : (laNam ? 8999 : 1299),
      laNam ? 17988 : 1999,
      laNam ? 36000 : 3000,
    )

    const maMax = laNam ? 'unlimited_yearly' : 'unlimited_plan'
    const gMax = layGia(
      maMax,
      daTungNap ? (laNam ? 5988000 : 799000) : (laNam ? 3590000 : 399000),
      laNam ? 5988000 : 799000,
      daTungNap ? (laNam ? 35988 : 3999) : (laNam ? 17999 : 2499),
      laNam ? 35988 : 3999,
      laNam ? 120000 : 10000,
    )

    return [
      {
        ma: maStarter,
        nhan: daTungNap
          ? (laEn ? '🌱 STARTER' : '🌱 GÓI STARTER')
          : (laEn ? '🎁 FIRST-TIME OFFER' : '🎁 ƯU ĐÃI LẦN ĐẦU'),
        ten: laEn
          ? (laNam ? 'Starter Yearly (3,600 Credits)' : 'Starter (300 Credits)')
          : (laNam ? 'Gói Starter Năm (3.600 Credits)' : 'Gói Starter (300 Credits / tháng)'),
        ...gStarter,
        chuKy: laEn ? '/ month' : '/ tháng',
        phuChuKy: daTungNap
          ? (laEn ? '🔄 Standard Renewal Rate' : '🔄 Giá gia hạn tiêu chuẩn')
          : (laNam
              ? (laEn ? `🎁 1st Year $${gStarter.giaUsd} · Renews at $${gStarter.giaGocUsd}/yr` : `🎁 Năm đầu ${(gStarter.giaVnd / 1000).toLocaleString('vi-VN')}k · Gia hạn ${(gStarter.giaGocVnd / 1000).toLocaleString('vi-VN')}k/năm`)
              : (laEn ? `🎁 1st Month $${gStarter.giaUsd} · Renews at $${gStarter.giaGocUsd}/mo` : `🎁 Tháng đầu ${(gStarter.giaVnd / 1000).toLocaleString('vi-VN')}k · Gia hạn ${(gStarter.giaGocVnd / 1000).toLocaleString('vi-VN')}k`)),
        uocChap: laNam ? '~180 chapters' : '~15 chapters',
        khuyenMai: daTungNap ? '300 Credits' : (laEn ? 'First-time Promo' : 'Ưu đãi lần đầu'),
        donGiaVnd: `${Math.max(1, Math.round(gStarter.giaVnd / Math.max(1, gStarter.soTrang)))}đ/credit`,
        donGiaUsd: `$${(Number(gStarter.giaUsd) / Math.max(1, gStarter.soTrang)).toFixed(3)}/credit`,
        diemManh: laEn
          ? [
              `${laNam ? '3,600 Credits / year' : '300 Credits / month'} (1 Credit = 1 Page · 3h shaping: 90/3h)`,
              '🔑 Unlocks BYOK (Plug your Gemini/DeepSeek/Claude/GPT key → -50% Credits)',
              '🔓 Unlocks Context AI Dialogue mode (Local OCR + AI Text Context)',
              'Smart Speech Bubble Inpainting & 4 Comic Genre Fonts',
            ]
          : [
              `${laNam ? '3.600 Credits / năm' : '300 Credits / tháng'} (1 Credit = 1 Trang · Định hình 90 lượt/3 giờ)`,
              '🔑 Mở khoá cắm API Key riêng (BYOK -50% lượt tiêu hao)',
              '🔓 Mở khoá OCR Tách Chữ Trước + Dịch Hội Thoại AI Ngữ Cảnh',
              'Mở khoá Xoá chữ tái tạo nền bóng thoại & 4 bộ Phông chữ thể loại',
            ],
        noiBat: false,
      },
      {
        ma: maPro,
        nhan: laEn ? '⭐ TIER 2 · PRO / READER' : '⭐ GÓI 2 · LITE / ĐỌC TRUYỆN',
        ten: laEn
          ? (laNam ? 'Lite Yearly (9,600 Credits)' : 'Lite Monthly (800 Credits)')
          : (laNam ? 'Gói Lite Năm (9.600 Credits)' : 'Gói Lite (800 Credits / tháng)'),
        ...gPro,
        chuKy: laEn ? '/ month' : '/ tháng',
        phuChuKy: daTungNap
          ? (laEn ? '🔄 Standard Renewal Rate' : '🔄 Giá gia hạn tiêu chuẩn')
          : (laNam
              ? (laEn ? `🎁 1st Year $${gPro.giaUsd} · Renews at $${gPro.giaGocUsd}/yr` : `🎁 Năm đầu ${(gPro.giaVnd / 1000).toLocaleString('vi-VN')}k · Gia hạn ${(gPro.giaGocVnd / 1000).toLocaleString('vi-VN')}k/năm`)
              : (laEn ? `🎁 1st Month $${gPro.giaUsd} · Renews at $${gPro.giaGocUsd}/mo` : `🎁 Tháng đầu ${(gPro.giaVnd / 1000).toLocaleString('vi-VN')}k · Gia hạn ${(gPro.giaGocVnd / 1000).toLocaleString('vi-VN')}k`)),
        uocChap: laNam ? '~480 chapters' : '~40 chapters',
        khuyenMai: daTungNap ? '800 Credits' : (laEn ? 'First-time -30%' : 'Lần đầu -33%'),
        donGiaVnd: `${Math.max(1, Math.round(gPro.giaVnd / Math.max(1, gPro.soTrang)))}đ/credit`,
        donGiaUsd: `$${(Number(gPro.giaUsd) / Math.max(1, gPro.soTrang)).toFixed(4)}/credit`,
        diemManh: laEn
          ? [
              `${laNam ? '9,600 Credits / year' : '800 Credits / month'} (~40 chapters/mo · 3h shaping: 200/3h)`,
              '🔓 Unlocks Full Cloud Image Scan + Context AI Studio mode',
              'Unlocks Windows App Continuous Multi-Chapter Auto-Crawl',
              'Unlocks Context AI Pro + Character & Pronoun Glossary (.ZIP, .CBZ, .PDF)',
            ]
          : [
              `${laNam ? '9.600 Credits / năm' : '800 Credits / tháng'} (~40 chapter/tháng · Định hình 200 lượt/3 giờ)`,
              '🔓 Mở khoá Quét Ảnh Đám Mây (Scan Hình Ảnh) + AI Ngữ Cảnh Studio',
              'Mở khoá App Windows tải & dịch liên tục nhiều Chapter',
              'Mở khoá AI Chuẩn Ngữ Cảnh Pro + Từ điển Nhân vật (.ZIP, .CBZ, .PDF)',
            ],
        noiBat: false,
      },
      {
        ma: maStudio,
        nhan: laEn ? '💎 STANDARD / STUDIO + API (BEST VALUE)' : '💎 TIÊU CHUẨN / STUDIO + API (ĐỀ XUẤT)',
        ten: laEn
          ? (laNam ? 'Standard + API Yearly (36,000 Credits)' : 'Standard + API (3,000 Credits)')
          : (laNam ? 'Gói Tiêu Chuẩn + API Năm (36.000 Credits)' : 'Gói Tiêu Chuẩn + API (3.000 Credits)'),
        ...gStudio,
        chuKy: laEn ? '/ month' : '/ tháng',
        phuChuKy: daTungNap
          ? (laEn ? '🔄 Standard Renewal Rate (+API · 450/3h)' : '🔄 Giá gia hạn tiêu chuẩn (+Mở Cổng API · 450 lượt/3 giờ)')
          : (laNam
              ? (laEn ? `🎁 1st Year $${gStudio.giaUsd} · Renews at $${gStudio.giaGocUsd}/yr` : `🎁 Năm đầu ${(gStudio.giaVnd / 1000).toLocaleString('vi-VN')}k · Gia hạn ${(gStudio.giaGocVnd / 1000).toLocaleString('vi-VN')}k/năm`)
              : (laEn ? `⚡ 1st Month $${gStudio.giaUsd} (+API) · Renews at $${gStudio.giaGocUsd}` : `⚡ Tháng đầu ${(gStudio.giaVnd / 1000).toLocaleString('vi-VN')}k (+Mở API) · Gia hạn ${(gStudio.giaGocVnd / 1000).toLocaleString('vi-VN')}k`)),
        uocChap: laNam ? '~1,800 chapters' : '~150 chapters',
        khuyenMai: laEn ? 'Recommended + API' : 'Đề xuất + Mở API',
        donGiaVnd: `${Math.max(1, Math.round(gStudio.giaVnd / Math.max(1, gStudio.soTrang)))}đ/credit`,
        donGiaUsd: `$${(Number(gStudio.giaUsd) / Math.max(1, gStudio.soTrang)).toFixed(4)}/credit`,
        diemManh: laEn
          ? [
              `${laNam ? '36,000 Credits / year' : '3,000 Credits / month'} (3.7x Lite credits + Developer API · 450/3h)`,
              '✅ Unlocks Personal Developer REST API Key (tr_live_...)',
              '✅ Unlocks Layered Photoshop (.PSD) Export & Video Review Studio',
              '✅ Priority Support + Cross-chapter Glossary consistency',
            ]
          : [
              `${laNam ? '36.000 Credits / năm' : '3.000 Credits / tháng'} (Gấp 3.7 lần gói Lite + Mở Cổng API · 450 lượt/3 giờ)`,
              '✅ Mở khoá Khoá Developer REST API riêng (tr_live_...)',
              '✅ Mở khoá Xuất file Photoshop (.PSD) tách lớp & Video Review Studio',
              '✅ Hỗ trợ ưu tiên + Đồng bộ thuật ngữ xuyên suốt các chương',
            ],
        noiBat: true,
      },
      {
        ma: maMax,
        nhan: laEn ? '🏢 PRO MAX / UNLIMITED API' : '🏢 GÓI PRO MAX / FULL API',
        ten: laEn
          ? (laNam ? 'Pro Max API Yearly (120,000 Credits)' : 'Pro Max API (10,000 Credits)')
          : (laNam ? 'Gói Pro Max API Năm (120.000 Credits)' : 'Gói Pro Max (10.000 Credits)'),
        ...gMax,
        chuKy: laEn ? '/ month' : '/ tháng',
        phuChuKy: daTungNap
          ? (laEn ? '🔄 Standard Renewal Rate (10,000 Credits + VIP GPU · 900/3h)' : '🔄 Giá gia hạn tiêu chuẩn (10.000 Credits + GPU VIP · 900 lượt/3 giờ)')
          : (laNam
              ? (laEn ? `🎁 1st Year $${gMax.giaUsd} · Renews at $${gMax.giaGocUsd}/yr` : `🎁 Năm đầu ${(gMax.giaVnd / 1000).toLocaleString('vi-VN')}k · Gia hạn ${(gMax.giaGocVnd / 1000).toLocaleString('vi-VN')}k/năm`)
              : (laEn ? `🎁 1st Month $${gMax.giaUsd} · Renews at $${gMax.giaGocUsd}/mo` : `🎁 Tháng đầu ${(gMax.giaVnd / 1000).toLocaleString('vi-VN')}k · Gia hạn ${(gMax.giaGocVnd / 1000).toLocaleString('vi-VN')}k`)),
        uocChap: laNam ? '~6,000 chapters' : '~500 chapters',
        khuyenMai: daTungNap ? 'Full VIP API' : (laEn ? '1st Payment -50%' : 'Lần đầu -50%'),
        donGiaVnd: `${Math.max(1, Math.round(gMax.giaVnd / Math.max(1, gMax.soTrang)))}đ/credit`,
        donGiaUsd: `$${(Number(gMax.giaUsd) / Math.max(1, gMax.soTrang)).toFixed(4)}/credit`,
        diemManh: laEn
          ? [
              `${laNam ? '120,000 Credits / year' : '10,000 Credits / month'} (Highest volume for comic sites & teams)`,
              '✅ Full Developer REST API Key (tr_live_...) + Highest GPU Priority',
              '✅ Unlocks Batch Chapter URL API (translate-chapter, up to 100 ch)',
              '✅ 0.15s High-Speed Image Cache + 1-on-1 Priority Engineering Support',
            ]
          : [
              `${laNam ? '120.000 Credits / năm' : '10.000 Credits / tháng'} (~500 chapter/tháng cho Web truyện & Nhóm dịch)`,
              '✅ Full Khoá Developer REST API (tr_live_...) + Luồng GPU VIP cao nhất',
              '✅ Mở khoá API đẩy cả Chapter qua URL (translate-chapter, tới 100 chap)',
              '✅ Bộ nhớ đệm siêu tốc 0.15s + Hỗ trợ kỹ thuật 1-1 ưu tiên',
            ],
        noiBat: true,
      },
    ]
  }, [laNam, daTungNap, laEn, mapGoiMayChu])

  const [maGoiChon, setMaGoiChon] = useState('studio_monthly')
  const goiDangChon = useMemo(
    () => DANH_SACH_GOI.find((x) => x.ma === maGoiChon) || DANH_SACH_GOI[2],
    [DANH_SACH_GOI, maGoiChon],
  )

  // Khi chuyển chu kỳ Tháng <-> Năm, tự đổi mã gói tương ứng
  useEffect(() => {
    setMaGoiChon((cu) => {
      if (laNam) {
        if (cu === 'starter_monthly') return 'starter_yearly'
        if (cu === 'pro_monthly') return 'pro_yearly'
        if (cu === 'studio_monthly') return 'studio_yearly'
        if (cu === 'unlimited_plan') return 'unlimited_yearly'
      } else {
        if (cu === 'starter_yearly') return 'starter_monthly'
        if (cu === 'pro_yearly') return 'pro_monthly'
        if (cu === 'studio_yearly') return 'studio_monthly'
        if (cu === 'unlimited_yearly') return 'unlimited_plan'
      }
      return cu
    })
  }, [laNam, lang])

  // Nạp bảng giá + cờ cổng thanh toán từ máy chủ
  async function taiLaiBangGia() {
    try {
      const tt = await api.layBangGiaThanhToan()
      setThongTinNap(tt)
      return tt
    } catch {
      try {
        const ttCu = await api.layThongTinNapLuot()
        setThongTinNap(ttCu)
        return ttCu
      } catch {
        return null
      }
    }
  }

  useEffect(() => {
    taiLaiBangGia()
  }, [nguoiDung?.id])

  // Xử lý khi khách quay về từ Stripe Checkout hoặc PayPal Orders v2 (`?payment=...&order_id=...`)
  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const q = new URLSearchParams(window.location.search)
    const paymentAction = (q.get('payment') || '').trim()
    const orderId = (q.get('order_id') || '').trim()
    if (!paymentAction) return undefined

    // Dọn query khỏi thanh địa chỉ để F5 không gọi lặp
    try {
      const cleanUrl = `${window.location.pathname}#bang-gia`
      window.history.replaceState({}, '', cleanUrl)
    } catch {
      /* bỏ qua nếu môi trường test chặn history */
    }

    let huy = false
    ;(async () => {
      setLoiThanhToan('')
      if (paymentAction === 'paypal_return' && orderId) {
        setDangChuyenCong('paypal')
        try {
          // CHỈ truyền `order_id` NỘI BỘ của hệ thống, tuyệt đối không truyền PayPal token tuỳ ý!
          const kq = await api.capturePayPalOrder(orderId)
          if (huy) return
          if (kq?.order) setDonHienTai(kq.order)
          await taiLaiBangGia()
        } catch (err) {
          if (!huy) {
            setLoiThanhToan(err?.cauNguoiDoc || err?.message || 'Không thể xác nhận giao dịch PayPal.')
            // Thử đọc lại trạng thái đơn nội bộ nếu webhook đã xử lý
            const don = await api.layDonThanhToan(orderId).catch(() => null)
            if (!huy && don) setDonHienTai(don)
          }
        } finally {
          if (!huy) setDangChuyenCong('')
        }
      } else if (paymentAction === 'stripe_success' && orderId) {
        setThongBaoThanhToan(
          laEn
            ? 'Stripe checkout returned! Verifying webhook confirmation...'
            : 'Đã quay về từ cổng thẻ quốc tế Stripe! Đang xác nhận kích hoạt tự động...',
        )
        const don = await api.layDonThanhToan(orderId).catch(() => null)
        if (!huy && don) setDonHienTai(don)
        await taiLaiBangGia()
      } else if (paymentAction === 'paypal_cancel' || paymentAction === 'stripe_cancel') {
        setThongBaoThanhToan(
          laEn
            ? 'Checkout was canceled before payment. No charge was made.'
            : 'Bạn đã huỷ phiên thanh toán trước khi trừ tiền. Chưa phát sinh giao dịch nào.',
        )
        if (orderId) {
          await api.huyDonThanhToan(orderId).catch(() => null)
        }
      }
    })()

    return () => {
      huy = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nguoiDung?.id])

  // Hỏi trạng thái đơn `pending` định kỳ 4 giây/lần — DỪNG NGAY khi `paid` hoặc `needs_manual_review` (§7)
  useEffect(() => {
    if (!nguoiDung || !donHienTai?.id || donHienTai.status !== 'pending') return undefined
    let huy = false
    const timer = setInterval(async () => {
      try {
        const capNhat = await api.layDonThanhToan(donHienTai.id)
        if (huy || !capNhat) return
        setDonHienTai(capNhat)
        if (capNhat.status === 'paid') {
          await taiLaiBangGia()
        }
      } catch {
        /* bỏ qua lỗi mạng tạm thời khi polling */
      }
    }, 4000)
    return () => {
      huy = true
      clearInterval(timer)
    }
  }, [nguoiDung, donHienTai?.id, donHienTai?.status])

  const nganHangTen = thongTinNap?.ngan_hang_ten || donHienTai?.bank_name || ''
  const nganHangSoTk = thongTinNap?.ngan_hang_so_tk || donHienTai?.bank_account || ''
  const nganHangChuTk = thongTinNap?.ngan_hang_chu_tk || donHienTai?.bank_holder || ''
  const vietqrEnabled = Boolean(thongTinNap?.vietqr_enabled || (nganHangTen && nganHangSoTk))
  const stripeEnabled = Boolean(thongTinNap?.stripe_enabled)
  const paypalEnabled = Boolean(thongTinNap?.paypal_enabled)
  const rapidapiUrl = (
    thongTinNap?.rapidapi_url || 'https://rapidapi.com/thientrieu753/api/ai-comic-manga-webtoon-translator'
  ).trim()

  async function bamTaoDonVietQr(goiMucTieu = goiDangChon) {
    setLoiThanhToan('')
    setThongBaoThanhToan('')
    if (!nguoiDung) {
      if (onMoDangNhap) onMoDangNhap()
      return
    }
    setDangTaoDon(true)
    try {
      const don = await api.taoDonThanhToan({ plan: goiMucTieu.ma, rail: 'vietqr' })
      setDonHienTai(don)
      document.getElementById('khung-thanh-toan-qr')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    } catch (err) {
      setLoiThanhToan(err?.cauNguoiDoc || err?.message || 'Không thể tạo đơn thanh toán VietQR.')
    } finally {
      setDangTaoDon(false)
    }
  }

  async function bamThanhToanStripe() {
    setLoiThanhToan('')
    setThongBaoThanhToan('')
    if (!nguoiDung) {
      if (onMoDangNhap) onMoDangNhap()
      return
    }
    setDangChuyenCong('stripe')
    try {
      const kq = await api.taoStripeCheckout({ plan: goiDangChon.ma })
      if (kq?.order) setDonHienTai(kq.order)
      if (kq?.checkout_url) {
        window.location.assign(kq.checkout_url)
        return
      }
      setLoiThanhToan('Máy chủ chưa trả về liên kết Stripe Checkout.')
    } catch (err) {
      setLoiThanhToan(err?.cauNguoiDoc || err?.message || 'Không khởi tạo được phiên Stripe Checkout.')
    } finally {
      setDangChuyenCong('')
    }
  }

  async function bamThanhToanPayPal() {
    setLoiThanhToan('')
    setThongBaoThanhToan('')
    if (!nguoiDung) {
      if (onMoDangNhap) onMoDangNhap()
      return
    }
    setDangChuyenCong('paypal')
    try {
      const kq = await api.taoPayPalOrder({ plan: goiDangChon.ma })
      if (kq?.order) setDonHienTai(kq.order)
      if (kq?.approve_url) {
        window.location.assign(kq.approve_url)
        return
      }
      setLoiThanhToan('Máy chủ chưa trả về liên kết xác nhận PayPal.')
    } catch (err) {
      setLoiThanhToan(err?.cauNguoiDoc || err?.message || 'Không khởi tạo được đơn PayPal.')
    } finally {
      setDangChuyenCong('')
    }
  }

  async function bamHuyDonHienTai() {
    if (!donHienTai?.id) return
    try {
      const daHuy = await api.huyDonThanhToan(donHienTai.id)
      setDonHienTai(daHuy)
    } catch (err) {
      setLoiThanhToan(err?.cauNguoiDoc || err?.message || 'Không thể huỷ đơn thanh toán.')
    }
  }

  function saoChepMaDon() {
    if (!donHienTai?.code) return
    navigator.clipboard?.writeText(donHienTai.code)
    setDaChepMaDon(true)
    setTimeout(() => setDaChepMaDon(false), 2000)
  }

  const donKhongPhaiGoiDangChon =
    donHienTai && donHienTai.status === 'pending' && donHienTai.plan !== goiDangChon.ma

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
            💎 {laEn ? 'GLOBAL & VIETNAM PRICING (STRIPE · PAYPAL · VIETQR)' : 'BẢNG GIÁ VIỆT NAM & QUỐC TẾ (VIETQR · STRIPE · PAYPAL)'}
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
            ? 'Server-verified online checkout via VietQR (auto-credited in seconds), Stripe Cards, and PayPal Orders v2. Unused credits & days roll over when renewed on time!'
            : 'Thanh toán trực tuyến an toàn chuẩn quốc tế qua VietQR tự động (mã đơn CIO riêng biệt, khớp trong vài giây), Thẻ quốc tế Stripe và PayPal Orders v2. Cộng dồn ngày & số trang khi gia hạn đúng hạn!'}
        </p>

        {/* Thanh chuyển đổi Chu kỳ (Monthly | Yearly) và Tiền tệ (USD | VNĐ) */}
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
              🌍 USD (Stripe / PayPal)
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

      {/* Lưới 4 gói cước trả phí */}
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
          const hienGiaGoc = !daTungNap && (tienTe === 'USD' ? g.giaHienGocUsd !== g.giaHienUsd : g.giaGocVnd > g.giaVnd)
            ? (tienTe === 'USD'
                ? `$${g.giaHienGocUsd}`
                : `${g.giaGocVnd.toLocaleString('vi-VN')}đ`)
            : ''
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
                  setMaGoiChon(g.ma)
                  setLoiThanhToan('')
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

      {/* Khung Thanh Toán Trực Tuyến Chuẩn An Toàn */}
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
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          boxShadow: '0 18px 40px rgba(16, 185, 129, 0.15)',
        }}
      >
        <div style={{ flex: '1 1 420px' }}>
          <div style={{ color: '#34d399', fontWeight: 800, fontSize: 15.5, marginBottom: 6 }}>
            ⚡ {laEn ? 'SECURE ONLINE CHECKOUT:' : 'THANH TOÁN ONLINE & KÍCH HOẠT TỰ ĐỘNG 24/7:'}{' '}
            {goiDangChon.ten} ({tienTe === 'USD' ? `$${goiDangChon.giaUsd} USD` : `${goiDangChon.giaVnd.toLocaleString('vi-VN')} VNĐ`})
          </div>
          <p style={{ margin: '0 0 14px', fontSize: 13.8, color: '#cbd5e1', lineHeight: 1.6 }}>
            {laEn
              ? 'Every order is locked on our server with an exact price and unique order code (CIO...). Choose VietQR bank transfer, Stripe Card, or PayPal below.'
              : 'Mọi đơn thanh toán đều được máy chủ tạo mã đơn riêng (CIO...) và khoá chặt số tiền chuẩn. Chọn tạo mã VietQR tự động (khớp sau 5–15 giây), Thẻ quốc tế Stripe hoặc PayPal bên dưới.'}
          </p>

          {!nguoiDung ? (
            <div style={{
              padding: '16px 18px',
              borderRadius: 12,
              background: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.45)',
              marginBottom: 14,
            }}>
              <div style={{ fontWeight: 800, color: '#38bdf8', fontSize: 14.5, marginBottom: 6 }}>
                🔐 {laEn
                  ? 'Sign in first so your plan & credits are permanently bound to your account'
                  : 'Đăng nhập tài khoản để tạo mã đơn thanh toán riêng & nhận gói tự động'}
              </div>
              <p style={{ margin: '0 0 12px', fontSize: 13, color: '#cbd5e1', lineHeight: 1.55 }}>
                {laEn
                  ? 'For privacy & security, we never put your personal email or phone number inside bank transfer memos — each order uses a short Crockford code (CIOXXXXXXXX).'
                  : 'Để bảo mật tuyệt đối quyền riêng tư, hệ thống KHÔNG ghi email hay SĐT cá nhân vào nội dung chuyển khoản — mỗi đơn có một mã ngắn chuẩn CIOXXXXXXXX gắn trực tiếp với tài khoản của bạn.'}
              </p>
              <button
                type="button"
                onClick={() => onMoDangNhap && onMoDangNhap()}
                style={{
                  padding: '11px 20px',
                  borderRadius: 10,
                  border: '1px solid #38bdf8',
                  background: 'linear-gradient(135deg, #0284c7, #0ea5e9)',
                  color: '#fff',
                  fontSize: 14,
                  fontWeight: 800,
                  cursor: 'pointer',
                }}
              >
                🔐 {laEn ? 'Sign In / Create Free Account' : 'Đăng nhập / Tạo tài khoản ngay'}
              </button>
            </div>
          ) : (
            <>
              {/* Nút chọn 3 cổng thanh toán */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
                <button
                  type="button"
                  disabled={dangTaoDon || !vietqrEnabled}
                  onClick={() => bamTaoDonVietQr(goiDangChon)}
                  title={!vietqrEnabled ? 'Cổng VietQR đang chờ cấu hình số tài khoản' : ''}
                  style={{
                    padding: '12px 18px',
                    borderRadius: 10,
                    border: '1px solid #34d399',
                    background: vietqrEnabled
                      ? 'linear-gradient(135deg, #059669, #10b981)'
                      : 'rgba(51, 65, 85, 0.7)',
                    color: '#ffffff',
                    fontSize: 14,
                    fontWeight: 800,
                    cursor: !vietqrEnabled ? 'not-allowed' : (dangTaoDon ? 'wait' : 'pointer'),
                    opacity: vietqrEnabled ? 1 : 0.65,
                    boxShadow: vietqrEnabled ? '0 8px 20px rgba(16, 185, 129, 0.3)' : 'none',
                  }}
                >
                  {dangTaoDon
                    ? (laEn ? '⏳ Creating VietQR Order...' : '⏳ Đang tạo mã đơn VietQR...')
                    : (laEn
                        ? `🇻🇳 Pay ${goiDangChon.giaVnd.toLocaleString('vi-VN')}đ via VietQR`
                        : `🇻🇳 Tạo Mã QR Chuyển Khoản (${goiDangChon.giaVnd.toLocaleString('vi-VN')}đ)`)}
                </button>

                {stripeEnabled && (
                  <button
                    type="button"
                    disabled={Boolean(dangChuyenCong)}
                    onClick={bamThanhToanStripe}
                    style={{
                      padding: '12px 18px',
                      borderRadius: 10,
                      border: '1px solid #818cf8',
                      background: 'linear-gradient(135deg, #4f46e5, #6366f1)',
                      color: '#ffffff',
                      fontSize: 14,
                      fontWeight: 800,
                      cursor: dangChuyenCong ? 'wait' : 'pointer',
                      boxShadow: '0 8px 20px rgba(99, 102, 241, 0.35)',
                    }}
                  >
                    {dangChuyenCong === 'stripe'
                      ? (laEn ? '⏳ Opening Stripe...' : '⏳ Đang chuyển sang Stripe...')
                      : (laEn
                          ? `💳 Pay $${goiDangChon.giaUsd} via Card (Stripe)`
                          : `💳 Thẻ Quốc Tế Stripe ($${goiDangChon.giaUsd} USD)`)}
                  </button>
                )}

                {paypalEnabled && (
                  <button
                    type="button"
                    disabled={Boolean(dangChuyenCong)}
                    onClick={bamThanhToanPayPal}
                    style={{
                      padding: '12px 18px',
                      borderRadius: 10,
                      border: '1px solid #38bdf8',
                      background: 'linear-gradient(135deg, #003087, #0070ba)',
                      color: '#ffffff',
                      fontSize: 14,
                      fontWeight: 800,
                      cursor: dangChuyenCong ? 'wait' : 'pointer',
                      boxShadow: '0 8px 20px rgba(0, 112, 186, 0.35)',
                    }}
                  >
                    {dangChuyenCong === 'paypal'
                      ? (laEn ? '⏳ Connecting PayPal...' : '⏳ Đang kết nối PayPal...')
                      : (laEn
                          ? `🅿️ Pay $${goiDangChon.giaUsd} USD via PayPal`
                          : `🅿️ Thanh Toán PayPal ($${goiDangChon.giaUsd} USD)`)}
                  </button>
                )}

                <a
                  href={rapidapiUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    padding: '11px 15px',
                    borderRadius: 10,
                    border: '1px solid rgba(148, 163, 184, 0.4)',
                    background: 'rgba(30, 41, 59, 0.85)',
                    color: '#e2e8f0',
                    fontSize: 13,
                    fontWeight: 700,
                    textDecoration: 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                  }}
                >
                  ⚡ {laEn ? 'RapidAPI B2B Hub ↗' : 'Thuê API trên RapidAPI ↗'}
                </a>
              </div>

              {donKhongPhaiGoiDangChon && (
                <div style={{
                  marginBottom: 12,
                  padding: '9px 12px',
                  borderRadius: 10,
                  background: 'rgba(251, 191, 36, 0.14)',
                  border: '1px solid rgba(251, 191, 36, 0.45)',
                  color: '#fde68a',
                  fontSize: 13,
                }}>
                  ℹ️ {laEn
                    ? `Active order below (${donHienTai.code}) is for plan "${donHienTai.plan_name}". Click the VietQR/Stripe/PayPal button above to create an order for "${goiDangChon.ten}".`
                    : `Đơn đang mở bên dưới (${donHienTai.code}) thuộc gói "${donHienTai.plan_name}". Bấm nút Tạo Mã QR / Stripe / PayPal ở trên nếu muốn đổi sang "${goiDangChon.ten}".`}
                </div>
              )}

              {/* Chi tiết Đơn Thanh Toán đã được Server tạo & khoá giá */}
              {donHienTai && (
                <div style={{
                  fontSize: 13.8,
                  background: '#090d16',
                  padding: '15px 16px',
                  borderRadius: 12,
                  border: '1px solid #334155',
                  lineHeight: 1.75,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                    <span>
                      🧾 {laEn ? 'Order Code:' : 'Mã đơn nội bộ:'}{' '}
                      <code style={{ color: '#38bdf8', fontWeight: 800, fontSize: 15 }}>{donHienTai.code}</code>
                    </span>
                    <span style={{
                      fontSize: 12,
                      fontWeight: 800,
                      padding: '2px 9px',
                      borderRadius: 999,
                      background:
                        donHienTai.status === 'paid'
                          ? 'rgba(16, 185, 129, 0.2)'
                          : (REVIEW_STATUSES.has(donHienTai.status)
                              ? 'rgba(245, 158, 11, 0.22)'
                              : 'rgba(56, 189, 248, 0.16)'),
                      color:
                        donHienTai.status === 'paid'
                          ? '#34d399'
                          : (REVIEW_STATUSES.has(donHienTai.status) ? '#fbbf24' : '#38bdf8'),
                    }}>
                      {donHienTai.status === 'paid'
                        ? (laEn ? '✅ PAID & ACTIVATED' : '✅ ĐÃ THANH TOÁN & KÍCH HOẠT')
                        : (REVIEW_STATUSES.has(donHienTai.status)
                            ? (laEn ? '🔍 UNDER VERIFICATION (24H)' : '🔍 ĐANG KIỂM TRA ĐỐI SOÁT (24H)')
                            : (donHienTai.status === 'pending'
                                ? (laEn ? '⏳ WAITING FOR PAYMENT...' : '⏳ ĐANG CHỜ NHẬN TIỀN TỰ ĐỘNG...')
                                : donHienTai.status.toUpperCase()))}
                    </span>
                  </div>

                  {donHienTai.rail === 'vietqr' && (
                    <div>
                      🏦 {laEn ? 'Receiving Bank:' : 'Ngân hàng nhận:'}{' '}
                      <b>{donHienTai.bank_name || nganHangTen}</b>
                      {(donHienTai.bank_account || nganHangSoTk) ? (
                        <> · STK: <b style={{ color: '#38bdf8' }}>{donHienTai.bank_account || nganHangSoTk}</b></>
                      ) : null}
                      {(donHienTai.bank_holder || nganHangChuTk) ? (
                        <> ({donHienTai.bank_holder || nganHangChuTk})</>
                      ) : null}
                    </div>
                  )}

                  <div>
                    💰 {laEn ? 'Exact Locked Amount:' : 'Số tiền cần chuyển đúng:'}{' '}
                    <strong style={{ color: '#38bdf8', fontSize: 16 }}>
                      {donHienTai.amount_display}
                    </strong>{' '}
                    ({laEn ? 'Receive' : 'Nhận'} <b>{Number(donHienTai.credits || 0).toLocaleString('vi-VN')} {laEn ? 'Credits' : 'trang'}</b> · {donHienTai.duration_days} {laEn ? 'days' : 'ngày'})
                  </div>

                  {donHienTai.rail === 'vietqr' && donHienTai.status === 'pending' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 6 }}>
                      <span>
                        📝 {laEn ? 'Required Transfer Memo (Exact Code):' : 'Nội dung chuyển khoản bắt buộc (ghi đúng mã):'}{' '}
                        <code style={{
                          color: '#f97316',
                          fontWeight: 800,
                          fontSize: 15.5,
                          background: 'rgba(249,115,22,0.14)',
                          padding: '2px 9px',
                          borderRadius: 6,
                        }}>
                          {donHienTai.code}
                        </code>
                      </span>
                      <button
                        type="button"
                        onClick={saoChepMaDon}
                        style={{
                          padding: '4px 10px',
                          borderRadius: 6,
                          border: '1px solid #475569',
                          background: daChepMaDon ? '#059669' : '#1e293b',
                          color: '#fff',
                          fontSize: 12,
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        {daChepMaDon
                          ? (laEn ? '✅ Copied Code' : '✅ Đã chép mã đơn')
                          : (laEn ? '📋 Copy Order Code' : '📋 Sao chép mã đơn')}
                      </button>
                      <button
                        type="button"
                        onClick={bamHuyDonHienTai}
                        style={{
                          padding: '4px 10px',
                          borderRadius: 6,
                          border: '1px solid rgba(248,113,113,0.45)',
                          background: 'transparent',
                          color: '#fca5a5',
                          fontSize: 12,
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        {laEn ? 'Cancel order' : 'Huỷ đơn này'}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Trạng thái thành công `paid` */}
          {donHienTai?.status === 'paid' && (
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
                ? `PAYMENT COMPLETED (${donHienTai.code})! +${Number(donHienTai.credits || 0).toLocaleString('vi-VN')} Credits activated. Total purchased balance: ${Number(thongTinNap?.so_luot_mua_them || donHienTai.credits || 0).toLocaleString('vi-VN')} pages.`
                : `ĐÃ NHẬN THANH TOÁN & KÍCH HOẠT GÓI THÀNH CÔNG (${donHienTai.code})! Đã cộng +${Number(donHienTai.credits || 0).toLocaleString('vi-VN')} trang. Số dư tích luỹ hiện tại: ${Number(thongTinNap?.so_luot_mua_them || donHienTai.credits || 0).toLocaleString('vi-VN')} trang.`}
            </div>
          )}

          {/* §7: Trạng thái `needs_manual_review` / `underpaid` / `expired_late_payment` — DỪNG vòng xoay chờ, báo rõ 24h! */}
          {donHienTai && REVIEW_STATUSES.has(donHienTai.status) && (
            <div style={{
              marginTop: 12,
              padding: '14px 16px',
              borderRadius: 12,
              background: 'rgba(245, 158, 11, 0.18)',
              border: '2px solid #fbbf24',
              color: '#fef3c7',
              fontSize: 14,
              fontWeight: 700,
              lineHeight: 1.65,
            }}>
              🔍 {laEn
                ? `Your payment for order ${donHienTai.code} is under verification — our team has been alerted and will contact/activate within 24 hours.`
                : `Thanh toán đang được kiểm tra, chúng tôi sẽ liên hệ trong 24h (Mã đơn đối soát: ${donHienTai.code}). Quản trị viên đã nhận cảnh báo tự động!`}
            </div>
          )}

          {thongBaoThanhToan && !loiThanhToan && (
            <div style={{
              marginTop: 10,
              padding: '10px 14px',
              borderRadius: 10,
              background: 'rgba(56, 189, 248, 0.14)',
              border: '1px solid rgba(56, 189, 248, 0.45)',
              color: '#bae6fd',
              fontSize: 13.5,
            }}>
              ℹ️ {thongBaoThanhToan}
            </div>
          )}

          {loiThanhToan && (
            <div style={{
              marginTop: 10,
              padding: '11px 14px',
              borderRadius: 10,
              background: 'rgba(239, 68, 68, 0.16)',
              border: '1px solid rgba(248, 113, 113, 0.55)',
              color: '#fca5a5',
              fontSize: 13.5,
              lineHeight: 1.55,
            }}>
              ⚠️ {loiThanhToan}
            </div>
          )}
        </div>

        {/* Ảnh VietQR do chính Server sinh kèm số tiền khoá & mã đơn `CIOXXXXXXXX` */}
        {donHienTai?.vietqr_url && donHienTai.status === 'pending' && (
          <div style={{
            background: '#ffffff',
            padding: 12,
            borderRadius: 14,
            textAlign: 'center',
            boxShadow: '0 10px 25px rgba(0,0,0,0.4)',
            margin: '0 auto',
          }}>
            <img
              src={donHienTai.vietqr_url}
              alt={`VietQR ${donHienTai.code}`}
              style={{ width: 215, height: 'auto', display: 'block', borderRadius: 8 }}
            />
            <div style={{ color: '#0f172a', fontWeight: 800, fontSize: 12.5, marginTop: 6 }}>
              {donHienTai.code} · {donHienTai.amount_display}
            </div>
            <div style={{ color: '#475569', fontWeight: 600, fontSize: 11.5, marginTop: 2 }}>
              {laEn ? 'Scan with Banking App (Auto-fills exact memo)' : 'Quét bằng App Ngân hàng (Tự điền đúng mã CIO)'}
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
