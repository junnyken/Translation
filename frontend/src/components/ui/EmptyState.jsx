import Icon from './Icon.jsx'

/** Chỗ trống có ích: nói rõ vì sao trống và làm gì tiếp — thay cho một dòng chữ nhỏ lạc lõng. */
export default function EmptyState({ icon = 'sach', tieuDe, moTa, children }) {
  return (
    <div className="trong">
      <div className="trong-icon"><Icon ten={icon} co={22} /></div>
      <h3>{tieuDe}</h3>
      {moTa && <p>{moTa}</p>}
      {children}
    </div>
  )
}
