import { useEffect, useId, useRef } from 'react'

const DIEM_FOCUS = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])', 'textarea:not([disabled])', '[tabindex]:not([tabindex="-1"])',
].join(',')

/** Hộp thoại dùng chung cho cảnh báo/xác nhận/xem ảnh.
 *
 * Bẫy thường gặp của hộp thoại tự viết:
 *  - không đóng được bằng bàn phím  → Esc đóng;
 *  - focus vẫn nằm ở trang phía sau, "tab vào hư không" → focus đưa vào hộp khi mở và bị GIỮ
 *    trong hộp (Tab ở phần tử cuối quay về đầu, Shift+Tab ngược lại);
 *  - đóng xong người dùng bàn phím mất vị trí → trả focus về đúng nút đã mở hộp.
 *
 * Props: `tieuDe` (chuỗi, bắt buộc — thành <h2> và tên của hộp), `onDong`, `rong` (bản rộng cho
 * xem ảnh), `chan` (mảng nút ở chân hộp).
 */
export default function Dialog({ tieuDe, onDong, children, chan = [], rong = false }) {
  const hop = useRef(null)
  const idTieuDe = useId()
  // Giữ `onDong` mới nhất trong ref: cha hay truyền arrow function mới mỗi lần vẽ, nếu để nó trong
  // deps thì effect chạy lại và cướp focus về hộp giữa lúc người dùng đang gõ vào ô.
  const dongRef = useRef(onDong)
  dongRef.current = onDong

  useEffect(() => {
    const nutMo = document.activeElement
    hop.current?.focus()
    const nghe = (e) => {
      if (e.key === 'Escape') { dongRef.current(); return }
      if (e.key !== 'Tab' || !hop.current) return
      // jsdom không có layout (offsetParent luôn null) nên lọc bằng thuộc tính `hidden`, không bằng kích thước.
      const ds = [...hop.current.querySelectorAll(DIEM_FOCUS)].filter((el) => !el.closest('[hidden]'))
      if (ds.length === 0) { e.preventDefault(); hop.current.focus(); return }
      const dau = ds[0]
      const cuoi = ds[ds.length - 1]
      const dangO = document.activeElement
      if (!hop.current.contains(dangO) || dangO === hop.current) {
        e.preventDefault(); (e.shiftKey ? cuoi : dau).focus()
      } else if (e.shiftKey && dangO === dau) {
        e.preventDefault(); cuoi.focus()
      } else if (!e.shiftKey && dangO === cuoi) {
        e.preventDefault(); dau.focus()
      }
    }
    document.addEventListener('keydown', nghe)
    return () => {
      document.removeEventListener('keydown', nghe)
      if (nutMo && typeof nutMo.focus === 'function' && document.contains(nutMo)) nutMo.focus()
    }
  }, [])

  return (
    <div className="lop-phu" onClick={(e) => e.target === e.currentTarget && onDong()}>
      <div className={`hop-thoai${rong ? ' hop-thoai-rong' : ''}`} role="dialog" aria-modal="true"
           aria-labelledby={idTieuDe} tabIndex={-1} ref={hop}>
        <h2 id={idTieuDe}>{tieuDe}</h2>
        {children}
        {chan.length > 0 && <div className="chan-hop-thoai">{chan}</div>}
      </div>
    </div>
  )
}
