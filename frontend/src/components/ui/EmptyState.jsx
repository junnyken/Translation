import Icon from './Icon.jsx'

/** Chỗ trống có ích: nói rõ vì sao trống và làm gì tiếp — thay cho một dòng chữ nhỏ lạc lõng.
 *
 * `gon` = dòng rỗng gọn (icon nhỏ + tiêu đề + mô tả cùng một khối, không khung nét đứt cao) —
 * dùng khi trống là trạng thái BÌNH THƯỜNG của một mục phụ, không phải cả màn.
 */
export default function EmptyState({ icon = 'sach', tieuDe, moTa, gon = false, children }) {
  if (gon) {
    return (
      <div className="trong trong-gon">
        <Icon ten={icon} co={16} />
        <div className="trong-gon-chu">
          <h3>{tieuDe}</h3>
          {moTa && <p>{moTa}</p>}
        </div>
        {children}
      </div>
    )
  }
  return (
    <div className="trong">
      <div className="trong-icon"><Icon ten={icon} co={24} /></div>
      <h3>{tieuDe}</h3>
      {moTa && <p>{moTa}</p>}
      {children}
    </div>
  )
}
