
/** Danh sách chapter đã mở **trên trình duyệt này**.
 *
 * Nói rõ "trên trình duyệt này" là bắt buộc: backend chưa có endpoint liệt kê project (đã ghi
 * thành khoảng trống trong REPORT_E11), nên danh sách này lấy từ bộ nhớ trình duyệt. Gọi nó là
 * "tất cả chapter của bạn" sẽ là nói quá — mở máy khác là mất.
 */
export default function ChapterRecentList({ danhSach }) {
  if (!danhSach.length) {
    // E63 — lúc trống, khối này CHỈ là một dòng.
    //
    // Bản cũ dựng một `EmptyState` cao gần bằng cả cột form bên trái, với một nút chính
    // "Tạo chapter đầu tiên". Hai vấn đề, cả hai nhìn thấy được trên màn thật:
    //
    // 1. Nó là nút chính THỨ HAI trên cùng một màn, cạnh "Dịch ngay" — hai nút cùng màu đậm
    //    tranh nhau làm hành động chính, mà chúng dẫn đi hai nơi khác nhau.
    // 2. Nó là lối vào THỨ BA cho cùng một việc (tab "Tạo chapter mới", mục "Tạo chapter" trên
    //    thanh đầu trang). Nhiều lối vào giống hệt nhau không làm người dùng nhanh hơn, nó làm
    //    họ dừng lại đoán xem ba cái đó có khác nhau không.
    return (
      <section className="the-lon" aria-labelledby="tieu-de-gan-day">
        <header className="the-dau"><h2 id="tieu-de-gan-day">Chapter gần đây</h2></header>
        <p className="gan-day-trong">
          Chưa có chapter nào trên trình duyệt này. Chapter bạn tạo sẽ hiện ở đây; đã có mã sẵn
          thì dán vào ô tìm ở đầu trang.
        </p>
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
