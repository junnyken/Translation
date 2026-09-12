import {
  LY_DO_HUONG_CHU, NGUON_HUONG_CHU, nhanHuongChu,
} from '../lib/status-presentation.js'
import StatusBadge from './ui/StatusBadge.jsx'

/** E15 §D2 — khối giải thích hướng chữ của MỘT vùng.
 *
 * Ba luật của khối này:
 *
 * 1. **Chỉ dịch mã lý do, không tự diễn giải thêm.** Mã nào backend không gửi thì không được
 *    bịa ra câu tương ứng; mã lạ hiện nguyên mã thô để còn lần ra.
 * 2. **Lưới cột chữ chỉ hiện khi `status === 'ready'`.** Vẽ lưới cột cho một vùng mà hệ thống
 *    chưa dựng được chữ dọc là vẽ ra một thứ không tồn tại.
 * 3. **Chữ nghiêng phải nói thẳng là bản này không tự xoay** — không để người dùng ngồi chờ
 *    một thao tác sẽ không bao giờ xảy ra.
 */
export default function OrientationBox({ huongChu, hienLuoi, onDoiLuoi }) {
  // Chưa phân tích khác hẳn "đã phân tích và không rõ" — nói đúng cái nào là cái nào.
  if (!huongChu) {
    return (
      <div className="the-huong-chu">
        <b>Chưa nhận biết hướng chữ</b>
        <p className="ghi-chu">
          Vùng này chưa được chạy bước nhận biết hướng chữ. Đây <b>không</b> có nghĩa là chữ ngang.
        </p>
      </div>
    )
  }

  const d = nhanHuongChu(huongChu.orientation, huongChu.status, huongChu.reason_codes)
  const ly_do = huongChu.reason_codes ?? []
  const la_doc_san_sang = huongChu.orientation === 'vertical_ttb' && huongChu.status === 'ready'
  const la_nghieng = huongChu.orientation === 'rotated_horizontal'

  return (
    <div className="the-huong-chu">
      <div className="hang-tieu-de">
        <b>Hướng chữ</b>
        <StatusBadge dienGiai={d} />
      </div>

      <p className="ghi-chu">{d.mo_ta}</p>

      {/* Bằng chứng là thứ để TRA KHI CẦN, không phải thứ chiếm mặt tiền.
       *
       * Trên trang tiếng Nhật, mọi vùng đều ra `unknown` (đo được: `MangaOCREngine.recognize()`
       * không trả đường bao dòng), nên bảng căn cứ + danh sách lý do lặp lại y hệt nhau ở MỌI
       * vùng và đẩy bản dịch — thứ người ta thật sự cần nhìn — xuống dưới màn hình.
       *
       * Thu vào `<details>` khi KHÔNG có kết luận gì đáng chú ý; còn khi hệ thống thật sự nhận ra
       * chữ dọc hoặc chữ nghiêng thì mở sẵn, vì lúc đó bằng chứng mới có ích. Không XOÁ gì —
       * đúng nguyên tắc "nói ra căn cứ" của E15. */}
      <details className="chi-tiet-ky-thuat" open={la_doc_san_sang || la_nghieng}>
        <summary>Căn cứ kỹ thuật</summary>
      <dl className="bang-bang-chung">
        <dt>Căn cứ</dt>
        <dd>{NGUON_HUONG_CHU[huongChu.source] ?? huongChu.source}</dd>
        {huongChu.line_count_estimate != null && (
          <>
            <dt>Số dòng đo được</dt>
            <dd>{huongChu.line_count_estimate}</dd>
          </>
        )}
        {huongChu.rotation_degrees != null && (
          <>
            <dt>Góc nghiêng</dt>
            <dd>{huongChu.rotation_degrees}°</dd>
          </>
        )}
      </dl>

      {ly_do.length > 0 && (
        <ul className="ds-ly-do">
          {ly_do.map((m) => (
            <li key={m}>{LY_DO_HUONG_CHU[m] ?? m}</li>
          ))}
        </ul>
      )}
      </details>

      {la_nghieng && (
        <p className="ghi-chu">
          Chữ dịch đã được <b>đặt nghiêng theo đúng góc này</b>, và tự thu nhỏ cho nằm gọn trong
          bong bóng. Thấy chưa ưng thì chỉnh tay được ở phần sửa bên dưới.
        </p>
      )}

      {la_doc_san_sang && (
        <label className="o-chon">
          <input type="checkbox" checked={!!hienLuoi} onChange={(e) => onDoiLuoi?.(e.target.checked)} />
          <span>Hiện lưới cột chữ</span>
        </label>
      )}
    </div>
  )
}
