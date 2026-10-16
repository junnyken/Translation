import { useRef } from 'react'
import Icon from './Icon.jsx'

/** Tab theo mẫu ARIA (WAI-ARIA Authoring Practices): `tablist` / `tab` / `tabpanel`.
 *
 * - Roving tabindex: chỉ tab đang chọn nằm trong thứ tự Tab; ← → chuyển và đổi luôn tab
 *   (kích hoạt tự động — hai tab này rẻ, không có lý do bắt bấm thêm Enter), Home/End nhảy
 *   đầu/cuối.
 * - Chỉ render nội dung của tab đang chọn (`children`), giống hành vi cũ: đổi tab là gỡ form kia.
 *
 * `cacTab` = [{ ma, nhan, icon }]. `idGoc` để các id `tb-<ma>` / `tp-<ma>` không trùng nhau.
 */
export default function Tabs({ nhan, cacTab, chon, onDoi, idGoc = 'tab', children }) {
  const refs = useRef({})

  const chuyenToi = (i) => {
    const t = cacTab[(i + cacTab.length) % cacTab.length]
    onDoi(t.ma)
    refs.current[t.ma]?.focus()
  }

  const onPhim = (e, i) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); chuyenToi(i + 1) }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); chuyenToi(i - 1) }
    else if (e.key === 'Home') { e.preventDefault(); chuyenToi(0) }
    else if (e.key === 'End') { e.preventDefault(); chuyenToi(cacTab.length - 1) }
  }

  return (
    <>
      <div className="tabs" role="tablist" aria-label={nhan}>
        {cacTab.map((t, i) => (
          <button
            key={t.ma} ref={(el) => { refs.current[t.ma] = el }}
            type="button" role="tab" className="tab"
            id={`${idGoc}-tb-${t.ma}`} aria-controls={`${idGoc}-tp-${t.ma}`}
            aria-selected={chon === t.ma} tabIndex={chon === t.ma ? 0 : -1}
            onClick={() => onDoi(t.ma)} onKeyDown={(e) => onPhim(e, i)}
          >
            {t.icon && <Icon ten={t.icon} />}{t.nhan}
          </button>
        ))}
      </div>
      <div
        role="tabpanel" className="tab-noi-dung" tabIndex={0}
        id={`${idGoc}-tp-${chon}`} aria-labelledby={`${idGoc}-tb-${chon}`}
      >
        {children}
      </div>
    </>
  )
}
