import { useEffect, useState } from 'react'

import * as api from '../../api'
import { chuDemNguoc } from '../../lib/dem-nguoc'
import { useNgonNguUI } from '../../lib/ngon-ngu-ui'
import Alert from '../ui/Alert'
import Icon from '../ui/Icon'
import Skeleton from '../ui/Skeleton'

const HIEN_BANG_GIA_VIP = false

/** Thẻ hạn mức: còn bao nhiêu lượt hôm nay, và bao giờ có lại.
 *
 * ## Vì sao thẻ này BẮT BUỘC có
 *
 * §1.3(c) đặc tả: hiện `0/6` mà không nói "có lại lúc 0h" thì người ta tưởng hệ thống hỏng rồi
 * bấm lại liên tục — vừa vô ích cho họ vừa tốn tài nguyên của mình.
 *
 * ## Hai chỗ dễ nói SAI
 *
 * 1. **`con_lai` KHÔNG bằng `tran - da_dung`.** Nó là nhỏ nhất trong các chốt. Khách ở văn phòng
 *    đã chạm trần IP thì còn 0 dù chốt cookie của họ còn nguyên. Tự tính lại là mời người ta thả
 *    6 tệp lên rồi nhận 429.
 * 2. **Chốt `khach_ip` phải nói là "địa chỉ mạng dùng chung"**, không nói "bạn đã hết lượt".
 *    Người chưa dịch trang nào mà bị chặn không có cách nào tự đoán ra lý do.
 */
export default function TheHanMuc({ hanMuc, dangTai, loi, onTaiLai }) {
  const { laEn } = useNgonNguUI()
  const [nhip, setNhip] = useState(0)
  const [moNapLuot, setMoNapLuot] = useState(false)
  const [thongTinNap, setThongTinNap] = useState(null)
  const [goiDangChon, setGoiDangChon] = useState(null)
  const [dangXacNhanCk, setDangXacNhanCk] = useState(false)
  const [ketQuaCk, setKetQuaCk] = useState(null)
  const [loiCk, setLoiCk] = useState(null)
  // Form quản trị cấp lượt nhanh
  const [qtEmail, setQtEmail] = useState('')
  const [qtCongLuot, setQtCongLuot] = useState('200')
  const [qtTranVip, setQtTranVip] = useState('')
  const [qtKetQua, setQtKetQua] = useState(null)
  const [qtLoi, setQtLoi] = useState(null)
  const [qtDangGui, setQtDangGui] = useState(false)

  // Nhịp lại mỗi 30 giây để đồng hồ không đứng im trên một tab để mở lâu. 30 giây là đủ: chuỗi
  // chữ chỉ hiện tới phút, nên nhịp dày hơn chỉ tốn lượt render mà không đổi được gì trên màn.
  useEffect(() => {
    const t = setInterval(() => setNhip((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [])

  async function batTatNapLuot() {
    const tiep = !moNapLuot
    setMoNapLuot(tiep)
    if (tiep && !thongTinNap) {
      try {
        const tt = await api.layThongTinNapLuot()
        setThongTinNap(tt)
        if (tt.goi_goi_y?.length) setGoiDangChon(tt.goi_goi_y[0])
      } catch {
        // Không chặn hiển thị thẻ hạn mức nếu API phụ trợ chưa phản hồi
      }
    }
  }

  async function guiCapLuotQuanTri(e) {
    e.preventDefault()
    if (!qtEmail.trim()) return
    setQtDangGui(true)
    setQtKetQua(null)
    setQtLoi(null)
    try {
      const kq = await api.quanTriCapLuot({
        email: qtEmail.trim(),
        congThemLuot: Number(qtCongLuot) || 0,
        tranHangNgayRieng: qtTranVip === '' ? null : Number(qtTranVip),
      })
      setQtKetQua(kq.thong_diep)
      if (onTaiLai) onTaiLai()
    } catch (err) {
      setQtLoi(String(err.message || err))
    } finally {
      setQtDangGui(false)
    }
  }

  if (loi) {
    return (
      <Alert sac="canh" tieuDe={laEn ? 'Failed to load quota' : 'Chưa lấy được hạn mức'}>
        {String(loi.message || loi)}
        {onTaiLai && (
          <>
            {' '}
            <button type="button" className="nut-chu" onClick={onTaiLai}>
              {laEn ? 'Retry' : 'Thử lại'}
            </button>
          </>
        )}
      </Alert>
    )
  }

  if (dangTai || !hanMuc) {
    // Đang tải ≠ 0 lượt: hiện khung chờ, KHÔNG hiện con số.
    return (
      <div className="the-han-muc dang-tai" aria-busy="true">
        <p aria-live="polite">{laEn ? 'Checking your remaining quota…' : 'Đang xem bạn còn bao nhiêu lượt…'}</p>
        <Skeleton soDong={2} />
      </div>
    )
  }

  const chan = api.chotDangChan(hanMuc)
  const chanBoiMangChung = chan?.loai === 'khach_ip'
  const conLai = hanMuc.con_lai
  const sacVien = conLai <= 0 ? 'loi' : (conLai < hanMuc.tran && conLai <= 2) ? 'canh' : 'ok'

  return (
    <section className={`the-han-muc vien-${sacVien}`} aria-labelledby="tieu-de-han-muc">
      <h2 id="tieu-de-han-muc" className="nho">
        {laEn ? 'Daily Translation Quota' : 'Lượt dịch hôm nay'}
      </h2>

      {/* Màu KHÔNG bao giờ là nguồn thông tin duy nhất: luôn kèm con số và nhãn chữ. */}
      <p className="so-luot">
        <strong>{conLai}</strong> / {hanMuc.tran} {laEn ? 'pages remaining' : 'trang còn lại'}
      </p>
      {hanMuc.so_luot_mua_them > 0 && (
        <p className="ghi-chu" style={{ color: '#059669', fontWeight: 600, marginTop: 2 }}>
          💎 {laEn
            ? <>Includes <strong>{hanMuc.so_luot_mua_them}</strong> purchased pages (never expire overnight)</>
            : <>Đã bao gồm <strong>{hanMuc.so_luot_mua_them}</strong> lượt tích luỹ (không hết hạn qua đêm)</>}
        </p>
      )}
      {hanMuc.tran > 0 && (
        <div
          className={`thanh-tien thanh-tien-mong thanh-tien-${sacVien}`} role="img"
          aria-label={laEn ? `${conLai} of ${hanMuc.tran} pages remaining` : `Còn ${conLai} trong ${hanMuc.tran} lượt`}
        >
          <div
            className="thanh-tien-trong"
            style={{ width: `${Math.max(0, Math.min(100, Math.round((conLai / hanMuc.tran) * 100)))}%` }}
          />
        </div>
      )}

      <p className="ghi-chu moc-reset">
        <Icon ten="dong-ho" co={16} />{' '}
        {laEn ? (
          <>Resets in <strong>{chuDemNguoc(hanMuc.reset_luc, Date.now(), true)}</strong> (00:00 GMT+7)</>
        ) : (
          <>Có lại sau <strong>{chuDemNguoc(hanMuc.reset_luc)}</strong> (0h00 giờ Việt Nam)</>
        )}
      </p>

      {conLai <= 0 && (
        <Alert
          sac="loi"
          tieuDe={
            chanBoiMangChung
              ? (laEn ? 'Shared network quota reached' : 'Địa chỉ mạng này đã hết lượt chung')
              : (laEn ? 'You have reached today’s quota' : 'Bạn đã hết lượt hôm nay')
          }
        >
          {chanBoiMangChung ? (
            laEn ? (
              <>
                Quota is also tracked by <strong>shared IP address</strong>. If you are at an office,
                school, or café, others on the same network may have used it up. Wait until 00:00 GMT+7
                or switch networks.
              </>
            ) : (
              <>
                Lượt được tính theo <strong>địa chỉ mạng</strong>, nên nếu bạn đang ở văn phòng,
                trường học hay quán cà phê thì người khác cùng mạng đã dùng hết. Bạn có thể đợi tới
                0h00, hoặc đổi sang mạng khác.
              </>
            )
          ) : (
            laEn ? <>Quota resets at 00:00 GMT+7.</> : <>Đợi tới 0h00 giờ Việt Nam là có lại.</>
          )}
          {!hanMuc.co_tai_khoan && (
            laEn
              ? <> Sign in or create a free account to get more pages per day (20 pages/day — enough for a full chapter).</>
              : <> Tạo tài khoản thì được nhiều lượt hơn mỗi ngày (20 trang/ngày — đủ trọn 1 chapter).</>
          )}
        </Alert>
      )}

      {conLai > 0 && !hanMuc.co_tai_khoan && (
        <p className="ghi-chu">
          {laEn ? (
            <>Create a free account to get more pages per day (<strong>20 pages/day</strong> instead of {hanMuc.tran} pages).</>
          ) : (
            <>Tạo tài khoản để được nhiều lượt hơn mỗi ngày (<strong>20 trang/ngày</strong> thay vì {hanMuc.tran} trang).</>
          )}
        </p>
      )}

      {/* Chi tiết từng chốt — chỉ hiện khi CÓ NHIỀU HƠN MỘT chốt, tức người gọi là khách lạ.
          Người đã đăng nhập chỉ có một chốt, bày bảng một dòng ra là tiếng ồn. */}
      {(hanMuc.chot || []).length > 1 && (
        <details className="chi-tiet-chot">
          <summary>{laEn ? 'How is quota calculated?' : 'Lượt được tính thế nào?'}</summary>
          <ul>
            {hanMuc.chot.map((c) => (
              <li key={c.loai}>
                {c.loai === 'khach_cookie'
                  ? (laEn ? 'This browser' : 'Theo trình duyệt này')
                  : (laEn ? 'Shared IP network' : 'Theo địa chỉ mạng (dùng chung)')}
                : {c.da_dung}/{c.tran} {laEn ? 'pages' : 'trang'}
              </li>
            ))}
          </ul>
          <p className="ghi-chu">
            {laEn ? (
              <>
                Quota must remain in <strong>both</strong> limits to translate. The shared IP limit is
                higher because multiple people may share one network.
              </>
            ) : (
              <>
                Phải còn lượt ở <strong>cả hai</strong> mới dịch được. Trần theo địa chỉ mạng cao hơn
                vì nhiều người có thể dùng chung một mạng.
              </>
            )}
          </p>
        </details>
      )}

      {(HIEN_BANG_GIA_VIP || hanMuc.la_quan_tri) && (
      <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px dashed var(--vien, #e2e8f0)' }}>
        <button
          type="button"
          className="nut-chu"
          onClick={batTatNapLuot}
          style={{ fontWeight: 600, fontSize: 13, cursor: 'pointer' }}
        >
          {moNapLuot
            ? (laEn ? '▲ Collapse Top-up / VIP Panel' : '▲ Thu gọn bảng Nạp thêm lượt / VIP')
            : (laEn ? '💎 Top Up Quota / Upgrade VIP' : '💎 Nạp thêm lượt / Nâng cấp VIP')}
        </button>

        {moNapLuot && (
          <div style={{ marginTop: 10, padding: 10, borderRadius: 8, background: 'var(--nen-phu, rgba(15,23,42,0.04))', fontSize: 13 }}>
            {!hanMuc.co_tai_khoan && (
              <p className="ghi-chu" style={{ marginBottom: 8 }}>
                ⚠️ Hãy <strong>Đăng nhập / Tạo tài khoản</strong> trên thanh đầu trang trước khi nạp để lượt mua được gắn vĩnh viễn vào tài khoản của bạn (dùng chung cả Web lẫn Tiện ích mở rộng).
              </p>
            )}

            {thongTinNap?.goi_goi_y?.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                {thongTinNap.goi_goi_y.map((g) => {
                  const dangChon = goiDangChon?.ma === g.ma
                  return (
                    <div
                      key={g.ma}
                      onClick={() => setGoiDangChon(g)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setGoiDangChon(g) }}
                      style={{
                        padding: '8px 10px', borderRadius: 6, cursor: 'pointer',
                        border: dangChon ? '2px solid #2563eb' : '1px solid var(--vien, #cbd5e1)',
                        background: dangChon ? 'rgba(37,99,235,0.06)' : 'transparent',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
                        <span>{g.ten}</span>
                        <span style={{ color: '#2563eb' }}>{g.so_tien_vnd.toLocaleString('vi-VN')}đ</span>
                      </div>
                      <div className="ghi-chu" style={{ fontSize: 12, marginTop: 2 }}>{g.ghi_chu}</div>
                    </div>
                  )
                })}
              </div>
            )}

            {(() => {
              const nhTen = thongTinNap?.ngan_hang_ten || 'ACB'
              const nhStk = thongTinNap?.ngan_hang_so_tk || '20260457'
              const nhChu = thongTinNap?.ngan_hang_chu_tk || 'NGUYEN THIEN TRIEU'
              const ndCk = thongTinNap?.noi_dung_chuyen_khoan || 'NAP <EMAIL>'
              const soTien = goiDangChon?.so_tien_vnd || 50000
              return (
                <div style={{ textAlign: 'center', padding: 10, background: '#fff', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <img
                    src={`https://img.vietqr.io/image/${encodeURIComponent(nhTen)}-${encodeURIComponent(nhStk)}-compact2.png?amount=${soTien}&addInfo=${encodeURIComponent(ndCk)}&accountName=${encodeURIComponent(nhChu)}`}
                    alt="Mã VietQR nạp lượt ACB"
                    style={{ maxWidth: 195, width: '100%', height: 'auto', margin: '0 auto', display: 'block' }}
                  />
                  <p className="ghi-chu" style={{ marginTop: 6, color: '#0f172a', lineHeight: 1.5 }}>
                    Ngân hàng: <strong>{nhTen}</strong> · STK: <strong>{nhStk}</strong> ({nhChu})
                    <br />
                    Nội dung CK: <code style={{ fontWeight: 700, color: '#dc2626' }}>{ndCk}</code>
                  </p>
                  {hanMuc.co_tai_khoan && (
                    <button
                      type="button"
                      disabled={dangXacNhanCk}
                      onClick={async () => {
                        setDangXacNhanCk(true)
                        setLoiCk(null)
                        try {
                          const kq = await api.xacNhanChuyenKhoanGoi({
                            ma_goi: goiDangChon?.ma || 'co_ban',
                            ten_goi: goiDangChon?.ten || 'Gói Nạp Lượt',
                            so_tien_vnd: soTien,
                            so_trang: goiDangChon?.so_trang || 100,
                            noi_dung_chuyen_khoan: ndCk,
                          })
                          setKetQuaCk(kq)
                          if (onTaiLai) onTaiLai()
                        } catch (err) {
                          setLoiCk(String(err.message || err))
                        } finally {
                          setDangXacNhanCk(false)
                        }
                      }}
                      style={{
                        marginTop: 6,
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: 6,
                        border: 'none',
                        background: '#059669',
                        color: '#fff',
                        fontWeight: 700,
                        fontSize: 12.5,
                        cursor: 'pointer',
                      }}
                    >
                      {dangXacNhanCk ? '⏳ Đang kích hoạt gói…' : '✅ Tôi đã chuyển khoản — Nhận Gói Ngay'}
                    </button>
                  )}
                  {ketQuaCk && (
                    <p className="ghi-chu" style={{ color: '#059669', fontWeight: 700, marginTop: 6 }}>
                      🎉 Đã ghi nhận đơn {ketQuaCk.ma_don} (+{ketQuaCk.so_trang_cong} trang)!
                    </p>
                  )}
                  {loiCk && (
                    <p className="ghi-chu" style={{ color: '#dc2626', marginTop: 6 }}>
                      {loiCk}
                    </p>
                  )}
                </div>
              )
            })()}

            {hanMuc.la_quan_tri && (
              <form onSubmit={guiCapLuotQuanTri} style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--vien, #cbd5e1)' }}>
                <div style={{ fontWeight: 600, marginBottom: 6 }}>⚡ Cấp lượt nhanh (Dành cho Quản trị viên)</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <input
                    type="email"
                    className="o"
                    placeholder="Email khách hàng (vd: khach@gmail.com)"
                    value={qtEmail}
                    onChange={(e) => setQtEmail(e.target.value)}
                    required
                  />
                  <div style={{ display: 'flex', gap: 6 }}>
                    <input
                      type="number"
                      className="o"
                      placeholder="Cộng thêm lượt (vd: 200)"
                      value={qtCongLuot}
                      onChange={(e) => setQtCongLuot(e.target.value)}
                      title="Số lượt mua thêm cộng vào tài khoản"
                    />
                    <input
                      type="number"
                      className="o"
                      placeholder="Trần VIP/ngày (tuỳ chọn)"
                      value={qtTranVip}
                      onChange={(e) => setQtTranVip(e.target.value)}
                      title="Trần lượt mỗi ngày riêng cho khách VIP (bỏ trống = giữ nguyên)"
                    />
                  </div>
                  <button
                    type="submit"
                    className="nut nut-chinh"
                    disabled={qtDangGui}
                    style={{ padding: '6px 12px', borderRadius: 6, cursor: 'pointer' }}
                  >
                    {qtDangGui ? 'Đang cấp lượt…' : 'Cấp lượt / Cập nhật VIP'}
                  </button>
                  {qtKetQua && <p className="ghi-chu" style={{ color: '#059669', fontWeight: 600 }}>{qtKetQua}</p>}
                  {qtLoi && <p className="ghi-chu" style={{ color: '#dc2626' }}>{qtLoi}</p>}
                </div>
              </form>
            )}
          </div>
        )}
      </div>
      )}
    </section>
  )
}
