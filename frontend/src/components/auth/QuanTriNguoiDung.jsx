import { useEffect, useState } from 'react'
import * as api from '../../api.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'

/** Dashboard Quản trị & Danh bạ tài khoản — chỉ quản trị thấy (Auth slice B1a + E107).
 *
 * Vì sao cần: phát tài khoản và bán gói ra được thì phải theo dõi được:
 * 1. Ai đang còn bao nhiêu lượt hôm nay, bao nhiêu lượt mua tích luỹ (`so_luot_mua_them`), trần VIP/ngày.
 * 2. Hôm nay / 7 ngày qua / toàn thời gian hệ thống đã dịch bao nhiêu trang.
 * 3. Cấp nhanh các gói (+200 / +550 / +1200 trang hoặc đặt trần VIP/ngày) ngay trên bảng quản trị.
 *
 * **Khoá** và **xoá** là hai việc khác nhau, và màn này phải nói rõ sự khác nhau đó:
 * khoá giữ nguyên chapter của họ, xoá làm chapter thành vô chủ.
 */
export default function QuanTriNguoiDung({ toi }) {
  const [ds, setDs] = useState(null)
  const [thongKe, setThongKe] = useState(null)
  const [loi, setLoi] = useState(null)
  const [thongBaoOk, setThongBaoOk] = useState(null)
  const [dangLam, setDangLam] = useState(null)
  const [tuKhoa, setTuKhoa] = useState('')

  // Form cấp gói / kích hoạt VIP nhanh cho khách hàng
  const [emailCap, setEmailCap] = useState('')
  const [congLuot, setCongLuot] = useState('200')
  const [tranVip, setTranVip] = useState('')
  const [dangCap, setDangCap] = useState(false)

  // Form cấu hình VietQR Ngân hàng & Webhook tự động
  const [nhTen, setNhTen] = useState('ACB')
  const [nhSoTk, setNhSoTk] = useState('20260457')
  const [nhChuTk, setNhChuTk] = useState('NGUYEN THIEN TRIEU')
  const [dangLuuNh, setDangLuuNh] = useState(false)

  async function nap() {
    try {
      const danhSach = await api.layDanhSachNguoiDung()
      if (Array.isArray(danhSach)) {
        setDs(danhSach)
      }
      // Gọi thêm thống kê chi tiết nếu máy chủ hỗ trợ (không chặn nếu bài test chỉ mock `/auth/users`)
      try {
        const tk = await api.layThongKeQuanTri()
        if (tk && typeof tk === 'object' && Array.isArray(tk.nguoi_dung_chi_tiet)) {
          setThongKe(tk)
          setDs(tk.nguoi_dung_chi_tiet)
          if (tk.ngan_hang_ten !== undefined) setNhTen(tk.ngan_hang_ten || '')
          if (tk.ngan_hang_so_tk !== undefined) setNhSoTk(tk.ngan_hang_so_tk || '')
          if (tk.ngan_hang_chu_tk !== undefined) setNhChuTk(tk.ngan_hang_chu_tk || '')
        }
      } catch {
        // Giữ nguyên danh sách cơ bản từ `/auth/users`
      }
    } catch (e) {
      setLoi(String(e?.message || e))
    }
  }

  useEffect(() => { nap() }, [])

  async function lam(id, viec) {
    setDangLam(id); setLoi(null); setThongBaoOk(null)
    try { await viec(); await nap() }
    catch (e) { setLoi(String(e?.message || e).replace(/^\d+:\s*/, '')) }
    finally { setDangLam(null) }
  }

  async function xuLyCapGoi(e) {
    e.preventDefault()
    if (!emailCap.trim()) return
    setDangCap(true); setLoi(null); setThongBaoOk(null)
    try {
      const kq = await api.quanTriCapLuot({
        email: emailCap.trim(),
        congThemLuot: Number(congLuot) || 0,
        tranHangNgayRieng: tranVip === '' ? null : Number(tranVip),
      })
      setThongBaoOk(kq?.thong_diep || `Đã cập nhật gói cho ${emailCap.trim()}`)
      await nap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangCap(false)
    }
  }

  async function xuLyLuuNganHang(e) {
    e.preventDefault()
    setDangLuuNh(true); setLoi(null); setThongBaoOk(null)
    try {
      const kq = await api.quanTriCapLuot({
        email: '',
        nganHangTen: nhTen.trim(),
        nganHangSoTk: nhSoTk.trim(),
        nganHangChuTk: nhChuTk.trim(),
      })
      setThongBaoOk(kq?.thong_diep || 'Đã lưu cấu hình VietQR ngân hàng thành công.')
      await nap()
    } catch (err) {
      setLoi(String(err?.message || err).replace(/^\d+:\s*/, ''))
    } finally {
      setDangLuuNh(false)
    }
  }

  if (!ds) return null

  const dsLoc = tuKhoa.trim()
    ? ds.filter((n) =>
        (n.email || '').toLowerCase().includes(tuKhoa.trim().toLowerCase()) ||
        (n.ten_hien || '').toLowerCase().includes(tuKhoa.trim().toLowerCase()),
      )
    : ds

  return (
    <section className="quan-tri manga-admin-panel">
      <div className="quan-tri-dau">
        <div>
          <h2>🛡️ Trung tâm Quản trị & Theo dõi Gói cước — Tài khoản ({ds.length})</h2>
          <p className="ghi-chu" style={{ marginTop: 4 }}>
            Quản lý người dùng, theo dõi sản lượng dịch thuật theo thời gian thực và kích hoạt gói VIP cho khách hàng.
          </p>
        </div>
      </div>

      {loi && <Alert sac="loi" tieuDe="Không làm được" onDong={() => setLoi(null)}>{loi}</Alert>}
      {thongBaoOk && <Alert sac="ok" tieuDe="Đã cập nhật thành công" onDong={() => setThongBaoOk(null)}>{thongBaoOk}</Alert>}

      {thongKe && (
        <div className="luoi-thong-ke-admin" aria-label="Thống kê hệ thống">
          <div className="the-so-lieu-admin">
            <span className="nhan-so-lieu">👥 Tổng khách hàng</span>
            <strong className="gia-tri-so-lieu">{thongKe.tong_nguoi_dung}</strong>
            <span className="phu-so-lieu">{thongKe.nguoi_dung_hoat_dong} đang hoạt động</span>
          </div>
          <div className="the-so-lieu-admin vip">
            <span className="nhan-so-lieu">💎 Tài khoản VIP / Có gói</span>
            <strong className="gia-tri-so-lieu">{thongKe.so_khach_vip}</strong>
            <span className="phu-so-lieu">Còn {thongKe.tong_luot_tich_luy_con_lai.toLocaleString('vi-VN')} lượt tích luỹ</span>
          </div>
          <div className="the-so-lieu-admin">
            <span className="nhan-so-lieu">🔥 Trang dịch hôm nay</span>
            <strong className="gia-tri-so-lieu">{thongKe.trang_dich_hom_nay.toLocaleString('vi-VN')}</strong>
            <span className="phu-so-lieu">Tính từ 0h00 giờ Việt Nam</span>
          </div>
          <div className="the-so-lieu-admin">
            <span className="nhan-so-lieu">📈 Sản lượng 7 ngày qua</span>
            <strong className="gia-tri-so-lieu">{thongKe.trang_dich_7_ngay.toLocaleString('vi-VN')}</strong>
            <span className="phu-so-lieu">Trang đã xử lý thành công</span>
          </div>
          <div className="the-so-lieu-admin">
            <span className="nhan-so-lieu">📚 Tổng trang toàn thời gian</span>
            <strong className="gia-tri-so-lieu">{thongKe.trang_dich_toan_thoi_gian.toLocaleString('vi-VN')}</strong>
            <span className="phu-so-lieu">Trên tổng số {thongKe.tong_chapter} chapter</span>
          </div>
        </div>
      )}

      {/* Thanh kích hoạt gói cước / Cấp lượt VIP nhanh cho khách hàng */}
      <form className="khung-cap-goi-admin" onSubmit={xuLyCapGoi}>
        <div className="tieu-de-cap-goi">
          <strong>⚡ Kích hoạt Gói cước / Cấp lượt VIP cho khách hàng</strong>
          <span className="ghi-chu">Chọn nhanh gói bên dưới hoặc nhập số lượt bất kỳ (dùng chung cho Web, Tiện ích Chrome & App Windows)</span>
        </div>
        <div className="hang-goi-nhanh">
          <span
            role="button"
            tabIndex={0}
            className={`nhan-goi-nhanh ${congLuot === '100' ? 'dang-chon' : ''}`}
            onClick={() => setCongLuot('100')}
            onKeyDown={(e) => { if (e.key === 'Enter') setCongLuot('100') }}
          >
            🌱 Gói Khởi Động (+100 trang)
          </span>
          <span
            role="button"
            tabIndex={0}
            className={`nhan-goi-nhanh ${congLuot === '550' ? 'dang-chon' : ''}`}
            onClick={() => setCongLuot('550')}
            onKeyDown={(e) => { if (e.key === 'Enter') setCongLuot('550') }}
          >
            🔥 Gói Cày Truyện (+550 trang)
          </span>
          <span
            role="button"
            tabIndex={0}
            className={`nhan-goi-nhanh ${congLuot === '1200' ? 'dang-chon' : ''}`}
            onClick={() => setCongLuot('1200')}
            onKeyDown={(e) => { if (e.key === 'Enter') setCongLuot('1200') }}
          >
            👑 Gói Studio / Nhóm Dịch (+1.200 trang)
          </span>
          <span
            role="button"
            tabIndex={0}
            className={`nhan-goi-nhanh ${congLuot === '6500' ? 'dang-chon' : ''}`}
            onClick={() => setCongLuot('6500')}
            onKeyDown={(e) => { if (e.key === 'Enter') setCongLuot('6500') }}
          >
            🏢 Gói Doanh Nghiệp API (+6.500 trang)
          </span>
          <span
            role="button"
            tabIndex={0}
            className={`nhan-goi-nhanh ${congLuot === '28000' ? 'dang-chon' : ''}`}
            onClick={() => setCongLuot('28000')}
            onKeyDown={(e) => { if (e.key === 'Enter') setCongLuot('28000') }}
          >
            🏛️ Gói Enterprise (+28.000 trang)
          </span>
        </div>
        <div className="hang-o-cap-goi">
          <input
            type="email"
            className="o"
            list="ds-email-khach-hang"
            placeholder="Nhập hoặc chọn Email khách hàng..."
            value={emailCap}
            onChange={(e) => setEmailCap(e.target.value)}
            required
          />
          <datalist id="ds-email-khach-hang">
            {ds.map((u) => (
              <option key={u.id} value={u.email}>{u.ten_hien || u.email}</option>
            ))}
          </datalist>
          <input
            type="number"
            className="o"
            placeholder="Số lượt cộng thêm (vd: 200)"
            value={congLuot}
            onChange={(e) => setCongLuot(e.target.value)}
            title="Số lượt mua thêm cộng vào tài khoản (nhập số âm nếu muốn trừ bớt)"
          />
          <input
            type="number"
            className="o"
            placeholder="Trần VIP/ngày (tuỳ chọn, vd: 100)"
            value={tranVip}
            onChange={(e) => setTranVip(e.target.value)}
            title="Đặt trần lượt miễn phí mỗi ngày riêng cho khách VIP (bỏ trống = giữ nguyên)"
          />
          <Button type="submit" kieu="chinh" disabled={dangCap}>
            {dangCap ? 'Đang kích hoạt…' : '💎 Kích hoạt ngay'}
          </Button>
        </div>
      </form>

      {/* Cấu hình VietQR Ngân hàng & Webhook Tự động 24/7 (SePay / Casso) */}
      <details className="khung-vietqr-admin" style={{ marginBottom: 18 }}>
        <summary style={{ cursor: 'pointer', fontWeight: 800, fontSize: 14 }}>
          🏦 Cấu hình Mã QR Ngân hàng (VietQR) &amp; Tự động cộng lượt 24/7 (SePay / Casso)
          {nhTen && nhSoTk ? ` — Đang bật (${nhTen}: ${nhSoTk} - ${nhChuTk})` : ' — Chưa cài STK'}
        </summary>
        <form onSubmit={xuLyLuuNganHang} style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <p className="ghi-chu" style={{ margin: 0 }}>
            Mặc định đã cấu hình sẵn <strong>ACB — 20260457 — NGUYEN THIEN TRIEU</strong> (Quản trị: <code>thientrieu753@gmail.com</code>).
            Khi kết nối Webhook của <strong>SePay.vn</strong> hoặc <strong>Casso.vn</strong> trỏ về địa chỉ{' '}
            <code>{typeof window !== 'undefined' ? `${window.location.origin}/api/v1/nap-luot/webhook` : '/api/v1/nap-luot/webhook'}</code>,
            khách quét mã chuyển khoản xong sẽ được <strong>tự động đối soát và cộng lượt sau 5 giây</strong> kể cả nửa đêm!
          </p>
          <div className="hang-o-cap-goi">
            <input
              type="text"
              className="o"
              placeholder="Mã Ngân hàng (VD: MB, VCB, ACB, TCB, VPB, BIDV...)"
              value={nhTen}
              onChange={(e) => setNhTen(e.target.value)}
            />
            <input
              type="text"
              className="o"
              placeholder="Số tài khoản nhận tiền..."
              value={nhSoTk}
              onChange={(e) => setNhSoTk(e.target.value)}
            />
            <input
              type="text"
              className="o"
              placeholder="Tên chủ tài khoản (IN HOA KHÔNG DẤU)..."
              value={nhChuTk}
              onChange={(e) => setNhChuTk(e.target.value)}
            />
            <Button type="submit" kieu="phu" disabled={dangLuuNh}>
              {dangLuuNh ? 'Đang lưu…' : '💾 Lưu VietQR'}
            </Button>
          </div>
        </form>
      </details>

      {/* Bảng đơn chuyển khoản khách đã chọn trên trang Bảng Giá */}
      {Array.isArray(thongKe?.don_nap_gan_day) && thongKe.don_nap_gan_day.length > 0 && (
        <div className="khung-cap-goi-admin" style={{ marginBottom: 18 }}>
          <div className="tieu-de-cap-goi" style={{ marginBottom: 10 }}>
            <strong>📋 Lịch sử Đơn Chuyển Khoản Khách Đã Chọn ({thongKe.don_nap_gan_day.length} đơn gần nhất)</strong>
            <span className="ghi-chu">
              Ghi nhận tự động khi khách chọn gói &amp; bấm xác nhận chuyển khoản tới ACB 20260457 (NGUYEN THIEN TRIEU)
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="bang-tai-khoan">
              <thead>
                <tr>
                  <th>Mã đơn</th>
                  <th>Khách hàng</th>
                  <th>Gói đã chọn</th>
                  <th>Số tiền</th>
                  <th>Số trang</th>
                  <th>Nội dung CK</th>
                  <th>Trạng thái</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {thongKe.don_nap_gan_day.map((don) => (
                  <tr key={don.ma_don}>
                    <td><code>{don.ma_don}</code></td>
                    <td><strong>{don.email}</strong></td>
                    <td>{don.ten_goi}</td>
                    <td><strong>{Number(don.so_tien_vnd || 0).toLocaleString('vi-VN')}đ</strong></td>
                    <td>+{Number(don.so_trang_cong || 0).toLocaleString('vi-VN')} trang</td>
                    <td><code>{don.noi_dung_chuyen_khoan}</code></td>
                    <td>
                      {don.trang_thai === 'da_xac_nhan' && (
                        <span style={{ color: '#059669', fontWeight: 700 }}>✅ Đã khớp sao kê</span>
                      )}
                      {don.trang_thai === 'da_cong_tu_dong' && (
                        <span style={{ color: '#0284c7', fontWeight: 700 }}>⚡ Đã tự động kích hoạt</span>
                      )}
                      {don.trang_thai === 'cho_duyet' && (
                        <span style={{ color: '#d97706', fontWeight: 700 }}>⏳ Chờ xác nhận</span>
                      )}
                      {don.trang_thai === 'da_thu_hoi' && (
                        <span style={{ color: '#dc2626', fontWeight: 700 }}>⛔ Đã thu hồi</span>
                      )}
                    </td>
                    <td className="hang-cong-cu">
                      {don.trang_thai !== 'da_xac_nhan' && (
                        <Button
                          kieu="chinh"
                          disabled={dangLam === don.ma_don}
                          onClick={() =>
                            lam(don.ma_don, () =>
                              api.quanTriDuyetDonNap({ ma_don: don.ma_don, hanh_dong: 'xac_nhan' })
                            )
                          }
                        >
                          ✅ Xác nhận
                        </Button>
                      )}
                      {don.trang_thai !== 'da_thu_hoi' && (
                        <Button
                          kieu="phu"
                          disabled={dangLam === don.ma_don}
                          onClick={() =>
                            lam(don.ma_don, () =>
                              api.quanTriDuyetDonNap({ ma_don: don.ma_don, hanh_dong: 'thu_hoi' })
                            )
                          }
                        >
                          Thu hồi
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {ds.length > 3 && (
        <div style={{ marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
          <input
            type="search"
            className="o"
            placeholder="🔍 Tìm nhanh theo email hoặc tên khách hàng…"
            value={tuKhoa}
            onChange={(e) => setTuKhoa(e.target.value)}
            style={{ maxWidth: 340 }}
          />
          <span className="ghi-chu">Đang hiển thị {dsLoc.length} / {ds.length} tài khoản</span>
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table className="bang-tai-khoan">
          <thead>
            <tr>
              <th>Email</th>
              <th>Tên</th>
              <th>Vai trò</th>
              <th>Hôm nay</th>
              <th>Lượt tích luỹ</th>
              <th>Tổng đã dịch</th>
              <th>Trạng thái</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {dsLoc.map((n) => {
              const laToi = n.id === toi?.id
              const tranNgay = n.tran_hang_ngay ?? n.tran_hang_ngay_rieng ?? 20
              const daDung = n.da_dung_hom_nay ?? 0
              const muaThem = n.so_luot_mua_them ?? 0
              const tongDich = n.tong_trang_da_dich ?? 0
              const coVip = muaThem > 0 || Boolean(n.tran_hang_ngay_rieng)
              return (
                <tr
                  key={n.id}
                  onClick={() => { if (! emailCap) setEmailCap(n.email) }}
                  style={{ cursor: 'pointer' }}
                  title="Bấm vào dòng để điền nhanh email vào ô Kích hoạt gói"
                >
                  <td>
                    <strong>{n.email}</strong>
                    {coVip && <span className="nhan-vip-nho">VIP</span>}
                  </td>
                  <td>{n.ten_hien || <span className="ghi-chu">—</span>}</td>
                  <td>{n.la_quan_tri ? 'Quản trị' : 'Thường'}</td>
                  <td>
                    <span>{daDung} / {tranNgay}</span>
                    {n.tran_hang_ngay_rieng ? <span className="ghi-chu"> (VIP)</span> : null}
                  </td>
                  <td>
                    <strong style={{ color: muaThem > 0 ? '#059669' : 'inherit' }}>
                      {muaThem.toLocaleString('vi-VN')}
                    </strong>
                    {' '}trang
                  </td>
                  <td>
                    {tongDich.toLocaleString('vi-VN')} trang
                    {n.so_chapter ? <span className="ghi-chu"> ({n.so_chapter} chap)</span> : null}
                  </td>
                  <td>{n.dang_hoat_dong === false ? 'Đã khoá' : 'Đang dùng'}</td>
                  <td className="hang-cong-cu" onClick={(e) => e.stopPropagation()}>
                    {/* Không hiện nút cho chính mình: tự khoá là tự đẩy mình ra ngoài, và nếu
                        đây là quản trị duy nhất thì không còn ai mở lại được. Máy chủ cũng chặn,
                        nhưng hiện một cái nút chắc chắn báo lỗi là thiết kế tồi. */}
                    {laToi ? <span className="ghi-chu">(bạn)</span> : (
                      <>
                        <Button
                          kieu="phu" disabled={dangLam === n.id}
                          onClick={() => lam(n.id, () => api.doiTrangThaiNguoiDung(
                            n.id, { dang_hoat_dong: n.dang_hoat_dong === false }))}
                        >
                          {n.dang_hoat_dong === false ? 'Mở khoá' : 'Khoá'}
                        </Button>
                        <Button
                          kieu="phu" disabled={dangLam === n.id}
                          onClick={() => lam(n.id, () => api.doiTrangThaiNguoiDung(
                            n.id, { la_quan_tri: !n.la_quan_tri }))}
                        >
                          {n.la_quan_tri ? 'Thu quyền quản trị' : 'Phong quản trị'}
                        </Button>
                        <Button
                          kieu="phu" disabled={dangLam === n.id}
                          onClick={() => {
                            if (!window.confirm(
                              `Xoá hẳn tài khoản ${n.email}?\n\n` +
                              'Chapter của họ KHÔNG bị xoá — chúng trở về "chưa có chủ" và người ' +
                              'khác nhận được.\n\nMuốn giữ nguyên chủ sở hữu thì bấm Khoá.'
                            )) return
                            lam(n.id, () => api.xoaNguoiDung(n.id))
                          }}
                        >
                          Xoá
                        </Button>
                      </>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="ghi-chu" style={{ marginTop: 10 }}>
        <b>Khoá</b> giữ nguyên chapter của họ và cắt phiên đang mở ngay lập tức.
        {' '}<b>Xoá</b> làm chapter của họ thành <i>chưa có chủ</i>.
        {' '}Nên có <b>ít nhất hai quản trị</b>: mất tài khoản quản trị duy nhất là không ai
        quản lý được người dùng nữa.
      </p>
    </section>
  )
}
