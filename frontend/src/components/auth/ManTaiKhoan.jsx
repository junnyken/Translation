import { useEffect, useState } from 'react'

import * as api from '../../api'
import { chuDemNguoc } from '../../lib/dem-nguoc'
import Alert from '../ui/Alert'
import Button from '../ui/Button'
import Dialog from '../ui/Dialog'
import Icon from '../ui/Icon'
import { Input } from '../ui/Field'

/** Màn tài khoản (§4.4 đặc tả) — xem và SỬA (E56).
 *
 * ## Nguyên tắc: hiện ĐÚNG những gì có thật
 *
 * §4.4 nói rõ: *"Hiện đúng những gì có thật: email, tên hiển thị, hạn mức đã dùng / còn lại, mốc
 * reset. **Không** bịa thêm hạng thành viên hay số liệu chưa có thật."*
 *
 * Nên ở đây **không** có: hạng thành viên, tổng số trang đã dịch từ đầu, số chapter, ngày tham
 * gia, chuỗi ngày liên tiếp — hệ thống **không lưu** những thứ đó. Một màn tài khoản trông đầy
 * đặn bằng số liệu bịa thì tệ hơn một màn ngắn nói thật.
 *
 * ## Vì sao hạn mức lấy từ `/han-muc` chứ không tự tính
 *
 * `con_lai` là **nhỏ nhất** trong các chốt, không phải `tran - da_dung`. Tự tính lại ở đây sẽ cho
 * một con số khác với con số ở trang chủ, và người dùng thấy hai số vênh nhau trên cùng một sản
 * phẩm thì không biết tin cái nào.
 *
 * ## E56 — vì sao ô "nhập lại mật khẩu mới" là BẮT BUỘC
 *
 * Hệ thống **không có hạ tầng gửi thư** (giới hạn đã ghi ở `REPORT_E52.md`), nên **không có đường
 * lấy lại mật khẩu**. Gõ sai mật khẩu mới một lần là mất tài khoản vĩnh viễn — không phải "bất
 * tiện", mà là mất hẳn dữ liệu. Ô nhập lại là thứ duy nhất chặn được chuyện đó, và nó so ở NGAY
 * trình duyệt để người dùng biết trước khi bấm.
 *
 * ## Nói TRƯỚC hệ quả, không phải báo sau
 *
 * Đổi mật khẩu thu hồi mọi phiên khác (`services/tai_khoan.doi_mat_khau` giải thích vì sao). Câu
 * cảnh báo nằm cạnh nút, **trước** khi bấm — báo sau khi đã đăng xuất điện thoại của người ta thì
 * đã muộn.
 */
export default function ManTaiKhoan({ nguoiDung, onDong, onDoiNguoiDung }) {
  const [hanMuc, setHanMuc] = useState(null)
  const [loi, setLoi] = useState(null)

  useEffect(() => {
    let huy = false
    api.layHanMuc()
      .then((hm) => { if (!huy) setHanMuc(hm) })
      .catch((e) => { if (!huy) setLoi(e) })
    return () => { huy = true }
  }, [])

  const giuPhut = hanMuc?.giu_ket_qua_phut ?? null

  return (
    <Dialog tieuDe="Tài khoản của bạn" onDong={onDong}>
      <dl className="man-tai-khoan">
        <dt>Email</dt>
        <dd>{nguoiDung.email}</dd>
      </dl>
      {/* Email KHÔNG sửa được ở đây — có chủ đích, xem docstring của `SuaTaiKhoanRequest`. */}
      <p className="ghi-chu">
        Email là tên đăng nhập nên không đổi được ở đây. Cần đổi thì nhờ người quản trị.
      </p>

      <OTenHien nguoiDung={nguoiDung} onXong={onDoiNguoiDung} />

      {nguoiDung.la_quan_tri && (
        <dl className="man-tai-khoan">
          <dt>Quyền</dt>
          <dd>Quản trị</dd>
        </dl>
      )}

      <OMatKhau />

      <h3 className="nho">Lượt dịch hôm nay</h3>

      {loi && (
        <Alert sac="canh" tieuDe="Chưa lấy được hạn mức">{String(loi.message || loi)}</Alert>
      )}

      {!loi && !hanMuc && <p className="ghi-chu" aria-live="polite">Đang xem…</p>}

      {hanMuc && (
        <>
          <p className="so-luot">
            <strong>{hanMuc.con_lai}</strong> / {hanMuc.tran} trang còn lại
            {' '}<span className="ghi-chu">(đã dùng {hanMuc.da_dung})</span>
          </p>
          <p className="ghi-chu">
            <Icon ten="dong-ho" co={14} /> Có lại sau{' '}
            <strong>{chuDemNguoc(hanMuc.reset_luc)}</strong> (0h00 giờ Việt Nam)
          </p>

          {/* `con_lai` khác `tran - da_dung` khi một chốt khác thấp hơn. Nói ra khi hai số vênh,
              thay vì để người dùng tự trừ rồi thấy mình tính sai. */}
          {hanMuc.con_lai !== hanMuc.tran - hanMuc.da_dung && (
            <p className="ghi-chu">
              Số còn lại thấp hơn phép trừ vì lượt còn được tính theo <strong>địa chỉ mạng</strong>
              {' '}dùng chung.
            </p>
          )}

          <h3 className="nho">Kết quả được giữ bao lâu</h3>
          <p className="ghi-chu">
            {typeof giuPhut === 'number'
              ? <>Tự xoá <strong>{giuPhut} phút</strong> sau khi dịch xong — ảnh gốc, bản dịch và
                  tệp đã gói đều mất, không chạy lại và không sửa lại được.</>
              : <>Hiện <strong>không tự xoá</strong> theo giờ. Vẫn nên tải về: đây không phải chỗ
                  lưu trữ lâu dài, và chính sách có thể đổi.</>}
          </p>
        </>
      )}
    </Dialog>
  )
}

/** Tên hiển thị — sửa tại chỗ, KHÔNG đòi mật khẩu.
 *
 * Đòi mật khẩu cho một thao tác vô hại là dạy người dùng gõ mật khẩu vào bất cứ ô nào hỏng ra —
 * đó là huấn luyện cho lừa đảo, không phải bảo mật.
 */
function OTenHien({ nguoiDung, onXong }) {
  const [moSua, setMoSua] = useState(false)
  const [ten, setTen] = useState(nguoiDung.ten_hien || '')
  const [dangLuu, setDangLuu] = useState(false)
  const [loi, setLoi] = useState(null)
  const [xong, setXong] = useState(false)

  const luu = async () => {
    setDangLuu(true); setLoi(null)
    try {
      const kq = await api.suaTaiKhoanCuaToi({ ten_hien: ten })
      onXong?.(kq.nguoi_dung)
      setXong(true)
      setMoSua(false)
    } catch (e) {
      setLoi(e)
    } finally {
      setDangLuu(false)
    }
  }

  if (!moSua) {
    return (
      <>
        <dl className="man-tai-khoan">
          <dt>Tên hiển thị</dt>
          <dd>
            {nguoiDung.ten_hien
              ? nguoiDung.ten_hien
              : <span className="ghi-chu">(chưa đặt — đang dùng phần trước @)</span>}
            {' '}
            <Button kieu="phu" onClick={() => { setMoSua(true); setXong(false) }}>Sửa</Button>
          </dd>
        </dl>
        {xong && <Alert sac="ok" tieuDe="Đã lưu tên hiển thị" />}
      </>
    )
  }

  return (
    <form className="khoi-sua" onSubmit={(e) => { e.preventDefault(); luu() }}>
      <Input
        nhan="Tên hiển thị" value={ten} onChange={(e) => setTen(e.target.value)}
        moTa="Để trống thì hệ thống lấy phần trước @ của email."
        maxLength={120}
      />
      {loi && <Alert sac="loi" tieuDe="Chưa lưu được">{thongDiep(loi)}</Alert>}
      <div className="hang-nut">
        <Button type="submit" kieu="chinh" dangChay={dangLuu}>Lưu</Button>
        <Button onClick={() => { setMoSua(false); setTen(nguoiDung.ten_hien || ''); setLoi(null) }}>
          Huỷ
        </Button>
      </div>
    </form>
  )
}

/** Đổi mật khẩu. Đóng sẵn — mở ra mới hiện ô, để màn chính không thành một rừng ô nhập. */
function OMatKhau() {
  const [mo, setMo] = useState(false)
  const [cu, setCu] = useState('')
  const [moi, setMoi] = useState('')
  const [lai, setLai] = useState('')
  const [dangLuu, setDangLuu] = useState(false)
  const [loi, setLoi] = useState(null)
  const [ketQua, setKetQua] = useState(null)

  const dong = () => {
    setMo(false); setCu(''); setMoi(''); setLai(''); setLoi(null)
  }

  // Kiểm NGAY ở trình duyệt: không có đường lấy lại mật khẩu, nên gõ lệch hai ô là mất tài khoản.
  const lechNhau = lai.length > 0 && moi !== lai
  const quaNgan = moi.length > 0 && moi.length < 8
  const lyDoKhoa = !cu || !moi || !lai
    ? 'Nhập đủ ba ô.'
    : lechNhau
      ? 'Hai ô mật khẩu mới chưa khớp.'
      : quaNgan
        ? 'Mật khẩu mới phải dài ít nhất 8 ký tự.'
        : undefined

  const luu = async () => {
    setDangLuu(true); setLoi(null)
    try {
      const kq = await api.suaTaiKhoanCuaToi({ mat_khau_cu: cu, mat_khau_moi: moi })
      setKetQua(kq)
      dong()
    } catch (e) {
      setLoi(e)
    } finally {
      setDangLuu(false)
    }
  }

  if (!mo) {
    return (
      <>
        <h3 className="nho">Mật khẩu</h3>
        {ketQua && (
          <Alert sac="ok" tieuDe="Đã đổi mật khẩu">
            {ketQua.so_phien_khac_da_thu_hoi > 0
              ? <>Đã đăng xuất <strong>{ketQua.so_phien_khac_da_thu_hoi}</strong> thiết bị khác.
                  Máy này vẫn đang đăng nhập.</>
              : <>Không có thiết bị nào khác đang đăng nhập. Máy này vẫn đang đăng nhập.</>}
          </Alert>
        )}
        <p className="ghi-chu">
          <Button onClick={() => { setMo(true); setKetQua(null) }}>Đổi mật khẩu</Button>
        </p>
      </>
    )
  }

  return (
    /* PHẢI là <form>. Ô mật khẩu ngoài form thì Chrome ghi thẳng vào console
       ("Password field is not contained in a form") và — quan trọng hơn — trình quản lý mật khẩu
       KHÔNG nhận ra đây là lượt đổi mật khẩu, nên nó giữ nguyên mật khẩu cũ đã lưu. Lần đăng nhập
       sau nó tự điền mật khẩu cũ và người dùng tưởng việc đổi đã thất bại. Bọc form cũng cho phép
       bấm Enter để gửi, thứ mọi người đều thử. */
    <form className="khoi-sua" onSubmit={(e) => { e.preventDefault(); if (!lyDoKhoa) luu() }}>
      <h3 className="nho">Đổi mật khẩu</h3>
      <Input
        nhan="Mật khẩu hiện tại" type="password" autoComplete="current-password" batBuoc
        value={cu} onChange={(e) => setCu(e.target.value)}
      />
      <Input
        nhan="Mật khẩu mới" type="password" autoComplete="new-password" batBuoc
        value={moi} onChange={(e) => setMoi(e.target.value)}
        moTa="Ít nhất 8 ký tự."
        loi={quaNgan ? 'Mật khẩu mới phải dài ít nhất 8 ký tự.' : undefined}
      />
      <Input
        nhan="Nhập lại mật khẩu mới" type="password" autoComplete="new-password" batBuoc
        value={lai} onChange={(e) => setLai(e.target.value)}
        loi={lechNhau ? 'Hai ô chưa khớp.' : undefined}
        moTa="Không có đường lấy lại mật khẩu, nên phải gõ đúng hai lần."
      />

      {/* Nói TRƯỚC khi bấm. Báo sau khi đã đăng xuất điện thoại của người ta thì đã muộn. */}
      <Alert sac="canh" tieuDe="Các thiết bị khác sẽ bị đăng xuất">
        Đổi mật khẩu sẽ thu hồi mọi phiên đăng nhập khác. Máy bạn đang dùng thì vẫn đăng nhập.
      </Alert>

      {loi && <Alert sac="loi" tieuDe="Chưa đổi được">{thongDiep(loi)}</Alert>}

      <div className="hang-nut">
        <Button
          type="submit" kieu="chinh" dangChay={dangLuu} lyDoKhoa={lyDoKhoa} id="nut-doi-mk"
        >
          Đổi mật khẩu
        </Button>
        <Button onClick={dong}>Huỷ</Button>
      </div>
    </form>
  )
}

/** Lấy câu của MÁY CHỦ, không thay bằng câu chung.
 *
 * Máy chủ phân biệt "mật khẩu hiện tại không đúng" với "mật khẩu mới phải khác" — thay cả hai
 * bằng "có lỗi xảy ra" là bắt người dùng đoán xem mình sai ở đâu.
 */
function thongDiep(e) {
  if (typeof e?.cauNguoiDoc === 'string' && e.cauNguoiDoc) return e.cauNguoiDoc
  return String(e?.message || e)
}
