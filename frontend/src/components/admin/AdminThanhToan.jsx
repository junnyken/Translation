import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Button from '../ui/Button.jsx'

const PLAN_OPTIONS = [
  { value: '', label: '— Tự động theo đơn / Chọn gói nếu chuyển khoản lẻ —' },
  { value: 'trial_pack_50', label: 'trial_pack_50 (150 Credits · Cấp 1)' },
  { value: 'starter_monthly', label: 'starter_monthly (300 Credits · Cấp 2)' },
  { value: 'pro_monthly', label: 'pro_monthly (800 Credits · Cấp 3)' },
  { value: 'studio_monthly', label: 'studio_monthly (3.000 Credits + API · Cấp 4)' },
  { value: 'unlimited_plan', label: 'unlimited_plan (10.000 Credits + API · Cấp 5)' },
  { value: 'starter_yearly', label: 'starter_yearly (3.600 Credits/năm · Cấp 2)' },
  { value: 'pro_yearly', label: 'pro_yearly (9.600 Credits/năm · Cấp 3)' },
  { value: 'studio_yearly', label: 'studio_yearly (36.000 Credits/năm · Cấp 4)' },
  { value: 'unlimited_yearly', label: 'unlimited_yearly (120.000 Credits/năm · Cấp 5)' },
]

/**
 * AdminThanhToan — Quản trị cổng thanh toán chuẩn an toàn (VietQR/SePay HMAC, Stripe, PayPal Orders v2,
 * Cảnh báo Telegram) + Hàng chờ "Giao dịch cần duyệt tay" (`payment_reviews`) & Lịch sử đơn nạp.
 */
export default function AdminThanhToan({ thongKe, onNap, setLoi, setThongBaoOk }) {
  const { laEn } = useNgonNguUI()

  const apiOrigin =
    api.API_BASE ||
    (typeof window !== 'undefined' ? window.location.origin : 'https://translation-api.vibe1.tinhgon.xyz')

  // Trạng thái cấu hình đọc từ `/quan-tri/thanh-toan/cau-hinh` (secret luôn được che mặt nạ)
  const [cauHinhServer, setCauHinhServer] = useState(null)
  const [dangTaiCauHinh, setDangTaiCauHinh] = useState(false)
  const [dangLuu, setDangLuu] = useState(false)
  const [dangKiemBot, setDangKiemBot] = useState(false)
  const [dangKiemPaypal, setDangKiemPaypal] = useState(false)

  // VietQR + SePay HMAC-SHA256
  const [nhTen, setNhTen] = useState(thongKe?.ngan_hang_ten || '')
  const [nhSoTk, setNhSoTk] = useState(thongKe?.ngan_hang_so_tk || '')
  const [nhChuTk, setNhChuTk] = useState(thongKe?.ngan_hang_chu_tk || '')
  const [sepaySecret, setSepaySecret] = useState('')
  const [sepaySecretPrev, setSepaySecretPrev] = useState('')

  // Stripe Checkout & Billing
  const [stripeSecretKey, setStripeSecretKey] = useState('')
  const [stripeWebhookSecret, setStripeWebhookSecret] = useState('')
  const [stripeWebhookSecretPrev, setStripeWebhookSecretPrev] = useState('')

  // PayPal Orders API v2
  const [paypalMode, setPaypalMode] = useState('live')
  const [paypalEmail, setPaypalEmail] = useState(thongKe?.paypal_email || '')
  const [paypalMerchantId, setPaypalMerchantId] = useState('')
  const [paypalClientId, setPaypalClientId] = useState(thongKe?.paypal_client_id || '')
  const [paypalClientSecret, setPaypalClientSecret] = useState('')
  const [paypalWebhookId, setPaypalWebhookId] = useState('')

  // Cảnh báo Telegram / Webhook & RapidAPI
  const [telegramBotToken, setTelegramBotToken] = useState('')
  const [telegramChatId, setTelegramChatId] = useState('')
  const [alertWebhookUrl, setAlertWebhookUrl] = useState('')
  const [rapidapiUrl, setRapidapiUrl] = useState(thongKe?.rapidapi_url || '')
  const [rapidapiProxySecret, setRapidapiProxySecret] = useState('')

  // Hàng chờ "Giao dịch cần duyệt tay" (`payment_reviews`)
  const [locDuyetTay, setLocDuyetTay] = useState('needs_manual_review')
  const [dsDuyetTay, setDsDuyetTay] = useState([])
  const [dangTaiDuyetTay, setDangTaiDuyetTay] = useState(false)
  const [formDuyet, setFormDuyet] = useState({}) // { [reviewId]: { email, plan, note } }
  const [dangLam, setDangLam] = useState(null)

  const napCauHinhThanhToan = useCallback(async ({ checkBot = false, checkPaypal = false } = {}) => {
    setDangTaiCauHinh(true)
    try {
      const cfg = await api.quanTriLayCauHinhThanhToan({ checkBot, checkPaypal })
      setCauHinhServer(cfg)
      setNhTen(cfg.ngan_hang_ten || '')
      setNhSoTk(cfg.ngan_hang_so_tk || '')
      setNhChuTk(cfg.ngan_hang_chu_tk || '')
      setPaypalMode(cfg.paypal_mode || 'live')
      setPaypalEmail(cfg.paypal_email || '')
      setPaypalMerchantId(cfg.paypal_merchant_id || '')
      setPaypalClientId(cfg.paypal_client_id || '')
      setPaypalWebhookId(cfg.paypal_webhook_id || '')
      setTelegramChatId(cfg.telegram_chat_id || '')
      setAlertWebhookUrl(cfg.payment_alert_webhook_url || '')
      setRapidapiUrl(cfg.rapidapi_url || '')
      return cfg
    } catch {
      return null
    } finally {
      setDangTaiCauHinh(false)
    }
  }, [])

  const napDanhSachDuyetTay = useCallback(async (statusFilter = locDuyetTay) => {
    setDangTaiDuyetTay(true)
    try {
      const rows = await api.quanTriLayDsDuyetTay({ status: statusFilter, limit: 100 })
      setDsDuyetTay(Array.isArray(rows) ? rows : [])
    } catch {
      setDsDuyetTay([])
    } finally {
      setDangTaiDuyetTay(false)
    }
  }, [locDuyetTay])

  useEffect(() => {
    napCauHinhThanhToan()
  }, [napCauHinhThanhToan])

  useEffect(() => {
    napDanhSachDuyetTay(locDuyetTay)
  }, [locDuyetTay, napDanhSachDuyetTay])

  async function xuLyLuuTatCaCong(e) {
    e.preventDefault()
    setDangLuu(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const payload = {
        ngan_hang_ten: nhTen.trim(),
        ngan_hang_so_tk: nhSoTk.trim(),
        ngan_hang_chu_tk: nhChuTk.trim(),
        paypal_mode: paypalMode,
        paypal_email: paypalEmail.trim(),
        paypal_merchant_id: paypalMerchantId.trim(),
        paypal_client_id: paypalClientId.trim(),
        paypal_webhook_id: paypalWebhookId.trim(),
        telegram_chat_id: telegramChatId.trim(),
        payment_alert_webhook_url: alertWebhookUrl.trim(),
        rapidapi_url: rapidapiUrl.trim(),
      }
      // Chỉ gửi secret mới khi quản trị viên chủ động nhập (không bao giờ gửi lại chuỗi mặt nạ!)
      if (sepaySecret.trim()) payload.sepay_webhook_secret = sepaySecret.trim()
      if (sepaySecretPrev.trim()) payload.sepay_webhook_secret_previous = sepaySecretPrev.trim()
      if (stripeSecretKey.trim()) payload.stripe_secret_key = stripeSecretKey.trim()
      if (stripeWebhookSecret.trim()) payload.stripe_webhook_secret = stripeWebhookSecret.trim()
      if (stripeWebhookSecretPrev.trim()) payload.stripe_webhook_secret_previous = stripeWebhookSecretPrev.trim()
      if (paypalClientSecret.trim()) payload.paypal_client_secret = paypalClientSecret.trim()
      if (telegramBotToken.trim()) payload.telegram_bot_token = telegramBotToken.trim()
      if (rapidapiProxySecret.trim()) payload.rapidapi_proxy_secret = rapidapiProxySecret.trim()

      const kq = await api.quanTriLuuCauHinhThanhToan(payload)
      if (!kq || kq.ok !== true) {
        throw new Error('Máy chủ không xác nhận đã lưu cấu hình thành công.')
      }
      setCauHinhServer(kq)
      // Xoá các ô nhập khoá bí mật sau khi đã lưu xuống kho
      setSepaySecret('')
      setSepaySecretPrev('')
      setStripeSecretKey('')
      setStripeWebhookSecret('')
      setStripeWebhookSecretPrev('')
      setPaypalClientSecret('')
      setTelegramBotToken('')
      setRapidapiProxySecret('')

      setThongBaoOk(
        kq.thong_diep ||
          (laEn
            ? 'Payment gateways saved & verified from storage.'
            : 'Đã lưu và đối chiếu lại cấu hình cổng thanh toán từ kho lưu trữ.'),
      )
      await onNap()
    } catch (err) {
      setLoi(String(err?.cauNguoiDoc || err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLuu(false)
    }
  }

  async function bamKiemTraTelegramBot() {
    setDangKiemBot(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const kq = await napCauHinhThanhToan({ checkBot: true })
      const tg = kq?.telegram_health
      if (tg?.valid) {
        setThongBaoOk(`✅ Bot Telegram hoạt động tốt (@${tg.bot_username || 'ok'}).`)
      } else if (!tg?.configured) {
        setLoi('Chưa cấu hình đủ TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID.')
      } else {
        setLoi(`⚠️ Bot Telegram báo lỗi (${tg?.detail || tg?.http_status || 'invalid_token'}). Hãy tạo lại token từ @BotFather!`)
      }
    } finally {
      setDangKiemBot(false)
    }
  }

  async function bamKiemTraPaypalOAuth() {
    setDangKiemPaypal(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const kq = await napCauHinhThanhToan({ checkPaypal: true })
      const pp = kq?.paypal_health
      if (pp?.ok) {
        setThongBaoOk(
          `✅ ${pp.hint || 'Kết nối PayPal OAuth thành công!'} (mode=${pp.mode}, cid=${pp.client_id_source}, secret=${pp.secret_source})`,
        )
      } else {
        const extra = pp?.source_mismatch_warning ? ` [${pp.source_mismatch_warning}]` : ''
        setLoi(
          `⚠️ PayPal OAuth thất bại (${pp?.error || 'unknown'}, mode=${pp?.mode || 'live'}, cid=${pp?.client_id_source || '?'}, secret=${pp?.secret_source || '?'}, secret_len=${pp?.secret_len ?? 0}): ${pp?.hint || ''}${extra}`,
        )
      }
    } finally {
      setDangKiemPaypal(false)
    }
  }

  function layFormDong(r) {
    return (
      formDuyet[r.id] || {
        email: r.user_email || '',
        plan: '',
        note: '',
      }
    )
  }

  function capNhatFormDong(reviewId, patch, r) {
    setFormDuyet((cu) => ({
      ...cu,
      [reviewId]: {
        ...layFormDong(r),
        ...patch,
      },
    }))
  }

  async function xuLyMotReview(r, hanhDong) {
    const f = layFormDong(r)
    setDangLam(`rev_${r.id}`)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const body = {
        hanh_dong: hanhDong,
        ghi_chu: f.note.trim(),
      }
      if (f.email.trim()) body.user_email_override = f.email.trim()
      if (f.plan.trim()) body.plan_override = f.plan.trim()
      await api.quanTriXuLyDuyetTay(r.id, body)
      setThongBaoOk(
        hanhDong === 'kich_hoat'
          ? `✅ Đã kích hoạt gói & đóng bản ghi duyệt tay (${r.order_code || r.id.slice(0, 8)}).`
          : `✅ Đã cập nhật trạng thái xử lý (${hanhDong}) cho bản ghi duyệt tay.`,
      )
      await napDanhSachDuyetTay(locDuyetTay)
      await onNap()
    } catch (err) {
      setLoi(String(err?.cauNguoiDoc || err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLam(null)
    }
  }

  async function lam(id, viec) {
    setDangLam(id)
    setLoi(null)
    setThongBaoOk(null)
    try {
      await viec()
      await onNap()
    } catch (e) {
      setLoi(String(e?.cauNguoiDoc || e?.message || e).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLam(null)
    }
  }

  const donNapGanDay = Array.isArray(thongKe?.don_nap_gan_day) ? thongKe.don_nap_gan_day : []
  const canhBaoTrungGia = Array.isArray(cauHinhServer?.canh_bao_trung_gia)
    ? cauHinhServer.canh_bao_trung_gia
    : []
  const schemaOk = cauHinhServer?.schema_status?.ok

  return (
    <>
      {/* ── 1. Hàng chờ Giao dịch cần duyệt tay (`payment_reviews`) ─────── */}
      <div className="admin-khung" style={{ borderColor: dsDuyetTay.length > 0 && locDuyetTay === 'needs_manual_review' ? '#f59e0b' : undefined }}>
        <div className="admin-khung-dau" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h3>
              🛡️ {laEn
                ? `Manual Payment Review Queue (${dsDuyetTay.length})`
                : `Giao Dịch Cần Duyệt Tay (${dsDuyetTay.length})`}
            </h3>
            <p className="ghi-chu">
              {laEn
                ? 'Money arrived with discrepancy (underpaid, expired order, missing memo code, tier downgrade) — safely held here for 1-click admin resolution.'
                : 'Mọi khoản tiền thật bị lệch số tiền, trễ hạn đơn, thiếu mã CIO hoặc vướng luật hạ gói đều tự động giữ lại ở đây kèm cảnh báo tức thì.'}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            {['needs_manual_review', 'resolved', 'all'].map((st) => (
              <Button
                key={st}
                type="button"
                kieu={locDuyetTay === st ? 'chinh' : 'phu'}
                onClick={() => setLocDuyetTay(st)}
              >
                {st === 'needs_manual_review'
                  ? (laEn ? 'Needs Review' : 'Cần duyệt tay')
                  : (st === 'resolved' ? (laEn ? 'Resolved' : 'Đã xử lý') : (laEn ? 'All' : 'Tất cả'))}
              </Button>
            ))}
            <Button type="button" kieu="phu" disabled={dangTaiDuyetTay} onClick={() => napDanhSachDuyetTay(locDuyetTay)}>
              🔄 {laEn ? 'Refresh' : 'Làm mới'}
            </Button>
          </div>
        </div>

        {dangTaiDuyetTay ? (
          <div className="admin-khung-than" style={{ padding: 24, textAlign: 'center', color: '#94a3b8' }}>
            ⏳ {laEn ? 'Loading review queue...' : 'Đang tải hàng chờ đối soát...'}
          </div>
        ) : dsDuyetTay.length === 0 ? (
          <div className="admin-khung-than" style={{ padding: 26, textAlign: 'center', color: '#34d399', fontWeight: 600 }}>
            ✅ {laEn
              ? 'Zero transactions waiting for manual review.'
              : 'Tuyệt vời — Hiện không có giao dịch lệch nào chờ duyệt tay.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="admin-bang">
              <thead>
                <tr>
                  <th>{laEn ? 'Time / Gateway' : 'Thời gian / Cổng'}</th>
                  <th>{laEn ? 'Reason' : 'Lý do giữ lại'}</th>
                  <th>{laEn ? 'Order / Customer' : 'Mã đơn / Khách'}</th>
                  <th>{laEn ? 'Amount' : 'Số tiền'}</th>
                  <th>{laEn ? 'Resolution Controls' : 'Ghi đè & Xử lý'}</th>
                </tr>
              </thead>
              <tbody>
                {dsDuyetTay.map((r) => {
                  const f = layFormDong(r)
                  const daXong = r.status === 'resolved'
                  const hienTien =
                    r.amount != null
                      ? (r.currency === 'USD'
                          ? `$${(Number(r.amount) / 100).toFixed(2)} USD`
                          : `${Number(r.amount).toLocaleString('vi-VN')} ${r.currency || 'VND'}`)
                      : '—'
                  return (
                    <tr key={r.id}>
                      <td>
                        <div style={{ fontWeight: 700, textTransform: 'uppercase', color: '#38bdf8' }}>{r.provider}</div>
                        <div style={{ fontSize: 11.5, color: '#94a3b8' }}>
                          {r.created_at ? new Date(r.created_at).toLocaleString('vi-VN') : ''}
                        </div>
                        {r.provider_event_id && (
                          <div style={{ fontSize: 11, color: '#64748b' }}>
                            Tx: <code>{r.provider_event_id}</code>
                          </div>
                        )}
                      </td>
                      <td>
                        <span style={{
                          display: 'inline-block',
                          padding: '3px 8px',
                          borderRadius: 6,
                          fontSize: 12,
                          fontWeight: 700,
                          background: daXong ? 'rgba(16,185,129,0.16)' : 'rgba(245,158,11,0.2)',
                          color: daXong ? '#34d399' : '#fbbf24',
                        }}>
                          {r.reason || r.status}
                        </span>
                        {(r.current_tier || r.target_tier) && (
                          <div style={{ fontSize: 11.5, color: '#cbd5e1', marginTop: 4 }}>
                            {r.current_tier || 'free'} → <b>{r.target_tier || '?'}</b>
                          </div>
                        )}
                      </td>
                      <td>
                        {r.order_code && <div><code>{r.order_code}</code></div>}
                        <div style={{ fontWeight: 600 }}>{r.user_email || 'Chưa rõ tài khoản'}</div>
                      </td>
                      <td>
                        <strong style={{ color: '#34d399' }}>{hienTien}</strong>
                      </td>
                      <td style={{ minWidth: 320 }}>
                        {daXong ? (
                          <div style={{ fontSize: 12.5, color: '#94a3b8' }}>
                            ✅ Đã xử lý bởi <b>{r.resolved_by || 'admin'}</b>
                            {r.resolution_note ? <> — <i>{r.resolution_note}</i></> : null}
                          </div>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                              <input
                                type="email"
                                placeholder="Email nhận gói (nếu thiếu)"
                                value={f.email}
                                onChange={(e) => capNhatFormDong(r.id, { email: e.target.value }, r)}
                                style={{ flex: '1 1 150px', fontSize: 12, padding: '5px 8px' }}
                              />
                              <select
                                value={f.plan}
                                onChange={(e) => capNhatFormDong(r.id, { plan: e.target.value }, r)}
                                style={{ flex: '1 1 160px', fontSize: 12, padding: '5px 8px' }}
                              >
                                {PLAN_OPTIONS.map((opt) => (
                                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                              </select>
                            </div>
                            <input
                              type="text"
                              placeholder="Ghi chú đối soát (bắt buộc lưu vết audit)"
                              value={f.note}
                              onChange={(e) => capNhatFormDong(r.id, { note: e.target.value }, r)}
                              style={{ fontSize: 12, padding: '5px 8px' }}
                            />
                            <div className="admin-hang-cong-cu">
                              <Button
                                type="button"
                                kieu="chinh"
                                disabled={dangLam === `rev_${r.id}`}
                                onClick={() => xuLyMotReview(r, 'kich_hoat')}
                              >
                                ✅ {laEn ? 'Activate Plan' : 'Kích hoạt gói'}
                              </Button>
                              <Button
                                type="button"
                                kieu="phu"
                                disabled={dangLam === `rev_${r.id}`}
                                onClick={() => xuLyMotReview(r, 'da_xu_ly')}
                              >
                                ✔ {laEn ? 'Mark Resolved' : 'Đánh dấu đã xử lý'}
                              </Button>
                              <Button
                                type="button"
                                kieu="phu"
                                disabled={dangLam === `rev_${r.id}`}
                                onClick={() => xuLyMotReview(r, 'hoan_tien')}
                              >
                                ↩ {laEn ? 'Refunded' : 'Đã hoàn tiền'}
                              </Button>
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── 2. Cấu hình Cổng Thanh Toán Chuẩn An Toàn (VN + Quốc tế) ────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h3>
              🔐 {laEn
                ? 'Online Payment Gateways & Webhook Security'
                : 'Cấu Hình Cổng Thanh Toán Online & Bảo Mật Webhook'}
            </h3>
            <p className="ghi-chu">
              {dangTaiCauHinh
                ? 'Đang kiểm tra trạng thái cổng...'
                : (
                  <>
                    VietQR/SePay: <b>{cauHinhServer?.vietqr_enabled ? '🟢 Bật' : '⚪ Chưa đủ'}</b>
                    {' · '}Stripe: <b>{cauHinhServer?.stripe_enabled ? '🟢 Bật' : '⚪ Tắt'}</b>
                    {' · '}PayPal v2: <b>{cauHinhServer?.paypal_enabled ? '🟢 Bật' : '⚪ Tắt'}</b>
                    {' · '}DB Schema: <b>{schemaOk === false ? '🔴 Thiếu bảng' : '🟢 Chuẩn (0039)'}</b>
                  </>
                )}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Button type="button" kieu="phu" disabled={dangKiemPaypal} onClick={bamKiemTraPaypalOAuth}>
              {dangKiemPaypal ? '⏳…' : '🅿️ Kiểm tra PayPal OAuth'}
            </Button>
            <Button type="button" kieu="phu" disabled={dangKiemBot} onClick={bamKiemTraTelegramBot}>
              {dangKiemBot ? '⏳…' : '🤖 Kiểm tra Bot Telegram (getMe)'}
            </Button>
          </div>
        </div>

        <div className="admin-khung-than">
          {canhBaoTrungGia.length > 0 && (
            <div style={{
              padding: '10px 14px',
              borderRadius: 10,
              background: 'rgba(239,68,68,0.16)',
              border: '1px solid rgba(248,113,113,0.55)',
              color: '#fca5a5',
              marginBottom: 14,
              fontSize: 12.8,
            }}>
              ⚠️ <b>Phát hiện trùng vùng giá VNĐ:</b> {canhBaoTrungGia.join(' | ')}
            </div>
          )}

          {/* Danh sách URL Webhook chuẩn để dán lên SePay / Stripe / PayPal */}
          <div style={{
            padding: '11px 14px',
            borderRadius: 10,
            background: 'rgba(16,185,129,0.08)',
            border: '1px solid rgba(16,185,129,0.28)',
            marginBottom: 16,
            fontSize: 12.5,
            color: '#cbd5e1',
            lineHeight: 1.75,
          }}>
            <div>
              🇻🇳 <strong>Webhook SePay chuẩn HMAC-SHA256 (`X-SePay-Signature`):</strong>{' '}
              <code style={{ color: '#34d399', fontWeight: 700 }}>{`${apiOrigin}/api/v1/thanh-toan/webhook/sepay`}</code>
            </div>
            <div>
              💳 <strong>Webhook Stripe Checkout & Billing (`Stripe-Signature`):</strong>{' '}
              <code style={{ color: '#818cf8', fontWeight: 700 }}>{`${apiOrigin}/api/v1/thanh-toan/webhook/stripe`}</code>
            </div>
            <div>
              🅿️ <strong>Webhook PayPal Orders API v2 (`PAYMENT.CAPTURE.COMPLETED`):</strong>{' '}
              <code style={{ color: '#38bdf8', fontWeight: 700 }}>{`${apiOrigin}/api/v1/thanh-toan/webhook/paypal`}</code>
            </div>
          </div>

          <form onSubmit={xuLyLuuTatCaCong}>
            {/* A. VietQR + SePay */}
            <h4 style={{ margin: '0 0 10px', fontSize: 14, color: '#34d399' }}>
              🇻🇳 1. VietQR & SePay Webhook (VNĐ — Xác thực HMAC-SHA256 + Xoay vòng 2 khoá)
            </h4>
            <div className="admin-form-hang" style={{ marginBottom: 18 }}>
              <div className="admin-form-nhom">
                <label>{laEn ? 'Bank Code' : 'Mã Ngân hàng'}</label>
                <input
                  type="text"
                  placeholder="MB, ACB, VCB..."
                  value={nhTen}
                  onChange={(e) => setNhTen(e.target.value)}
                />
              </div>
              <div className="admin-form-nhom">
                <label>{laEn ? 'Receiving Account Number' : 'Số tài khoản nhận (bắt buộc khớp)'}</label>
                <input
                  type="text"
                  placeholder="Số tài khoản nhận tiền thật"
                  value={nhSoTk}
                  onChange={(e) => setNhSoTk(e.target.value)}
                />
              </div>
              <div className="admin-form-nhom">
                <label>{laEn ? 'Account Holder' : 'Chủ tài khoản'}</label>
                <input
                  type="text"
                  placeholder="NGUYEN VAN A"
                  value={nhChuTk}
                  onChange={(e) => setNhChuTk(e.target.value)}
                />
              </div>
              <div className="admin-form-nhom" style={{ flex: '1 1 230px' }}>
                <label>
                  🔐 SePay Webhook Secret{' '}
                  {cauHinhServer?.sepay_configured ? (
                    <span style={{ color: '#34d399', fontSize: 11 }}>({cauHinhServer.sepay_masked})</span>
                  ) : (
                    <span style={{ color: '#fbbf24', fontSize: 11 }}>(Chưa đặt — cổng sẽ trả 503)</span>
                  )}
                </label>
                <input
                  type="password"
                  autoComplete="new-password"
                  placeholder={cauHinhServer?.sepay_secret_configured ? 'Đang bảo vệ — dán khoá mới nếu muốn đổi' : 'Dán khoá ngẫu nhiên >= 32 ký tự'}
                  value={sepaySecret}
                  onChange={(e) => setSepaySecret(e.target.value)}
                />
              </div>
              <div className="admin-form-nhom" style={{ flex: '1 1 210px' }}>
                <label>🔄 Secret cũ (khi đang xoay khoá)</label>
                <input
                  type="password"
                  autoComplete="new-password"
                  placeholder="Tuỳ chọn: giữ tạm khoá cũ khi đổi khoá"
                  value={sepaySecretPrev}
                  onChange={(e) => setSepaySecretPrev(e.target.value)}
                />
              </div>
            </div>

            {/* B. Stripe Checkout */}
            <div style={{ paddingTop: 14, borderTop: '1px dashed rgba(148,163,184,0.25)', marginBottom: 18 }}>
              <h4 style={{ margin: '0 0 10px', fontSize: 14, color: '#818cf8' }}>
                💳 2. Quốc Tế — Stripe Checkout & Subscription Billing (USD)
              </h4>
              <div className="admin-form-hang">
                <div className="admin-form-nhom" style={{ flex: '1 1 250px' }}>
                  <label>
                    Stripe Secret Key{' '}
                    {cauHinhServer?.stripe_secret_configured && (
                      <span style={{ color: '#34d399', fontSize: 11 }}>({cauHinhServer.stripe_secret_masked})</span>
                    )}
                  </label>
                  <input
                    type="password"
                    autoComplete="new-password"
                    placeholder={cauHinhServer?.stripe_secret_configured ? 'Đã lưu — nhập sk_live_... mới nếu đổi' : 'sk_live_... hoặc sk_test_...'}
                    value={stripeSecretKey}
                    onChange={(e) => setStripeSecretKey(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 250px' }}>
                  <label>
                    Stripe Webhook Secret{' '}
                    {cauHinhServer?.stripe_webhook_configured && (
                      <span style={{ color: '#34d399', fontSize: 11 }}>({cauHinhServer.stripe_webhook_masked})</span>
                    )}
                  </label>
                  <input
                    type="password"
                    autoComplete="new-password"
                    placeholder={cauHinhServer?.stripe_webhook_configured ? 'Đã lưu — nhập whsec_... mới nếu đổi' : 'whsec_... (thiếu sẽ trả 404 an toàn)'}
                    value={stripeWebhookSecret}
                    onChange={(e) => setStripeWebhookSecret(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 210px' }}>
                  <label>Stripe Webhook Secret cũ</label>
                  <input
                    type="password"
                    autoComplete="new-password"
                    placeholder="Tuỳ chọn khi xoay whsec_"
                    value={stripeWebhookSecretPrev}
                    onChange={(e) => setStripeWebhookSecretPrev(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* C. PayPal Orders API v2 */}
            <div style={{ paddingTop: 14, borderTop: '1px dashed rgba(148,163,184,0.25)', marginBottom: 18 }}>
              <h4 style={{ margin: '0 0 10px', fontSize: 14, color: '#38bdf8' }}>
                🅿️ 3. Quốc Tế — PayPal Orders API v2 (USD — Tạo & Capture từ Server)
              </h4>
              <div className="admin-form-hang">
                <div className="admin-form-nhom" style={{ maxWidth: 140 }}>
                  <label>Môi trường</label>
                  <select value={paypalMode} onChange={(e) => setPaypalMode(e.target.value)}>
                    <option value="live">Live (Thật)</option>
                    <option value="sandbox">Sandbox (Test)</option>
                  </select>
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 220px' }}>
                  <label>Email Merchant PayPal nhận tiền</label>
                  <input
                    type="email"
                    placeholder="merchant@domain.com"
                    value={paypalEmail}
                    onChange={(e) => setPaypalEmail(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 180px' }}>
                  <label>PayPal Merchant ID</label>
                  <input
                    type="text"
                    placeholder="13 ký tự Merchant ID (tuỳ chọn)"
                    value={paypalMerchantId}
                    onChange={(e) => setPaypalMerchantId(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 230px' }}>
                  <label>PayPal Client ID</label>
                  <input
                    type="text"
                    placeholder="REST App Client ID"
                    value={paypalClientId}
                    onChange={(e) => setPaypalClientId(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 230px' }}>
                  <label>
                    PayPal Client Secret{' '}
                    {cauHinhServer?.paypal_secret_configured && (
                      <span style={{ color: '#34d399', fontSize: 11 }}>({cauHinhServer.paypal_secret_masked})</span>
                    )}
                  </label>
                  <input
                    type="password"
                    autoComplete="new-password"
                    placeholder={cauHinhServer?.paypal_secret_configured ? 'Đã lưu — nhập mới nếu đổi' : 'REST App Secret'}
                    value={paypalClientSecret}
                    onChange={(e) => setPaypalClientSecret(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 200px' }}>
                  <label>PayPal Webhook ID</label>
                  <input
                    type="text"
                    placeholder="ID Webhook trên PayPal Developer"
                    value={paypalWebhookId}
                    onChange={(e) => setPaypalWebhookId(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {/* D. Cảnh báo tức thì Telegram + RapidAPI */}
            <div style={{ paddingTop: 14, borderTop: '1px dashed rgba(148,163,184,0.25)', marginBottom: 16 }}>
              <h4 style={{ margin: '0 0 10px', fontSize: 14, color: '#fbbf24' }}>
                🚨 4. Cảnh Báo Đối Soát Tức Thì (Telegram / Webhook) & Chợ B2B RapidAPI
              </h4>
              <div className="admin-form-hang">
                <div className="admin-form-nhom" style={{ flex: '1 1 230px' }}>
                  <label>
                    Telegram Bot Token{' '}
                    {cauHinhServer?.telegram_configured && (
                      <span style={{ color: '#34d399', fontSize: 11 }}>(✅ Đã kết nối)</span>
                    )}
                  </label>
                  <input
                    type="password"
                    autoComplete="new-password"
                    placeholder={cauHinhServer?.telegram_configured ? 'Đã lưu — dán token mới nếu đổi' : '123456:ABC-DEF...'}
                    value={telegramBotToken}
                    onChange={(e) => setTelegramBotToken(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 170px' }}>
                  <label>Telegram Chat ID</label>
                  <input
                    type="text"
                    placeholder="-1001234567890"
                    value={telegramChatId}
                    onChange={(e) => setTelegramChatId(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 230px' }}>
                  <label>Slack / Discord Alert Webhook URL</label>
                  <input
                    type="url"
                    placeholder="https://hooks.slack.com/... (tuỳ chọn)"
                    value={alertWebhookUrl}
                    onChange={(e) => setAlertWebhookUrl(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 230px' }}>
                  <label>Link API trên chợ RapidAPI</label>
                  <input
                    type="text"
                    placeholder="https://rapidapi.com/..."
                    value={rapidapiUrl}
                    onChange={(e) => setRapidapiUrl(e.target.value)}
                  />
                </div>
                <div className="admin-form-nhom" style={{ flex: '1 1 220px' }}>
                  <label>
                    🛡️ X-RapidAPI-Proxy-Secret{' '}
                    {(cauHinhServer?.rapidapi_proxy_secret_configured || thongKe?.rapidapi_proxy_secret_configured) && (
                      <span style={{ color: '#34d399', fontSize: 11 }}>(✅ Đã kết nối)</span>
                    )}
                  </label>
                  <input
                    type="password"
                    autoComplete="new-password"
                    placeholder="Dán mã mới nếu muốn đổi"
                    value={rapidapiProxySecret}
                    onChange={(e) => setRapidapiProxySecret(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <Button type="submit" kieu="chinh" disabled={dangLuu}>
                {dangLuu
                  ? '⏳ Đang lưu & xác minh kho...'
                  : `💾 ${laEn ? 'Save & Verify All Gateways' : 'Lưu & Đối Chiếu Tất Cả Cổng Thanh Toán'}`}
              </Button>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>
                📦 OpenAPI B2B:{' '}
                <a href="/tai-ve/openapi-rapidapi.json" download="openapi-rapidapi.json" style={{ color: '#34d399', fontWeight: 700 }}>
                  ⬇️ Tải openapi-rapidapi.json
                </a>
              </span>
            </div>
          </form>
        </div>
      </div>

      {/* ── 3. Lịch sử Đơn Chuyển Khoản Cũ (`don_nap_gan_day`) ─────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <h3>
            📋 {laEn
              ? `Legacy Transfer History (${donNapGanDay.length})`
              : `Lịch sử Đơn Chuyển Khoản (${donNapGanDay.length})`}
          </h3>
        </div>
        {donNapGanDay.length === 0 ? (
          <div className="admin-khung-than" style={{ textAlign: 'center', padding: 32, color: '#94a3b8' }}>
            {laEn ? 'No transfer orders yet.' : 'Chưa có đơn chuyển khoản nào.'}
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="admin-bang">
              <thead>
                <tr>
                  <th>{laEn ? 'Order ID' : 'Mã đơn'}</th>
                  <th>{laEn ? 'Customer' : 'Khách hàng'}</th>
                  <th>{laEn ? 'Package' : 'Gói'}</th>
                  <th>{laEn ? 'Amount' : 'Số tiền'}</th>
                  <th>{laEn ? 'Pages' : 'Trang'}</th>
                  <th>{laEn ? 'Memo' : 'Nội dung CK'}</th>
                  <th>{laEn ? 'Status' : 'Trạng thái'}</th>
                  <th>{laEn ? 'Actions' : 'Thao tác'}</th>
                </tr>
              </thead>
              <tbody>
                {donNapGanDay.map((don) => (
                  <tr key={don.ma_don}>
                    <td><code>{don.ma_don}</code></td>
                    <td><strong>{don.email}</strong></td>
                    <td>{don.ten_goi}</td>
                    <td><strong>{Number(don.so_tien_vnd || 0).toLocaleString('vi-VN')}đ</strong></td>
                    <td>+{Number(don.so_trang_cong || 0).toLocaleString('vi-VN')}</td>
                    <td><code>{don.noi_dung_chuyen_khoan || don.noi_dung_ck}</code></td>
                    <td>
                      {don.trang_thai === 'da_xac_nhan' && (
                        <span className="admin-don-tt da-xac-nhan">✅ {laEn ? 'Confirmed' : 'Đã khớp'}</span>
                      )}
                      {don.trang_thai === 'da_cong_tu_dong' && (
                        <span className="admin-don-tt tu-dong">⚡ {laEn ? 'Auto-credited' : 'Tự động'}</span>
                      )}
                      {don.trang_thai === 'cho_duyet' && (
                        <span className="admin-don-tt cho-duyet">⏳ {laEn ? 'Pending' : 'Chờ duyệt'}</span>
                      )}
                      {don.trang_thai === 'da_thu_hoi' && (
                        <span className="admin-don-tt thu-hoi">⛔ {laEn ? 'Revoked' : 'Đã thu hồi'}</span>
                      )}
                    </td>
                    <td>
                      <div className="admin-hang-cong-cu">
                        {don.trang_thai !== 'da_xac_nhan' && (
                          <Button
                            kieu="chinh"
                            disabled={dangLam === don.ma_don}
                            onClick={() =>
                              lam(don.ma_don, () =>
                                api.quanTriDuyetDonNap({ ma_don: don.ma_don, hanh_dong: 'xac_nhan' }),
                              )
                            }
                          >
                            ✅ {laEn ? 'Confirm' : 'Xác nhận'}
                          </Button>
                        )}
                        {don.trang_thai !== 'da_thu_hoi' && (
                          <Button
                            kieu="phu"
                            disabled={dangLam === don.ma_don}
                            onClick={() =>
                              lam(don.ma_don, () =>
                                api.quanTriDuyetDonNap({ ma_don: don.ma_don, hanh_dong: 'thu_hoi' }),
                              )
                            }
                          >
                            {laEn ? 'Revoke' : 'Thu hồi'}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
