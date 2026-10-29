import { useState } from 'react'

// wording: BA review — nhãn chỗ mở ra được
export const NHAN_GIAI_THICH = 'Giải thích'
export const NHAN_CHI_TIET = 'Chi tiết'
export const NHAN_THU_GON = 'Thu gọn'

/** Đoạn giải thích dài: thu lại thành một dòng nhãn, mở ra vẫn là NGUYÊN VĂN. */
export function GiaiThich({ nhan = NHAN_GIAI_THICH, children }) {
  return (
    <details className="giai-thich">
      <summary>{nhan}</summary>
      <div className="giai-thich-noi-dung">{children}</div>
    </details>
  )
}

/** Chữ dài rút còn một dòng (CSS line-clamp) + nút "Chi tiết" mở ra toàn văn.
 * Chỉ MỘT bản chữ trong DOM — không nhân đôi giữa bản rút gọn và bản đầy đủ. */
export function ChuRutGon({ children, dai = false, so = 1 }) {
  const [mo, setMo] = useState(false)
  return (
    <span className="chu-rut-gon">
      <span
        className={mo ? 'chu-rut-gon-chu mo' : 'chu-rut-gon-chu'}
        style={mo ? undefined : { WebkitLineClamp: so }}
      >
        {children}
      </span>
      {dai && (
        <button type="button" className="lien-ket" aria-expanded={mo} onClick={() => setMo(!mo)}>
          {mo ? NHAN_THU_GON : NHAN_CHI_TIET}
        </button>
      )}
    </span>
  )
}
