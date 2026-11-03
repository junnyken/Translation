import { useState } from 'react'
import * as api from '../../api.js'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Button from '../ui/Button.jsx'

/**
 * AdminTaiKhoan — Quản lý tài khoản khách hàng CRM đầy đủ.
 *
 * Filter pills, search, sort, bảng chi tiết, và thao tác quản trị
 * (khoá, phong/thu quyền, xoá, cộng lượt nhanh).
 */
export default function AdminTaiKhoan({ ds, thongKe, toi, tranMacDinh, onNap, setLoi, setThongBaoOk }) {
  const { laEn } = useNgonNguUI()
  const [tuKhoa, setTuKhoa] = useState('')
  const [boLocNhom, setBoLocNhom] = useState('tat_ca')
  const [sapXep, setSapXep] = useState('moi_nhat')
  const [dangLam, setDangLam] = useState(null)

  // Form cấp VIP inline
  const [emailCap, setEmailCap] = useState('')
  const [congLuot, setCongLuot] = useState('100')
  const [tranVip, setTranVip] = useState('')
  const [kemTaoKey, setKemTaoKey] = useState(false)
  const [dangCap, setDangCap] = useState(false)

  // Key API (tr_live_...) vừa cấp cho khách để Admin copy gửi khách
  const [keyVuaCap, setKeyVuaCap] = useState(null) // { email, api_key, tao_luc }
  const [daCopyKey, setDaCopyKey] = useState(false)
  const [daCopyTronBo, setDaCopyTronBo] = useState(false)

  if (!ds) return null

  const soKhachVip = ds.filter(
    (u) => (u.so_luot_mua_them || 0) > 0 || (u.tran_hang_ngay_rieng && u.tran_hang_ngay_rieng > tranMacDinh),
  ).length
  const soCoApiKey = ds.filter((u) => Boolean(u.co_api_key)).length
  const soQuanTri = ds.filter((u) => u.la_quan_tri).length
  const soDungHomNay = ds.filter((u) => (u.da_dung_hom_nay || 0) > 0).length
  const soDaKhoa = ds.filter((u) => u.dang_hoat_dong === false).length

  // Lọc và sắp xếp
  const dsLoc = ds
    .filter((n) => {
      if (tuKhoa.trim()) {
        const tk = tuKhoa.trim().toLowerCase()
        const khop = (n.email || '').toLowerCase().includes(tk) || (n.ten_hien || '').toLowerCase().includes(tk)
        if (!khop) return false
      }
      if (boLocNhom === 'vip') {
        return (n.so_luot_mua_them || 0) > 0 || Boolean(n.tran_hang_ngay_rieng && n.tran_hang_ngay_rieng > tranMacDinh)
      }
      if (boLocNhom === 'co_api_key') return Boolean(n.co_api_key)
      if (boLocNhom === 'quan_tri') return Boolean(n.la_quan_tri)
      if (boLocNhom === 'hoat_dong_hom_nay') return (n.da_dung_hom_nay || 0) > 0
      if (boLocNhom === 'da_khoa') return n.dang_hoat_dong === false
      return true
    })
    .slice()
    .sort((a, b) => {
      if (sapXep === 'luot_tich_luy') return (b.so_luot_mua_them || 0) - (a.so_luot_mua_them || 0)
      if (sapXep === 'dung_hom_nay') return (b.da_dung_hom_nay || 0) - (a.da_dung_hom_nay || 0)
      if (sapXep === 'tong_dich') return (b.tong_trang_da_dich || 0) - (a.tong_trang_da_dich || 0)
      const ta = a.created_at ? new Date(a.created_at).getTime() : 0
      const tb = b.created_at ? new Date(b.created_at).getTime() : 0
      return tb - ta
    })

  async function lam(id, viec) {
    setDangLam(id)
    setLoi(null)
    setThongBaoOk(null)
    try {
      await viec()
      await onNap()
    } catch (e) {
      setLoi(String(e?.message || e).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLam(null)
    }
  }

  async function capNhanhChoEmail(email, soLuotCong) {
    setDangLam(`cap-${email}`)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const kq = await api.quanTriCapLuot({
        email,
        congThemLuot: soLuotCong,
        tranHangNgayRieng: null,
      })
      setThongBaoOk(kq?.thong_diep || `Đã cộng +${soLuotCong} trang cho ${email}`)
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLam(null)
    }
  }

  async function capApiKeyChoKhach(nguoi) {
    setDangLam(`key-${nguoi.id}`)
    setLoi(null)
    setThongBaoOk(null)
    setDaCopyKey(false)
    setDaCopyTronBo(false)
    try {
      const kq = await api.quanTriTaoApiKeyChoKhach(nguoi.id)
      setKeyVuaCap({
        email: nguoi.email,
        api_key: kq.api_key || '',
        tao_luc: kq.tao_luc,
      })
      setThongBaoOk(
        kq?.thong_diep || `Đã tạo Developer API Key (tr_live_...) cho ${nguoi.email}`,
      )
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLam(null)
    }
  }

  async function thuHoiApiKeyCuaKhach(nguoi) {
    if (
      !window.confirm(
        laEn
          ? `Revoke Developer API Key (tr_live_...) of ${nguoi.email}?`
          : `Thu hồi ngay Developer API Key (tr_live_...) của ${nguoi.email}?`,
      )
    )
      return
    setDangLam(`key-${nguoi.id}`)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const kq = await api.quanTriThuHoiApiKeyKhach(nguoi.id)
      if (keyVuaCap?.email === nguoi.email) setKeyVuaCap(null)
      setThongBaoOk(kq?.thong_diep || `Đã thu hồi API Key của ${nguoi.email}`)
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLam(null)
    }
  }

  async function xuLyCapGoi(e) {
    e.preventDefault()
    if (!emailCap.trim()) return
    setDangCap(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const emailSach = emailCap.trim()
      const kq = await api.quanTriCapLuot({
        email: emailSach,
        congThemLuot: Number(congLuot) || 0,
        tranHangNgayRieng: tranVip === '' ? null : Number(tranVip),
      })
      if (kemTaoKey) {
        const mucTieu = ds.find((u) => (u.email || '').toLowerCase() === emailSach.toLowerCase())
        if (mucTieu) {
          const kqKey = await api.quanTriTaoApiKeyChoKhach(mucTieu.id)
          setKeyVuaCap({
            email: mucTieu.email,
            api_key: kqKey.api_key || '',
            tao_luc: kqKey.tao_luc,
          })
          setDaCopyKey(false)
          setDaCopyTronBo(false)
        }
      }
      setThongBaoOk(kq?.thong_diep || `Đã cập nhật gói cho ${emailSach}`)
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangCap(false)
    }
  }

  return (
    <>
      {/* ── Newly Issued Customer API Key Banner ───────────────────────── */}
      {keyVuaCap && keyVuaCap.api_key && (
        <div
          className="admin-khung"
          style={{
            border: '1.5px solid #10b981',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%)',
          }}
        >
          <div className="admin-khung-than">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#065f46' }}>
                🔑 {laEn ? 'New Developer API Key issued for:' : 'Đã cấp mới Developer API Key cho khách:'}{' '}
                <span style={{ color: '#047857', textDecoration: 'underline' }}>{keyVuaCap.email}</span>
              </div>
              <button
                type="button"
                className="admin-nut-cong-nhanh"
                onClick={() => setKeyVuaCap(null)}
              >
                ✕ {laEn ? 'Dismiss' : 'Đóng'}
              </button>
            </div>
            <p style={{ fontSize: 12.5, color: '#047857', margin: '0 0 10px' }}>
              {laEn
                ? 'Copy and send this key to the customer. For security, the full raw key is only shown once:'
                : 'Sao chép mã này gửi cho khách hàng gắn vào Tool / Website / Tiện ích / App Windows (mã đầy đủ chỉ hiển thị 1 lần):'}
            </p>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <code
                style={{
                  flex: 1,
                  minWidth: 260,
                  padding: '10px 14px',
                  borderRadius: 8,
                  background: '#0f172a',
                  color: '#34d399',
                  fontSize: 13.5,
                  fontWeight: 700,
                  wordBreak: 'break-all',
                  border: '1px solid #059669',
                }}
              >
                {keyVuaCap.api_key}
              </code>
              <Button
                kieu="chinh"
                onClick={() => {
                  navigator.clipboard?.writeText(keyVuaCap.api_key)
                  setDaCopyKey(true)
                }}
              >
                {daCopyKey ? '✅ Đã Copy Key!' : '📋 Copy Mã tr_live_'}
              </Button>
              <Button
                kieu="phu"
                onClick={() => {
                  const originUrl = typeof window !== 'undefined' ? window.location.origin : 'https://comic.io.vn'
                  const noiDungGuiKhach =
                    `🔑 Thông tin kết nối API Dịch Truyện (${originUrl}):\n` +
                    `- Tài khoản: ${keyVuaCap.email}\n` +
                    `- Developer API Key: ${keyVuaCap.api_key}\n` +
                    `- Base URL: ${originUrl}/api/v1/developer\n` +
                    `- Header xác thực: X-Customer-Api-Key: ${keyVuaCap.api_key}\n` +
                    `- Tài liệu & Code mẫu: ${originUrl}/#ket-noi-api`
                  navigator.clipboard?.writeText(noiDungGuiKhach)
                  setDaCopyTronBo(true)
                }}
              >
                {daCopyTronBo ? '✅ Đã Copy Trọn Bộ!' : '📨 Copy Kèm Hướng Dẫn Gửi Khách'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── VIP Activation Form ────────────────────────────────────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <div>
            <h3>⚡ {laEn ? 'Activate VIP Package & Issue API Key' : 'Kích hoạt gói VIP & Cấp Khoá API (tr_live_...)'}</h3>
            <p className="ghi-chu">
              {laEn
                ? 'Add purchased pages, set daily VIP cap, and optionally generate a Developer API Key for the customer.'
                : 'Cộng lượt mua thêm, đặt trần VIP/ngày và tuỳ chọn cấp luôn mã Developer API Key (tr_live_...) cho khách.'}
            </p>
          </div>
        </div>
        <div className="admin-khung-than">
          <div className="admin-goi-nhanh">
            {[
              { luot: '100', nhan: '🌱 +100' },
              { luot: '550', nhan: '🔥 +550' },
              { luot: '1200', nhan: '👑 +1.200' },
              { luot: '6500', nhan: '🏢 +6.500 (API Pro)' },
              { luot: '28000', nhan: '🏛️ +28.000 (Enterprise)' },
            ].map((g) => (
              <button
                key={g.luot}
                type="button"
                className={`admin-chip-goi ${congLuot === g.luot ? 'dang-chon' : ''}`}
                onClick={() => {
                  setCongLuot(g.luot)
                  if (Number(g.luot) >= 6500) setKemTaoKey(true)
                }}
              >
                {g.nhan}
              </button>
            ))}
          </div>
          <form className="admin-form-hang" onSubmit={xuLyCapGoi}>
            <div className="admin-form-nhom" style={{ flex: 2 }}>
              <label>Email</label>
              <input
                type="email"
                list="admin-ds-email-tk"
                placeholder={laEn ? 'customer@gmail.com' : 'khachhang@gmail.com'}
                value={emailCap}
                onChange={(e) => setEmailCap(e.target.value)}
                required
              />
              <datalist id="admin-ds-email-tk">
                {ds.map((u) => (
                  <option key={u.id} value={u.email}>{u.ten_hien || u.email}</option>
                ))}
              </datalist>
            </div>
            <div className="admin-form-nhom" style={{ flex: 1 }}>
              <label>{laEn ? 'Credits' : 'Lượt cộng'}</label>
              <input
                type="number"
                value={congLuot}
                onChange={(e) => setCongLuot(e.target.value)}
              />
            </div>
            <div className="admin-form-nhom" style={{ flex: 1 }}>
              <label>{laEn ? 'Daily cap' : 'Trần/ngày'}</label>
              <input
                type="number"
                placeholder={`${laEn ? 'Default' : 'Mặc định'}: ${tranMacDinh}`}
                value={tranVip}
                onChange={(e) => setTranVip(e.target.value)}
              />
            </div>
            <Button type="submit" kieu="chinh" disabled={dangCap}>
              {dangCap ? '⏳' : `💎 ${laEn ? 'Activate' : 'Kích hoạt'}`}
            </Button>
          </form>
          <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: '#475569', cursor: 'pointer', fontWeight: 500 }}>
              <input
                type="checkbox"
                checked={kemTaoKey}
                onChange={(e) => setKemTaoKey(e.target.checked)}
              />
              🔑 {laEn
                ? 'Also generate a new Developer API Key (tr_live_...) for this account upon activation'
                : 'Kèm tạo mới mã Developer API Key (tr_live_...) cho tài khoản này ngay khi bấm Kích hoạt'}
            </label>
          </div>
        </div>
      </div>

      {/* ── Filter Pills ───────────────────────────────────────────────── */}
      <div className="admin-loc">
        {[
          { ma: 'tat_ca', nhan: `${laEn ? 'All' : 'Tất cả'} (${ds.length})` },
          { ma: 'vip', nhan: `💎 VIP (${soKhachVip})` },
          { ma: 'co_api_key', nhan: `🔑 Có API Key (${soCoApiKey})` },
          { ma: 'hoat_dong_hom_nay', nhan: `🔥 ${laEn ? 'Active Today' : 'Hôm nay'} (${soDungHomNay})` },
          { ma: 'quan_tri', nhan: `🛡️ Admin (${soQuanTri})` },
          { ma: 'da_khoa', nhan: `🔒 ${laEn ? 'Locked' : 'Đã khoá'} (${soDaKhoa})` },
        ].map((loc) => (
          <button
            key={loc.ma}
            type="button"
            className={`admin-pill ${boLocNhom === loc.ma ? 'dang-chon' : ''}`}
            onClick={() => setBoLocNhom(loc.ma)}
          >
            {loc.nhan}
          </button>
        ))}
      </div>

      {/* ── Search & Sort ──────────────────────────────────────────────── */}
      <div className="admin-thanh-tim">
        <input
          type="search"
          className="admin-o-tim"
          placeholder={laEn ? '🔍 Search by email or name…' : '🔍 Tìm theo email hoặc tên…'}
          value={tuKhoa}
          onChange={(e) => setTuKhoa(e.target.value)}
        />
        <select
          className="admin-chon"
          value={sapXep}
          onChange={(e) => setSapXep(e.target.value)}
          aria-label={laEn ? 'Sort accounts' : 'Sắp xếp'}
        >
          <option value="moi_nhat">🕒 {laEn ? 'Newest' : 'Mới nhất'}</option>
          <option value="luot_tich_luy">💎 {laEn ? 'Most credits' : 'Lượt tích luỹ'}</option>
          <option value="dung_hom_nay">🔥 {laEn ? 'Most active today' : 'Dùng hôm nay'}</option>
          <option value="tong_dich">📚 {laEn ? 'Most translated' : 'Tổng dịch'}</option>
        </select>
        <span className="admin-so-ket-qua">
          {laEn ? 'Showing' : 'Hiển thị'} <strong>{dsLoc.length}</strong> / {ds.length}
        </span>
      </div>

      {/* ── User Table ─────────────────────────────────────────────────── */}
      <div className="admin-khung" style={{ overflow: 'visible' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="admin-bang">
            <thead>
              <tr>
                <th>{laEn ? 'Customer' : 'Khách hàng'}</th>
                <th>{laEn ? 'Role' : 'Vai trò'}</th>
                <th>{laEn ? 'Usage Today' : 'Hôm nay'} ({tranMacDinh})</th>
                <th>{laEn ? 'Credits Balance' : 'Lượt tích luỹ'}</th>
                <th>{laEn ? 'Total Translated' : 'Tổng đã dịch'}</th>
                <th>{laEn ? 'API Key (tr_live_)' : 'Khoá API (tr_live_)'}</th>
                <th>{laEn ? 'Status' : 'Trạng thái'}</th>
                <th>{laEn ? 'Actions' : 'Thao tác'}</th>
              </tr>
            </thead>
            <tbody>
              {dsLoc.map((n) => {
                const laToi = n.id === toi?.id
                const tranNgay = n.tran_hang_ngay ?? n.tran_hang_ngay_rieng ?? tranMacDinh
                const daDung = n.da_dung_hom_nay ?? 0
                const muaThem = n.so_luot_mua_them ?? 0
                const tongDich = n.tong_trang_da_dich ?? 0
                const coVip = muaThem > 0 || Boolean(n.tran_hang_ngay_rieng && n.tran_hang_ngay_rieng > tranMacDinh)
                const pctHomNay = Math.min(100, Math.round((daDung / Math.max(1, tranNgay)) * 100))
                return (
                  <tr
                    key={n.id}
                    className={emailCap === n.email ? 'noi-bat' : ''}
                    onClick={() => setEmailCap(n.email)}
                    style={{ cursor: 'pointer' }}
                    title={laEn ? 'Click to fill email' : 'Bấm để điền email'}
                  >
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <strong>{n.email}</strong>
                        {coVip && <span className="admin-nhan-vip">VIP</span>}
                      </div>
                      <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>
                        {n.ten_hien || '—'}
                        {n.created_at ? ` · ${new Date(n.created_at).toLocaleDateString('vi-VN')}` : ''}
                      </div>
                    </td>
                    <td>
                      <span className={`admin-nhan-vai-tro ${n.la_quan_tri ? 'quan-tri' : 'thuong'}`}>
                        {n.la_quan_tri ? 'Admin' : (laEn ? 'User' : 'Thường')}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <strong>{daDung} / {tranNgay}</strong>
                        {n.tran_hang_ngay_rieng && <span style={{ fontSize: 11, color: '#94a3b8' }}>(VIP)</span>}
                      </div>
                      <div className="admin-thanh-tien">
                        <div
                          className="admin-thanh-tien-ruot"
                          style={{
                            width: `${pctHomNay}%`,
                            background: pctHomNay >= 100 ? '#ef4444' : pctHomNay >= 75 ? '#f59e0b' : '#10b981',
                          }}
                        />
                      </div>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        <strong style={{ color: muaThem > 0 ? '#059669' : 'inherit' }}>
                          {muaThem.toLocaleString('vi-VN')}
                        </strong>
                        <span style={{ fontSize: 11, color: '#94a3b8' }}>{laEn ? 'pages' : 'trang'}</span>
                        <button
                          type="button"
                          className="admin-nut-cong-nhanh"
                          disabled={dangLam === `cap-${n.email}`}
                          onClick={() => capNhanhChoEmail(n.email, 100)}
                          title={`+100 → ${n.email}`}
                        >
                          +100
                        </button>
                      </div>
                    </td>
                    <td>
                      <strong>{tongDich.toLocaleString('vi-VN')}</strong>{' '}
                      <span style={{ fontSize: 11, color: '#94a3b8' }}>{laEn ? 'pages' : 'trang'}</span>
                      {n.so_chapter ? <span style={{ fontSize: 11, color: '#94a3b8' }}> ({n.so_chapter} chap)</span> : null}
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          {n.co_api_key ? (
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 700,
                                padding: '2px 7px',
                                borderRadius: 4,
                                background: '#dcfce7',
                                color: '#166534',
                              }}
                            >
                              🟢 tr_live_•••
                            </span>
                          ) : (
                            <span style={{ fontSize: 11, color: '#94a3b8' }}>
                              {laEn ? 'None' : 'Chưa tạo'}
                            </span>
                          )}
                          <button
                            type="button"
                            className="admin-nut-cong-nhanh"
                            disabled={dangLam === `key-${n.id}`}
                            onClick={() => capApiKeyChoKhach(n)}
                            title={laEn ? 'Generate or rotate tr_live_ API Key' : 'Tạo mới hoặc đổi mã API Key (tr_live_...) cho khách'}
                            style={{ borderColor: '#6366f1', color: '#4f46e5' }}
                          >
                            {dangLam === `key-${n.id}`
                              ? '⏳'
                              : n.co_api_key
                                ? `🔄 ${laEn ? 'Rotate' : 'Đổi Key'}`
                                : `🔑 ${laEn ? 'Issue Key' : 'Tạo Key'}`}
                          </button>
                          {n.co_api_key && (
                            <button
                              type="button"
                              className="admin-nut-cong-nhanh"
                              disabled={dangLam === `key-${n.id}`}
                              onClick={() => thuHoiApiKeyCuaKhach(n)}
                              title={laEn ? 'Revoke API Key' : 'Thu hồi API Key'}
                              style={{ borderColor: '#fca5a5', color: '#dc2626' }}
                            >
                              ✕
                            </button>
                          )}
                        </div>
                        {n.api_key_dung_lan_cuoi && (
                          <span style={{ fontSize: 10.5, color: '#64748b' }}>
                            {laEn ? 'Used:' : 'Gọi:'} {new Date(n.api_key_dung_lan_cuoi).toLocaleDateString('vi-VN')}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`admin-trang-thai ${n.dang_hoat_dong === false ? 'khoa' : 'ok'}`}>
                        {n.dang_hoat_dong === false
                          ? (laEn ? 'Locked' : 'Đã khoá')
                          : (laEn ? 'Active' : 'Đang dùng')}
                      </span>
                    </td>
                    <td onClick={(e) => e.stopPropagation()}>
                      {laToi ? (
                        <span style={{ fontSize: 12, color: '#94a3b8' }}>({laEn ? 'you' : 'bạn'})</span>
                      ) : (
                        <div className="admin-hang-cong-cu">
                          <Button
                            kieu="phu"
                            disabled={dangLam === n.id}
                            onClick={() =>
                              lam(n.id, () =>
                                api.doiTrangThaiNguoiDung(n.id, { dang_hoat_dong: n.dang_hoat_dong === false }),
                              )
                            }
                          >
                            {n.dang_hoat_dong === false ? (laEn ? 'Unlock' : 'Mở khoá') : (laEn ? 'Lock' : 'Khoá')}
                          </Button>
                          <Button
                            kieu="phu"
                            disabled={dangLam === n.id}
                            onClick={() =>
                              lam(n.id, () =>
                                api.doiTrangThaiNguoiDung(n.id, { la_quan_tri: !n.la_quan_tri }),
                              )
                            }
                          >
                            {n.la_quan_tri
                              ? (laEn ? 'Revoke Admin' : 'Thu quyền')
                              : (laEn ? 'Grant Admin' : 'Phong QT')}
                          </Button>
                          <Button
                            kieu="phu"
                            disabled={dangLam === n.id}
                            onClick={() => {
                              if (
                                !window.confirm(
                                  laEn
                                    ? `Delete account ${n.email}?\n\nTheir chapters won't be deleted.`
                                    : `Xoá hẳn tài khoản ${n.email}?\n\nChapter của họ KHÔNG bị xoá — chúng trở về "chưa có chủ".`,
                                )
                              )
                                return
                              lam(n.id, () => api.xoaNguoiDung(n.id))
                            }}
                          >
                            {laEn ? 'Delete' : 'Xoá'}
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p style={{ fontSize: 12, color: '#94a3b8', marginTop: 8, lineHeight: 1.6 }}>
        <b>{laEn ? 'Lock' : 'Khoá'}</b>{' '}
        {laEn
          ? 'preserves chapters and revokes active sessions immediately.'
          : 'giữ nguyên chapter và cắt phiên đang mở ngay lập tức.'}
        {' '}
        <b>{laEn ? 'Delete' : 'Xoá'}</b>{' '}
        {laEn
          ? 'makes their chapters unclaimed (admin-only visible).'
          : 'làm chapter thành "chưa có chủ" (chỉ quản trị thấy).'}
        {soQuanTri < 2 && (
          <>
            {' '}
            {laEn
              ? 'Have at least 2 admins to avoid lockout.'
              : 'Nên có ít nhất 2 quản trị để không bị khoá ngoài.'}
          </>
        )}
      </p>
    </>
  )
}
