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
  const [dangCap, setDangCap] = useState(false)

  if (!ds) return null

  const soKhachVip = ds.filter(
    (u) => (u.so_luot_mua_them || 0) > 0 || (u.tran_hang_ngay_rieng && u.tran_hang_ngay_rieng > tranMacDinh),
  ).length
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

  async function xuLyCapGoi(e) {
    e.preventDefault()
    if (!emailCap.trim()) return
    setDangCap(true)
    setLoi(null)
    setThongBaoOk(null)
    try {
      const kq = await api.quanTriCapLuot({
        email: emailCap.trim(),
        congThemLuot: Number(congLuot) || 0,
        tranHangNgayRieng: tranVip === '' ? null : Number(tranVip),
      })
      setThongBaoOk(kq?.thong_diep || `Đã cập nhật gói cho ${emailCap.trim()}`)
      await onNap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangCap(false)
    }
  }

  return (
    <>
      {/* ── VIP Activation Form ────────────────────────────────────────── */}
      <div className="admin-khung">
        <div className="admin-khung-dau">
          <h3>⚡ {laEn ? 'Activate VIP Package' : 'Kích hoạt gói VIP'}</h3>
        </div>
        <div className="admin-khung-than">
          <div className="admin-goi-nhanh">
            {[
              { luot: '100', nhan: '🌱 +100' },
              { luot: '550', nhan: '🔥 +550' },
              { luot: '1200', nhan: '👑 +1.200' },
              { luot: '6500', nhan: '🏢 +6.500' },
              { luot: '28000', nhan: '🏛️ +28.000' },
            ].map((g) => (
              <button
                key={g.luot}
                type="button"
                className={`admin-chip-goi ${congLuot === g.luot ? 'dang-chon' : ''}`}
                onClick={() => setCongLuot(g.luot)}
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
                placeholder={String(tranMacDinh)}
                value={tranVip}
                onChange={(e) => setTranVip(e.target.value)}
              />
            </div>
            <Button type="submit" kieu="chinh" disabled={dangCap}>
              {dangCap ? '⏳' : `💎 ${laEn ? 'Activate' : 'Kích hoạt'}`}
            </Button>
          </form>
        </div>
      </div>

      {/* ── Filter Pills ───────────────────────────────────────────────── */}
      <div className="admin-loc">
        {[
          { ma: 'tat_ca', nhan: `${laEn ? 'All' : 'Tất cả'} (${ds.length})` },
          { ma: 'vip', nhan: `💎 VIP (${soKhachVip})` },
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
