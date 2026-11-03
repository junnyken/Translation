import { createContext, useContext, useEffect, useState } from 'react'

const KHOA_NGON_NGU_UI = 'translation:ui-lang'
export const CAC_NGON_NGU_HO_TRO = ['vi', 'en']

export const SEO_META_BY_PAGE = {
  home: {
    vi: {
      title: 'comic.io.vn — Dịch Truyện Tranh AI Miễn Phí | Manga, Manhwa, Webtoon & API',
      description:
        'Nền tảng dịch truyện tranh tự động bằng AI (Manga, Manhwa, Manhua, Comic) sang 9 ngôn ngữ quốc tế. Tự tái tạo nền sạch, dàn chữ chuẩn thẩm mỹ, hỗ trợ Tiện ích Chrome, App Windows & B2B REST API.',
      canonical: 'https://comic.io.vn/',
    },
    en: {
      title: 'comic.io.vn — Free AI Manga, Manhwa & Webtoon Translator Online + REST API',
      description:
        'Translate raw Japanese Manga, Korean Manhwa, Chinese Manhua & Webtoons online in ~3 seconds. AI bubble detection, smart background inpainting & studio typesetting in 9 languages.',
      canonical: 'https://comic.io.vn/en',
    },
  },
  'ket-noi-api': {
    vi: {
      title: 'API Dịch Truyện Tranh AI (B2B REST API & RapidAPI) — comic.io.vn',
      description:
        'Tích hợp REST API dịch truyện tranh tự động (OCR, xoá chữ tái tạo nền, dịch ngữ cảnh 9 ngôn ngữ) vào Website đọc truyện, App Mobile & công cụ Scanlation với khoá tr_live_... bảo mật.',
      canonical: 'https://comic.io.vn/ket-noi-api',
    },
    en: {
      title: 'AI Manga & Webtoon Translation REST API (OpenAPI 3.0 & RapidAPI) — comic.io.vn',
      description:
        'Enterprise B2B REST API for automated Manga, Manhwa & Webtoon OCR, speech bubble detection, clean background inpainting & 9-language translation. Ready for RapidAPI, Python, Node.js & cURL.',
      canonical: 'https://comic.io.vn/api-docs',
    },
  },
  'bang-gia': {
    vi: {
      title: 'Bảng Giá Dịch Truyện Tranh AI & Gói API B2B (VNĐ / USD) — comic.io.vn',
      description:
        'Tặng miễn phí 10 trang/ngày cho mọi tài khoản. Gói lượt dịch tích luỹ không giới hạn thời gian và gói API B2B cho nhóm dịch, Website đọc truyện chỉ từ 19.000đ ($0.99 USD).',
      canonical: 'https://comic.io.vn/bang-gia',
    },
    en: {
      title: 'Pricing & B2B API Plans — AI Manga & Webtoon Translator | comic.io.vn',
      description:
        'Get 10 free translated pages every day. Flexible non-expiring credit packs and high-volume B2B API plans for readers, scanlation teams, and platforms starting at $0.99 USD.',
      canonical: 'https://comic.io.vn/pricing',
    },
  },
  'tien-ich': {
    vi: {
      title: 'Tiện Ích Chrome Dịch Truyện Trực Tiếp & App Windows Tự Động — comic.io.vn',
      description:
        'Tải Tiện ích Chrome (Manifest V3) dịch trực tiếp trên mọi web truyện Raw và Phần mềm Windows (.EXE) tự động tải & dịch hàng loạt 100 Chapter chuẩn ngữ cảnh.',
      canonical: 'https://comic.io.vn/tien-ich',
    },
    en: {
      title: 'Chrome Extension & Windows Batch App for AI Manga Translation — comic.io.vn',
      description:
        'Translate raw Manga, Manhwa & Webtoons directly in your browser with our Manifest V3 Chrome Extension, or batch-translate 100+ chapters automatically on Windows 10/11.',
      canonical: 'https://comic.io.vn/extensions',
    },
  },
  'privacy-policy': {
    vi: {
      title: 'Chính Sách Quyền Riêng Tư & Bảo Mật Dữ Liệu — comic.io.vn',
      description:
        'Chính sách bảo mật dữ liệu, quyền riêng tư người dùng và tiêu chuẩn an toàn thông tin cho Website, Tiện ích Chrome và REST API tại comic.io.vn.',
      canonical: 'https://comic.io.vn/privacy-policy',
    },
    en: {
      title: 'Privacy Policy & Data Security — Manga Translation Studio (comic.io.vn)',
      description:
        'Official privacy policy and data handling commitments for comic.io.vn Web Studio, Chrome Web Store Extension, and Developer REST API.',
      canonical: 'https://comic.io.vn/privacy-policy',
    },
  },
}

export function capNhatSeoTheoTrang(trangTinh = '', lang = 'vi') {
  try {
    const key = trangTinh && SEO_META_BY_PAGE[trangTinh] ? trangTinh : 'home'
    const nhom = SEO_META_BY_PAGE[key] || SEO_META_BY_PAGE.home
    const seo = (lang !== 'vi' ? nhom.en : nhom.vi) || SEO_META_BY_LANG[lang] || SEO_META_BY_LANG.en
    if (!seo) return
    document.title = seo.title
    const metaDesc = document.querySelector('meta[name="description"]')
    if (metaDesc) metaDesc.setAttribute('content', seo.description)
    const canonical = document.getElementById('seo-canonical')
    if (canonical) canonical.setAttribute('href', seo.canonical)
    const ogTitle = document.getElementById('seo-og-title')
    if (ogTitle) ogTitle.setAttribute('content', seo.title)
    const ogDesc = document.getElementById('seo-og-desc')
    if (ogDesc) ogDesc.setAttribute('content', seo.description)
    const ogUrl = document.getElementById('seo-og-url')
    if (ogUrl) ogUrl.setAttribute('content', seo.canonical)
    const twTitle = document.getElementById('seo-tw-title')
    if (twTitle) twTitle.setAttribute('content', seo.title)
    const twDesc = document.getElementById('seo-tw-desc')
    if (twDesc) twDesc.setAttribute('content', seo.description)
  } catch {
    /* bỏ qua */
  }
}

export const SEO_META_BY_LANG = {
  vi: {
    title: 'comic.io.vn — Dịch Truyện Tranh AI Miễn Phí | Manga, Manhwa, Webtoon',
    description:
      'Nền tảng dịch truyện tranh tự động bằng AI (Manga, Manhwa, Manhua, Comic) sang 9 ngôn ngữ. Tự tái tạo nền sạch, dàn chữ chuẩn thẩm mỹ, hỗ trợ Tiện ích Chrome, App Windows & API.',
    canonical: 'https://comic.io.vn/',
  },
  en: {
    title: 'comic.io.vn — Free AI Manga, Manhwa & Webtoon Translator Online',
    description:
      'Translate raw Japanese Manga, Korean Manhwa, Chinese Manhua & Webtoons online in 3 seconds. AI bubble detection, smart background clean & studio typesetting in 9 languages.',
    canonical: 'https://comic.io.vn/en',
  },
  es: {
    title: 'comic.io.vn — Traductor de Manga, Manhwa y Webtoon con IA Gratis',
    description:
      'Traduce manga raw, manhwa coreano y cómics online en segundos con IA. Detección de bocadillos, limpieza inteligente de texto y tipografía automática en 9 idiomas.',
    canonical: 'https://comic.io.vn/es',
  },
  pt: {
    title: 'comic.io.vn — Tradutor de Mangá, Manhwa e Webtoon com IA Grátis',
    description:
      'Traduza mangá raw, manhwa e quadrinhos online em segundos com Inteligência Artificial. Limpeza inteligente de balões, OCR avançado e diagramação automática.',
    canonical: 'https://comic.io.vn/pt',
  },
  fr: {
    title: 'comic.io.vn — Traducteur de Manga, Manhwa et Webtoon par IA Gratuit',
    description:
      'Traduisez vos scans manga raw, manhwa et webtoons en ligne en quelques secondes grâce à l’IA. Nettoyage intelligent, OCR précis et lettrage automatique.',
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
    bubbleLeft: '¡Traducción Instantánea de Cómics — Limpieza IA y Fuentes por Género!',
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
    bubbleLeft: 'Tradução Instantânea de Quadrinhos — Limpeza IA e Fontes de Estúdio!',
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
    bubbleLeft: 'Traduction Instantanée de Scans — Nettoyage IA & Lettrage Pro !',
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

    const rawPath = (window.location.pathname || '').replace(/^\/+|\/+$/g, '').toLowerCase()
    const seg = rawPath.split('/')[0]
    const pLang = chuanHoaNgonNguUI(seg)
    if (pLang && seg.length <= 5) return pLang
    if (rawPath === 'api-docs' || rawPath === 'pricing' || rawPath === 'extensions') {
      return 'en'
    }
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
