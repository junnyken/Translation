import Button from '../ui/Button.jsx'
import EmptyState from '../ui/EmptyState.jsx'

/** Danh sách chapter đã mở **trên trình duyệt này**.
 *
 * Nói rõ "trên trình duyệt này" là bắt buộc: backend chưa có endpoint liệt kê project (đã ghi
 * thành khoảng trống trong REPORT_E11), nên danh sách này lấy từ bộ nhớ trình duyệt. Gọi nó là
 * "tất cả chapter của bạn" sẽ là nói quá — mở máy khác là mất.
 */
export default function ChapterRecentList({ danhSach, onTaoMoi }) {
  if (!danhSach.length) {
    return (
      <section className="the-lon" aria-labelledby="tieu-de-gan-day">
        <header className="the-dau"><h2 id="tieu-de-gan-day">Chapter gần đây</h2></header>
        <EmptyState
          tieuDe="Chưa có chapter nào"
          moTa="Tạo chapter đầu tiên để bắt đầu dịch. Bạn cũng có thể dán mã chapter vào ô tìm ở đầu trang nếu đã có sẵn."
        >
          <Button kieu="chinh" onClick={onTaoMoi}>Tạo chapter đầu tiên</Button>
        </EmptyState>
      </section>
    )
  }

  return (
    <section className="the-lon" aria-labelledby="tieu-de-gan-day">
      <header className="the-dau">
        <h2 id="tieu-de-gan-day">Chapter gần đây</h2>
        <p>Ghi nhớ trên trình duyệt này. Mở ở máy khác thì dùng mã chapter.</p>
      </header>
      <ul className="ds-chapter">
        {danhSach.map((c) => (
          <li key={c.id}>
            <a href={`#project=${c.id}`}>
              <b>{c.ten}</b>
              <span className="ma">{c.id.slice(0, 8)}</span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}
