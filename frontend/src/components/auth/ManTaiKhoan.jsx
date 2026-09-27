import { useEffect, useState } from 'react'

import * as api from '../../api'
import { chuDemNguoc } from '../../lib/dem-nguoc'
import Alert from '../ui/Alert'
import Dialog from '../ui/Dialog'
import Icon from '../ui/Icon'

/** Màn tài khoản (§4.4 đặc tả).
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
 */
export default function ManTaiKhoan({ nguoiDung, onDong }) {
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

        <dt>Tên hiển thị</dt>
        {/* Bỏ trống thì máy chủ lấy phần trước @ — nói ra thay vì hiện một ô rỗng bí ẩn. */}
        <dd>{nguoiDung.ten_hien || <span className="ghi-chu">(chưa đặt — đang dùng phần trước @)</span>}</dd>

        {nguoiDung.la_quan_tri && (
          <>
            <dt>Quyền</dt>
            <dd>Quản trị</dd>
          </>
        )}
      </dl>

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
