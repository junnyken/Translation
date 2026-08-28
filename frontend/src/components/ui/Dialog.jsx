import { useEffect, useRef } from 'react'

/** Hộp thoại dùng chung cho cảnh báo/xác nhận.
 *
 * Bẫy thường gặp: hộp thoại không đóng được bằng bàn phím, và focus vẫn nằm ở trang phía sau
 * nên người dùng bàn phím "tab vào hư không". Ở đây: Esc đóng, focus đưa vào hộp khi mở.
 */
export default function Dialog({ tieuDe, onDong, children, chan = [] }) {
  const hop = useRef(null)
  useEffect(() => {
    const nghe = (e) => { if (e.key === 'Escape') onDong() }
    window.addEventListener('keydown', nghe)
    hop.current?.focus()
    return () => window.removeEventListener('keydown', nghe)
  }, [onDong])

  return (
    <div className="lop-phu" onClick={(e) => e.target === e.currentTarget && onDong()}>
      <div className="hop-thoai" role="dialog" aria-modal="true" aria-label={tieuDe}
           tabIndex={-1} ref={hop}>
        <h2>{tieuDe}</h2>
        {children}
        {chan.length > 0 && <div className="chan-hop-thoai">{chan}</div>}
      </div>
    </div>
  )
}
