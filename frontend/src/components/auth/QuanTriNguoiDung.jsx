import { useEffect, useState } from 'react'
import * as api from '../../api.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'

/** Danh bạ tài khoản — chỉ quản trị thấy (Auth slice B1a).
 *
 * Vì sao cần: phát tài khoản ra được mà không thu lại được thì "cho người khác dùng" mới xong
 * một nửa. Không có màn này, muốn gỡ một người phải sửa tay trong CSDL — mà CSDL trên bản chạy
 * thật thì không phải lúc nào cũng với tới.
 *
 * **Khoá** và **xoá** là hai việc khác nhau, và màn này phải nói rõ sự khác nhau đó:
 * khoá giữ nguyên chapter của họ, xoá làm chapter thành vô chủ.
 */
export default function QuanTriNguoiDung({ toi }) {
  const [ds, setDs] = useState(null)
  const [loi, setLoi] = useState(null)
  const [dangLam, setDangLam] = useState(null)

  async function nap() {
    try { setDs(await api.layDanhSachNguoiDung()) } catch (e) { setLoi(String(e?.message || e)) }
  }
  useEffect(() => { nap() }, [])

  async function lam(id, viec) {
    setDangLam(id); setLoi(null)
    try { await viec(); await nap() }
    catch (e) { setLoi(String(e?.message || e).replace(/^\d+:\s*/, '')) }
    finally { setDangLam(null) }
  }

  if (!ds) return null

  return (
    <section className="quan-tri">
      <h2>Tài khoản ({ds.length})</h2>
      {loi && <Alert sac="loi" tieuDe="Không làm được" onDong={() => setLoi(null)}>{loi}</Alert>}
      <table className="bang-tai-khoan">
        <thead>
          <tr><th>Email</th><th>Tên</th><th>Vai trò</th><th>Trạng thái</th><th /></tr>
        </thead>
        <tbody>
          {ds.map((n) => {
            const laToi = n.id === toi?.id
            return (
              <tr key={n.id}>
                <td>{n.email}</td>
                <td>{n.ten_hien}</td>
                <td>{n.la_quan_tri ? 'Quản trị' : 'Thường'}</td>
                <td>{n.dang_hoat_dong === false ? 'Đã khoá' : 'Đang dùng'}</td>
                <td className="hang-cong-cu">
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
      <p className="ghi-chu">
        <b>Khoá</b> giữ nguyên chapter của họ và cắt phiên đang mở ngay lập tức.
        {' '}<b>Xoá</b> làm chapter của họ thành <i>chưa có chủ</i>.
        {' '}Nên có <b>ít nhất hai quản trị</b>: mất tài khoản quản trị duy nhất là không ai
        quản lý được người dùng nữa.
      </p>
    </section>
  )
}
