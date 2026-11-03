import { createContext, useContext, useEffect, useState } from 'react'

const KHOA_NGON_NGU_UI = 'translation:ui-lang'
export const CAC_NGON_NGU_HO_TRO = ['vi', 'en', 'es', 'pt', 'fr']

export const SEO_META_BY_LANG = {
  vi: {
    title: 'comic.io.vn — Dịch Truyện Tranh AI Miễn Phí | Manga, Manhwa, Webtoon',
    description:
      'Nền tảng dịch truyện tranh tự động bằng AI (Manga, Manhwa, Manhua, Comic) sang 9 ngôn ngữ. Tự xoá chữ gốc LaMa, dàn chữ chuẩn thẩm mỹ, hỗ trợ Tiện ích Chrome, App Windows & API.',
    canonical: 'https://comic.io.vn/',
  },
  en: {
    title: 'comic.io.vn — Free AI Manga, Manhwa & Webtoon Translator Online',
    description:
      'Translate raw Japanese Manga, Korean Manhwa, Chinese Manhua & Webtoons online in 3 seconds. AI bubble detection, LaMa background inpainting & smart typesetting in 9 languages.',
    canonical: 'https://comic.io.vn/en',
  },
  es: {
    title: 'comic.io.vn — Traductor de Manga, Manhwa y Webtoon con IA Gratis',
    description:
      'Traduce manga raw, manhwa coreano y cómics online en segundos con IA. Detección de bocadillos, limpieza de texto LaMa y tipografía automática en 9 idiomas.',
    canonical: 'https://comic.io.vn/es',
  },
  pt: {
    title: 'comic.io.vn — Tradutor de Mangá, Manhwa e Webtoon com IA Grátis',
    description:
      'Traduza mangá raw, manhwa e quadrinhos online em segundos com Inteligência Artificial. Limpeza de balões LaMa, OCR inteligente e diagramação automática.',
    canonical: 'https://comic.io.vn/pt',
  },
  fr: {
    title: 'comic.io.vn — Traducteur de Manga, Manhwa et Webtoon par IA Gratuit',
    description:
      'Traduisez vos scans manga raw, manhwa et webtoons en ligne en quelques secondes grâce à l’IA. Nettoyage LaMa, OCR précis et lettrage automatique.',
    canonical: 'https://comic.io.vn/fr',
  },
}

export const HERO_I18N = {
  vi: {
    h1: 'Dịch truyện tranh sang tiếng Việt',
    subtitle: 'Thả ảnh trang truyện vào đây là chạy — không cần đăng ký trước.',
    bubbleLeft: 'Dịch Tự Động Siêu Tốc — Chuẩn Phong Cách Truyện Tranh!',
    navTranslate: '🏠 Dịch Truyện',
    navExt: '🧩 Tiện Ích',
    navApi: '⚡ Kết Nối API',
    navPricing: '💎 Bảng Giá',
    signIn: 'Đăng nhập',
    newChapter: 'Tạo chapter',
  },
  en: {
    h1: 'AI Manga, Manhwa & Webtoon Translator',
    subtitle: 'Drop comic pages or chapter archives (.zip / .cbz / .pdf) here to translate instantly — no sign-up required.',
    bubbleLeft: 'Instant Comic Translation — Natural Layout & Genre Fonts!',
    navTranslate: '🏠 Translate',
    navExt: '🧩 Extensions & App',
    navApi: '⚡ Developer API',
    navPricing: '💎 Pricing',
    signIn: 'Sign In',
    newChapter: 'New Chapter',
  },
  es: {
    h1: 'Traductor de Manga, Manhwa y Webtoon con IA',
    subtitle: 'Suelta páginas de cómic o capítulos (.zip / .cbz / .pdf) aquí para traducir al instante — sin registro obligatorio.',
    bubbleLeft: '¡Traducción Instantánea de Cómics — Limpieza LaMa y Fuentes por Género!',
    navTranslate: '🏠 Traducir',
    navExt: '🧩 Extensión y App',
    navApi: '⚡ API Desarrollador',
    navPricing: '💎 Precios',
    signIn: 'Iniciar sesión',
    newChapter: 'Nuevo Capítulo',
  },
  pt: {
    h1: 'Tradutor de Mangá, Manhwa e Webtoon com IA',
    subtitle: 'Arraste páginas ou capítulos (.zip / .cbz / .pdf) aqui para traduzir instantaneamente — sem necessidade de cadastro.',
    bubbleLeft: 'Tradução Instantânea de Quadrinhos — Limpeza LaMa e Fontes de Estúdio!',
    navTranslate: '🏠 Traduzir',
    navExt: '🧩 Extensão e App',
    navApi: '⚡ API Developer',
    navPricing: '💎 Planos e Preços',
    signIn: 'Entrar',
    newChapter: 'Novo Capítulo',
  },
  fr: {
    h1: 'Traducteur de Manga, Manhwa & Webtoon par IA',
    subtitle: 'Glissez vos pages ou chapitres (.zip / .cbz / .pdf) ici pour traduire instantanément — sans inscription requise.',
    bubbleLeft: 'Traduction Instantanée de Scans — Nettoyage LaMa & Lettrage Pro !',
    navTranslate: '🏠 Traduire',
    navExt: '🧩 Extension & App',
    navApi: '⚡ API Développeur',
    navPricing: '💎 Tarifs',
    signIn: 'Connexion',
    newChapter: 'Nouveau Chapitre',
  },
}

const NgonNguUIContext = createContext({
  lang: 'vi',
  setLang: () => {},
  laEn: false,
})

export function chuanHoaNgonNguUI(ma) {
  const s = String(ma || '').toLowerCase().trim()
  if (s.startsWith('pt')) return 'pt'
  if (s.startsWith('es')) return 'es'
  if (s.startsWith('fr')) return 'fr'
  if (s.startsWith('en')) return 'en'
  if (s.startsWith('vi')) return 'vi'
  return ''
}

export function docNgonNguTuUrl() {
  try {
    const params = new URLSearchParams(window.location.search || '')
    const qLang = chuanHoaNgonNguUI(params.get('lang'))
    if (qLang) return qLang

    const seg = (window.location.pathname || '')
      .replace(/^\/+|\/+$/g, '')
      .split('/')[0]
    const pLang = chuanHoaNgonNguUI(seg)
    if (pLang && seg.length <= 5) return pLang
  } catch {
    /* bỏ qua */
  }
  return ''
}

export function docNgonNguUI() {
  const tuUrl = docNgonNguTuUrl()
  if (tuUrl) return tuUrl
  try {
    const v = chuanHoaNgonNguUI(window.localStorage.getItem(KHOA_NGON_NGU_UI))
    return v || 'vi'
  } catch {
    return 'vi'
  }
}

export function NgonNguUIProvider({ children }) {
  const [lang, setLangState] = useState(docNgonNguUI)

  const setLang = (moi, capNhatUrl = false) => {
    const chuan = chuanHoaNgonNguUI(moi) || 'vi'
    setLangState(chuan)
    try {
      window.localStorage.setItem(KHOA_NGON_NGU_UI, chuan)
    } catch {
      /* bỏ qua nếu trình duyệt chặn localStorage */
    }
    if (capNhatUrl) {
      try {
        const curPath = window.location.pathname.replace(/^\/+|\/+$/g, '')
        const segs = curPath ? curPath.split('/') : []
        if (segs.length > 0 && CAC_NGON_NGU_HO_TRO.includes(segs[0])) {
          segs.shift()
        }
        const rest = segs.join('/')
        const nextPath = chuan === 'vi'
          ? (rest ? `/${rest}` : '/')
          : (rest ? `/${chuan}/${rest}` : `/${chuan}`)
        if (window.location.pathname !== nextPath && !window.location.hash.includes('project=') && !window.location.hash.includes('page=')) {
          window.history.pushState({}, '', `${nextPath}${window.location.hash || ''}`)
        }
      } catch {
        /* bỏ qua */
      }
    }
  }

  useEffect(() => {
    try {
      document.documentElement.lang = lang
      const seo = SEO_META_BY_LANG[lang] || SEO_META_BY_LANG.en
      if (seo) {
        document.title = seo.title
        const metaDesc = document.querySelector('meta[name="description"]')
        if (metaDesc) metaDesc.setAttribute('content', seo.description)
        const canonical = document.getElementById('seo-canonical')
        if (canonical) canonical.setAttribute('href', seo.canonical)
        const ogTitle = document.getElementById('seo-og-title')
        if (ogTitle) ogTitle.setAttribute('content', seo.title)
        const ogDesc = document.getElementById('seo-og-desc')
        if (ogDesc) ogDesc.setAttribute('content', seo.description)
      }
    } catch {
      /* bỏ qua */
    }
  }, [lang])

  return (
    <NgonNguUIContext.Provider value={{ lang, setLang, laEn: lang !== 'vi' }}>
      {children}
    </NgonNguUIContext.Provider>
  )
}

export function useNgonNguUI() {
  return useContext(NgonNguUIContext)
}

const DANH_SACH_NUT_LANG = [
  { ma: 'vi', nhan: '🇻🇳 VN', title: 'Tiếng Việt' },
  { ma: 'en', nhan: '🇺🇸 EN', title: 'English (International)' },
  { ma: 'es', nhan: '🇪🇸 ES', title: 'Español (LATAM & España)' },
  { ma: 'pt', nhan: '🇧🇷 PT', title: 'Português (Brasil)' },
  { ma: 'fr', nhan: '🇫🇷 FR', title: 'Français' },
]

/**
 * Công tắc chuyển đổi ngôn ngữ giao diện Website: 🇻🇳 VN | 🇺🇸 EN | 🇪🇸 ES | 🇧🇷 PT | 🇫🇷 FR
 * Dùng `role="radio"` trong `role="radiogroup"` để hỗ trợ trợ năng và không đụng các bài test
 * tìm `getByRole('button')`.
 */
export function DoiNgonNguUI() {
  const { lang, setLang } = useNgonNguUI()

  return (
    <div
      className="doi-ngon-ngu-ui"
      role="radiogroup"
      aria-label={lang === 'vi' ? 'Ngôn ngữ giao diện' : 'Website language'}
    >
      {DANH_SACH_NUT_LANG.map((item) => (
        <span
          key={item.ma}
          role="radio"
          tabIndex={0}
          aria-checked={lang === item.ma}
          className={`nut-lang-ui ${lang === item.ma ? 'dang-chon' : ''}`}
          onClick={() => setLang(item.ma, true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') setLang(item.ma, true)
          }}
          title={item.title}
        >
          {item.nhan}
        </span>
      ))}
    </div>
  )
}
