import { createContext, useContext, useEffect, useState } from 'react'

const KHOA_NGON_NGU_UI = 'translation:ui-lang'

const NgonNguUIContext = createContext({
  lang: 'vi',
  setLang: () => {},
  laEn: false,
})

export function docNgonNguUI() {
  try {
    const v = window.localStorage.getItem(KHOA_NGON_NGU_UI)
    return v === 'en' ? 'en' : 'vi'
  } catch {
    return 'vi'
  }
}

export function NgonNguUIProvider({ children }) {
  const [lang, setLangState] = useState(docNgonNguUI)

  const setLang = (moi) => {
    const chuan = moi === 'en' ? 'en' : 'vi'
    setLangState(chuan)
    try {
      window.localStorage.setItem(KHOA_NGON_NGU_UI, chuan)
    } catch {
      /* bỏ qua nếu trình duyệt chặn localStorage */
    }
  }

  useEffect(() => {
    try {
      document.documentElement.lang = lang
    } catch {
      /* bỏ qua */
    }
  }, [lang])

  return (
    <NgonNguUIContext.Provider value={{ lang, setLang, laEn: lang === 'en' }}>
      {children}
    </NgonNguUIContext.Provider>
  )
}

export function useNgonNguUI() {
  return useContext(NgonNguUIContext)
}

/**
 * Công tắc chuyển đổi ngôn ngữ giao diện Website: 🇻🇳 VN | 🇺🇸 EN
 * Dùng `role="radio"` trong `role="radiogroup"` để hỗ trợ trợ năng và không đụng các bài test
 * tìm `getByRole('button')`.
 */
export function DoiNgonNguUI() {
  const { lang, setLang } = useNgonNguUI()

  return (
    <div
      className="doi-ngon-ngu-ui"
      role="radiogroup"
      aria-label={lang === 'en' ? 'Website language' : 'Ngôn ngữ giao diện'}
    >
      <span
        role="radio"
        tabIndex={0}
        aria-checked={lang === 'vi'}
        className={`nut-lang-ui ${lang === 'vi' ? 'dang-chon' : ''}`}
        onClick={() => setLang('vi')}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setLang('vi') }}
        title="Tiếng Việt"
      >
        🇻🇳 VN
      </span>
      <span
        role="radio"
        tabIndex={0}
        aria-checked={lang === 'en'}
        className={`nut-lang-ui ${lang === 'en' ? 'dang-chon' : ''}`}
        onClick={() => setLang('en')}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setLang('en') }}
        title="English (International)"
      >
        🇺🇸 EN
      </span>
    </div>
  )
}
