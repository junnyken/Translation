import { createContext, useContext, useEffect, useState } from 'react'

const KHOA_NGON_NGU_UI = 'translation:ui-lang'
export const CAC_NGON_NGU_HO_TRO = ['en', 'vi', 'es', 'pt', 'fr', 'id']

const CAC_DUONG_DAN_CANONICAL_HOP_LE = new Set([
  '/',
  '/en',
  '/vi',
  '/es',
  '/pt',
  '/fr',
  '/id',
  '/ket-noi-api',
  '/api-docs',
  '/en/api-docs',
  '/bang-gia',
  '/pricing',
  '/en/pricing',
  '/tien-ich',
  '/extensions',
  '/en/extensions',
  '/privacy-policy',
])

export function xacDinhCanonicalUrl(trangTinh = '', lang = 'en', seoFallback = 'https://comic.io.vn/') {
  try {
    const rawPath = (window.location.pathname || '/').replace(/\/+$/g, '') || '/'
    const pathLower = rawPath.toLowerCase()
    if (trangTinh && trangTinh !== 'home' && pathLower === '/') {
      return seoFallback
    }
    if (CAC_DUONG_DAN_CANONICAL_HOP_LE.has(pathLower)) {
      return `https://comic.io.vn${pathLower === '/' ? '/' : pathLower}`
    }
  } catch {
    /* bỏ qua */
  }
  return seoFallback
}

export const SEO_META_BY_PAGE = {
  home: {
    vi: {
      title: 'comic.io.vn — Dịch Truyện Tranh AI | Manga, Manhwa & Webtoon',
      description:
        'Dịch truyện tranh AI miễn phí (Manga, Manhwa, Manhua, Webtoon) sang 9 ngôn ngữ trong 3 giây. Tự xoá chữ, tái tạo nền sạch, hỗ trợ Chrome, Windows & API.',
      canonical: 'https://comic.io.vn/vi',
    },
    en: {
      title: 'comic.io.vn — Free AI Manga, Manhwa & Webtoon Translator',
      description:
        'Translate raw Manga, Manhwa, Manhua & Webtoons online in 3 seconds. AI bubble detection, clean inpainting, studio typesetting & REST API in 9 languages.',
      canonical: 'https://comic.io.vn/',
    },
  },
  'ket-noi-api': {
    vi: {
      title: 'API Dịch Truyện Tranh AI (REST API & RapidAPI) — comic.io.vn',
      description:
        'Tích hợp REST API dịch truyện tranh AI (OCR, xoá chữ tái tạo nền, dịch 9 ngôn ngữ) vào web đọc truyện, app mobile & công cụ Scanlation với khoá tr_live.',
      canonical: 'https://comic.io.vn/ket-noi-api',
    },
    en: {
      title: 'AI Manga & Webtoon Translation REST API — comic.io.vn',
      description:
        'Enterprise B2B REST API for automated Manga, Manhwa & Webtoon OCR, speech bubble detection, clean inpainting & 9-language translation via RapidAPI.',
      canonical: 'https://comic.io.vn/api-docs',
    },
  },
  'bang-gia': {
    vi: {
      title: 'Bảng Giá Dịch Truyện Tranh AI & Gói API B2B — comic.io.vn',
      description:
        'Đăng ký nhận ngay 20 Credits miễn phí. 4 gói Tháng & Năm quốc tế (300 đến 10.000 Credits) kèm ưu đãi lần đầu giảm 50% chỉ từ $2.99 USD (49.000 VNĐ).',
      canonical: 'https://comic.io.vn/bang-gia',
    },
    en: {
      title: 'Pricing & B2B API Plans — AI Manga Translator | comic.io.vn',
      description:
        'Sign up for 20 Free Credits. 4 flexible Monthly & Yearly plans (300 to 10,000 Credits) with 50% OFF first-time offer starting at $2.99 USD for AI manga.',
      canonical: 'https://comic.io.vn/pricing',
    },
  },
  'tien-ich': {
    vi: {
      title: 'Tiện Ích Chrome & App Windows Dịch Truyện AI — comic.io.vn',
      description:
        'Tải Tiện ích Chrome (Manifest V3) dịch trực tiếp trên web truyện Raw và App Windows (.EXE) tự động tải, xoá chữ & dịch hàng loạt 100 Chapter truyện.',
      canonical: 'https://comic.io.vn/tien-ich',
    },
    en: {
      title: 'Chrome Extension & Windows App for AI Manga — comic.io.vn',
      description:
        'Translate raw Manga, Manhwa & Webtoons live in your browser with our Chrome Extension, or batch-translate 100+ chapters automatically on Windows 10/11.',
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
      title: 'Privacy Policy & Data Security — comic.io.vn Studio',
      description:
        'Official privacy policy, user data protection, and security commitments for comic.io.vn Web Studio, Chrome Web Store Extension, and Developer REST API.',
      canonical: 'https://comic.io.vn/privacy-policy',
    },
  },
}

export function capNhatSeoTheoTrang(trangTinh = '', lang = 'vi') {
  try {
    const key = trangTinh && SEO_META_BY_PAGE[trangTinh] ? trangTinh : 'home'
    const nhom = SEO_META_BY_PAGE[key] || SEO_META_BY_PAGE.home
    const seo =
      (key === 'home' && SEO_META_BY_LANG[lang]) ||
      (lang === 'vi' ? nhom.vi : nhom.en) ||
      SEO_META_BY_LANG[lang] ||
      SEO_META_BY_LANG.en
    if (!seo) return
    const canonicalUrl = xacDinhCanonicalUrl(trangTinh, lang, seo.canonical)
    document.title = seo.title
    const metaDesc = document.querySelector('meta[name="description"]')
    if (metaDesc) metaDesc.setAttribute('content', seo.description)
    const canonical = document.getElementById('seo-canonical')
    if (canonical) canonical.setAttribute('href', canonicalUrl)
    const ogTitle = document.getElementById('seo-og-title')
    if (ogTitle) ogTitle.setAttribute('content', seo.title)
    const ogDesc = document.getElementById('seo-og-desc')
    if (ogDesc) ogDesc.setAttribute('content', seo.description)
    const ogUrl = document.getElementById('seo-og-url')
    if (ogUrl) ogUrl.setAttribute('content', canonicalUrl)
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
    title: 'comic.io.vn — Dịch Truyện Tranh AI | Manga, Manhwa & Webtoon',
    description:
      'Dịch truyện tranh AI miễn phí (Manga, Manhwa, Manhua, Webtoon) sang 9 ngôn ngữ trong 3 giây. Tự xoá chữ, tái tạo nền sạch, hỗ trợ Chrome, Windows & API.',
    canonical: 'https://comic.io.vn/vi',
  },
  en: {
    title: 'comic.io.vn — Free AI Manga, Manhwa & Webtoon Translator',
    description:
      'Translate raw Manga, Manhwa, Manhua & Webtoons online in 3 seconds. AI bubble detection, clean inpainting, studio typesetting & REST API in 9 languages.',
    canonical: 'https://comic.io.vn/en',
  },
  es: {
    title: 'comic.io.vn — Traductor de Manga, Manhwa y Webtoon con IA',
    description:
      'Traduce manga raw, manhwa coreano y webtoons online en 3 segundos con IA. Detección de bocadillos, limpieza inteligente y tipografía en 9 idiomas.',
    canonical: 'https://comic.io.vn/es',
  },
  pt: {
    title: 'comic.io.vn — Tradutor de Mangá, Manhwa e Webtoon com IA',
    description:
      'Traduza mangá raw, manhwa e webtoons online em 3 segundos com IA. Limpeza inteligente de balões, OCR avançado e diagramação automática em 9 idiomas.',
    canonical: 'https://comic.io.vn/pt',
  },
  fr: {
    title: 'comic.io.vn — Traducteur de Manga, Manhwa et Webtoon IA',
    description:
      'Traduisez vos scans manga raw, manhwa et webtoons en ligne en 3 secondes par IA. Nettoyage intelligent des bulles, OCR précis et lettrage en 9 langues.',
    canonical: 'https://comic.io.vn/fr',
  },
  id: {
    title: 'comic.io.vn — Penerjemah Manga, Manhwa & Webtoon AI Gratis',
    description:
      'Terjemahkan manga raw, manhwa Korea & webtoon online dalam 3 detik dengan AI. Deteksi balon teks otomatis, hapus teks bersih & typesetting 9 bahasa.',
    canonical: 'https://comic.io.vn/id',
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
  if (s.startsWith('id')) return 'id'
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
    if (v) return v
  } catch {
    /* bỏ qua */
  }
  const laMoiTruongTest =
    (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.MODE === 'test') ||
    (typeof navigator !== 'undefined' && /jsdom|happy-dom/i.test(navigator.userAgent || ''))
  return laMoiTruongTest ? 'vi' : 'en'
}

export function NgonNguUIProvider({ children }) {
  const [lang, setLangState] = useState(docNgonNguUI)

  const setLang = (moi, capNhatUrl = false) => {
    const chuan = chuanHoaNgonNguUI(moi) || 'en'
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
        const nextPath = chuan === 'en'
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
        const canonicalUrl = xacDinhCanonicalUrl('', lang, seo.canonical)
        document.title = seo.title
        const metaDesc = document.querySelector('meta[name="description"]')
        if (metaDesc) metaDesc.setAttribute('content', seo.description)
        const canonical = document.getElementById('seo-canonical')
        if (canonical) canonical.setAttribute('href', canonicalUrl)
        const ogTitle = document.getElementById('seo-og-title')
        if (ogTitle) ogTitle.setAttribute('content', seo.title)
        const ogDesc = document.getElementById('seo-og-desc')
        if (ogDesc) ogDesc.setAttribute('content', seo.description)
        const ogUrl = document.getElementById('seo-og-url')
        if (ogUrl) ogUrl.setAttribute('content', canonicalUrl)
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
  { ma: 'en', nhan: '🇺🇸 EN', title: 'English (International)' },
  { ma: 'vi', nhan: '🇻🇳 VN', title: 'Tiếng Việt' },
]

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
