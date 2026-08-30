/** E15 §D3 — thẻ tổng hợp hướng chữ của một trang.
 *
 * Luật: **"chưa kiểm" không bao giờ được gộp vào "không sao".** `not_analyzed_count` có ô riêng,
 * vì một trang chưa chạy bước nhận biết hướng chữ trông y hệt một trang toàn chữ ngang nếu ta
 * để chúng chung một con số 0.
 */
export default function OrientationSummaryCard({ tomTat, dangBan, onChayLai }) {
  if (!tomTat) return null

  const {
    total_regions: tong = 0,
    horizontal_count: ngang = 0,
    vertical_ready_count: doc_xong = 0,
    vertical_review_count: doc_can_xem = 0,
    rotated_review_count: nghieng = 0,
    unknown_count: chua_ro = 0,
    unavailable_count: chua_dung = 0,
    not_analyzed_count: chua_kiem = 0,
  } = tomTat

  const o = [
    { nhan: 'Chữ ngang', so: ngang, sac: 'ok' },
    { nhan: 'Chữ dọc — đã căn theo cột', so: doc_xong, sac: 'ok' },
    { nhan: 'Chữ dọc — cần kiểm tra', so: doc_can_xem, sac: 'canh' },
    { nhan: 'Chữ nghiêng/cách điệu', so: nghieng, sac: 'canh' },
    { nhan: 'Chưa xác định hướng', so: chua_ro, sac: 'canh' },
    { nhan: 'Chưa kiểm hướng chữ', so: chua_kiem, sac: 'trung' },
  ]

  const can_xem = doc_can_xem + nghieng + chua_ro

  return (
    <section className="the-tom-tat-huong">
      <div className="hang-tieu-de">
        <h3>Hướng chữ</h3>
        {onChayLai && (
          <button type="button" className="nut nut-phu" disabled={dangBan} onClick={onChayLai}>
            {dangBan ? 'Đang chạy lại…' : 'Chạy lại nhận biết hướng chữ'}
          </button>
        )}
      </div>

      <ul className="ds-so-lieu">
        {o.map((m) => (
          <li key={m.nhan} className={`so-lieu so-lieu-${m.sac}`}>
            <b>{m.so}</b>
            <span>{m.nhan}</span>
          </li>
        ))}
      </ul>

      <p className="ghi-chu">
        {tong} vùng trên trang này.
        {can_xem > 0
          ? ` ${can_xem} vùng nên tự nhìn lại trước khi xuất.`
          : ' Không vùng nào bị đánh dấu cần xem lại.'}
      </p>

      {chua_dung > 0 && (
        <p className="ghi-chu nhan-manh">
          {chua_dung} vùng nhận ra là chữ dọc nhưng hệ thống <b>chưa dựng được</b> chữ theo cột.
          Chữ ở những vùng đó vẫn đang được căn ngang.
        </p>
      )}

      {chua_kiem > 0 && (
        <p className="ghi-chu">
          {chua_kiem} vùng <b>chưa được kiểm</b> hướng chữ — khác với &ldquo;đã kiểm và không
          sao&rdquo;.
        </p>
      )}
    </section>
  )
}
