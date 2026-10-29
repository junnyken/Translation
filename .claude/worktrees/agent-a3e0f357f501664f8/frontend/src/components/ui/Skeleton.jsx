/** Khung chờ (skeleton) — thay chữ "Đang tải…" trơ trọi bằng hình dạng của nội dung sắp tới.
 *
 * Vẫn có chữ cho trình đọc màn hình (`role="status"` + `.an-di`), nên người dùng/test tìm theo chữ
 * "Đang tải…" vẫn thấy. Hiệu ứng chạy sáng tắt khi `prefers-reduced-motion: reduce` (xem styles.css).
 *
 * `kieu="dong"` — vài dòng chữ (`soDong`); `kieu="khoi"` — một khối (ảnh/canvas), `cao` là px.
 */
export default function Skeleton({ kieu = 'dong', soDong = 3, cao, nhan = 'Đang tải…', className = '' }) {
  return (
    <div className={`skeleton ${className}`.trim()} role="status" aria-live="polite" aria-busy="true">
      <span className="an-di">{nhan}</span>
      {kieu === 'khoi'
        ? <span className="skeleton-khoi" aria-hidden="true" style={cao ? { minHeight: cao } : undefined} />
        : Array.from({ length: soDong }, (_, i) => (
          <span key={i} className="skeleton-dong" aria-hidden="true" />
        ))}
    </div>
  )
}
