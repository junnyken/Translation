import { dienGiaiTrangThai } from '../../lib/status-presentation.js'
import Icon from './Icon.jsx'

/** Huy hiệu trạng thái: **icon + chữ + màu**, theo đúng thứ tự quan trọng.
 *
 * Màu là lớp cuối cùng chứ không phải lớp duy nhất — bỏ màu đi vẫn phải đọc được trạng thái.
 */
export default function StatusBadge({ loai, trangThai, boiCanh, hienMoTa = false, dienGiai }) {
  // `dienGiai` cho phép các bảng không tra được bằng (loai, trangThai) — như hướng chữ của E15,
  // vốn phụ thuộc CẢ hướng lẫn trạng thái — dùng lại đúng component này thay vì đẻ huy hiệu mới.
  const d = dienGiai ?? dienGiaiTrangThai(loai, trangThai, boiCanh)
  return (
    <span className={`the-tt the-tt-${d.sac}`} title={d.mo_ta}>
      <Icon ten={d.icon} co={13} />
      <span>{d.nhan}</span>
      {hienMoTa && d.mo_ta && <span className="the-tt-mo-ta">{d.mo_ta}</span>}
    </span>
  )
}
