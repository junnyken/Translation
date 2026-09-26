import { useEffect, useState } from 'react'

import * as api from '../../api'
import { chuDemNguoc } from '../../lib/dem-nguoc'
import Alert from '../ui/Alert'
import Icon from '../ui/Icon'

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
  const [nhip, setNhip] = useState(0)

  // Nhịp lại mỗi 30 giây để đồng hồ không đứng im trên một tab để mở lâu. 30 giây là đủ: chuỗi
  // chữ chỉ hiện tới phút, nên nhịp dày hơn chỉ tốn lượt render mà không đổi được gì trên màn.
  useEffect(() => {
    const t = setInterval(() => setNhip((n) => n + 1), 30_000)
    return () => clearInterval(t)
  }, [])

  if (loi) {
    return (
      <Alert sac="canh" tieuDe="Chưa lấy được hạn mức">
        {String(loi.message || loi)}
        {onTaiLai && (
          <>
            {' '}
            <button type="button" className="nut-chu" onClick={onTaiLai}>Thử lại</button>
          </>
        )}
      </Alert>
    )
  }

  if (dangTai || !hanMuc) {
    return <p className="the-han-muc dang-tai" aria-live="polite">Đang xem bạn còn bao nhiêu lượt…</p>
  }

  const chan = api.chotDangChan(hanMuc)
  const chanBoiMangChung = chan?.loai === 'khach_ip'
  const conLai = hanMuc.con_lai
  const sacVien = conLai <= 0 ? 'loi' : conLai <= 2 ? 'canh' : 'ok'

  return (
    <section className={`the-han-muc vien-${sacVien}`} aria-labelledby="tieu-de-han-muc">
      <h2 id="tieu-de-han-muc" className="nho">Lượt dịch hôm nay</h2>

      {/* Màu KHÔNG bao giờ là nguồn thông tin duy nhất: luôn kèm con số và nhãn chữ. */}
      <p className="so-luot">
        <strong>{conLai}</strong> / {hanMuc.tran} trang còn lại
      </p>

      <p className="ghi-chu moc-reset">
        <Icon ten="dong-ho" co={14} /> Có lại sau <strong>{chuDemNguoc(hanMuc.reset_luc)}</strong>
        {' '}(0h00 giờ Việt Nam)
      </p>

      {conLai <= 0 && (
        <Alert sac="loi" tieuDe={chanBoiMangChung ? 'Địa chỉ mạng này đã hết lượt chung' : 'Bạn đã hết lượt hôm nay'}>
          {chanBoiMangChung ? (
            <>
              Lượt được tính theo <strong>địa chỉ mạng</strong>, nên nếu bạn đang ở văn phòng,
              trường học hay quán cà phê thì người khác cùng mạng đã dùng hết. Bạn có thể đợi tới
              0h00, hoặc đổi sang mạng khác.
            </>
          ) : (
            <>Đợi tới 0h00 giờ Việt Nam là có lại.</>
          )}
          {!hanMuc.co_tai_khoan && (
            <> Tạo tài khoản thì được nhiều lượt hơn mỗi ngày.</>
          )}
        </Alert>
      )}

      {conLai > 0 && !hanMuc.co_tai_khoan && (
        <p className="ghi-chu">Tạo tài khoản để được nhiều lượt hơn mỗi ngày.</p>
      )}

      {/* Chi tiết từng chốt — chỉ hiện khi CÓ NHIỀU HƠN MỘT chốt, tức người gọi là khách lạ.
          Người đã đăng nhập chỉ có một chốt, bày bảng một dòng ra là tiếng ồn. */}
      {(hanMuc.chot || []).length > 1 && (
        <details className="chi-tiet-chot">
          <summary>Lượt được tính thế nào?</summary>
          <ul>
            {hanMuc.chot.map((c) => (
              <li key={c.loai}>
                {c.loai === 'khach_cookie' ? 'Theo trình duyệt này' : 'Theo địa chỉ mạng (dùng chung)'}
                : {c.da_dung}/{c.tran} trang
              </li>
            ))}
          </ul>
          <p className="ghi-chu">
            Phải còn lượt ở <strong>cả hai</strong> mới dịch được. Trần theo địa chỉ mạng cao hơn
            vì nhiều người có thể dùng chung một mạng.
          </p>
        </details>
      )}
    </section>
  )
}
