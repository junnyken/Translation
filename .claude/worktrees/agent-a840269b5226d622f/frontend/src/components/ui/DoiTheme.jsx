import { useEffect, useState } from 'react'
import Icon from './Icon.jsx'

/** Nút đổi giao diện Sáng / Tối / Theo máy. Mặc định "Theo máy" (không ghi gì vào `data-theme`,
 *  để CSS đi theo `prefers-color-scheme`). Lựa chọn lưu ở localStorage; storage bị chặn (chế độ
 *  riêng tư, iframe…) thì vẫn đổi được trong phiên, chỉ là không nhớ.
 *
 *  Nhãn là câu MỚI nên đặt hằng số để BA duyệt câu chữ. */
const KHOA = 'translation.theme'
// wording: BA review
const NHAN_NHOM = 'Giao diện'
// wording: BA review
const LUA_CHON = [
  { ma: 'light', icon: 'sun', nhan: 'Giao diện sáng' },
  { ma: 'dark', icon: 'moon', nhan: 'Giao diện tối' },
  { ma: 'auto', icon: 'monitor', nhan: 'Giao diện theo máy' },
]

export function docTheme() {
  try {
    const v = window.localStorage.getItem(KHOA)
    return v === 'light' || v === 'dark' ? v : 'auto'
  } catch { return 'auto' }
}

export function apDungTheme(ma) {
  const goc = document.documentElement
  if (ma === 'light' || ma === 'dark') goc.setAttribute('data-theme', ma)
  else goc.removeAttribute('data-theme')
}

export default function DoiTheme() {
  const [ma, setMa] = useState(docTheme)
  useEffect(() => { apDungTheme(ma) }, [ma])

  const chon = (moi) => {
    setMa(moi)
    try {
      if (moi === 'auto') window.localStorage.removeItem(KHOA)
      else window.localStorage.setItem(KHOA, moi)
    } catch { /* không lưu được thì thôi — vẫn đổi trong phiên này */ }
  }

  return (
    <div className="doi-theme" role="group" aria-label={NHAN_NHOM}>
      {LUA_CHON.map((l) => (
        <button
          key={l.ma} type="button" className="doi-theme-nut"
          aria-label={l.nhan} title={l.nhan} aria-pressed={ma === l.ma}
          onClick={() => chon(l.ma)}
        >
          <Icon ten={l.icon} co={16} />
        </button>
      ))}
    </div>
  )
}
