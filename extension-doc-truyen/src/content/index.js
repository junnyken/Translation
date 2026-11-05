/** Phủ chữ dịch lên trang truyện đang đọc (E19-4).
 *
 * Tiêm khi người dùng bấm biểu tượng, không tiêm sẵn vào mọi trang.
 *
 * Nạp hai module thuần bằng `import()` động thay vì chép lại logic vào đây: chúng có bộ test
 * riêng (`tests/chon-anh.test.js`, `tests/toa-do.test.js`), còn tệp này chỉ sống được trong
 * trình duyệt thật. Chép lại = có hai bản và một bản sẽ lệch.
 */
void (async () => {
  const CO = '__translation_doc_truyen__'
  window[CO] = window[CO] || { daDich: new Map(), dangXepHang: new Set(), luotChayId: 0 }
  if (window[CO].dangChay && window[CO].dangChayBulk) {
    chrome.storage?.local?.remove?.(['__e60_snip', '__e59_bulk', '__e102_auto_scroll'])?.catch?.(() => {})
    return
  }
  window[CO].dangChay = true
  const maLuotHienTai = (window[CO].luotChayId || 0) + 1
  window[CO].luotChayId = maLuotHienTai

  const { chonCacTrangKeTiep, chonMoiTrang, chonTrangKeTiep, chonTrangTruyen } = await import(chrome.runtime.getURL('src/lib/chon-anh.js'))
  const { coChu, moRongKhungBongBong, quyDoi, sanSangQuyDoi } = await import(chrome.runtime.getURL('src/lib/toa-do.js'))

  // E101 + E105 — Kho 4 Font truyện tranh theo thể loại (Hành động / Ngôn tình / Cổ trang / Hài hước)
  // đóng gói nội bộ trong tiện ích để không bao giờ bị chặn bởi CSP của trang truyện.
  const KHO_FONT_TRUYEN = {
    bangers: {
      ten: '⚔️ Hành động',
      fontFace: 'TranslationBangers',
      tep: 'src/fonts/Bangers-Regular.ttf',
      css: "'TranslationBangers', 'Bangers', 'Microsoft YaHei', 'Microsoft JhengHei', 'Leelawadee UI', 'Tahoma', system-ui, -apple-system, sans-serif",
      lineHeight: '1.18',
      letterSpacing: '0.035em',
      wordSpacing: '0.075em',
    },
    shantell: {
      ten: '🌸 Ngôn tình',
      fontFace: 'TranslationShantell',
      tep: 'src/fonts/ShantellSans-Regular.ttf',
      css: "'TranslationShantell', 'Shantell Sans', 'Microsoft YaHei', 'Microsoft JhengHei', 'Leelawadee UI', 'Tahoma', system-ui, -apple-system, sans-serif",
      lineHeight: '1.26',
      letterSpacing: '0.032em',
      wordSpacing: '0.085em',
    },
    mansalva: {
      ten: '🏮 Cổ trang',
      fontFace: 'TranslationMansalva',
      tep: 'src/fonts/Mansalva-Regular.ttf',
      css: "'TranslationMansalva', 'Mansalva', 'KaiTi', 'STKaiti', 'Microsoft JhengHei', 'Leelawadee UI', cursive, system-ui, sans-serif",
      lineHeight: '1.25',
      letterSpacing: '0.036em',
      wordSpacing: '0.09em',
    },
    sigmar: {
      ten: '💥 Hài hước',
      fontFace: 'TranslationSigmar',
      tep: 'src/fonts/SigmarOne-Regular.ttf',
      css: "'TranslationSigmar', 'Sigmar One', 'Microsoft YaHei', 'Microsoft JhengHei', 'Leelawadee UI', 'Tahoma', system-ui, sans-serif",
      lineHeight: '1.22',
      letterSpacing: '0.042em',
      wordSpacing: '0.09em',
    },
  }
  const NHAN_NGON_NGU_DICH_NOI = {
    vi: '🇻🇳 VI',
    en: '🇺🇸 EN',
    zh: '🇨🇳 ZH',
    'zh-TW': '🇹🇼 TW',
    id: '🇮🇩 ID',
    es: '🇪🇸 ES',
    pt: '🇧🇷 PT',
    th: '🇹🇭 TH',
    fr: '🇫🇷 FR',
  }
  const DS_MA_NGON_NGU_DICH = Object.keys(NHAN_NGON_NGU_DICH_NOI)
  const NHAN_ENGINE_AI_NOI = {
    local_ocr_gpu: '⚡ 1 Lượt',
    local_hybrid_pro: '🧠 2 Lượt Pro',
    llm_context: '✨ 3 Lượt Ultra',
  }
  const DS_MA_ENGINE_AI = Object.keys(NHAN_ENGINE_AI_NOI)
  const layThongSoFont = (maFont) => KHO_FONT_TRUYEN[maFont] || KHO_FONT_TRUYEN.bangers

  if (!window[CO].daNapFont && typeof FontFace !== 'undefined') {
    window[CO].daNapFont = true
    for (const cfg of Object.values(KHO_FONT_TRUYEN)) {
      try {
        const fontUrl = chrome.runtime.getURL(cfg.tep)
        const ff = new FontFace(cfg.fontFace, `url(${fontUrl})`, { style: 'normal', weight: '400' })
        ff.load().then((loaded) => {
          document.fonts.add(loaded)
          window.dispatchEvent(new CustomEvent('translation:ve-lai'))
        }).catch(() => {})
      } catch {
        // Bỏ qua nếu môi trường không hỗ trợ FontFace
      }
    }
  }

  if (!window[CO].daNgheStorageFont && chrome.storage?.onChanged) {
    window[CO].daNgheStorageFont = true
    chrome.storage.onChanged.addListener((thayDoi, vungLuu) => {
      if (vungLuu !== 'local') return
      if (thayDoi.fontChuTruyen?.newValue) {
        window[CO].fontChuHienTai = thayDoi.fontChuTruyen.newValue
        const nutFont = document.getElementById('translation-nut-doi-font')
        if (nutFont) nutFont.textContent = layThongSoFont(window[CO].fontChuHienTai).ten
        window.dispatchEvent(new CustomEvent('translation:ve-lai'))
      }
      if (thayDoi.ngonNguDich?.newValue) {
        window[CO].ngonNguDichHienTai = thayDoi.ngonNguDich.newValue
        const nutNnDich = document.getElementById('translation-nut-ngon-ngu-dich')
        if (nutNnDich) nutNnDich.textContent = NHAN_NGON_NGU_DICH_NOI[thayDoi.ngonNguDich.newValue] || '🇻🇳 VI'
      }
      if (thayDoi.engine?.newValue) {
        window[CO].engineHienTai = thayDoi.engine.newValue
        const nutModel = document.getElementById('translation-nut-doi-model')
        if (nutModel) nutModel.textContent = NHAN_ENGINE_AI_NOI[thayDoi.engine.newValue] || '⚡ 1 Lượt'
      }
      if (thayDoi.cheDoSfx?.newValue) {
        window[CO].cheDoSfx = thayDoi.cheDoSfx.newValue
        window.dispatchEvent(new CustomEvent('translation:ve-lai'))
      }
    })
  }

  // Chế độ xử lý chữ tượng thanh (SFX) vẽ thẳng lên tranh như STOMP, SPLRRRSH, ズシン, ドジュウウウウ...:
  // - `giu_nguyen` (mặc định): Không xoá, không dịch đè lên chữ SFX vẽ cách điệu để giữ nguyên 100% nét vẽ tranh gốc, không bị nhoè hay mất hình.
  // - `ghi_chu`   : Giữ nguyên nét vẽ gốc, chỉ gắn 1 nhãn dịch nhỏ bên cạnh.
  // - `dich_de`   : Xoá chữ gốc rồi đè chữ dịch lên như bóng thoại.
  const DS_CHE_DO_SFX = ['giu_nguyen', 'ghi_chu', 'dich_de']
  const NHAN_CHE_DO_SFX = {
    giu_nguyen: '💥 SFX: Giữ gốc',
    ghi_chu: '💥 SFX: Ghi chú',
    dich_de: '💥 SFX: Dịch đè',
  }
  if (!window[CO].cheDoSfx) {
    window[CO].cheDoSfx = 'giu_nguyen'
    chrome.storage?.local?.get?.({ cheDoSfx: 'giu_nguyen' })
      ?.then?.((d) => {
        if (d?.cheDoSfx && DS_CHE_DO_SFX.includes(d.cheDoSfx)) window[CO].cheDoSfx = d.cheDoSfx
      })
      ?.catch?.(() => {})
  }

  const TU_TUONG_THANH_SFX = /^(?:splr*sh|splash|spurt|splat|stomp|bam|boom|ba-?boom|bang|blam|clang|cling|clong|clank|clink|crack|crackle|crash|crunch|thud|thump|whoosh|fwoosh|woosh|swish|swoosh|slash|slice|shing|zoom|zap|zip|zzt+|bzz+|wham|whack|smack|slam|pow|kaboom|rumble|roar+|screech|shriek|grr+|rrr+|krr+|skrr+|doki|ba-?dump|dun|don|gogo+|zuzu+|kra+k|krak|shwa+|fwip|fump|tap|tak|thwack|drip|drop|tick|tock|ding|dong|ring|beep|snap|pop|poof|puff|rustle|creak|clatter|shatter|sizzle|hiss+|fizz+|whirr+|vrr+|brr+|wobble|ripple|flash|flap|flutter|sway|shake|tremble|gasp|huff|pant|sniff|sob|gulp|ba-?dum|thump-?thump)[!.?~]*$/i

  const TU_TUONG_THANH_VI = /^(?:xè+|xèo+|xẹt+|xoẹt+|vụt+|vù+|vút+|vèo+|keng(?:\s*keng)?|leng\s*keng|loảng\s*xoảng|dậm+|thình\s*thịch|bịch+|bốp+|cốp+|chát+|rắc+|krắc+|crắc+|uỳnh+|đùng(?:\s*đùng|\s*đoàng)?|ầm(?:\s*ầm|\s*ĩ)?|rầm+|bùm+|ào(?:\s*ào)?|rào(?:\s*rào)?|roạt+|soạt+|sột\s*soạt|phập+|phụt+|phịch+|phựt+|bựt+|phạch+|bạch+|két+|kít+|rít+|gừ+|rừ+|grừ+|cạch+|cộp(?:\s*cộp)?|lộp\s*cộp|lộp\s*bộp|tách+|tí\s*tách|tõm+|ủm+|ùng\s*ục|khè+|phù+|u+|ù+|rè+|zè+|xì+|xì\s*xèo)[!?.…~]*$/i

  /**
   * Nhận diện vùng chữ là TIẾNG ĐỘNG (SFX) vẽ cách điệu thẳng lên tranh (như SPLRRRSH, ドジュウウウウ, STOMP, XÈÈÈÈ!).
   * Mặc định ở chế độ `giu_nguyen`, các vùng SFX này sẽ được giữ nguyên 100% nét vẽ gốc, tuyệt đối không xoá nền
   * để tránh làm mất hình nhân vật hoặc gây vệt nhoè trên tranh.
   */
  function laVungSfx(v) {
    if (!v || v._sfxDichDe || v._laBongKhepKin) return false
    const dich = String(v.ban_dich || '').trim()
    const goc = String(v.chu_goc || '').trim()

    // 1. Kiểm tra trực tiếp từ tượng thanh rõ ràng trong bản dịch Tiếng Việt (vd: "XÈÈÈÈ!", "DẬM. THÌNH THỊCH.", "KENG KENG.", "VỤT.")
    if (dich) {
      const cauDich = dich.split(/[.!?…~]+/).map((s) => s.trim()).filter(Boolean)
      if (cauDich.length >= 1 && cauDich.length <= 3 && cauDich.every((c) => TU_TUONG_THANH_VI.test(c))) {
        return true
      }
      const tuDich = dich.replace(/[.!?…~]+/g, '').trim().split(/\s+/).filter(Boolean)
      if (tuDich.length >= 1 && tuDich.length <= 2 && /(.)\1{2,}/iu.test(dich)) {
        return true
      }
    }

    // 2. Kiểm tra trực tiếp từ tượng thanh trong chữ gốc (vd: "SPLRRRSH", "STOMP", "KRAAAK", "ドジュウウウウ")
    if (goc) {
      const tuGoc = goc.replace(/[.!！?？…~〜ー―\-・]+/g, ' ').trim().split(/\s+/).filter(Boolean)
      if (tuGoc.length >= 1 && tuGoc.length <= 3 && tuGoc.every((t) => TU_TUONG_THANH_SFX.test(t))) {
        return true
      }
      if (tuGoc.length >= 1 && tuGoc.length <= 2 && /([A-Za-z])\1{2,}/.test(goc)) {
        return true
      }
    }

    // 3. Kiểm tra kết hợp hình học (không phải bong bóng thoại khép kín) + đặc trưng chữ SFX ngắn
    if (v._laBongKhepKin) return false
    if (goc) {
      const gocGon = goc.replace(/[\s!！?？.…~〜ー―\-・♡♥]+/g, '')
      if (/^[\u3040-\u30ff\uff66-\uff9f]+$/.test(gocGon) && gocGon.length <= 6) return true
      if (/^[\uac00-\ud7af]+$/.test(gocGon) && gocGon.length <= 4) return true
      const tu = goc.split(/\s+/).filter(Boolean)
      if (tu.length === 1 && /^[A-Z]{2,10}[!.?]*$/.test(goc) && /([A-Z])\1{2,}/.test(goc)) return true
    }
    return false
  }

  let bang = window[CO].bang
  if (!bang) {
    bang = document.createElement('div')
    bang.style.cssText = [
      'position:fixed', 'z-index:2147483647', 'right:16px', 'bottom:16px',
      'max-width:330px', 'padding:11px 14px', 'border-radius:12px',
      'border:1px solid rgba(129,140,248,.35)',
      'background:rgba(15,23,42,.94)', 'color:#f8fafc', 'font:13px/1.45 system-ui,-apple-system,sans-serif',
      'box-shadow:0 8px 24px rgba(15,23,42,.45)', 'backdrop-filter:blur(8px)', 'white-space:pre-wrap',
    ].join(';')
    window[CO].bang = bang
  }
  if (!bang.isConnected) document.body.appendChild(bang)
  bang.style.display = ''

  const V = chrome.runtime.getManifest().version
  // Gắn phiên bản vào MỌI thông báo: người dùng tải gói .zip về máy nên bản đang chạy có thể cũ
  // hơn bản vừa sửa, và hai lượt thử vừa rồi không có cách nào phân biệt "bản sửa không ăn thua"
  // với "bản sửa chưa tới máy".
  const noi = (t) => {
    if (window[CO].henXoaBang) {
      clearTimeout(window[CO].henXoaBang)
      window[CO].henXoaBang = null
    }
    if (!bang.isConnected) document.body.appendChild(bang)
    bang.style.display = ''
    bang.textContent = `[v${V}] ${t}`
  }
  const xong = (t, giay = 6) => {
    noi(t)
    window[CO].henXoaBang = setTimeout(() => bang.remove(), giay * 1000)
  }

  const layCauHinhHienTai = async () => {
    try {
      const d = await chrome.storage.local.get({
        cheDoGpuKhach: 'chi_chu',
        ngonNgu: 'ja',
        ngonNguDich: 'vi',
        engine: 'llm_context',
        fontChuTruyen: 'bangers',
      })
      const fontChu = d?.fontChuTruyen || 'bangers'
      const ngonNguDich = d?.ngonNguDich || 'vi'
      window[CO].fontChuHienTai = fontChu
      window[CO].ngonNguDichHienTai = ngonNguDich
      return {
        cheDo: d?.cheDoGpuKhach || 'chi_chu',
        ngonNgu: d?.ngonNgu || 'ja',
        ngonNguDich,
        engine: d?.engine || 'llm_context',
        fontChu,
      }
    } catch {
      return {
        cheDo: 'chi_chu',
        ngonNgu: 'ja',
        ngonNguDich: window[CO].ngonNguDichHienTai || 'vi',
        engine: 'llm_context',
        fontChu: window[CO].fontChuHienTai || 'bangers',
      }
    }
  }
  const layCheDoHienTai = async () => (await layCauHinhHienTai()).cheDo
  const khoaCache = (src, cheDo, ngonNgu = 'ja', engine = 'llm_context', ngonNguDich = 'vi') =>
    `${cheDo || 'chi_chu'}::${ngonNgu || 'ja'}::${ngonNguDich || 'vi'}::${engine || 'llm_context'}::${src}`

  //: Lớp phủ nay có NHIỀU cái cùng lúc (E59 — dịch cả chapter): mỗi trang đã dịch giữ lớp của
  //: riêng nó, để cuộn qua là thấy chữ Việt sẵn thay vì phải bấm lại từng trang.
  //:
  //: Trước E59 chỉ có MỘT lớp, nhận theo `id`, và dòng đầu `vePhu` xoá lớp cũ. Giữ `id` duy nhất
  //: thì lớp thứ hai đè mất lớp thứ nhất — nên nhận theo `class` + `data-src`, và chỉ xoá lớp của
  //: CHÍNH ảnh đang vẽ lại.
  const LOP_CLASS = 'translation-lop-phu'
  const timLop = (src) => document.querySelector(
    `.${LOP_CLASS}[data-src="${CSS.escape(src)}"]`,
  )

  // E99 + E101 — Đo độ sáng nền & dò lòng bong bóng thực tế trên Canvas (`doKhungBongBongCanvas`).
  //
  // Vì sao cần dò trên điểm ảnh thật (tương tự `grow.py` + `long_bong_bong.py` của máy chủ):
  // 1. Trong bong bóng tròn/gai góc lớn, khung chữ Nhật gốc chỉ chiếm ~1/3 ở tâm. Dò tia (ray-march)
  //    ra 4 phía trên nền trắng của bong bóng giúp mở rộng hộp chữ gấp ~2 lần để cỡ chữ to đẹp,
  //    đồng thời nuốt trọn các dấu câu (`!`, `?`) bị lệch nhẹ ra rìa khung chữ.
  // 2. Trong hộp thoại hình chữ nhật hẹp nằm đè lên tranh vẽ (như khung chữ nhật cận cảnh mặt nhân vật),
  //    dò tia sẽ DỪNG NGAY LẬP TỨC khi chạm đường viền mực của hộp chữ nhật, tuyệt đối không nở mù
  //    quáng tràn ra che mất mắt/tóc nhân vật.
  function layCtxMau(el) {
    try {
      const srcHienTai = el.currentSrc || el.src || el.dataset?.translationCanvasId || ''
      if (el.__translationCtxMau && (!srcHienTai || el.__translationCtxSrc === srcHienTai)) {
        return el.__translationCtxMau
      }
      const w = el.naturalWidth || el.width || 0
      const h = el.naturalHeight || el.height || 0
      if (w < 1 || h < 1) return el?.__translationCtxMau || null
      const c = document.createElement('canvas')
      c.width = w
      c.height = h
      const ctx = c.getContext('2d', { willReadFrequently: true })
      ctx.drawImage(el, 0, 0, w, h)
      ctx.getImageData(0, 0, 1, 1)
      el.__translationCtxMau = ctx
      el.__translationCtxSrc = srcHienTai
      return el.__translationCtxMau
    } catch {
      return el?.__translationCtxMau || null
    }
  }

  // Nạp ảnh từ Data URL (do service worker tải vượt CORS) vào Canvas của máy khách để
  // 100% trang web truyện (kể cả CDN khác tên miền không có CORS) đều dùng được CPU/Canvas
  // của máy khách để xoá chữ gốc và đo viền bong bóng thật.
  async function napCanvasTuDataUrl(el, dataUrl) {
    if (!el || !dataUrl) return null
    const srcHienTai = el.currentSrc || el.src || el.dataset?.translationCanvasId || ''
    if (el.__translationCtxMau && el.__translationCtxSrc === srcHienTai) {
      return el.__translationCtxMau
    }
    try {
      const img = new Image()
      await new Promise((resolve, reject) => {
        img.onload = resolve
        img.onerror = reject
        img.src = dataUrl
      })
      const c = document.createElement('canvas')
      c.width = el.naturalWidth || el.width || img.naturalWidth
      c.height = el.naturalHeight || el.height || img.naturalHeight
      const ctx = c.getContext('2d', { willReadFrequently: true })
      ctx.drawImage(img, 0, 0, c.width, c.height)
      ctx.getImageData(0, 0, 1, 1)
      el.__translationCtxMau = ctx
      el.__translationCtxSrc = srcHienTai
      return ctx
    } catch {
      return null
    }
  }

  function timAnhTheoSrc(srcCanTim) {
    if (!srcCanTim) return null
    for (const img of document.images) {
      const s = img.currentSrc || img.src || img.dataset?.translationLazySrc
      if (s === srcCanTim && img.isConnected) return img
    }
    for (const cv of document.getElementsByTagName('canvas')) {
      if (cv.dataset?.translationCanvasId === srcCanTim && cv.isConnected) return cv
    }
    return null
  }

  /**
   * Phục hồi phần tử `<img>` hoặc `<canvas>` khi các trình đọc Virtual DOM / `blob:` (như MangaPlus)
   * huỷ và dựng lại nút DOM trong lúc chờ máy chủ dịch hoặc khi cuộn trang.
   */
  function timAnhThayThe(elCu, srcCanTim, thongSoGoc = {}, choPhepKhungNhin = false) {
    const wGoc = thongSoGoc.naturalWidth || elCu?.naturalWidth || elCu?.width || 0
    const hGoc = thongSoGoc.naturalHeight || elCu?.naturalHeight || elCu?.height || 0
    const docTopGoc = thongSoGoc.docTop

    const khopKichThuoc = (w, h) => {
      if (!wGoc || !hGoc || !w || !h) return true
      if (w === wGoc && h === hGoc) return true
      const tlGoc = wGoc / Math.max(1, hGoc)
      const tlMoi = w / Math.max(1, h)
      return Math.abs(tlMoi - tlGoc) <= 0.08
    }

    const khopViTriDoc = (topHienThi, saiSoToiDa = 220) => {
      if (typeof docTopGoc !== 'number' || !Number.isFinite(docTopGoc)) return true
      return Math.abs((window.scrollY + topHienThi) - docTopGoc) <= saiSoToiDa
    }

    const chonHopLe = (node) => {
      if (!node || !node.isConnected) return null
      const r = node.getBoundingClientRect()
      if (r.width < 40 || r.height < 40) return null
      if (node.tagName === 'CANVAS') {
        try {
          if (!node.naturalWidth) node.naturalWidth = node.width || Math.round(r.width)
          if (!node.naturalHeight) node.naturalHeight = node.height || Math.round(r.height)
        } catch {}
      }
      if (elCu?.__translationCtxMau && !node.__translationCtxMau) {
        node.__translationCtxMau = elCu.__translationCtxMau
        node.__translationCtxSrc = node.currentSrc || node.src || node.dataset?.translationCanvasId || ''
      }
      return node
    }

    const giuNguyen = chonHopLe(elCu)
    if (giuNguyen) return giuNguyen

    const ungVienTheoSrc = timAnhTheoSrc(srcCanTim)
    if (ungVienTheoSrc) {
      const rSrc = ungVienTheoSrc.getBoundingClientRect()
      if (!String(srcCanTim).startsWith('canvas://') || khopViTriDoc(rSrc.top, 260)) {
        const theoSrc = chonHopLe(ungVienTheoSrc)
        if (theoSrc) return theoSrc
      }
    }

    // Bước 1: Tìm trong các thẻ cha bao quanh đúng 1 trang (ví dụ khung trang `.zao-page` trên MangaPlus).
    // Kiểm tra chặt `khopViTriDoc` để không bao giờ lấy nhầm trang khác trong cùng danh sách chapter!
    const dsCha = [elCu?.__translationCha1, elCu?.__translationCha2, elCu?.__translationCha3].filter(
      (c) => c && c.isConnected && c !== document.body && c !== document.documentElement,
    )
    for (const cha of dsCha) {
      const ungVienCon = [...cha.querySelectorAll('img, canvas')].filter((node) => {
        if (!node.isConnected || node.closest(`.${LOP_CLASS}`)) return false
        const r = node.getBoundingClientRect()
        if (r.width < 120 || r.height < 120) return false
        if (!khopViTriDoc(r.top, 220)) return false
        const nw = node.naturalWidth || node.width || Math.round(r.width)
        const nh = node.naturalHeight || node.height || Math.round(r.height)
        return khopKichThuoc(nw, nh)
      })
      if (ungVienCon.length === 1) {
        return chonHopLe(ungVienCon[0])
      }
    }

    // Bước 2: Tìm ảnh đang nằm ở cùng toạ độ dọc trên tài liệu (`docTop = window.scrollY + r.top`)
    const moTaHienTai = layMoTa()
    if (typeof docTopGoc === 'number' && Number.isFinite(docTopGoc)) {
      const cungViTri = moTaHienTai
        .filter((m) => (
          !m.mo
          && m.el?.isConnected
          && (m.clientWidth || 0) >= 160
          && (m.clientHeight || 0) >= 200
          && khopKichThuoc(m.naturalWidth, m.naturalHeight)
          && Math.abs((window.scrollY + m.top) - docTopGoc) <= 220
        ))
        .sort((a, b) => Math.abs((window.scrollY + a.top) - docTopGoc) - Math.abs((window.scrollY + b.top) - docTopGoc))
      if (cungViTri.length > 0) {
        return chonHopLe(cungViTri[0].el)
      }
    }

    // Bước 3: Chỉ dùng cho dịch 1 trang hiện tại (`choPhepKhungNhin = true`) và bắt buộc kiểm tra không lệch trang
    if (choPhepKhungNhin) {
      let chonMoi = chonTrangTruyen(moTaHienTai, { caoKhungNhin: window.innerHeight })
      if (!chonMoi.anh) {
        const hienThi = moTaHienTai.filter((m) => (
          !m.mo
          && m.bottom > 20
          && m.top < window.innerHeight - 20
          && (m.clientWidth || 0) >= 200
          && (m.clientHeight || 0) >= 240
        ))
        if (hienThi.length > 0) {
          const diem = (a) => Math.max(0, Math.min(a.bottom, window.innerHeight) - Math.max(a.top, 0)) * (a.clientWidth || 1)
          chonMoi = { anh: hienThi.reduce((a, b) => (diem(b) > diem(a) ? b : a)) }
        }
      }
      if (
        chonMoi?.anh?.el
        && khopKichThuoc(chonMoi.anh.naturalWidth, chonMoi.anh.naturalHeight)
        && khopViTriDoc(chonMoi.anh.top, Math.max(320, Math.round(window.innerHeight * 0.55)))
      ) {
        return chonHopLe(chonMoi.anh.el)
      }
    }

    return null
  }

  function laBongBongToi(el, v) {
    try {
      const ctx = layCtxMau(el)
      if (!ctx) return false
      const W = el.naturalWidth || el.width || 0
      const H = el.naturalHeight || el.height || 0
      if (W < 4 || H < 4) return false
      const pad = Math.max(4, Math.round(Math.min(v.w || 10, v.h || 10) * 0.15))
      const x = Math.max(0, Math.min(W - 1, Math.round(v.x - pad)))
      const y = Math.max(0, Math.min(H - 1, Math.round(v.y - pad)))
      const w = Math.max(1, Math.min(W - x, Math.round(v.w + pad * 2)))
      const h = Math.max(1, Math.min(H - y, Math.round(v.h + pad * 2)))
      const data = ctx.getImageData(x, y, w, h).data
      const buoc = Math.max(4, Math.floor((data.length / 4) / 96) * 4)
      const doSang = []
      for (let i = 0; i < data.length; i += buoc) {
        if (data[i + 3] < 128) continue
        const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2]
        doSang.push(lum)
      }
      if (!doSang.length) return false
      doSang.sort((a, b) => a - b)
      const p50 = doSang[Math.floor(doSang.length * 0.5)]
      return p50 < 95
    } catch {
      return false
    }
  }

  /**
   * E106 + E112 — Dò lòng bong bóng 2D chống rò rỉ gai nhọn & Xoá chính xác từng nét chữ gốc (`vungXoaChu`) trên Canvas.
   *
   * Khắc phục triệt để lỗi tạo mảng trắng đè mất chi tiết tranh vẽ ở các bong bóng hình gai nhọn,
   * đám mây, đa giác, khung hở viền hoặc chữ đè trên nền kẻ sọc (screentone):
   * 1. Không bao giờ tô trắng cả vùng loang `longTrang` tràn qua khe gai nhọn ("GRA-HEE-HAW !!!", "ARE YOU SURPRISED?!").
   * 2. Chỉ xoá đúng các nét chữ gốc cô lập trong hộp chữ (`laChuGoc`) cộng thêm viền khử răng cưa 3px (`vungXoaChu`),
   *    giữ trong suốt (`alpha = 0`) 100% cho gai nhọn, đường viền khung tranh, vương miện/tóc nhân vật và nền screentone bên ngoài nét chữ.
   */
  function doKhungBongBongCanvas(el, v, tatCaVung) {
    if (v._khungCanvas) return v._khungCanvas
    const ctx = layCtxMau(el)
    if (!ctx) return null

    try {
      const W = el.naturalWidth || el.width || 0
      const H = el.naturalHeight || el.height || 0
      if (W < 8 || H < 8) return null
      if (v.nen_toi === undefined) {
        v.nen_toi = laBongBongToi(el, v)
      }
      const nenToi = Boolean(v.nen_toi)
      const xGoc = Math.max(0, Math.round(v.x))
      const yGoc = Math.max(0, Math.round(v.y))
      const wGoc = Math.max(4, Math.min(W - xGoc, Math.round(v.w)))
      const hGoc = Math.max(4, Math.min(H - yGoc, Math.round(v.h)))
      const canhDai = Math.max(wGoc, hGoc)

      // Mở ROI đủ rộng quanh bbox chữ gốc để bao trọn cả các chữ cái/dấu câu/dòng cuối bị Gemini khoanh hụt ("ness...", "Tenpai...", "k-", "be")
      const padCheX = Math.max(24, Math.min(52, Math.round(wGoc * 0.44)))
      const padCheY = Math.max(38, Math.min(68, Math.round(hGoc * 0.52)))
      const moX = Math.max(padCheX + 20, Math.min(Math.max(Math.round(canhDai * 0.95), Math.round(W * 0.12)), Math.round(W * 0.22)))
      const moY = Math.max(padCheY + 24, Math.min(Math.max(Math.round(canhDai * 1.15), Math.round(H * 0.14)), Math.round(H * 0.24)))
      let rx0 = Math.max(2, xGoc - moX)
      let ry0 = Math.max(2, yGoc - moY)
      let rx1 = Math.min(W - 2, xGoc + wGoc + moX)
      let ry1 = Math.min(H - 2, yGoc + hGoc + moY)

      // Không cho ROI lấn vào lõi chữ gốc của bong bóng khác
      const kheHoGoc = 4
      for (const u of tatCaVung) {
        if (u === v) continue
        const ux0 = u.x + u.w * 0.1
        const uy0 = u.y + u.h * 0.1
        const ux1 = u.x + u.w * 0.9
        const uy1 = u.y + u.h * 0.9
        const giaoBanDau = xGoc < ux1 && xGoc + wGoc > ux0 && yGoc < uy1 && yGoc + hGoc > uy0
        if (giaoBanDau) continue
        if (yGoc < uy1 && yGoc + hGoc > uy0) {
          if (ux1 <= xGoc) rx0 = Math.max(rx0, Math.round(ux1 + kheHoGoc))
          if (ux0 >= xGoc + wGoc) rx1 = Math.min(rx1, Math.round(ux0 - kheHoGoc))
        }
        if (xGoc < ux1 && xGoc + wGoc > ux0) {
          if (uy1 <= yGoc) ry0 = Math.max(ry0, Math.round(uy1 + kheHoGoc))
          if (uy0 >= yGoc + hGoc) ry1 = Math.min(ry1, Math.round(uy0 - kheHoGoc))
        }
      }

      const rw = Math.max(4, rx1 - rx0)
      const rh = Math.max(4, ry1 - ry0)
      const N = rw * rh
      const data = ctx.getImageData(rx0, ry0, rw, rh).data

      const cx0 = Math.max(0, xGoc - rx0)
      const cy0 = Math.max(0, yGoc - ry0)
      const cx1 = Math.min(rw, xGoc + wGoc - rx0)
      const cy1 = Math.min(rh, yGoc + hGoc - ry0)

      // Lấy mẫu màu nền thật `(bgR, bgG, bgB)` bằng cụm màu chủ đạo (16-mức RGB) từ vành đai + lòng hộp chữ.
      // Khắc phục triệt để bong bóng màu (hộp hệ thống xanh dương/tím chữ trắng, giấy da vàng, hồng, xám...)
      // vốn có độ sáng trung bình (82 < lum < 180) hoặc chữ trắng trên nền màu đậm:
      const bangDemBin = new Int32Array(4096)
      const tongRBin = new Int32Array(4096)
      const tongGBin = new Int32Array(4096)
      const tongBBin = new Int32Array(4096)
      const vx0 = Math.max(0, cx0 - 8)
      const vy0 = Math.max(0, cy0 - 8)
      const vx1 = Math.min(rw, cx1 + 8)
      const vy1 = Math.min(rh, cy1 + 8)

      const themMauBin = (r, g, b, trongSo) => {
        const bin = ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)
        bangDemBin[bin] += trongSo
        tongRBin[bin] += r * trongSo
        tongGBin[bin] += g * trongSo
        tongBBin[bin] += b * trongSo
      }

      // Quét vành đai sát quanh chữ (trọng số 2 vì ít dính nét chữ hơn) + lòng hộp chữ (trọng số 1)
      for (let py = vy0; py < vy1; py += 2) {
        for (let px = vx0; px < vx1; px += 2) {
          const i = (py * rw + px) * 4
          if (data[i + 3] < 128) continue
          const trongHop = px >= cx0 && px < cx1 && py >= cy0 && py < cy1
          themMauBin(data[i], data[i + 1], data[i + 2], trongHop ? 1 : 2)
        }
      }

      // Tìm cụm màu nền chiếm đa số trong bóng thoại (gộp cả 26 bin lân cận 3x3x3 để chống nhiễu JPEG)
      let binTotNhat = -1
      let diemBinTotNhat = -1
      for (let bIdx = 0; bIdx < 4096; bIdx += 1) {
        if (bangDemBin[bIdx] === 0) continue
        const br = (bIdx >> 8) & 15
        const bg = (bIdx >> 4) & 15
        const bb = bIdx & 15
        let tongCum = 0
        for (let dr = -1; dr <= 1; dr += 1) {
          const nr = br + dr
          if (nr < 0 || nr > 15) continue
          for (let dg = -1; dg <= 1; dg += 1) {
            const ng = bg + dg
            if (ng < 0 || ng > 15) continue
            for (let db = -1; db <= 1; db += 1) {
              const nb = bb + db
              if (nb < 0 || nb > 15) continue
              tongCum += bangDemBin[(nr << 8) | (ng << 4) | nb]
            }
          }
        }
        if (tongCum > diemBinTotNhat) {
          diemBinTotNhat = tongCum
          binTotNhat = bIdx
        }
      }

      let bgR = nenToi ? 12 : 255
      let bgG = nenToi ? 12 : 255
      let bgB = nenToi ? 12 : 255
      if (binTotNhat >= 0) {
        const br = (binTotNhat >> 8) & 15
        const bg = (binTotNhat >> 4) & 15
        const bb = binTotNhat & 15
        let sumW = 0, sumR = 0, sumG = 0, sumB = 0
        for (let dr = -1; dr <= 1; dr += 1) {
          const nr = br + dr
          if (nr < 0 || nr > 15) continue
          for (let dg = -1; dg <= 1; dg += 1) {
            const ng = bg + dg
            if (ng < 0 || ng > 15) continue
            for (let db = -1; db <= 1; db += 1) {
              const nb = bb + db
              if (nb < 0 || nb > 15) continue
              const nbIdx = (nr << 8) | (ng << 4) | nb
              sumW += bangDemBin[nbIdx]
              sumR += tongRBin[nbIdx]
              sumG += tongGBin[nbIdx]
              sumB += tongBBin[nbIdx]
            }
          }
        }
        if (sumW > 0) {
          bgR = Math.round(sumR / sumW)
          bgG = Math.round(sumG / sumW)
          bgB = Math.round(sumB / sumW)
        }
      }

      const bgLum = 0.299 * bgR + 0.587 * bgG + 0.114 * bgB
      const bgSat = Math.max(bgR, bgG, bgB) - Math.min(bgR, bgG, bgB)
      // Cập nhật lại `v.nen_toi` theo độ sáng thực sự của màu nền chủ đạo (giúp hộp hệ thống xanh đậm/tím/xám đậm luôn hiện chữ trắng sắc nét)
      v.nen_toi = bgLum < 128
      const nenToiThuc = Boolean(v.nen_toi)
      v._mauNenCss = `rgb(${bgR},${bgG},${bgB})`

      const dsLumNen = []
      let demKhopMauTrongHop = 0
      let tongMauQuet = 0
      for (let py = vy0; py < vy1; py += 2) {
        for (let px = vx0; px < vx1; px += 2) {
          const i = (py * rw + px) * 4
          if (data[i + 3] < 128) continue
          tongMauQuet += 1
          const r = data[i], g = data[i + 1], b = data[i + 2]
          const lum = 0.299 * r + 0.587 * g + 0.114 * b
          const saiSoBg = Math.abs(r - bgR) + Math.abs(g - bgG) + Math.abs(b - bgB)
          if (saiSoBg <= 58) {
            demKhopMauTrongHop += 1
          }
          // Chỉ đưa các điểm ứng viên nền (không phải nét mực chữ đậm) vào đo độ đồng nhất của nền bong bóng
          if (saiSoBg <= 75 || (!nenToiThuc && lum >= Math.max(175, bgLum - 45)) || (nenToiThuc && lum <= Math.min(85, bgLum + 45))) {
            dsLumNen.push(lum)
          }
        }
      }
      dsLumNen.sort((a, b) => a - b)
      const p20Idx = Math.floor(dsLumNen.length * 0.2)
      const p80Idx = Math.min(dsLumNen.length - 1, Math.floor(dsLumNen.length * 0.8))
      const doLechMauNen = dsLumNen.length >= 6 ? (dsLumNen[p80Idx] - dsLumNen[p20Idx]) : 99
      const laBongMauDongNhat = (demKhopMauTrongHop >= Math.max(6, Math.floor(tongMauQuet * 0.32))) || (doLechMauNen <= 42)
      const laNenTrangChuan = !nenToiThuc && bgLum >= 210 && bgSat <= 56
      const laNenDenChuan = nenToiThuc && bgLum <= 55 && bgSat <= 40

      // Ước lượng hồ sơ màu nền theo từng dòng `py` (`bgRowR`, `bgRowG`, `bgRowB`, `bgRowLum`)
      // để xử lý mượt các bong bóng màu có chuyển sắc nhẹ (vàng kem / trắng ngà trong truyện màu JoJo, Webtoon, Manhua)
      // mà không bao giờ bị lệch tông màu giữa đỉnh và đáy bong bóng:
      const rawRowR = new Int16Array(rh)
      const rawRowG = new Int16Array(rh)
      const rawRowB = new Int16Array(rh)
      const sxRow0 = Math.max(0, cx0 - Math.min(28, padCheX))
      const sxRow1 = Math.min(rw, cx1 + Math.min(28, padCheX))
      for (let py = 0; py < rh; py += 1) {
        const mauDong = []
        const base = py * rw
        for (let px = sxRow0; px < sxRow1; px += 2) {
          const i = (base + px) * 4
          if (data[i + 3] < 128) continue
          const r = data[i], g = data[i + 1], b = data[i + 2]
          const lum = 0.299 * r + 0.587 * g + 0.114 * b
          const saiSo = Math.abs(r - bgR) + Math.abs(g - bgG) + Math.abs(b - bgB)
          if (saiSo <= 82 || (!nenToiThuc && lum >= Math.max(185, bgLum - 42)) || (nenToiThuc && lum <= Math.min(75, bgLum + 42))) {
            mauDong.push({ r, g, b, lum, saiSo })
          }
        }
        if (mauDong.length >= 3) {
          mauDong.sort((a, b) => a.saiSo - b.saiSo)
          const soLay = Math.max(2, Math.ceil(mauDong.length * 0.55))
          let sr = 0, sg = 0, sb = 0
          for (let k = 0; k < soLay; k += 1) {
            sr += mauDong[k].r
            sg += mauDong[k].g
            sb += mauDong[k].b
          }
          rawRowR[py] = Math.round(sr / soLay)
          rawRowG[py] = Math.round(sg / soLay)
          rawRowB[py] = Math.round(sb / soLay)
        } else {
          rawRowR[py] = bgR
          rawRowG[py] = bgG
          rawRowB[py] = bgB
        }
      }
      const bgRowR = new Uint8Array(rh)
      const bgRowG = new Uint8Array(rh)
      const bgRowB = new Uint8Array(rh)
      const bgRowLum = new Float32Array(rh)
      for (let py = 0; py < rh; py += 1) {
        const y0s = Math.max(0, py - 6)
        const y1s = Math.min(rh - 1, py + 6)
        let sr = 0, sg = 0, sb = 0, cnt = 0
        for (let yy = y0s; yy <= y1s; yy += 1) {
          sr += rawRowR[yy]
          sg += rawRowG[yy]
          sb += rawRowB[yy]
          cnt += 1
        }
        const rr = Math.round(sr / cnt)
        const gg = Math.round(sg / cnt)
        const bb = Math.round(sb / cnt)
        bgRowR[py] = rr
        bgRowG[py] = gg
        bgRowB[py] = bb
        bgRowLum[py] = 0.299 * rr + 0.587 * gg + 0.114 * bb
      }

      const laNenMask = new Uint8Array(N)
      let demNenTrongHop = 0
      const dienTichHopGoc = Math.max(1, (cx1 - cx0) * (cy1 - cy0))
      const nguongSaiSoMau = laBongMauDongNhat ? 42 : 48
      for (let py = 0; py < rh; py += 1) {
        const base = py * rw
        const rDong = bgRowR[py]
        const gDong = bgRowG[py]
        const bDong = bgRowB[py]
        const lumDong = bgRowLum[py]
        const trongDaiChuY = py >= Math.max(0, cy0 - padCheY) && py < Math.min(rh, cy1 + padCheY)
        for (let px = 0; px < rw; px += 1) {
          const idx = base + px
          const i = idx * 4
          if (data[i + 3] < 128) continue
          const r = data[i]
          const g = data[i + 1]
          const b = data[i + 2]
          const lum = 0.299 * r + 0.587 * g + 0.114 * b
          const sat = Math.max(r, g, b) - Math.min(r, g, b)
          const saiSoRow = Math.abs(r - rDong) + Math.abs(g - gDong) + Math.abs(b - bDong)
          const saiSoGlobal = Math.abs(r - bgR) + Math.abs(g - bgG) + Math.abs(b - bgB)
          const trongHopMoRong = trongDaiChuY && px >= Math.max(0, cx0 - padCheX) && px < Math.min(rw, cx1 + padCheX)

          // Trong vùng chữ gốc mở rộng, mọi nét chữ màu/xám nhạt lệch rõ so với màu nền tại dòng `py`
          // đều phải tính là chữ gốc (`laNenMask = 0`) để xoá sạch 100%, đồng thời vẫn cho phép các khe trắng/đen
          // bị nhiễu DCT JPEG (`lum >= 204` hoặc `lum <= 62`) giữa các chữ cái gần mép bong bóng đi qua `laNenMask = 1`:
          const laNenTrangRong = laNenTrangChuan && lum >= 204 && sat <= Math.max(42, bgSat + 20)
          const laNenDenRong = laNenDenChuan && lum <= 62 && sat <= 42
          if (trongHopMoRong && !laNenTrangRong && !laNenDenRong && (saiSoRow > 48 || Math.abs(lum - lumDong) > 26)) {
            continue
          }

          const khopTrangDen = (laNenTrangChuan && lum >= 224 && sat <= Math.max(36, bgSat + 16)) || (laNenDenChuan && lum <= 48 && sat <= 36)
          const khopBongMau = saiSoGlobal <= nguongSaiSoMau || (
            saiSoRow <= 36 && (
              (!nenToiThuc && lum >= Math.max(170, bgLum - 48)) ||
              (nenToiThuc && lum <= Math.min(90, bgLum + 48))
            )
          )
          if (khopTrangDen || khopBongMau) {
            laNenMask[idx] = 1
            if (px >= cx0 && px < cx1 && py >= cy0 && py < cy1) demNenTrongHop += 1
          }
        }
      }
      const tyLeNenTrongHop = demNenTrongHop / dienTichHopGoc

      // Ranh giới lãnh thổ Voronoi (`vungBienBaoVe[pos] = 1`) giữa bóng thoại `v` và các bóng thoại `u` khác
      const dsLangGieng = []
      for (const u of tatCaVung) {
        if (u === v) continue
        const ucx0 = Math.round(u.x - rx0)
        const ucy0 = Math.round(u.y - ry0)
        const ucx1 = Math.round(u.x + u.w - rx0)
        const ucy1 = Math.round(u.y + u.h - ry0)
        if (ucx1 < -rw || ucx0 > rw * 2 || ucy1 < -rh || ucy0 > rh * 2) continue
        dsLangGieng.push([ucx0, ucy0, ucx1, ucy1])
      }

      const vungBienBaoVe = new Uint8Array(N)
      if (dsLangGieng.length > 0) {
        for (let py = 0; py < rh; py += 1) {
          const dvy = py < cy0 ? cy0 - py : (py > cy1 ? py - cy1 : 0)
          const dvy2 = dvy * dvy
          const base = py * rw
          for (let px = 0; px < rw; px += 1) {
            const dvx = px < cx0 ? cx0 - px : (px > cx1 ? px - cx1 : 0)
            const distV2 = dvx * dvx + dvy2
            if (distV2 === 0) continue
            for (let k = 0; k < dsLangGieng.length; k += 1) {
              const lg = dsLangGieng[k]
              const dux = px < lg[0] ? lg[0] - px : (px > lg[2] ? px - lg[2] : 0)
              const duy = py < lg[1] ? lg[1] - py : (py > lg[3] ? py - lg[3] : 0)
              if (dux * dux + duy * duy <= distV2) {
                vungBienBaoVe[base + px] = 1
                break
              }
            }
          }
        }
      }

      // Bước 1: Dò lòng bong bóng 2D (`longTrang`) có kiểm soát khe hở gai nhọn (`laNenRong`).
      const tamGocX = (cx0 + cx1) * 0.5
      const tamGocY = (cy0 + cy1) * 0.5
      const banRongGoc = Math.max(3, (cx1 - cx0) * 0.5)
      const banCaoGoc = Math.max(3, (cy1 - cy0) * 0.5)

      const laNenRong = new Uint8Array(N)
      for (let py = 2; py < rh - 2; py += 1) {
        const base = py * rw
        for (let px = 2; px < rw - 2; px += 1) {
          const pos = base + px
          if (!laNenMask[pos] || vungBienBaoVe[pos]) continue
          // Dùng đệm 3x3 cho bong bóng màu đồng nhất (để dòng loang dễ lách qua khe hẹp giữa chữ dày đặc và viền bong bóng),
          // và 5x5 ở vùng ngoài hộp chữ để chặn rò rỉ qua tia gai nhọn
          const trongVungChuMoRong = px >= Math.max(2, cx0 - padCheX) && px < Math.min(rw - 2, cx1 + padCheX) &&
            py >= Math.max(2, cy0 - padCheY) && py < Math.min(rh - 2, cy1 + padCheY)
          const sach3x3 = (
            laNenMask[pos - 1] && laNenMask[pos + 1] &&
            laNenMask[pos - rw] && laNenMask[pos + rw] &&
            laNenMask[pos - rw - 1] && laNenMask[pos - rw + 1] &&
            laNenMask[pos + rw - 1] && laNenMask[pos + rw + 1]
          )
          if (sach3x3 && (trongVungChuMoRong || (
            laNenMask[pos - 2] && laNenMask[pos + 2] &&
            laNenMask[pos - 2 * rw] && laNenMask[pos + 2 * rw]
          ))) {
            laNenRong[pos] = 1
          }
        }
      }

      const longTrang = new Uint8Array(N)
      const hangDoi = new Int32Array(N)
      let dau = 0
      let cuoi = 0

      // Khởi tạo hạt giống `longTrang` từ vùng lõi trung tâm (`bkHat = 0.22`, dự phòng `0.48` nếu chữ quá dày)
      // để tuyệt đối không nhảy cóc qua đường viền bong bóng uốn lượn / lồi lõm ở sát biên `cx0..cx1`:
      for (const bkHat of [0.22, 0.48]) {
        for (let py = cy0; py < cy1; py += 1) {
          const ny = (py - tamGocY) / banCaoGoc
          for (let px = cx0; px < cx1; px += 1) {
            const nx = (px - tamGocX) / banRongGoc
            if (nx * nx + ny * ny > bkHat) continue
            const pos = py * rw + px
            if (laNenMask[pos] && !vungBienBaoVe[pos] && !longTrang[pos]) {
              longTrang[pos] = 1
              hangDoi[cuoi++] = pos
            }
          }
        }
        if (cuoi >= 8) break
      }

      const laNenAnToan = (px, py) => {
        const pos = py * rw + px
        if (!laNenMask[pos] || vungBienBaoVe[pos]) return false
        const nx = (px - tamGocX) / banRongGoc
        const ny = (py - tamGocY) / banCaoGoc
        if (nx * nx + ny * ny <= 0.72) return true
        return laNenRong[pos] === 1
      }

      while (dau < cuoi) {
        const pos = hangDoi[dau++]
        const px = pos % rw
        const py = (pos - px) / rw
        if (px > 0) {
          const npos = pos - 1
          if (!longTrang[npos] && laNenAnToan(px - 1, py)) { longTrang[npos] = 1; hangDoi[cuoi++] = npos }
        }
        if (px + 1 < rw) {
          const npos = pos + 1
          if (!longTrang[npos] && laNenAnToan(px + 1, py)) { longTrang[npos] = 1; hangDoi[cuoi++] = npos }
        }
        if (py > 0) {
          const npos = pos - rw
          if (!longTrang[npos] && laNenAnToan(px, py - 1)) { longTrang[npos] = 1; hangDoi[cuoi++] = npos }
        }
        if (py + 1 < rh) {
          const npos = pos + rw
          if (!longTrang[npos] && laNenAnToan(px, py + 1)) { longTrang[npos] = 1; hangDoi[cuoi++] = npos }
        }
      }

      // Bù nhẹ 1px cho vùng `longTrang` nhưng vẫn giữ khoảng cách an toàn với vách mực đen
      const nhipNoi = cuoi
      let demLongTrang = cuoi
      for (let k = 0; k < nhipNoi; k += 1) {
        const pos = hangDoi[k]
        const px = pos % rw
        const py = (pos - px) / rw
        if (px > 0 && !longTrang[pos - 1] && laNenMask[pos - 1] && !vungBienBaoVe[pos - 1]) { longTrang[pos - 1] = 1; hangDoi[cuoi++] = pos - 1; demLongTrang += 1 }
        if (px + 1 < rw && !longTrang[pos + 1] && laNenMask[pos + 1] && !vungBienBaoVe[pos + 1]) { longTrang[pos + 1] = 1; hangDoi[cuoi++] = pos + 1; demLongTrang += 1 }
        if (py > 0 && !longTrang[pos - rw] && laNenMask[pos - rw] && !vungBienBaoVe[pos - rw]) { longTrang[pos - rw] = 1; hangDoi[cuoi++] = pos - rw; demLongTrang += 1 }
        if (py + 1 < rh && !longTrang[pos + rw] && laNenMask[pos + rw] && !vungBienBaoVe[pos + rw]) { longTrang[pos + rw] = 1; hangDoi[cuoi++] = pos + rw; demLongTrang += 1 }
      }

      // Kiểm tra chặt xem `longTrang` có rò rỉ ra biên ROI không
      let chamBien = 0
      const chuVi = (rw + rh) * 2
      for (let px = 0; px < rw; px += 1) {
        if (longTrang[px]) chamBien += 1
        if (longTrang[(rh - 1) * rw + px]) chamBien += 1
      }
      for (let py = 0; py < rh; py += 1) {
        if (longTrang[py * rw]) chamBien += 1
        if (longTrang[py * rw + (rw - 1)]) chamBien += 1
      }
      const laBannerLon = (wGoc > W * 0.44) || (hGoc > H * 0.40)
      const chamBienNhieu = chamBien >= Math.max(4, Math.round(chuVi * 0.02))
      const roRiBien = (
        laBannerLon ||
        chamBienNhieu ||
        (chamBien >= 2 && demLongTrang > dienTichHopGoc * 3.4) ||
        (chamBien >= 1 && demLongTrang > dienTichHopGoc * 5.2) ||
        demLongTrang > Math.max(dienTichHopGoc * 22.0, N * 0.72)
      )
      const laNenPhucTap = (tyLeNenTrongHop < 0.28) || (roRiBien && !laBongMauDongNhat) || (doLechMauNen > 44)
      const laBongKhepKin = !roRiBien && !laNenPhucTap && laBongMauDongNhat && (demLongTrang >= dienTichHopGoc * 0.36)
      // Khi bong bóng đã được xác nhận khép kín (`laBongKhepKin === true`), tiếp tục phủ `longTrang` qua các điểm `laNenMask === 1`
      // áp sát vách trong của viền bong bóng để bao vây trọn vẹn 100% các chữ cái nằm sát góc/rìa bong bóng (như chữ "TRUE!"):
      if (laBongKhepKin) {
        let dauMo = nhipNoi
        let cuoiMo = cuoi
        for (let buoc = 0; buoc < 32 && dauMo < cuoiMo; buoc += 1) {
          const cuoiHienTai = cuoiMo
          while (dauMo < cuoiHienTai) {
            const pos = hangDoi[dauMo++]
            const px = pos % rw
            const py = (pos - px) / rw
            if (px > 1 && !longTrang[pos - 1] && laNenMask[pos - 1] && !vungBienBaoVe[pos - 1]) { longTrang[pos - 1] = 1; hangDoi[cuoiMo++] = pos - 1; demLongTrang += 1 }
            if (px + 2 < rw && !longTrang[pos + 1] && laNenMask[pos + 1] && !vungBienBaoVe[pos + 1]) { longTrang[pos + 1] = 1; hangDoi[cuoiMo++] = pos + 1; demLongTrang += 1 }
            if (py > 1 && !longTrang[pos - rw] && laNenMask[pos - rw] && !vungBienBaoVe[pos - rw]) { longTrang[pos - rw] = 1; hangDoi[cuoiMo++] = pos - rw; demLongTrang += 1 }
            if (py + 2 < rh && !longTrang[pos + rw] && laNenMask[pos + rw] && !vungBienBaoVe[pos + rw]) { longTrang[pos + rw] = 1; hangDoi[cuoiMo++] = pos + rw; demLongTrang += 1 }
          }
        }
      }
      v._laNenPhucTap = laNenPhucTap
      // Lưu thêm 2 cờ để `laVungSfx` nhận ra chữ tượng thanh vẽ thẳng lên nền tranh (không có bong bóng)
      v._laBongKhepKin = laBongKhepKin
      v._roRiBien = roRiBien

      // Bước 2: Loang ngược từ 4 mép ngoài của ROI vào (`ngoaiBongBong = 1`) qua các điểm `longTrang === 0`.
      const ngoaiBongBong = new Uint8Array(N)
      dau = 0
      cuoi = 0
      const dayNgoai = (pos) => {
        if (ngoaiBongBong[pos] || longTrang[pos]) return
        if (vungBienBaoVe[pos] && laNenMask[pos]) return
        ngoaiBongBong[pos] = 1
        hangDoi[cuoi++] = pos
      }
      for (let px = 0; px < rw; px += 1) {
        dayNgoai(px)
        dayNgoai((rh - 1) * rw + px)
      }
      for (let py = 0; py < rh; py += 1) {
        dayNgoai(py * rw)
        dayNgoai(py * rw + (rw - 1))
      }
      while (dau < cuoi) {
        const pos = hangDoi[dau++]
        const px = pos % rw
        const py = (pos - px) / rw
        if (px > 0) dayNgoai(pos - 1)
        if (px + 1 < rw) dayNgoai(pos + 1)
        if (py > 0) dayNgoai(pos - rw)
        if (py + 1 < rh) dayNgoai(pos + rw)
      }
      for (let idx = 0; idx < N; idx += 1) {
        if (vungBienBaoVe[idx]) ngoaiBongBong[idx] = 1
      }

      // Bước 2B: Xác định chính xác mặt nạ nét chữ gốc cần xoá (`vungXoaChu`) trong vùng mở rộng `[ex0..ex1, ey0..ey1]`:
      // Kết hợp:
      // 1) Ngắt thông biên hộp `[ex0..ex1, ey0..ey1]` (`ketNoiBienHop === 0`),
      // 2) Phân tích thành phần liên thông 2D (Connected Component Analysis - CCA) để bắt trọn 100% các chữ cái,
      //    dấu câu (!, ?, ..., 「」) bị Gemini khoanh hụt thò ra mép `cx0..cx1` hoặc chạm `ex0..ey1` mà KHÔNG xoá nhầm viền bong bóng,
      // 3) Quét độ dày nét chữ (`doDayNetToiDa = 11px`) để cứu cả các chữ cái đậm vô tình chạm nhẹ vào đường viền bong bóng.
      const ex0 = Math.max(0, cx0 - padCheX)
      const ey0 = Math.max(0, cy0 - padCheY)
      const ex1 = Math.min(rw, cx1 + padCheX)
      const ey1 = Math.min(rh, cy1 + padCheY)

      // E115 — Phân tích chuyên biệt Chữ nổi có viền Halo trên nền Screentone / Tóc đen / Bóng đổ (`laChuNoiTrenNen`):
      // Vì sao cần tách riêng khỏi thuật toán tô lòng bong bóng trắng:
      // - Trên nền hạt cát (screentone) hoặc bóng quân mạt chược ("The guy", "Dealt that 3-Sou...", "When I went up against him... Tenpai..."),
      //   chữ gốc là chữ đen có viền halo trắng dày 2–6px vẽ trực tiếp lên nền xám chấm bi (KHÔNG có bong bóng trắng).
      // - Nếu coi các chấm trắng của screentone + viền halo trắng là "nền bong bóng trắng" rồi chạy vòng lặp lấp lỗ `ngoaiVungXoa`
      //   và siêu elip `ryRescue0..ryRescue1`, nó sẽ đè một đám mây trắng đục khổng lồ xoá mất nền cát xám và góc bóng đen của quân bài!
      // - Đặc trưng vật lý phân biệt Viền Halo Trắng (`laTrangDac`) với Hạt Cát Screentone:
      //   Trong nền screentone, hạt đen và trắng xen kẽ từng 1–2px nên độ sáng trung bình lân cận 3x3 (`lum3x3`) chỉ ở mức 125..208.
      //   Ngược lại, viền halo trắng quanh chữ là nét cọ trắng đặc dày 3–6px nên `lum3x3 >= 215`!
      const lumPx = new Float32Array(N)
      const satPx = new Uint8Array(N)
      for (let idx = 0; idx < N; idx += 1) {
        const i = idx * 4
        const r = data[i], g = data[i + 1], b = data[i + 2]
        lumPx[idx] = 0.299 * r + 0.587 * g + 0.114 * b
        satPx[idx] = Math.max(r, g, b) - Math.min(r, g, b)
      }
      const lum3x3 = new Float32Array(N)
      const laTrangDac = new Uint8Array(N)
      const laSangDac = new Uint8Array(N)
      const laToiNet = new Uint8Array(N)
      const laMauDamNet = new Uint8Array(N)
      for (let py = 0; py < rh; py += 1) {
        const y0n = Math.max(0, py - 1)
        const y1n = Math.min(rh - 1, py + 1)
        const base = py * rw
        for (let px = 0; px < rw; px += 1) {
          const x0n = Math.max(0, px - 1)
          const x1n = Math.min(rw - 1, px + 1)
          let sLum = 0, cnt = 0, demTrangLanCan = 0, demSangLanCan = 0
          let coHatDen = false
          for (let yy = y0n; yy <= y1n; yy += 1) {
            const bY = yy * rw
            for (let xx = x0n; xx <= x1n; xx += 1) {
              const l = lumPx[bY + xx]
              sLum += l
              cnt += 1
              if (l >= 216 && satPx[bY + xx] <= 45) demTrangLanCan += 1
              if (l >= 200) demSangLanCan += 1
              if (l <= 78) coHatDen = true
            }
          }
          const pos = base + px
          const tb = sLum / cnt
          lum3x3[pos] = tb
          // Tách biệt dứt khoát giữa Viền Halo Trắng Đặc và Hạt Cát Screentone:
          // - Khi không chạm nét chữ đen (`!coHatDen`): bắt buộc `tb >= 222 || demTrangLanCan >= 7` để loại trừ 100% chấm cát screentone.
          // - Khi nằm sát cạnh nét chữ đen (`coHatDen === true`): 3-5 ô trong cửa sổ 3x3 là nét chữ đen, nên `demTrangLanCan >= 4` bắt trọn cả viền halo mảnh 2-3px!
          if (lumPx[pos] >= 220 && satPx[pos] <= 45 && (tb >= 222 || demTrangLanCan >= 7 || (coHatDen && demTrangLanCan >= 4))) {
            laTrangDac[pos] = 1
          }
          if (
            (lumPx[pos] >= 202 && (tb >= 212 || demSangLanCan >= 7 || (coHatDen && demSangLanCan >= 2))) ||
            (coHatDen && lumPx[pos] >= 158 && satPx[pos] <= 42)
          ) {
            laSangDac[pos] = 1
          }
          // Lõi chữ đen phải thực sự tối (`lumPx <= 88`) hoặc là rìa khử răng cưa (`lumPx <= 118`) chạm trực tiếp hạt đen `<= 78`
          if (lumPx[pos] <= 88 || (lumPx[pos] <= 118 && coHatDen)) {
            laToiNet[pos] = 1
          }
          if (satPx[pos] >= 52 && lumPx[pos] >= 42 && lumPx[pos] <= 232) {
            laMauDamNet[pos] = 1
          }
        }
      }

      // Đo đặc trưng nền thực sự ở vùng hộp chữ và vành đai xung quanh để phát hiện chữ nổi không bong bóng (`laChuNoiTrenNen`)
      // Bao phủ cả 4 kịch bản chữ nổi:
      // - Kịch bản A: Lõi tối/màu đậm + Viền Halo trắng/sáng (trên nền cát screentone, bóng đổ, tóc đen hoặc nền màu)
      // - Kịch bản B: Lõi trắng/sáng/màu tươi + Viền Halo đen/tối (rất phổ biến trên nền tranh màu Manhwa/Manhua)
      // - Kịch bản C: Chữ nổi không viền có độ tương phản màu cao đặt trực tiếp trên nền màu chuyển sắc (gradient)
      let demTrangDacTrongHop = 0
      let demToiTrongHop = 0
      let demSangTrongHop = 0
      let demCapToiTrang = 0
      let demCapTrangToi = 0
      for (let py = cy0; py < cy1; py += 1) {
        const base = py * rw
        for (let px = cx0; px < cx1; px += 1) {
          const pos = base + px
          if (laTrangDac[pos]) demTrangDacTrongHop += 1
          if (laToiNet[pos] || laMauDamNet[pos]) {
            demToiTrongHop += 1
            let ganTrang = false
            for (let d = 1; d <= 5; d += 1) {
              if (
                (px - d >= 0 && (laTrangDac[pos - d] || laSangDac[pos - d])) ||
                (px + d < rw && (laTrangDac[pos + d] || laSangDac[pos + d])) ||
                (py - d >= 0 && (laTrangDac[pos - d * rw] || laSangDac[pos - d * rw])) ||
                (py + d < rh && (laTrangDac[pos + d * rw] || laSangDac[pos + d * rw]))
              ) {
                ganTrang = true
                break
              }
            }
            if (ganTrang) demCapToiTrang += 1
          }
          if (laSangDac[pos] || laMauDamNet[pos]) {
            demSangTrongHop += 1
            // Chỉ tính cặp Đảo Chiều (Lõi sáng/màu kẹp giữa 2 phía Halo tối đối diện) để không nhầm với Halo trắng kẹp giữa nét chữ đen!
            let coToiTrai = false, coToiPhai = false, coToiTren = false, coToiDuoi = false
            for (let d = 1; d <= 8; d += 1) {
              if (!coToiTrai && px - d >= 0 && laToiNet[pos - d] && lumPx[pos - d] <= 95) coToiTrai = true
              if (!coToiPhai && px + d < rw && laToiNet[pos + d] && lumPx[pos + d] <= 95) coToiPhai = true
              if (!coToiTren && py - d >= 0 && laToiNet[pos - d * rw] && lumPx[pos - d * rw] <= 95) coToiTren = true
              if (!coToiDuoi && py + d < rh && laToiNet[pos + d * rw] && lumPx[pos + d * rw] <= 95) coToiDuoi = true
            }
            if ((coToiTrai && coToiPhai) || (coToiTren && coToiDuoi)) demCapTrangToi += 1
          }
        }
      }
      const tyLeTrangDacTrongHop = demTrangDacTrongHop / dienTichHopGoc

      // Đánh dấu trước mảng tối đặc (`laMangToiDacPre`, bề dày >= 5px như tóc đen/bóng đổ lớn)
      // và dải halo trắng mảnh (`laDaiTrangManh`, bề dày <= 9px) để tách biệt hoàn toàn với hành lang tường trắng kẻ sọc 1-2px:
      const laMangToiDacPre = new Uint8Array(N)
      for (let py = 0; py < rh; py += 1) {
        const base = py * rw
        for (let px = 0; px < rw; px += 1) {
          const pos = base + px
          if (lumPx[pos] <= 90) {
            let dlT = 0, drT = 0, duT = 0, ddT = 0
            while (dlT < 6 && px - dlT - 1 >= 0 && lumPx[pos - dlT - 1] <= 95) dlT += 1
            while (drT < 6 && px + drT + 1 < rw && lumPx[pos + drT + 1] <= 95) drT += 1
            while (duT < 6 && py - duT - 1 >= 0 && lumPx[pos - (duT + 1) * rw] <= 95) duT += 1
            while (ddT < 6 && py + ddT + 1 < rh && lumPx[pos + (ddT + 1) * rw] <= 95) ddT += 1
            if (Math.min(dlT + drT + 1, duT + ddT + 1) >= 5) laMangToiDacPre[pos] = 1
          }
        }
      }
      const laDaiTrangManh = new Uint8Array(N)
      for (let py = 0; py < rh; py += 1) {
        const base = py * rw
        for (let px = 0; px < rw; px += 1) {
          const pos = base + px
          if (lumPx[pos] >= 195 && (lum3x3[pos] >= 190 || laTrangDac[pos]) && satPx[pos] <= 55) {
            let dlW = 0, drW = 0, duW = 0, ddW = 0
            while (dlW < 11 && px - dlW - 1 >= 0 && (lum3x3[pos - dlW - 1] >= 190 || laTrangDac[pos - dlW - 1]) && satPx[pos - dlW - 1] <= 55) dlW += 1
            while (drW < 11 && px + drW + 1 < rw && (lum3x3[pos + drW + 1] >= 190 || laTrangDac[pos + drW + 1]) && satPx[pos + drW + 1] <= 55) drW += 1
            while (duW < 11 && py - duW - 1 >= 0 && (lum3x3[pos - (duW + 1) * rw] >= 190 || laTrangDac[pos - (duW + 1) * rw]) && satPx[pos - (duW + 1) * rw] <= 55) duW += 1
            while (ddW < 11 && py + ddW + 1 < rh && (lum3x3[pos + (ddW + 1) * rw] >= 190 || laTrangDac[pos + (ddW + 1) * rw]) && satPx[pos + (ddW + 1) * rw] <= 55) ddW += 1
            const wTr = dlW + drW + 1
            const hTr = duW + ddW + 1
            if (Math.min(wTr, hTr) >= 2 && Math.min(wTr, hTr) <= 9 && Math.max(wTr, hTr) >= 4) {
              if (Math.max(wTr, hTr) <= 15) {
                laDaiTrangManh[pos] = 1
              } else {
                let ganMangToiHoacXam = false
                for (let dM = 1; dM <= 7; dM += 1) {
                  const nList = [
                    px - dM >= 0 ? pos - dM : -1,
                    px + dM < rw ? pos + dM : -1,
                    py - dM >= 0 ? pos - dM * rw : -1,
                    py + dM < rh ? pos + dM * rw : -1
                  ]
                  for (let k = 0; k < 4; k += 1) {
                    const npM = nList[k]
                    if (npM < 0) continue
                    if (laMangToiDacPre[npM] || (lum3x3[npM] >= 90 && lum3x3[npM] <= 206 && !laToiNet[npM] && lumPx[npM] >= 85)) {
                      ganMangToiHoacXam = true
                      break
                    }
                  }
                  if (ganMangToiHoacXam) break
                }
                if (ganMangToiHoacXam) laDaiTrangManh[pos] = 1
              }
            }
          }
        }
      }

      // Lấy mẫu các điểm nền trong phạm vi hộp chữ + vành đai 14px để đo màu trung vị 3 kênh RGB, độ bão hoà & độ nhiễu hạt screentone
      const dsLumNenThuc = []
      const dsTbNenThuc = []
      const dsRNenThuc = []
      const dsGNenThuc = []
      const dsBNenThuc = []
      const dsSatNenThuc = []
      let tongContrastHat = 0
      let demContrastHat = 0
      const ny0M = Math.max(0, cy0 - 14)
      const ny1M = Math.min(rh, cy1 + 14)
      const nx0M = Math.max(0, cx0 - 14)
      const nx1M = Math.min(rw, cx1 + 14)
      for (let py = ny0M; py < ny1M; py += 2) {
        const base = py * rw
        for (let px = nx0M; px < nx1M; px += 2) {
          const pos = base + px
          if (vungBienBaoVe[pos]) continue
          const trongHop = px >= cx0 && px < cx1 && py >= cy0 && py < cy1
          if (trongHop && (laToiNet[pos] || laMauDamNet[pos])) continue
          if (laTrangDac[pos] || laSangDac[pos] || laDaiTrangManh[pos]) {
            let satNetToi = false
            for (let d = 1; d <= 5; d += 1) {
              if (
                (px - d >= 0 && laToiNet[pos - d]) ||
                (px + d < rw && laToiNet[pos + d]) ||
                (py - d >= 0 && laToiNet[pos - d * rw]) ||
                (py + d < rh && laToiNet[pos + d * rw])
              ) {
                satNetToi = true
                break
              }
            }
            if (satNetToi && laDaiTrangManh[pos]) continue
          }
          const idx4 = pos * 4
          dsRNenThuc.push(data[idx4])
          dsGNenThuc.push(data[idx4 + 1])
          dsBNenThuc.push(data[idx4 + 2])
          dsLumNenThuc.push(lumPx[pos])
          dsTbNenThuc.push(lum3x3[pos])
          dsSatNenThuc.push(satPx[pos])
          if (px + 1 < rw && py + 1 < rh) {
            tongContrastHat += Math.abs(lumPx[pos] - lumPx[pos + 1]) + Math.abs(lumPx[pos] - lumPx[pos + rw])
            demContrastHat += 2
          }
        }
      }
      dsLumNenThuc.sort((a, b) => a - b)
      dsTbNenThuc.sort((a, b) => a - b)
      dsRNenThuc.sort((a, b) => a - b)
      dsGNenThuc.sort((a, b) => a - b)
      dsBNenThuc.sort((a, b) => a - b)
      dsSatNenThuc.sort((a, b) => a - b)
      const midNen = Math.floor(dsLumNenThuc.length * 0.5)
      const lumNenTrungVi = dsLumNenThuc.length > 0 ? dsLumNenThuc[midNen] : bgLum
      const tbNenTrungVi = dsTbNenThuc.length > 0 ? dsTbNenThuc[midNen] : lumNenTrungVi
      const lumNenP30 = dsLumNenThuc.length > 0 ? dsLumNenThuc[Math.floor(dsLumNenThuc.length * 0.3)] : bgLum
      const lumNenP10 = dsLumNenThuc.length > 0 ? dsLumNenThuc[Math.floor(dsLumNenThuc.length * 0.1)] : bgLum
      const rNenTrungVi = dsRNenThuc.length > 0 ? dsRNenThuc[midNen] : bgR
      const gNenTrungVi = dsGNenThuc.length > 0 ? dsGNenThuc[midNen] : bgG
      const bNenTrungVi = dsBNenThuc.length > 0 ? dsBNenThuc[midNen] : bgB
      const satNenTrungVi = dsSatNenThuc.length > 0 ? dsSatNenThuc[midNen] : (Math.max(bgR, bgG, bgB) - Math.min(bgR, bgG, bgB))
      const doNhieuHat = demContrastHat > 0 ? (tongContrastHat / demContrastHat) : 0
      const laNenMauThuc = (satNenTrungVi >= 18) || (Math.max(rNenTrungVi, gNenTrungVi, bNenTrungVi) - Math.min(rNenTrungVi, gNenTrungVi, bNenTrungVi) >= 18)

      // Sau khi đã biết màu nền thực sự `(rNenTrungVi, gNenTrungVi, bNenTrungVi)`,
      // đo đối xứng tỷ lệ Kẹp 2 Phía Đối Diện trên vùng màu để phân biệt chính xác Chữ tối + Halo trắng với Chữ sáng/màu + Halo đen:
      if (laNenMauThuc) {
        demToiTrongHop = 0
        demSangTrongHop = 0
        demCapToiTrang = 0
        demCapTrangToi = 0
        for (let py = cy0; py < cy1; py += 1) {
          const base = py * rw
          for (let px = cx0; px < cx1; px += 1) {
            const pos = base + px
            const i4 = pos * 4
            const saiNen = Math.abs(data[i4] - rNenTrungVi) + Math.abs(data[i4 + 1] - gNenTrungVi) + Math.abs(data[i4 + 2] - bNenTrungVi)
            if (laToiNet[pos] || (laMauDamNet[pos] && saiNen >= 65 && lumPx[pos] < 115)) {
              demToiTrongHop += 1
              let coTrTrai = false, coTrPhai = false, coTrTren = false, coTrDuoi = false
              for (let d = 1; d <= 8; d += 1) {
                if (!coTrTrai && px - d >= 0 && (laTrangDac[pos - d] || laSangDac[pos - d])) coTrTrai = true
                if (!coTrPhai && px + d < rw && (laTrangDac[pos + d] || laSangDac[pos + d])) coTrPhai = true
                if (!coTrTren && py - d >= 0 && (laTrangDac[pos - d * rw] || laSangDac[pos - d * rw])) coTrTren = true
                if (!coTrDuoi && py + d < rh && (laTrangDac[pos + d * rw] || laSangDac[pos + d * rw])) coTrDuoi = true
              }
              if ((coTrTrai && coTrPhai) || (coTrTren && coTrDuoi)) demCapToiTrang += 1
            }
            if (laTrangDac[pos] || laSangDac[pos] || (laMauDamNet[pos] && saiNen >= 65 && lumPx[pos] >= 115)) {
              demSangTrongHop += 1
              let coToiTrai = false, coToiPhai = false, coToiTren = false, coToiDuoi = false
              for (let d = 1; d <= 8; d += 1) {
                if (!coToiTrai && px - d >= 0 && laToiNet[pos - d] && lumPx[pos - d] <= 95) coToiTrai = true
                if (!coToiPhai && px + d < rw && laToiNet[pos + d] && lumPx[pos + d] <= 95) coToiPhai = true
                if (!coToiTren && py - d >= 0 && laToiNet[pos - d * rw] && lumPx[pos - d * rw] <= 95) coToiTren = true
                if (!coToiDuoi && py + d < rh && laToiNet[pos + d * rw] && lumPx[pos + d * rw] <= 95) coToiDuoi = true
              }
              if ((coToiTrai && coToiPhai) || (coToiTren && coToiDuoi)) demCapTrangToi += 1
            }
          }
        }
      }
      const tyLeCapToiTrang = demCapToiTrang / Math.max(1, demToiTrongHop)
      const tyLeCapTrangToi = demCapTrangToi / Math.max(1, demSangTrongHop)
      const tyLeCapHalo = Math.max(tyLeCapToiTrang, tyLeCapTrangToi)

      // Kiểm tra chữ không viền đặt trên nền màu chuyển sắc (gradient) / đám mây màu hở viền (`!laBongKhepKin && roRiBien && laNenMauThuc`)
      let demNetTuongPhanNenMau = 0
      if (!laBongKhepKin && laNenMauThuc) {
        for (let py = cy0; py < cy1; py += 1) {
          const base = py * rw
          for (let px = cx0; px < cx1; px += 1) {
            const pos = base + px
            const i4 = pos * 4
            const saiSoNen = Math.abs(data[i4] - rNenTrungVi) + Math.abs(data[i4 + 1] - gNenTrungVi) + Math.abs(data[i4 + 2] - bNenTrungVi)
            if (saiSoNen >= 56) demNetTuongPhanNenMau += 1
          }
        }
      }
      const tyLeNetTrenNenMau = demNetTuongPhanNenMau / dienTichHopGoc
      const laChuKhongVienTrenNenMau = (
        !laBongKhepKin &&
        roRiBien &&
        laNenMauThuc &&
        tyLeTrangDacTrongHop < 0.58 &&
        tyLeNetTrenNenMau >= 0.04 &&
        tyLeNetTrenNenMau <= 0.52
      )

      const ketNoiBienHop = new Uint8Array(N)
      dau = 0
      cuoi = 0
      const dayBienHop = (pos) => {
        if (ketNoiBienHop[pos] || laNenMask[pos]) return
        ketNoiBienHop[pos] = 1
        hangDoi[cuoi++] = pos
      }
      for (let px = ex0; px < ex1; px += 1) {
        dayBienHop(ey0 * rw + px)
        dayBienHop((ey1 - 1) * rw + px)
      }
      for (let py = ey0; py < ey1; py += 1) {
        dayBienHop(py * rw + ex0)
        dayBienHop(py * rw + (ex1 - 1))
      }
      while (dau < cuoi) {
        const pos = hangDoi[dau++]
        const px = pos % rw
        const py = (pos - px) / rw
        for (let dy = -1; dy <= 1; dy += 1) {
          const ny = py + dy
          if (ny < ey0 || ny >= ey1) continue
          const baseY = ny * rw
          for (let dx = -1; dx <= 1; dx += 1) {
            if (dx === 0 && dy === 0) continue
            const nx = px + dx
            if (nx < ex0 || nx >= ex1) continue
            const npk = baseY + nx
            if (dx !== 0 && nx >= cx0 + 2 && nx < cx1 - 2 && ny >= cy0 + 6 && ny < cy1 - 6 && !laNenMask[npk]) {
              let duP = 0, ddP = 0
              while (duP < 18 && py - duP - 1 >= 0 && !laNenMask[pos - (duP + 1) * rw]) duP += 1
              while (ddP < 18 && py + ddP + 1 < rh && !laNenMask[pos + (ddP + 1) * rw]) ddP += 1
              if (duP + ddP + 1 >= 18) {
                let duK = 0, ddK = 0
                while (duK < 10 && ny - duK - 1 >= 0 && !laNenMask[npk - (duK + 1) * rw]) duK += 1
                while (ddK < 10 && ny + ddK + 1 < rh && !laNenMask[npk + (ddK + 1) * rw]) ddK += 1
                if (duK + ddK + 1 <= 7) {
                  const trTren = (ny - duK - 1 >= 0 && lumPx[npk - (duK + 1) * rw] >= 220) || (ny - duK - 2 >= 0 && lumPx[npk - (duK + 2) * rw] >= 220)
                  const trDuoi = (ny + ddK + 1 < rh && lumPx[npk + (ddK + 1) * rw] >= 220) || (ny + ddK + 2 < rh && lumPx[npk + (ddK + 2) * rw] >= 220)
                  if (trTren && trDuoi) continue
                }
              }
            }
            dayBienHop(npk)
          }
        }
      }
      let demNetXuyenHop = 0
      const ix0K = Math.min(rw, Math.min(cx1, cx0 + Math.max(5, Math.round((cx1 - cx0) * 0.16))))
      const ix1K = Math.min(rw, Math.max(ix0K, cx1 - Math.max(5, Math.round((cx1 - cx0) * 0.16))))
      const iy0K = Math.min(rh, Math.min(cy1, cy0 + Math.max(5, Math.round((cy1 - cy0) * 0.16))))
      const iy1K = Math.min(rh, Math.max(iy0K, cy1 - Math.max(5, Math.round((cy1 - cy0) * 0.16))))
      for (let py = iy0K; py < iy1K; py += 1) {
        const bK = py * rw
        for (let px = ix0K; px < ix1K; px += 1) {
          if (ketNoiBienHop[bK + px] && (!laBongKhepKin || ngoaiBongBong[bK + px] === 0)) demNetXuyenHop += 1
        }
      }
      let demKhongToiHop = 0
      let demTrangTinhHop = 0
      for (let py = cy0; py < cy1; py += 1) {
        const bW = py * rw
        for (let px = cx0; px < cx1; px += 1) {
          const lw = lumPx[bW + px]
          if (lw > 120) {
            demKhongToiHop += 1
            if (
              (lw >= 240 && satPx[bW + px] <= 36) ||
              (laNenTrangChuan && lw >= 224 && satPx[bW + px] <= Math.max(48, bgSat + 16))
            ) {
              demTrangTinhHop += 1
            }
          }
        }
      }
      const tyLeTrangTrenNenSang = demTrangTinhHop / Math.max(1, demKhongToiHop)
      const laNenKemSangPhang = (
        !nenToiThuc &&
        lumNenTrungVi >= 222 &&
        satNenTrungVi <= 48 &&
        doLechMauNen <= 28 &&
        (doNhieuHat < 18 || doLechMauNen <= 12) &&
        tyLeNenTrongHop >= 0.45
      )
      const laBongDaiHep = (
        chamBien < Math.floor(chuVi * 0.08) &&
        demLongTrang <= dienTichHopGoc * 1.75 &&
        demNetXuyenHop < 10 &&
        tyLeTrangDacTrongHop >= 0.62 &&
        tyLeTrangTrenNenSang >= 0.84
      )
      const roRiBienThuc = !laBongDaiHep && roRiBien
      const nguongTltBong = doNhieuHat >= 22 ? 0.84 : 0.78
      const coNetTranhXuyenHop = !laBongKhepKin && ((roRiBienThuc && demNetXuyenHop >= 10) || demNetXuyenHop >= 24)
      const laNenTrangPhang = (
        (!laNenMauThuc || laNenKemSangPhang) &&
        !coNetTranhXuyenHop &&
        lumNenTrungVi >= 224 &&
        (tyLeTrangTrenNenSang >= nguongTltBong || laNenKemSangPhang) &&
        (
          (lumNenP30 >= 218 && (lumNenP10 >= 205 || ((laBongKhepKin || !roRiBienThuc) && (tyLeTrangDacTrongHop >= 0.48 || laNenKemSangPhang)))) ||
          ((laBongKhepKin || !roRiBienThuc) && (tyLeTrangDacTrongHop >= 0.55 || laNenKemSangPhang)) ||
          (tyLeTrangTrenNenSang >= 0.83 && tyLeTrangDacTrongHop >= 0.55 && doNhieuHat < 18)
        )
      )

      // Vùng chữ được xác nhận là Chữ Nổi Không Bong Bóng (`laChuNoiTrenNen = true`) khi:
      // 1) Không phải bong bóng khép kín (`!laBongKhepKin`) và không phải nền bong bóng trắng phẳng (`!laNenTrangPhang`), VÀ
      // 2) Có đường kẻ nền xuyên hộp (`coNetTranhXuyenHop`) hoặc viền halo quanh chữ (thuận/đảo) hoặc chữ nổi trên nền màu chuyển sắc (`laChuKhongVienTrenNenMau`).
      const laBongKhepKinThuc = laBongKhepKin && (tyLeTrangTrenNenSang >= nguongTltBong || laNenKemSangPhang || (laBongMauDongNhat && doLechMauNen <= 24 && doNhieuHat < 14)) && (demNetXuyenHop < 10)
      const laChuNoiTrenNen = (
        !laBongKhepKinThuc &&
        !laNenTrangPhang &&
        (coNetTranhXuyenHop || tyLeCapHalo >= 0.20 || demTrangDacTrongHop >= dienTichHopGoc * 0.05 || laChuKhongVienTrenNenMau) &&
        (coNetTranhXuyenHop || tyLeTrangDacTrongHop < 0.65 || lumNenTrungVi < 224 || lumNenP30 < 214 || lumNenP10 < 205 || doNhieuHat >= 8.5 || nenToiThuc || (laNenMauThuc && !laNenKemSangPhang))
      )
      const laDaoChieuHalo = (
        laChuNoiTrenNen &&
        laNenMauThuc &&
        tyLeCapTrangToi > tyLeCapToiTrang * 1.15 &&
        tyLeCapTrangToi >= 0.28 &&
        lumNenTrungVi >= 48 &&
        tyLeTrangDacTrongHop < 0.45
      )
      v._laChuNoiTrenNen = laChuNoiTrenNen
      v._nenScreentone = laChuNoiTrenNen && !laNenMauThuc && (lumNenTrungVi >= 82)
      v._nenMauChuNoi = laChuNoiTrenNen && laNenMauThuc
      v._lumNenTrungVi = lumNenTrungVi
      v._mauNenChuNoiCss = `rgb(${Math.round(rNenTrungVi)}, ${Math.round(gNenTrungVi)}, ${Math.round(bNenTrungVi)})`

      const laChuGoc = new Uint8Array(N)
      const vungXoaChu = new Uint8Array(N)
      const kcLoi = new Uint8Array(N)
      let zx0 = ex0, zy0 = ey0, zx1 = ex1, zy1 = ey1

      if (laChuNoiTrenNen) {
        // === NHÁNH ĐA TÌNH HUỐNG CHO CHỮ NỔI KHÔNG BONG BÓNG (SCREENTONE / TÓC ĐEN / TƯỜNG TRẮNG KẺ SỌC / NỀN HỖN HỢP / NỀN MÀU) ===
        const laLoiChu = new Uint8Array(N)
        const ungVienNet = new Uint8Array(N)
        const netMongLoi = new Uint8Array(N)
        let qx0 = Math.max(2, cx0 - Math.min(32, padCheX))
        let qy0 = Math.max(2, cy0 - Math.min(38, padCheY))
        let qx1 = Math.min(rw - 2, cx1 + Math.min(32, padCheX))
        let qy1 = Math.min(rh - 2, cy1 + Math.min(58, padCheY))
        // Cắt chặn `qx0, qy0, qx1, qy1` tại đường viền khung tranh (panel border) để tuyệt đối không tràn sang khung tranh kế bên:
        const spanWB = Math.max(1, cx1 - cx0)
        const spanHB = Math.max(1, cy1 - cy0)
        for (let pyB = cy0 - 1; pyB >= qy0; pyB -= 1) {
          const baseB = pyB * rw
          let demToiB = 0
          for (let pxB = cx0; pxB < cx1; pxB += 1) {
            if (lumPx[baseB + pxB] <= 105) demToiB += 1
          }
          if (demToiB >= spanWB * 0.62) {
            qy0 = Math.min(cy0, pyB + 2)
            break
          }
        }
        for (let pyB = cy1; pyB < qy1; pyB += 1) {
          const baseB = pyB * rw
          let demToiB = 0
          for (let pxB = cx0; pxB < cx1; pxB += 1) {
            if (lumPx[baseB + pxB] <= 105) demToiB += 1
          }
          if (demToiB >= spanWB * 0.62) {
            qy1 = Math.max(cy1, pyB - 1)
            break
          }
        }
        for (let pxB = cx0 - 1; pxB >= qx0; pxB -= 1) {
          let demToiB = 0
          for (let pyB = cy0; pyB < cy1; pyB += 1) {
            if (lumPx[pyB * rw + pxB] <= 105) demToiB += 1
          }
          if (demToiB >= spanHB * 0.62) {
            qx0 = Math.min(cx0, pxB + 2)
            break
          }
        }
        for (let pxB = cx1; pxB < qx1; pxB += 1) {
          let demToiB = 0
          for (let pyB = cy0; pyB < cy1; pyB += 1) {
            if (lumPx[pyB * rw + pxB] <= 105) demToiB += 1
          }
          if (demToiB >= spanHB * 0.62) {
            qx1 = Math.max(cx1, pxB - 1)
            break
          }
        }

        const laNenToiChuNoi = !laNenMauThuc && lumNenTrungVi < 82

        // Hàm kiểm tra điểm ứng viên Lõi chữ & Viền Halo theo từng kịch bản
        const laUngVienLoi = (pos) => {
          const i4 = pos * 4
          const py = Math.floor(pos / rw)
          const saiSoMed = Math.abs(data[i4] - rNenTrungVi) + Math.abs(data[i4 + 1] - gNenTrungVi) + Math.abs(data[i4 + 2] - bNenTrungVi)
          const saiSoRow = Math.abs(data[i4] - bgRowR[py]) + Math.abs(data[i4 + 1] - bgRowG[py]) + Math.abs(data[i4 + 2] - bgRowB[py])
          if (laDaoChieuHalo) {
            if (laTrangDac[pos]) return true
            return saiSoMed >= 62 && saiSoRow >= 52 && Boolean(laSangDac[pos] || (laMauDamNet[pos] && lumPx[pos] >= 115))
          }
          if (laChuKhongVienTrenNenMau && tyLeCapHalo < 0.20) {
            return saiSoMed >= 58 && saiSoRow >= 48
          }
          if (laToiNet[pos]) return true
          if (laNenMauThuc && laMauDamNet[pos]) {
            return saiSoMed >= 68 && saiSoRow >= 62
          }
          return false
        }

        const laUngVienHalo = (pos) => {
          if (laDaoChieuHalo) {
            return Boolean(laToiNet[pos] || lumPx[pos] <= 105)
          }
          if (laNenToiChuNoi) {
            return Boolean(laTrangDac[pos] || (lumPx[pos] >= 145 && satPx[pos] <= 55))
          }
          return Boolean(laTrangDac[pos] || laDaiTrangManh[pos] || (laNenMauThuc && laSangDac[pos]))
        }

        const maxDayNet = Math.max(16, Math.min(32, Math.round(Math.min(wGoc, hGoc) * 0.24)))
        const maxScanD = Math.max(28, maxDayNet + 4)
        const BK_HALO = Math.max(10, Math.floor(maxDayNet / 2) + 4)
        for (let py = 1; py < rh - 1; py += 1) {
          const base = py * rw
          for (let px = 1; px < rw - 1; px += 1) {
            const pos = base + px
            if (vungBienBaoVe[pos] || !laUngVienLoi(pos)) continue
            let dL = 0, dR = 0, dU = 0, dD = 0
            while (dL < maxScanD && px - dL - 1 >= 0 && laUngVienLoi(pos - dL - 1)) dL += 1
            while (dR < maxScanD && px + dR + 1 < rw && laUngVienLoi(pos + dR + 1)) dR += 1
            while (dU < maxScanD && py - dU - 1 >= 0 && laUngVienLoi(pos - (dU + 1) * rw)) dU += 1
            while (dD < maxScanD && py + dD + 1 < rh && laUngVienLoi(pos + (dD + 1) * rw)) dD += 1
            const dayNgang = dL + dR + 1
            const dayDoc = dU + dD + 1
            if (Math.min(dayNgang, dayDoc) <= maxDayNet) {
              netMongLoi[pos] = 1
            }
            if (px < qx0 || px >= qx1 || py < qy0 || py >= qy1) continue
            if (Math.min(dayNgang, dayDoc) > maxDayNet || (Math.min(dayNgang, dayDoc) <= 3 && Math.max(dayNgang, dayDoc) >= 24)) continue

            if (laChuKhongVienTrenNenMau && tyLeCapHalo < 0.20) {
              if (!ketNoiBienHop[pos] && Math.min(dayNgang, dayDoc) <= 13) {
                ungVienNet[pos] = 1
              }
              continue
            }

            // Kiểm tra Halo 2px liên tiếp ngay sát rìa ngoài của nét chữ (1..3px tính từ mép nét dL, dR, dU, dD)
            // để tuyệt đối không nhảy qua khe hở giữa 2 dòng chữ bắt nhầm nét gạch chéo / speedline nền:
            const hTrai = (
              dayNgang <= 36 &&
              px - dL - 2 >= 0 &&
              (
                (laUngVienHalo(pos - dL - 1) && laUngVienHalo(pos - dL - 2)) ||
                (px - dL - 3 >= 0 && laUngVienHalo(pos - dL - 2) && laUngVienHalo(pos - dL - 3))
              )
            )
            const hPhai = (
              dayNgang <= 36 &&
              px + dR + 2 < rw &&
              (
                (laUngVienHalo(pos + dR + 1) && laUngVienHalo(pos + dR + 2)) ||
                (px + dR + 3 < rw && laUngVienHalo(pos + dR + 2) && laUngVienHalo(pos + dR + 3))
              )
            )
            const hTren = (
              dayDoc <= 42 &&
              py - dU - 2 >= 0 &&
              (
                (laUngVienHalo(pos - (dU + 1) * rw) && laUngVienHalo(pos - (dU + 2) * rw)) ||
                (py - dU - 3 >= 0 && laUngVienHalo(pos - (dU + 2) * rw) && laUngVienHalo(pos - (dU + 3) * rw))
              )
            )
            const hDuoi = (
              dayDoc <= 42 &&
              py + dD + 2 < rh &&
              (
                (laUngVienHalo(pos + (dD + 1) * rw) && laUngVienHalo(pos + (dD + 2) * rw)) ||
                (py + dD + 3 < rh && laUngVienHalo(pos + (dD + 2) * rw) && laUngVienHalo(pos + (dD + 3) * rw))
              )
            )
            const kepDoiDien = (hTrai && hPhai) || (hTren && hDuoi)
            if (kepDoiDien) {
              ungVienNet[pos] = 1
            }
          }
        }

        // Lan truyền 4 bước dọc theo nét chữ (`netMongLoi`) nối liền với `ungVienNet`
        for (let buoc = 0; buoc < 4; buoc += 1) {
          for (let py = qy0; py < qy1; py += 1) {
            const base = py * rw
            for (let px = qx0; px < qx1; px += 1) {
              const pos = base + px
              if (ungVienNet[pos] || !netMongLoi[pos] || vungBienBaoVe[pos]) continue
              if (ungVienNet[pos - 1] || ungVienNet[pos + 1] || ungVienNet[pos - rw] || ungVienNet[pos + rw]) {
                ungVienNet[pos] = 1
              }
            }
          }
        }

        // Phân tích thành phần liên thông 2D (8-connected CCA) trên `ungVienNet`
        // kết hợp Mật độ nét trung bình (`rho = area / max(w, h)`) và Liên kết chuỗi Từ/Dòng (Word/Line Chaining):
        const daDuyetComp = new Uint8Array(N)
        const dsCompChu = []
        const maxCompW = Math.max(56, Math.round(wGoc * 1.05))
        const maxCompH = Math.max(56, Math.round(hGoc * 0.65))
        const maxCompDt = Math.max(1450, Math.round(dienTichHopGoc * 0.46))

        for (let py = qy0; py < qy1; py += 1) {
          const base = py * rw
          for (let px = qx0; px < qx1; px += 1) {
            const sPos = base + px
            if (!ungVienNet[sPos] || daDuyetComp[sPos] || vungBienBaoVe[sPos]) continue
            daDuyetComp[sPos] = 1
            const pts = [sPos]
            let cMinX = px, cMaxX = px, cMinY = py, cMaxY = py
            let chamBienC = false
            let demUv = 0
            let headC = 0
            while (headC < pts.length) {
              const pC = pts[headC++]
              if (ungVienNet[pC]) demUv += 1
              const xc = pC % rw
              const yc = (pC - xc) / rw
              if (xc <= qx0 + 1 || xc >= qx1 - 2 || yc <= qy0 + 1 || yc >= qy1 - 2 || ketNoiBienHop[pC]) chamBienC = true
              if (xc < cMinX) cMinX = xc
              if (xc > cMaxX) cMaxX = xc
              if (yc < cMinY) cMinY = yc
              if (yc > cMaxY) cMaxY = yc
              for (let dyC = -1; dyC <= 1; dyC += 1) {
                const nyc = yc + dyC
                if (nyc <= 0 || nyc >= rh - 1) continue
                const nbc = nyc * rw
                for (let dxC = -1; dxC <= 1; dxC += 1) {
                  if (dxC === 0 && dyC === 0) continue
                  const nxc = xc + dxC
                  if (nxc <= 0 || nxc >= rw - 1) continue
                  const npc = nbc + nxc
                  if (ketNoiBienHop[npc]) chamBienC = true
                  if (!daDuyetComp[npc] && ungVienNet[npc] && !vungBienBaoVe[npc]) {
                    daDuyetComp[npc] = 1
                    pts.push(npc)
                  }
                }
              }
            }
            const cwC = cMaxX - cMinX + 1
            const chC = cMaxY - cMinY + 1
            const dtC = pts.length
            const maxD = Math.max(cwC, chC)
            const minD = Math.min(cwC, chC)
            const rhoC = dtC / Math.max(1, maxD)
            if (chamBienC || dtC > maxCompDt || cwC > maxCompW || chC > maxCompH) continue
            if (cwC >= wGoc * 0.82 && chC >= hGoc * 0.72) continue
            if (demUv < dtC * 0.35) continue
            const laDauCauNho = (dtC >= 3 && maxD <= 11) || (cwC <= 22 && chC >= 2 && chC <= 8 && dtC >= 6)
            const laChuIDoc = (cwC >= 1 && cwC <= 3 && chC >= 8 && chC <= 22 && dtC >= 8 && dtC >= chC * 0.75)
            if (!laDauCauNho && !laChuIDoc) {
              if (dtC < 9 || minD <= 2) continue
              if (minD <= 4 && maxD >= 10 && rhoC < 2.20) continue
              if (maxD >= 13 && rhoC < 1.95) continue
            }

            const trongHatGiong = (
              dtC >= 18 &&
              minD >= 4 &&
              rhoC >= 2.10 &&
              cMaxX >= cx0 - 8 &&
              cMinX <= cx1 + 8 &&
              cMaxY >= cy0 - 12 &&
              cMinY <= cy1 + 12
            )
            dsCompChu.push({
              pts,
              x0: cMinX,
              y0: cMinY,
              x1: cMaxX,
              y1: cMaxY,
              w: cwC,
              h: chC,
              chon: trongHatGiong
            })
          }
        }

        let curX0 = cx0, curY0 = cy0, curX1 = cx1, curY1 = cy1
        for (let i = 0; i < dsCompChu.length; i += 1) {
          const c = dsCompChu[i]
          if (c.chon) {
            if (c.x0 < curX0) curX0 = c.x0
            if (c.y0 < curY0) curY0 = c.y0
            if (c.x1 > curX1) curX1 = c.x1
            if (c.y1 > curY1) curY1 = c.y1
          }
        }
        for (let iter = 0; iter < 4; iter += 1) {
          let coThem = false
          const daChon = dsCompChu.filter((c) => c.chon)
          if (daChon.length === 0) break
          for (let i = 0; i < dsCompChu.length; i += 1) {
            const cUng = dsCompChu[i]
            if (cUng.chon) continue
            const ux0 = cUng.x0, uy0 = cUng.y0, ux1 = cUng.x1, uy1 = cUng.y1
            let hopLeChain = false
            for (let j = 0; j < daChon.length; j += 1) {
              const cGoc = daChon[j]
              const ax0 = cGoc.x0, ay0 = cGoc.y0, ax1 = cGoc.x1, ay1 = cGoc.y1
              const giaoY = Math.min(uy1, ay1) - Math.max(uy0, ay0)
              const kcX = Math.max(0, Math.max(ux0 - ax1, ax0 - ux1))
              const kcY = Math.max(0, Math.max(uy0 - ay1, ay0 - uy1))
              if (giaoY >= -2 && kcX <= 11 && uy0 >= curY0 - 16 && uy1 <= curY1 + 24) {
                hopLeChain = true
                break
              }
              if (kcY <= 18 && kcX <= 16 && ux0 >= curX0 - 14 && ux1 <= curX1 + 18) {
                hopLeChain = true
                break
              }
            }
            if (hopLeChain) {
              cUng.chon = true
              if (ux0 < curX0) curX0 = ux0
              if (uy0 < curY0) curY0 = uy0
              if (ux1 > curX1) curX1 = ux1
              if (uy1 > curY1) curY1 = uy1
              coThem = true
            }
          }
          if (!coThem) break
        }

        let hx0 = cx0, hy0 = cy0, hx1 = cx1, hy1 = cy1
        let coCompChon = false
        for (let i = 0; i < dsCompChu.length; i += 1) {
          const c = dsCompChu[i]
          if (!c.chon) continue
          coCompChon = true
          if (c.x0 < hx0) hx0 = c.x0
          if (c.y0 < hy0) hy0 = c.y0
          if (c.x1 + 1 > hx1) hx1 = c.x1 + 1
          if (c.y1 + 1 > hy1) hy1 = c.y1 + 1
          for (let k = 0; k < c.pts.length; k += 1) {
            const pC = c.pts[k]
            laLoiChu[pC] = 1
            laChuGoc[pC] = 1
          }
        }
        const choPhepCuuMangToi = Boolean(
          !laNenMauThuc &&
          (lumNenTrungVi < 212 || tyLeTrangDacTrongHop < 0.38 || doNhieuHat >= 18)
        )
        for (let pyFb = Math.max(2, cy0 - 4); pyFb < Math.min(rh - 2, cy1 + 4); pyFb += 1) {
          const bFb = pyFb * rw
          for (let pxFb = Math.max(2, cx0 - 4); pxFb < Math.min(rw - 2, cx1 + 4); pxFb += 1) {
            const pFb = bFb + pxFb
            if (!ungVienNet[pFb] || laLoiChu[pFb] || vungBienBaoVe[pFb]) continue
            let chonFb = !coCompChon
            if (!chonFb && choPhepCuuMangToi) {
              let coHaloFb = false
              let coToiFb = false
              for (let dyF = -4; dyF <= 4; dyF += 1) {
                const nyF = pyFb + dyF
                if (nyF < 0 || nyF >= rh) continue
                const nbF = nyF * rw
                for (let dxF = -4; dxF <= 4; dxF += 1) {
                  const nxF = pxFb + dxF
                  if (nxF < 0 || nxF >= rw) continue
                  const npF = nbF + nxF
                  if (Math.abs(dxF) <= 3 && Math.abs(dyF) <= 3 && (laTrangDac[npF] || laDaiTrangManh[npF])) {
                    coHaloFb = true
                  }
                  if (laMangToiDacPre[npF]) {
                    coToiFb = true
                  }
                }
                if (coHaloFb && coToiFb) break
              }
              chonFb = coHaloFb && coToiFb
            }
            if (chonFb) {
              laLoiChu[pFb] = 1
              laChuGoc[pFb] = 1
              if (pxFb < hx0) hx0 = pxFb
              if (pyFb < hy0) hy0 = pyFb
              if (pxFb + 1 > hx1) hx1 = pxFb + 1
              if (pyFb + 1 > hy1) hy1 = pyFb + 1
            }
          }
        }
        hx0 = Math.max(1, hx0 - 8)
        hy0 = Math.max(1, hy0 - 8)
        hx1 = Math.min(rw - 1, hx1 + 8)
        hy1 = Math.min(rh - 1, hy1 + 8)
        zx0 = Math.min(zx0, hx0)
        zy0 = Math.min(zy0, hy0)
        zx1 = Math.max(zx1, hx1)
        zy1 = Math.max(zy1, hy1)

        dau = 0
        cuoi = 0
        for (let py = hy0; py < hy1; py += 1) {
          const base = py * rw
          for (let px = hx0; px < hx1; px += 1) {
            const pos = base + px
            if (laLoiChu[pos]) {
              kcLoi[pos] = 1
              hangDoi[cuoi++] = pos
            }
          }
        }
        const BK_VIEN_HALO = (doNhieuHat >= 14 && !laNenToiChuNoi && !laNenMauThuc && maxDayNet <= 20) ? 2 : (maxDayNet >= 22 ? 5 : 4)
        while (dau < cuoi) {
          const pos = hangDoi[dau++]
          const buocHienTai = kcLoi[pos]
          if (buocHienTai > BK_VIEN_HALO) continue
          const px = pos % rw
          const py = (pos - px) / rw
          for (let dy = -1; dy <= 1; dy += 1) {
            const ny = py + dy
            if (ny < hy0 || ny >= hy1) continue
            const nBase = ny * rw
            for (let dx = -1; dx <= 1; dx += 1) {
              if (dx === 0 && dy === 0) continue
              const nx = px + dx
              if (nx < hx0 || nx >= hx1) continue
              const npos = nBase + nx
              if (kcLoi[npos] || vungBienBaoVe[npos]) continue
              let laDiemHalo = false
              if (laDaoChieuHalo) {
                laDiemHalo = Boolean(laToiNet[npos] || (buocHienTai <= 4 && lumPx[npos] <= 115))
              } else if (laNenToiChuNoi && !laNenMauThuc) {
                const nguongSangNenToi = Math.max(30, lumNenTrungVi + 16)
                laDiemHalo = Boolean(
                  laDaiTrangManh[npos] ||
                  laTrangDac[npos] ||
                  (buocHienTai <= 2 && lumPx[npos] >= nguongSangNenToi && satPx[npos] <= 55)
                )
              } else {
                laDiemHalo = Boolean(
                  (laTrangDac[npos] && buocHienTai <= BK_VIEN_HALO) ||
                  (laDaiTrangManh[npos] && buocHienTai <= (doNhieuHat >= 14 ? 3 : BK_VIEN_HALO)) ||
                  (buocHienTai <= 2 && (laTrangDac[npos] || laSangDac[npos])) ||
                  (laNenMauThuc && laSangDac[npos])
                )
              }
              if (laDiemHalo) {
                kcLoi[npos] = buocHienTai + 1
                laChuGoc[npos] = 1
                hangDoi[cuoi++] = npos
              }
            }
          }
        }

        // Đo màu chữ gốc (`_mauChuGocCss`) & màu viền halo gốc (`_mauHaloGocCss`) để giữ nguyên phong cách màu sắc trên nền màu
        const dsRLoi = [], dsGLoi = [], dsBLoi = []
        for (let py = hy0; py < hy1; py += 1) {
          const base = py * rw
          for (let px = hx0; px < hx1; px += 1) {
            const pos = base + px
            if (!laLoiChu[pos]) continue
            const i4 = pos * 4
            dsRLoi.push(data[i4])
            dsGLoi.push(data[i4 + 1])
            dsBLoi.push(data[i4 + 2])
          }
        }
        if (dsRLoi.length >= 6) {
          dsRLoi.sort((a, b) => a - b)
          dsGLoi.sort((a, b) => a - b)
          dsBLoi.sort((a, b) => a - b)
          const mIdx = Math.floor(dsRLoi.length * 0.5)
          const rLoi = dsRLoi[mIdx], gLoi = dsGLoi[mIdx], bLoi = dsBLoi[mIdx]
          const lumLoi = 0.299 * rLoi + 0.587 * gLoi + 0.114 * bLoi
          const satLoi = Math.max(rLoi, gLoi, bLoi) - Math.min(rLoi, gLoi, bLoi)
          if (laDaoChieuHalo || (laNenMauThuc && lumLoi >= 175 && lumNenTrungVi < 175)) {
            v._mauChuGocCss = satLoi >= 48 ? `rgb(${rLoi}, ${gLoi}, ${bLoi})` : '#ffffff'
            v._mauHaloGocCss = '#000000'
          } else if (laNenMauThuc && satLoi >= 58) {
            v._mauChuGocCss = `rgb(${rLoi}, ${gLoi}, ${bLoi})`
            v._mauHaloGocCss = lumLoi >= 135 ? '#000000' : '#ffffff'
          } else if (!laDaoChieuHalo && lumLoi <= 88 && demTrangDacTrongHop >= Math.max(18, Math.round(dienTichHopGoc * 0.04))) {
            v._mauChuGocCss = '#0f172a'
            v._mauHaloGocCss = '#ffffff'
          }
        }

        // Nở nhẹ quanh `laChuGoc` để xoá sạch viền khử răng cưa JPEG của halo mà không ăn rộng ra nền screentone/nền màu
        const maxR2Dil = (doNhieuHat >= 14 && !laNenToiChuNoi && !laNenMauThuc) ? 1 : 4
        for (let py = zy0; py < zy1; py += 1) {
          const base = py * rw
          for (let px = zx0; px < zx1; px += 1) {
            const pos = base + px
            if (!laChuGoc[pos]) continue
            vungXoaChu[pos] = 1
            for (let dy = -2; dy <= 2; dy += 1) {
              const ny = py + dy
              if (ny < zy0 || ny >= zy1) continue
              const nBase = ny * rw
              for (let dx = -2; dx <= 2; dx += 1) {
                if (dx * dx + dy * dy > maxR2Dil) continue
                const nx = px + dx
                if (nx < zx0 || nx >= zx1) continue
                const npos = nBase + nx
                if (vungBienBaoVe[npos]) continue
                if (!laDaoChieuHalo && laToiNet[npos] && !laLoiChu[npos] && lumPx[npos] < 105) continue
                vungXoaChu[npos] = 1
              }
            }
          }
        }

        // Lấp các lỗ nhỏ bên trong bụng chữ cái ('O', 'P', 'a', 'e', '6', '3', 'B')
        const maxLoBung = (doNhieuHat >= 14 && !laNenToiChuNoi && !laNenMauThuc) ? 68 : (maxDayNet >= 22 ? 160 : 95)
        const daDuyetLo = new Uint8Array(N)
        for (let py = zy0 + 1; py < zy1 - 1; py += 1) {
          const base = py * rw
          for (let px = zx0 + 1; px < zx1 - 1; px += 1) {
            const sPos = base + px
            if (vungXoaChu[sPos] || daDuyetLo[sPos] || vungBienBaoVe[sPos]) continue
            dau = 0
            cuoi = 0
            daDuyetLo[sPos] = 1
            hangDoi[cuoi++] = sPos
            let chamBien = false
            let loX0 = px, loX1 = px, loY0 = py, loY1 = py
            while (dau < cuoi) {
              const p = hangDoi[dau++]
              const x = p % rw
              const y = (p - x) / rw
              if (x < loX0) loX0 = x
              if (x > loX1) loX1 = x
              if (y < loY0) loY0 = y
              if (y > loY1) loY1 = y
              if (x <= zx0 + 1 || x >= zx1 - 2 || y <= zy0 + 1 || y >= zy1 - 2) chamBien = true
              if (x > zx0 && !vungXoaChu[p - 1] && !daDuyetLo[p - 1]) { daDuyetLo[p - 1] = 1; hangDoi[cuoi++] = p - 1 }
              if (x + 1 < zx1 && !vungXoaChu[p + 1] && !daDuyetLo[p + 1]) { daDuyetLo[p + 1] = 1; hangDoi[cuoi++] = p + 1 }
              if (y > zy0 && !vungXoaChu[p - rw] && !daDuyetLo[p - rw]) { daDuyetLo[p - rw] = 1; hangDoi[cuoi++] = p - rw }
              if (y + 1 < zy1 && !vungXoaChu[p + rw] && !daDuyetLo[p + rw]) { daDuyetLo[p + rw] = 1; hangDoi[cuoi++] = p + rw }
            }
            if (!chamBien && cuoi <= maxLoBung && (loX1 - loX0 + 1) <= 22 && (loY1 - loY0 + 1) <= 22) {
              for (let k = 0; k < cuoi; k += 1) vungXoaChu[hangDoi[k]] = 1
            }
          }
        }

        const laTuongTrangPre = Boolean(!laNenMauThuc && tyLeTrangDacTrongHop >= 0.38 && lumNenTrungVi >= 212 && doNhieuHat < 18)
        for (let passS = 0; passS < 2; passS += 1) {
          const snapXoa = new Uint8Array(vungXoaChu)
          for (let pyS = Math.max(4, hy0); pyS < Math.min(rh - 4, hy1); pyS += 1) {
            const baseS = pyS * rw
            for (let pxS = Math.max(4, hx0); pxS < Math.min(rw - 4, hx1); pxS += 1) {
              const posS = baseS + pxS
              if (snapXoa[posS] || vungBienBaoVe[posS]) continue
              const kepX4 = (snapXoa[posS - 1] || snapXoa[posS - 2] || snapXoa[posS - 3] || snapXoa[posS - 4]) &&
                (snapXoa[posS + 1] || snapXoa[posS + 2] || snapXoa[posS + 3] || snapXoa[posS + 4])
              const kepY4 = (snapXoa[posS - rw] || snapXoa[posS - 2 * rw] || snapXoa[posS - 3 * rw] || snapXoa[posS - 4 * rw]) &&
                (snapXoa[posS + rw] || snapXoa[posS + 2 * rw] || snapXoa[posS + 3 * rw] || snapXoa[posS + 4 * rw])
              const kepX7 = kepX4 || (
                (snapXoa[posS - 5] || snapXoa[posS - 6] || snapXoa[posS - 7]) &&
                (snapXoa[posS + 1] || snapXoa[posS + 2] || snapXoa[posS + 3] || snapXoa[posS + 4] || snapXoa[posS + 5] || snapXoa[posS + 6] || snapXoa[posS + 7])
              ) || (
                (snapXoa[posS - 1] || snapXoa[posS - 2] || snapXoa[posS - 3] || snapXoa[posS - 4]) &&
                (snapXoa[posS + 5] || snapXoa[posS + 6] || snapXoa[posS + 7])
              )
              const kepY7 = kepY4 || (
                (snapXoa[posS - 5 * rw] || snapXoa[posS - 6 * rw] || snapXoa[posS - 7 * rw]) &&
                (snapXoa[posS + rw] || snapXoa[posS + 2 * rw] || snapXoa[posS + 3 * rw] || snapXoa[posS + 4 * rw] || snapXoa[posS + 5 * rw] || snapXoa[posS + 6 * rw] || snapXoa[posS + 7 * rw])
              ) || (
                (snapXoa[posS - rw] || snapXoa[posS - 2 * rw] || snapXoa[posS - 3 * rw] || snapXoa[posS - 4 * rw]) &&
                (snapXoa[posS + 5 * rw] || snapXoa[posS + 6 * rw] || snapXoa[posS + 7 * rw])
              )
              if (
                (kepX7 && kepY7) ||
                (!laTuongTrangPre && (kepX4 || kepY4) && (lumPx[posS] <= 135 || laTrangDac[posS] || laSangDac[posS] || laDaiTrangManh[posS]))
              ) {
                vungXoaChu[posS] = 1
              }
            }
          }
        }

        // Hấp thụ phần lõi mực đen dày còn sót bên trong chữ in đậm lớn ("BUT WHAT A MIRROR SHOWED HIM!!", "3-Sou", "NOOOOOO!!")
        const daDuyetLoiDam = new Uint8Array(N)
        const maxLoiDam = Math.max(850, Math.round(dienTichHopGoc * 0.08))
        for (let py = qy0 + 1; py < qy1 - 1; py += 1) {
          const base = py * rw
          for (let px = qx0 + 1; px < qx1 - 1; px += 1) {
            const sPos = base + px
            if (vungXoaChu[sPos] || daDuyetLoiDam[sPos] || lumPx[sPos] > 102) continue
            dau = 0
            cuoi = 0
            daDuyetLoiDam[sPos] = 1
            hangDoi[cuoi++] = sPos
            let chamBienToi = false
            let chamXoaToi = false
            let chamLoiToi = false
            let vienXoaToi = 0
            let vienNenToi = 0
            while (dau < cuoi) {
              const pT = hangDoi[dau++]
              const xt = pT % rw
              const yt = (pT - xt) / rw
              if (xt <= qx0 + 1 || xt >= qx1 - 2 || yt <= qy0 + 1 || yt >= qy1 - 2 || ketNoiBienHop[pT]) chamBienToi = true
              for (let dyT = -1; dyT <= 1; dyT += 1) {
                const nyt = yt + dyT
                if (nyt <= 0 || nyt >= rh - 1) continue
                const nbt = nyt * rw
                for (let dxT = -1; dxT <= 1; dxT += 1) {
                  if (dxT === 0 && dyT === 0) continue
                  const nxt = xt + dxT
                  if (nxt <= 0 || nxt >= rw - 1) continue
                  const npt = nbt + nxt
                  if (vungXoaChu[npt]) {
                    chamXoaToi = true
                    vienXoaToi += 1
                    if (laLoiChu[npt]) chamLoiToi = true
                  } else if (!daDuyetLoiDam[npt]) {
                    if (lumPx[npt] <= 102) {
                      daDuyetLoiDam[npt] = 1
                      hangDoi[cuoi++] = npt
                    } else {
                      vienNenToi += 1
                    }
                  }
                }
              }
            }
            if (
              !chamBienToi &&
              chamXoaToi &&
              chamLoiToi &&
              vienXoaToi >= (vienXoaToi + vienNenToi) * 0.80 &&
              cuoi <= maxLoiDam
            ) {
              for (let k = 0; k < cuoi; k += 1) {
                const pT = hangDoi[k]
                if (vungBienBaoVe[pT]) continue
                vungXoaChu[pT] = 1
                const xt = pT % rw
                const yt = (pT - xt) / rw
                for (let dyN = -2; dyN <= 2; dyN += 1) {
                  const nyn = yt + dyN
                  if (nyn <= 1 || nyn >= rh - 2) continue
                  const nbn = nyn * rw
                  for (let dxN = -2; dxN <= 2; dxN += 1) {
                    const nxn = xt + dxN
                    if (nxn <= 1 || nxn >= rw - 2) continue
                    const npn = nbn + nxn
                    if (!vungBienBaoVe[npn] && (laTrangDac[npn] || laSangDac[npn] || lumPx[npn] <= 125)) {
                      vungXoaChu[npn] = 1
                    }
                  }
                }
              }
            }
          }
        }
      } else {
        // === NHÁNH BONG BÓNG THOẠI TIÊU CHUẨN (`!laChuNoiTrenNen`) ===
        let demNetTrongHop = 0
        let demChuCoLap = 0
        for (let py = ey0; py < ey1; py += 1) {
          const base = py * rw
          for (let px = ex0; px < ex1; px += 1) {
            const pos = base + px
            if (laNenMask[pos] || vungBienBaoVe[pos]) continue
            const trongHopChinh = px >= cx0 && px < cx1 && py >= cy0 && py < cy1
            if (trongHopChinh) demNetTrongHop += 1
            if (laBongKhepKin ? (ngoaiBongBong[pos] === 0) : (ketNoiBienHop[pos] === 0)) {
              laChuGoc[pos] = 1
              if (trongHopChinh) demChuCoLap += 1
            }
          }
        }

        // [Bảo vệ nét vẽ nhân vật nâng cao — chỉ chạy khi không phải chữ nổi có halo]:
        if (!laBongKhepKin && (v._cheDoPro || laNenPhucTap || dienTichHopGoc > 10000)) {
          const daKiemCoLap = new Uint8Array(N)
          const nguongMangDacToiDa = v._cheDoPro
            ? Math.max(260, Math.round(dienTichHopGoc * 0.16))
            : Math.max(380, Math.round(dienTichHopGoc * 0.24))
          const maxRongCoLap = Math.max(42, Math.round(wGoc * (v._cheDoPro ? 0.48 : 0.58)))
          const maxCaoCoLap = Math.max(42, Math.round(hGoc * (v._cheDoPro ? 0.48 : 0.58)))
          for (let py = ey0; py < ey1; py += 1) {
            const base = py * rw
            for (let px = ex0; px < ex1; px += 1) {
              const sPos = base + px
              if (!laChuGoc[sPos] || daKiemCoLap[sPos]) continue
              dau = 0
              cuoi = 0
              daKiemCoLap[sPos] = 1
              hangDoi[cuoi++] = sPos
              let minX = px, maxX = px, minY = py, maxY = py
              while (dau < cuoi) {
                const p = hangDoi[dau++]
                const x = p % rw
                const y = (p - x) / rw
                if (x < minX) minX = x
                if (x > maxX) maxX = x
                if (y < minY) minY = y
                if (y > maxY) maxY = y
                for (let dy = -1; dy <= 1; dy += 1) {
                  const ny = y + dy
                  if (ny < ey0 || ny >= ey1) continue
                  const nBase = ny * rw
                  for (let dx = -1; dx <= 1; dx += 1) {
                    if (dx === 0 && dy === 0) continue
                    const nx = x + dx
                    if (nx < ex0 || nx >= ex1) continue
                    const np = nBase + nx
                    if (!laChuGoc[np] || daKiemCoLap[np]) continue
                    daKiemCoLap[np] = 1
                    hangDoi[cuoi++] = np
                  }
                }
              }
              const cW = maxX - minX + 1
              const cH = maxY - minY + 1
              if (cuoi > nguongMangDacToiDa || (cW > maxRongCoLap && cH > maxCaoCoLap)) {
                for (let k = 0; k < cuoi; k += 1) {
                  const p = hangDoi[k]
                  laChuGoc[p] = 0
                  const x = p % rw
                  const y = (p - x) / rw
                  if (x >= cx0 && x < cx1 && y >= cy0 && y < cy1 && demChuCoLap > 0) demChuCoLap -= 1
                }
              }
            }
          }
        }

        // Phân tích thành phần liên thông 2D (CCA) cho các cụm nét mực bị chạm mép `ex0..ey1` (`ketNoiBienHop === 1`):
        const daDuyetCca = new Uint8Array(N)
        const ccaPadCore = Math.max(8, Math.round(Math.min(wGoc, hGoc) * 0.14))
        const maxCompW = Math.max(48, Math.round(wGoc * 0.76))
        const maxCompH = Math.max(48, Math.round(hGoc * 0.76))
        const maxCompArea = Math.max(220, Math.round(dienTichHopGoc * 0.42))

        for (let py = ey0; py < ey1; py += 1) {
          const base = py * rw
          for (let px = ex0; px < ex1; px += 1) {
            const startPos = base + px
            if (laNenMask[startPos] || laChuGoc[startPos] || daDuyetCca[startPos] || vungBienBaoVe[startPos] || (laBongKhepKin && ngoaiBongBong[startPos] === 1)) continue
            dau = 0
            cuoi = 0
            daDuyetCca[startPos] = 1
            hangDoi[cuoi++] = startPos
            let cMinX = px, cMaxX = px, cMinY = py, cMaxY = py
            let chamBienRoi = false
            let ganHopChinh = false

            while (dau < cuoi) {
              const p = hangDoi[dau++]
              const x = p % rw
              const y = (p - x) / rw
              if (x < cMinX) cMinX = x
              if (x > cMaxX) cMaxX = x
              if (y < cMinY) cMinY = y
              if (y > cMaxY) cMaxY = y
              if (x <= 1 || x >= rw - 2 || y <= 1 || y >= rh - 2) {
                chamBienRoi = true
              }
              if (
                x >= cx0 - ccaPadCore && x < cx1 + ccaPadCore &&
                y >= cy0 - ccaPadCore && y < cy1 + ccaPadCore
              ) {
                ganHopChinh = true
              }
              for (let dy = -1; dy <= 1; dy += 1) {
                const ny = y + dy
                if (ny < 0 || ny >= rh) continue
                const nBase = ny * rw
                for (let dx = -1; dx <= 1; dx += 1) {
                  if (dx === 0 && dy === 0) continue
                  const nx = x + dx
                  if (nx < 0 || nx >= rw) continue
                  const np = nBase + nx
                  if (daDuyetCca[np] || laNenMask[np] || vungBienBaoVe[np]) continue
                  daDuyetCca[np] = 1
                  hangDoi[cuoi++] = np
                }
              }
            }

            const compW = cMaxX - cMinX + 1
            const compH = cMaxY - cMinY + 1
            if (
              !chamBienRoi &&
              ganHopChinh &&
              cuoi <= maxCompArea &&
              compW <= maxCompW &&
              compH <= maxCompH &&
              !(compW >= wGoc * 0.65 && compH >= hGoc * 0.65)
            ) {
              for (let k = 0; k < cuoi; k += 1) {
                const p = hangDoi[k]
                laChuGoc[p] = 1
                const x = p % rw
                const y = (p - x) / rw
                if (x >= cx0 && x < cx1 && y >= cy0 && y < cy1) demChuCoLap += 1
              }
            }
          }
        }

        if (laBongKhepKin) {
          for (let idx = 0; idx < N; idx += 1) {
            if (!laNenMask[idx] && !vungBienBaoVe[idx] && ngoaiBongBong[idx] === 0) {
              laChuGoc[idx] = 1
            }
          }
        }

        const tyLeChuCoLap = demChuCoLap / Math.max(1, demNetTrongHop)
        const baoVeNetTranhPro = !laBongKhepKin && laNenPhucTap && v._cheDoPro
        const banKinhLoiChoPhep = baoVeNetTranhPro ? 0.76 : (tyLeChuCoLap < 0.72 ? 1.08 : 0.86)
        const doDayNetToiDa = baoVeNetTranhPro ? 5 : (tyLeChuCoLap < 0.72 ? 11 : 8)
        const rxRescue0 = Math.max(ex0 + 1, cx0 - Math.round(padCheX * 0.45))
        const ryRescue0 = Math.max(ey0 + 1, cy0 - Math.round(padCheY * 0.45))
        const rxRescue1 = Math.min(ex1 - 1, cx1 + Math.round(padCheX * 0.45))
        const ryRescue1 = Math.min(ey1 - 1, cy1 + Math.round(padCheY * 0.45))

        for (let py = ryRescue0; py < ryRescue1; py += 1) {
          const ny = Math.abs((py - tamGocY) / Math.max(3, banCaoGoc + padCheY * 0.35))
          const base = py * rw
          for (let px = rxRescue0; px < rxRescue1; px += 1) {
            const pos = base + px
            if (laChuGoc[pos] || laNenMask[pos] || vungBienBaoVe[pos]) continue
            const nx = Math.abs((px - tamGocX) / Math.max(3, banRongGoc + padCheX * 0.35))
            if (Math.pow(nx, 2.4) + Math.pow(ny, 2.4) > banKinhLoiChoPhep) continue
            let tTrai = false, tPhai = false
            let tTren = false, tDuoi = false
            let giapNenNgoai = false
            for (let d = 1; d <= doDayNetToiDa; d += 1) {
              if (px - d >= ex0 && laNenMask[pos - d]) {
                if (laBongKhepKin && !longTrang[pos - d]) giapNenNgoai = true
                else tTrai = true
              }
              if (px + d < ex1 && laNenMask[pos + d]) {
                if (laBongKhepKin && !longTrang[pos + d]) giapNenNgoai = true
                else tPhai = true
              }
              if (py - d >= ey0 && laNenMask[pos - d * rw]) {
                if (laBongKhepKin && !longTrang[pos - d * rw]) giapNenNgoai = true
                else tTren = true
              }
              if (py + d < ey1 && laNenMask[pos + d * rw]) {
                if (laBongKhepKin && !longTrang[pos + d * rw]) giapNenNgoai = true
                else tDuoi = true
              }
            }
            if (giapNenNgoai) continue
            if ((tTrai && tPhai) || (tTren && tDuoi)) {
              laChuGoc[pos] = 1
            }
          }
        }

        if (laBongKhepKin) {
          zx0 = 0; zy0 = 0; zx1 = rw; zy1 = rh
        }
        for (let py = zy0; py < zy1; py += 1) {
          const base = py * rw
          for (let px = zx0; px < zx1; px += 1) {
            const pos = base + px
            if (!laChuGoc[pos]) continue
            vungXoaChu[pos] = 1
            for (let dy = -4; dy <= 4; dy += 1) {
              const ny = py + dy
              if (ny < zy0 || ny >= zy1) continue
              const nBase = ny * rw
              for (let dx = -4; dx <= 4; dx += 1) {
                if (dx * dx + dy * dy > 18) continue
                const nx = px + dx
                if (nx < zx0 || nx >= zx1) continue
                const npos = nBase + nx
                if (vungBienBaoVe[npos]) continue
                if (laBongKhepKin && ngoaiBongBong[npos] === 1 && !laChuGoc[npos]) continue
                if (!laNenMask[npos] && ketNoiBienHop[npos] === 1 && !laChuGoc[npos]) continue
                vungXoaChu[npos] = 1
              }
            }
          }
        }

        // Lấp đầy các lỗ trắng nhỏ nằm lọt thỏm bên trong bụng chữ cái ('O', 'P', 'A', 'B', 'D', '0', '8')
        const ngoaiVungXoa = new Uint8Array(N)
        dau = 0
        cuoi = 0
        const dayNgoaiXoa = (pos) => {
          if (ngoaiVungXoa[pos] || vungXoaChu[pos]) return
          ngoaiVungXoa[pos] = 1
          hangDoi[cuoi++] = pos
        }
        for (let px = zx0; px < zx1; px += 1) {
          dayNgoaiXoa(zy0 * rw + px)
          dayNgoaiXoa((zy1 - 1) * rw + px)
        }
        for (let py = zy0; py < zy1; py += 1) {
          dayNgoaiXoa(py * rw + zx0)
          dayNgoaiXoa(py * rw + (zx1 - 1))
        }
        while (dau < cuoi) {
          const pos = hangDoi[dau++]
          const px = pos % rw
          const py = (pos - px) / rw
          if (px > zx0) dayNgoaiXoa(pos - 1)
          if (px + 1 < zx1) dayNgoaiXoa(pos + 1)
          if (py > zy0) dayNgoaiXoa(pos - rw)
          if (py + 1 < zy1) dayNgoaiXoa(pos + rw)
        }
        for (let py = zy0; py < zy1; py += 1) {
          const base = py * rw
          for (let px = zx0; px < zx1; px += 1) {
            const pos = base + px
            if (!ngoaiVungXoa[pos] && laNenMask[pos] && !vungBienBaoVe[pos]) {
              vungXoaChu[pos] = 1
            }
          }
        }
      }

      // Tìm hộp bao `[minX, minY, maxX, maxY]` của vùng xoá chữ `vungXoaChu`
      let minX = cx0
      let minY = cy0
      let maxX = cx1
      let maxY = cy1
      let coDiemXoa = false
      for (let py = zy0; py < zy1; py += 1) {
        const base = py * rw
        for (let px = zx0; px < zx1; px += 1) {
          if (vungXoaChu[base + px]) {
            if (!coDiemXoa) {
              minX = px; maxX = px + 1; minY = py; maxY = py + 1
              coDiemXoa = true
            } else {
              if (px < minX) minX = px
              if (px + 1 > maxX) maxX = px + 1
              if (py < minY) minY = py
              if (py + 1 > maxY) maxY = py + 1
            }
          }
        }
      }

      // Tính trọng tâm `(tamX, tamY)` của lòng bong bóng để căn khung xếp chữ
      let tongX = 0
      let tongY = 0
      let demTrong = 0
      if (laBongKhepKin) {
        for (let py = 0; py < rh; py += 1) {
          const base = py * rw
          for (let px = 0; px < rw; px += 1) {
            if (ngoaiBongBong[base + px] === 0) {
              tongX += px
              tongY += py
              demTrong += 1
            }
          }
        }
      }

      // Chỉ nối khe hở giữa các chữ cái khi là bong bóng thoại thường (`!laChuNoiTrenNen`)
      if (!laChuNoiTrenNen) {
        for (let py = zy0; py < zy1; py += 1) {
          const base = py * rw
          let prevX = -1
          for (let px = zx0; px < zx1; px += 1) {
            if (vungXoaChu[base + px]) {
              if (prevX >= 0 && px - prevX > 1 && px - prevX <= 14) {
                let deuLaNenBong = true
                for (let kx = prevX + 1; kx < px; kx += 1) {
                  const kpos = base + kx
                  if (!laNenMask[kpos] || vungBienBaoVe[kpos] || !(longTrang[kpos] || (laBongKhepKin && ngoaiBongBong[kpos] === 0))) {
                    deuLaNenBong = false
                    break
                  }
                }
                if (deuLaNenBong) {
                  for (let kx = prevX + 1; kx < px; kx += 1) vungXoaChu[base + kx] = 1
                }
              }
              prevX = px
            }
          }
        }
        for (let px = zx0; px < zx1; px += 1) {
          let prevY = -1
          for (let py = zy0; py < zy1; py += 1) {
            if (vungXoaChu[py * rw + px]) {
              if (prevY >= 0 && py - prevY > 1 && py - prevY <= 10) {
                let deuLaNenBong = true
                for (let ky = prevY + 1; ky < py; ky += 1) {
                  const kpos = ky * rw + px
                  if (!laNenMask[kpos] || vungBienBaoVe[kpos] || !(longTrang[kpos] || (laBongKhepKin && ngoaiBongBong[kpos] === 0))) {
                    deuLaNenBong = false
                    break
                  }
                }
                if (deuLaNenBong) {
                  for (let ky = prevY + 1; ky < py; ky += 1) vungXoaChu[ky * rw + px] = 1
                }
              }
              prevY = py
            }
          }
        }
      }

      // Dựng ảnh xoá chữ `_anhCheDataUrl`:
      const cwChe = Math.max(4, maxX - minX)
      const chChe = Math.max(4, maxY - minY)
      const cOut = document.createElement('canvas')
      cOut.width = cwChe
      cOut.height = chChe
      const ctxOut = cOut.getContext('2d')
      const outImg = ctxOut.createImageData(cwChe, chChe)
      const outData = outImg.data

      if (laChuNoiTrenNen) {
        // Tái tạo nền Đa Hướng Phân Cụm Cục Bộ (Mode-Consistent 4-Directional Ray Reconstruction + Halftone Phase Cloning):
        // - Tự động thích ứng từng điểm ảnh trên hộp hỗn hợp (nửa Tường trắng kẻ sọc + nửa Tóc đen hoặc Screentone + Tóc đen).
        // - Không bao giờ lấy mẫu đường kẻ tường 1-4px làm nhòe nền trắng, và không bao giờ lấy mẫu viền halo trắng mảnh (`laDaiTrangManh`).
        const laNenToiChuNoi = !laNenMauThuc && lumNenTrungVi < 82
        const laMangToiDac = new Uint8Array(N)
        const daDuyetMangToi = new Uint8Array(N)
        for (let py = 0; py < rh; py += 1) {
          const base = py * rw
          for (let px = 0; px < rw; px += 1) {
            const sPos = base + px
            if (vungXoaChu[sPos] || daDuyetMangToi[sPos] || lumPx[sPos] > 102) continue
            dau = 0
            cuoi = 0
            daDuyetMangToi[sPos] = 1
            hangDoi[cuoi++] = sPos
            let chamBienToi = false
            while (dau < cuoi) {
              const pT = hangDoi[dau++]
              const xt = pT % rw
              const yt = (pT - xt) / rw
              if (xt <= 2 || xt >= rw - 3 || yt <= 2 || yt >= rh - 3 || ketNoiBienHop[pT]) chamBienToi = true
              for (let dyT = -1; dyT <= 1; dyT += 1) {
                const nyt = yt + dyT
                if (nyt < 0 || nyt >= rh) continue
                const nbt = nyt * rw
                for (let dxT = -1; dxT <= 1; dxT += 1) {
                  if (dxT === 0 && dyT === 0) continue
                  const nxt = xt + dxT
                  if (nxt < 0 || nxt >= rw) continue
                  const npt = nbt + nxt
                  if (!vungXoaChu[npt] && !daDuyetMangToi[npt] && lumPx[npt] <= 102) {
                    daDuyetMangToi[npt] = 1
                    hangDoi[cuoi++] = npt
                  }
                }
              }
            }
            if (cuoi >= 650 || (chamBienToi && cuoi >= 180)) {
              for (let k = 0; k < cuoi; k += 1) {
                const pos = hangDoi[k]
                if (lumPx[pos] <= 90 && !vungXoaChu[pos]) {
                  const xt = pos % rw
                  const yt = (pos - xt) / rw
                  let dlT = 0, drT = 0, duT = 0, ddT = 0
                  let dlR = 0, drR = 0, duR = 0, ddR = 0
                  while (dlR < 5 && xt - dlR - 1 >= 0 && lumPx[pos - dlR - 1] <= 95 && !vungXoaChu[pos - dlR - 1]) dlR += 1
                  while (drR < 5 && xt + drR + 1 < rw && lumPx[pos + drR + 1] <= 95 && !vungXoaChu[pos + drR + 1]) drR += 1
                  while (duR < 5 && yt - duR - 1 >= 0 && lumPx[pos - (duR + 1) * rw] <= 95 && !vungXoaChu[pos - (duR + 1) * rw]) duR += 1
                  while (ddR < 5 && yt + ddR + 1 < rh && lumPx[pos + (ddR + 1) * rw] <= 95 && !vungXoaChu[pos + (ddR + 1) * rw]) ddR += 1
                  while (dlT < 6 && xt - dlT - 1 >= 0 && (lumPx[pos - dlT - 1] <= 95 || vungXoaChu[pos - dlT - 1])) dlT += 1
                  while (drT < 6 && xt + drT + 1 < rw && (lumPx[pos + drT + 1] <= 95 || vungXoaChu[pos + drT + 1])) drT += 1
                  while (duT < 6 && yt - duT - 1 >= 0 && (lumPx[pos - (duT + 1) * rw] <= 95 || vungXoaChu[pos - (duT + 1) * rw])) duT += 1
                  while (ddT < 6 && yt + ddT + 1 < rh && (lumPx[pos + (ddT + 1) * rw] <= 95 || vungXoaChu[pos + (ddT + 1) * rw])) ddT += 1
                  const wR = dlR + drR + 1
                  const hR = duR + ddR + 1
                  if ((dlT + drT + 1) >= 5 && (duT + ddT + 1) >= 5 && Math.min(wR, hR) >= 3 && Math.max(wR, hR) >= 5) laMangToiDac[pos] = 1
                }
              }
            }
          }
        }
        for (let idx = 0; idx < N; idx += 1) {
          if (laMangToiDacPre[idx] && !vungXoaChu[idx]) laMangToiDac[idx] = 1
        }
        // Hấp thụ nốt mọi mảnh viền halo trắng (`lum >= 180`) còn sót nằm kẹp cô lập
        // giữa `vungXoaChu` và mảng tóc đen `laMangToiDac` (không chạm biên ROI, diện tích <= 95px):
        const daDuyetRem = new Uint8Array(N)
        for (let py = 2; py < rh - 2; py += 1) {
          const base = py * rw
          for (let px = 2; px < rw - 2; px += 1) {
            const sPos = base + px
            if (vungXoaChu[sPos] || laMangToiDac[sPos] || daDuyetRem[sPos] || vungBienBaoVe[sPos] || lumPx[sPos] < 180) continue
            dau = 0
            cuoi = 0
            daDuyetRem[sPos] = 1
            hangDoi[cuoi++] = sPos
            let chamBienRem = false
            let chamXoaRem = false
            let chamToiRem = false
            while (dau < cuoi) {
              const pR = hangDoi[dau++]
              const xr = pR % rw
              const yr = (pR - xr) / rw
              if (xr <= zx0 + 1 || xr >= zx1 - 2 || yr <= zy0 + 1 || yr >= zy1 - 2) chamBienRem = true
              for (let dyR = -1; dyR <= 1; dyR += 1) {
                const nyr = yr + dyR
                if (nyr <= 0 || nyr >= rh - 1) continue
                const nbr = nyr * rw
                for (let dxR = -1; dxR <= 1; dxR += 1) {
                  if (dxR === 0 && dyR === 0) continue
                  const nxr = xr + dxR
                  if (nxr <= 0 || nxr >= rw - 1) continue
                  const npr = nbr + nxr
                  if (vungXoaChu[npr]) chamXoaRem = true
                  if (laMangToiDac[npr]) chamToiRem = true
                  if (!vungXoaChu[npr] && !laMangToiDac[npr] && !daDuyetRem[npr] && !vungBienBaoVe[npr] && lumPx[npr] >= 180) {
                    daDuyetRem[npr] = 1
                    hangDoi[cuoi++] = npr
                  }
                }
              }
            }
            if (!chamBienRem && chamXoaRem && chamToiRem && cuoi <= 95) {
              for (let k = 0; k < cuoi; k += 1) {
                const pR = hangDoi[k]
                vungXoaChu[pR] = 1
                const xr = pR % rw
                const yr = (pR - xr) / rw
                if (xr < minX) minX = xr
                if (xr + 1 > maxX) maxX = xr + 1
                if (yr < minY) minY = yr
                if (yr + 1 > maxY) maxY = yr + 1
              }
            }
          }
        }
        const laTuongTrangSach = !laNenMauThuc && tyLeTrangDacTrongHop >= 0.38 && lumNenTrungVi >= 212 && doNhieuHat < 18
        const laDiemNenSach = (pos, dxR = 0, dyR = 0) => {
          if (pos < 0 || pos >= N || vungXoaChu[pos]) return false
          const pxS = pos % rw
          const pyS = (pos - pxS) / rw
          if (!laDaoChieuHalo && lumPx[pos] >= 185) {
            if (
              (pxS > 0 && vungXoaChu[pos - 1]) ||
              (pxS + 1 < rw && vungXoaChu[pos + 1]) ||
              (pyS > 0 && vungXoaChu[pos - rw]) ||
              (pyS + 1 < rh && vungXoaChu[pos + rw])
            ) {
              return false
            }
          }
          if (!laDaoChieuHalo && laDaiTrangManh[pos]) {
            if (laTuongTrangSach || kcLoi[pos] > 0) return false
            if (
              (pxS > 1 && vungXoaChu[pos - 2]) ||
              (pxS + 2 < rw && vungXoaChu[pos + 2]) ||
              (pyS > 1 && vungXoaChu[pos - 2 * rw]) ||
              (pyS + 2 < rh && vungXoaChu[pos + 2 * rw]) ||
              (pxS > 0 && pyS > 0 && vungXoaChu[pos - rw - 1]) ||
              (pxS + 1 < rw && pyS > 0 && vungXoaChu[pos - rw + 1]) ||
              (pxS > 0 && pyS + 1 < rh && vungXoaChu[pos + rw - 1]) ||
              (pxS + 1 < rw && pyS + 1 < rh && vungXoaChu[pos + rw + 1])
            ) {
              return false
            }
          }
          if (!laDaoChieuHalo && laNenMauThuc && laSangDac[pos] && lumNenTrungVi < 218) return false
          if (lumPx[pos] <= 90 && !laNenMauThuc) {
            if (laMangToiDac[pos]) {
              if (dxR !== 0 || dyR !== 0) {
                const nxM = pxS + dxR
                const nyM = pyS + dyR
                if (nxM >= 0 && nxM < rw && nyM >= 0 && nyM < rh && !laMangToiDac[nyM * rw + nxM]) return false
              }
              return true
            }
            if (dyR !== 0 && dxR === 0 && tyLeTrangDacTrongHop < 0.42 && lumNenP30 < 205) {
              let dlV = 0, drV = 0, duV = 0, ddV = 0
              while (dlV < 6 && pxS - dlV - 1 >= 0 && lumPx[pos - dlV - 1] <= 105) dlV += 1
              while (drV < 6 && pxS + drV + 1 < rw && lumPx[pos + drV + 1] <= 105) drV += 1
              if (dlV + drV + 1 <= 5) {
                while (duV < 12 && pyS - duV - 1 >= 0 && !vungXoaChu[pos - (duV + 1) * rw] && lumPx[pos - (duV + 1) * rw] <= 105) duV += 1
                while (ddV < 12 && pyS + ddV + 1 < rh && !vungXoaChu[pos + (ddV + 1) * rw] && lumPx[pos + (ddV + 1) * rw] <= 105) ddV += 1
                if (duV + ddV + 1 >= 9) return true
              }
            }
            return false
          }
          if (!laNenMauThuc && lumPx[pos] < 228) {
            if (
              (pxS > 0 && laMangToiDac[pos - 1]) ||
              (pxS + 1 < rw && laMangToiDac[pos + 1]) ||
              (pyS > 0 && laMangToiDac[pos - rw]) ||
              (pyS + 1 < rh && laMangToiDac[pos + rw])
            ) {
              return false
            }
          }
          if (laTuongTrangSach && lumPx[pos] < 236) {
            if (
              (pxS > 0 && laToiNet[pos - 1] && !laMangToiDac[pos - 1]) ||
              (pxS + 1 < rw && laToiNet[pos + 1] && !laMangToiDac[pos + 1]) ||
              (pyS > 0 && laToiNet[pos - rw] && !laMangToiDac[pos - rw]) ||
              (pyS + 1 < rh && laToiNet[pos + rw] && !laMangToiDac[pos + rw])
            ) {
              return false
            }
          }
          if (laDaoChieuHalo && laToiNet[pos] && lumPx[pos] <= 95 && lumNenTrungVi > 110) return false
          return true
        }
        const HUONG = [[-1, 0], [1, 0], [0, -1], [0, 1], [-1, -1], [1, -1], [-1, 1], [1, 1]]
        const maxTiaStep = Math.max(96, Math.min(140, Math.max(rw, rh)))
        const nChe = cwChe * chChe
        const rBuf = new Int16Array(nChe)
        const gBuf = new Int16Array(nChe)
        const bBuf = new Int16Array(nChe)
        const rSangFb = new Int16Array(nChe).fill(-1)
        const gSangFb = new Int16Array(nChe).fill(-1)
        const bSangFb = new Int16Array(nChe).fill(-1)
        const cumToiMask = new Uint8Array(nChe)
        for (let py = 0; py < chChe; py += 1) {
          const roiY = minY + py
          const baseY = roiY * rw
          const phaY = roiY & 3
          for (let px = 0; px < cwChe; px += 1) {
            const roiX = minX + px
            const pos = baseY + roiX
            if (!vungXoaChu[pos]) continue

            let wSang = 0, rSang = 0, gSang = 0, bSang = 0
            let wToi = 0, rToi = 0, gToi = 0, bToi = 0
            const tiaToi = [false, false, false, false, false, false, false, false]
            let mauPhaR = -1, mauPhaG = -1, mauPhaB = -1, kcPhaTot = 999
            const phaX = roiX & 3

            for (let hIdx = 0; hIdx < 8; hIdx += 1) {
              const dx = HUONG[hIdx][0]
              const dy = HUONG[hIdx][1]
              const heSoCheo = (dx !== 0 && dy !== 0) ? 1.4142 : 1.0
              let daQuaVungTrang = false
              for (let d = 2; d < maxTiaStep; d += 1) {
                const nx = roiX + dx * d
                const ny = roiY + dy * d
                if (nx < zx0 - 2 || nx >= zx1 + 2 || ny < zy0 - 2 || ny >= zy1 + 2) break
                const npos = ny * rw + nx
                if (!vungXoaChu[npos] && lumPx[npos] >= 210 && (laTuongTrangSach || !laDaiTrangManh[npos])) daQuaVungTrang = true
                if (daQuaVungTrang && lumPx[npos] <= 90 && !laNenMauThuc) break
                if (!laDiemNenSach(npos, dx, dy)) continue
                const npos2 = (nx + dx >= 0 && nx + dx < rw && ny + dy >= 0 && ny + dy < rh && laDiemNenSach((ny + dy) * rw + (nx + dx), dx, dy))
                  ? ((ny + dy) * rw + (nx + dx))
                  : npos
                const i1 = npos * 4
                const i2 = npos2 * 4
                const kcThuc = d * heSoCheo
                const w = 1 / Math.pow(kcThuc + 1.0, 1.65)
                let rm, gm, bm, lm
                if (!laNenMauThuc && !laTuongTrangSach && !laMangToiDac[npos] && doNhieuHat >= 11.5) {
                  rm = gm = bm = (lum3x3[npos] + lum3x3[npos2]) * 0.5
                  lm = rm
                } else {
                  rm = (data[i1] + data[i2]) * 0.5
                  gm = (data[i1 + 1] + data[i2 + 1]) * 0.5
                  bm = (data[i1 + 2] + data[i2 + 2]) * 0.5
                  lm = 0.299 * rm + 0.587 * gm + 0.114 * bm
                }
                if (lm < 92 && !laNenMauThuc && (laMangToiDac[npos] || laNenToiChuNoi || laTuongTrangSach || lumNenTrungVi < 125)) {
                  wToi += w
                  rToi += rm * w
                  gToi += gm * w
                  bToi += bm * w
                  tiaToi[hIdx] = true
                } else {
                  wSang += w
                  rSang += rm * w
                  gSang += gm * w
                  bSang += bm * w
                  if (hIdx < 4 && !laNenMauThuc && !laTuongTrangSach && lm >= 90 && lm <= 225) {
                    for (let step = d; step <= Math.min(maxTiaStep, d + 7); step += 1) {
                      const sx = roiX + dx * step
                      const sy = roiY + dy * step
                      if (sx < 0 || sx >= rw || sy < 0 || sy >= rh) break
                      const spos = sy * rw + sx
                      if (ketNoiBienHop[spos] || laMangToiDac[spos] || lum3x3[spos] < 95) break
                      if (
                        vungXoaChu[spos] ||
                        !laDiemNenSach(spos) ||
                        lumPx[spos] < 98 ||
                        lum3x3[spos] > 235 ||
                        (sx > 0 && vungXoaChu[spos - 1]) ||
                        (sx + 1 < rw && vungXoaChu[spos + 1]) ||
                        (sy > 0 && vungXoaChu[spos - rw]) ||
                        (sy + 1 < rh && vungXoaChu[spos + rw])
                      ) continue
                      if (((sx & 3) === phaX && (sy & 3) === phaY) && step < kcPhaTot) {
                        kcPhaTot = step
                        const isrc = spos * 4
                        mauPhaR = data[isrc]
                        mauPhaG = data[isrc + 1]
                        mauPhaB = data[isrc + 2]
                        break
                      }
                    }
                  }
                }
                break
              }
            }

            let rOut = Math.round(rNenTrungVi)
            let gOut = Math.round(gNenTrungVi)
            let bOut = Math.round(bNenTrungVi)
            let demTiaToi = 0
            for (let k = 0; k < 8; k += 1) {
              if (tiaToi[k]) demTiaToi += 1
            }
            const kepNgangToi = Boolean(tiaToi[0] && tiaToi[1] && wToi >= wSang * 0.78)
            const kepDocToi = Boolean(tiaToi[2] && tiaToi[3] && wToi >= wSang * 0.78)
            const kepCheoToi = Boolean(((tiaToi[4] && tiaToi[7]) || (tiaToi[5] && tiaToi[6])) && wToi >= wSang * 0.82)
            const namTrongMangToi = Boolean(
              (laNenToiChuNoi && (wToi >= wSang * 0.65 || (demTiaToi >= 4 && wToi >= wSang * 0.55))) ||
              wSang === 0 ||
              (demTiaToi >= 5 && wToi >= wSang * 0.68) ||
              kepNgangToi ||
              kepDocToi ||
              (!laTuongTrangSach && kepCheoToi && demTiaToi >= 3) ||
              (!laTuongTrangSach && demTiaToi >= 3 && wToi >= wSang * 1.15) ||
              (lumNenTrungVi < 115 && wToi >= wSang * 0.80)
            )
            const idxChe = py * cwChe + px
            if (wSang > 0) {
              let rsC = Math.round(rSang / wSang)
              let gsC = Math.round(gSang / wSang)
              let bsC = Math.round(bSang / wSang)
              const lumOutS = 0.299 * rsC + 0.587 * gsC + 0.114 * bsC
              if (!laNenMauThuc && mauPhaR >= 0 && doNhieuHat >= 16 && lumOutS >= 115 && lumOutS <= 212) {
                const heSoPha = doNhieuHat >= 24 ? 0.26 : 0.16
                rsC = Math.round(mauPhaR * heSoPha + rsC * (1 - heSoPha))
                gsC = Math.round(mauPhaG * heSoPha + gsC * (1 - heSoPha))
                bsC = Math.round(mauPhaB * heSoPha + bsC * (1 - heSoPha))
              }
              rSangFb[idxChe] = rsC
              gSangFb[idxChe] = gsC
              bSangFb[idxChe] = bsC
            }
            if (namTrongMangToi && wToi > 0 && (wSang === 0 || wToi >= wSang * 0.55)) {
              rOut = Math.round(rToi / wToi)
              gOut = Math.round(gToi / wToi)
              bOut = Math.round(bToi / wToi)
              cumToiMask[idxChe] = 1
            } else if (wSang > 0) {
              rOut = rSangFb[idxChe]
              gOut = gSangFb[idxChe]
              bOut = bSangFb[idxChe]
            } else if (namTrongMangToi && wToi > 0) {
              rOut = Math.round(rToi / wToi)
              gOut = Math.round(gToi / wToi)
              bOut = Math.round(bToi / wToi)
              cumToiMask[idxChe] = 1
            }
            rBuf[idxChe] = rOut
            gBuf[idxChe] = gOut
            bBuf[idxChe] = bOut
          }
        }

        const nguongNbToi = laTuongTrangSach ? 3 : 4
        for (let passM = 0; passM < 3; passM += 1) {
          const snapToi = new Uint8Array(cumToiMask)
          let coThayDoiToi = false
          for (let py = 0; py < chChe; py += 1) {
            const roiY = minY + py
            for (let px = 0; px < cwChe; px += 1) {
              const idxChe = py * cwChe + px
              if (!snapToi[idxChe] || rSangFb[idxChe] < 0) continue
              const roiX = minX + px
              let demNbToi = 0
              for (let dyM = -1; dyM <= 1; dyM += 1) {
                const nym = roiY + dyM
                if (nym < 0 || nym >= rh) continue
                const nbm = nym * rw
                for (let dxM = -1; dxM <= 1; dxM += 1) {
                  if (dxM === 0 && dyM === 0) continue
                  const nxm = roiX + dxM
                  if (nxm < 0 || nxm >= rw) continue
                  const npm = nbm + nxm
                  if (vungXoaChu[npm]) {
                    const nxChe = px + dxM
                    const nyChe = py + dyM
                    if (nxChe >= 0 && nxChe < cwChe && nyChe >= 0 && nyChe < chChe && snapToi[nyChe * cwChe + nxChe]) {
                      demNbToi += 1
                    }
                  } else if (laMangToiDac[npm]) {
                    demNbToi += 1
                  }
                }
              }
              if (demNbToi <= nguongNbToi) {
                cumToiMask[idxChe] = 0
                rBuf[idxChe] = rSangFb[idxChe]
                gBuf[idxChe] = gSangFb[idxChe]
                bBuf[idxChe] = bSangFb[idxChe]
                coThayDoiToi = true
              }
            }
          }
          if (!coThayDoiToi) break
        }

        // Làm mượt đẳng hướng 2D (3 vòng Laplace/Harmonic Relaxation trong từng cụm Sáng/Tối)
        // để xoá sạch 100% vệt sọc ngang/dọc kiểu bàn cờ (plaid/crossbar artifacts) trên vùng gạch chéo & screentone:
        let rCur = rBuf, gCur = gBuf, bCur = bBuf
        for (let iter = 0; iter < 3; iter += 1) {
          const rNext = new Int16Array(rCur)
          const gNext = new Int16Array(gCur)
          const bNext = new Int16Array(bCur)
          for (let py = 0; py < chChe; py += 1) {
            const roiY = minY + py
            for (let px = 0; px < cwChe; px += 1) {
              const roiX = minX + px
              const pos = roiY * rw + roiX
              if (!vungXoaChu[pos]) continue
              const idxChe = py * cwChe + px
              const cMode = cumToiMask[idxChe]
              let sr = rCur[idxChe] * 2
              let sg = gCur[idxChe] * 2
              let sb = bCur[idxChe] * 2
              let sw = 2
              for (let dyN = -1; dyN <= 1; dyN += 1) {
                const ny = roiY + dyN
                if (ny < 0 || ny >= rh) continue
                for (let dxN = -1; dxN <= 1; dxN += 1) {
                  if (dxN === 0 && dyN === 0) continue
                  const nx = roiX + dxN
                  if (nx < 0 || nx >= rw) continue
                  const npos = ny * rw + nx
                  if (vungXoaChu[npos]) {
                    const npy = ny - minY
                    const npx = nx - minX
                    if (npy >= 0 && npy < chChe && npx >= 0 && npx < cwChe) {
                      const nIdxChe = npy * cwChe + npx
                      if (cumToiMask[nIdxChe] === cMode) {
                        sr += rCur[nIdxChe]
                        sg += gCur[nIdxChe]
                        sb += bCur[nIdxChe]
                        sw += 1
                      }
                    }
                  } else if (laDiemNenSach(npos)) {
                    const isDarkN = (lumPx[npos] < 92 && !laNenMauThuc) ? 1 : 0
                    if (isDarkN === cMode) {
                      const i4 = npos * 4
                      const dungTb = !laNenMauThuc && !laTuongTrangSach && !isDarkN
                      sr += dungTb ? Math.round(lum3x3[npos]) : data[i4]
                      sg += dungTb ? Math.round(lum3x3[npos]) : data[i4 + 1]
                      sb += dungTb ? Math.round(lum3x3[npos]) : data[i4 + 2]
                      sw += 1
                    }
                  }
                }
              }
              rNext[idxChe] = Math.round(sr / sw)
              gNext[idxChe] = Math.round(sg / sw)
              bNext[idxChe] = Math.round(sb / sw)
            }
          }
          rCur = rNext; gCur = gNext; bCur = bNext
        }

        for (let py = 0; py < chChe; py += 1) {
          const roiY = minY + py
          const baseY = roiY * rw
          for (let px = 0; px < cwChe; px += 1) {
            const pos = baseY + minX + px
            if (!vungXoaChu[pos]) continue
            const idxChe = py * cwChe + px
            const pOut = idxChe * 4
            outData[pOut] = rCur[idxChe]
            outData[pOut + 1] = gCur[idxChe]
            outData[pOut + 2] = bCur[idxChe]
            outData[pOut + 3] = 255
          }
        }
      } else {
        const laMauNenHopLeTai = (pos, roiY) => {
          if (pos < 0 || pos >= N || vungXoaChu[pos] || !laNenMask[pos]) return false
          if (!(longTrang[pos] || (laBongKhepKin && ngoaiBongBong[pos] === 0))) return false
          const i = pos * 4
          const saiSoRow = Math.abs(data[i] - bgRowR[roiY]) + Math.abs(data[i + 1] - bgRowG[roiY]) + Math.abs(data[i + 2] - bgRowB[roiY])
          return saiSoRow <= 34
        }

        for (let py = 0; py < chChe; py += 1) {
          const roiY = minY + py
          const baseY = roiY * rw
          const rDong = bgRowR[roiY]
          const gDong = bgRowG[roiY]
          const bDong = bgRowB[roiY]

          let px = 0
          while (px < cwChe) {
            if (!vungXoaChu[baseY + minX + px]) {
              px += 1
              continue
            }
            const segStart = px
            while (px < cwChe && vungXoaChu[baseY + minX + px]) {
              px += 1
            }
            const segEnd = px - 1

            let rTrai = rDong, gTrai = gDong, bTrai = bDong
            let rPhai = rDong, gPhai = gDong, bPhai = bDong
            for (let d = 1; d <= 6; d += 1) {
              const xL = minX + segStart - d
              if (xL < 0) break
              const posL = baseY + xL
              if (laMauNenHopLeTai(posL, roiY)) {
                const iL = posL * 4
                rTrai = Math.round(data[iL] * 0.6 + rDong * 0.4)
                gTrai = Math.round(data[iL + 1] * 0.6 + gDong * 0.4)
                bTrai = Math.round(data[iL + 2] * 0.6 + bDong * 0.4)
                break
              }
            }
            for (let d = 1; d <= 6; d += 1) {
              const xR = minX + segEnd + d
              if (xR >= rw) break
              const posR = baseY + xR
              if (laMauNenHopLeTai(posR, roiY)) {
                const iR = posR * 4
                rPhai = Math.round(data[iR] * 0.6 + rDong * 0.4)
                gPhai = Math.round(data[iR + 1] * 0.6 + gDong * 0.4)
                bPhai = Math.round(data[iR + 2] * 0.6 + bDong * 0.4)
                break
              }
            }

            const segLen = Math.max(1, segEnd - segStart)
            for (let sx = segStart; sx <= segEnd; sx += 1) {
              const t = segLen > 0 ? ((sx - segStart) / segLen) : 0.5
              const pOut = (py * cwChe + sx) * 4
              outData[pOut] = Math.round(rTrai * (1 - t) + rPhai * t)
              outData[pOut + 1] = Math.round(gTrai * (1 - t) + gPhai * t)
              outData[pOut + 2] = Math.round(bTrai * (1 - t) + bPhai * t)
              outData[pOut + 3] = 255
            }
          }
        }
      }
      ctxOut.putImageData(outImg, 0, 0)
      v._anhCheDataUrl = cOut.toDataURL('image/png')
      v._khungCheCanvas = {
        x: rx0 + minX,
        y: ry0 + minY,
        w: cwChe,
        h: chChe,
      }

      // Bước 3: Tìm khung xếp chữ nội tiếp (`_khungCanvas`)
      // Với bong bóng khép kín (`laBongKhepKin`): nở khung trong lòng bong bóng đã lấp lỗ chữ (`ngoaiBongBong === 0`).
      // Với bong bóng gai nhọn / hở viền / nền phức tạp (`!laBongKhepKin`): giữ khung bám sát quanh `cx0..cy1`
      // và chỉ nới nhẹ trong phạm vi `longTrang === 1 || vungXoaChu === 1`.
      const laTrongBong = (px, py) => {
        const pos = py * rw + px
        return laBongKhepKin ? (ngoaiBongBong[pos] === 0) : Boolean(longTrang[pos] || vungXoaChu[pos])
      }

      const daiTrongBong = (x0, y0, x1, y1, tyLeCan = 0.92, catGoc = 0.12) => {
        let ax0 = Math.max(0, x0)
        let ay0 = Math.max(0, y0)
        let ax1 = Math.min(rw, x1)
        let ay1 = Math.min(rh, y1)
        if (catGoc > 0 && ax1 - ax0 > 16) {
          const catX = Math.floor((ax1 - ax0) * catGoc)
          ax0 += catX
          ax1 -= catX
        }
        if (catGoc > 0 && ay1 - ay0 > 16) {
          const catY = Math.floor((ay1 - ay0) * catGoc)
          ay0 += catY
          ay1 -= catY
        }
        if (ax1 <= ax0 || ay1 <= ay0) return false
        let trong = 0
        let tong = 0
        for (let py = ay0; py < ay1; py += 1) {
          for (let px = ax0; px < ax1; px += 1) {
            tong += 1
            if (laTrongBong(px, py)) trong += 1
          }
        }
        return tong > 0 && (trong / tong) >= tyLeCan
      }

      const vanhElipTrongBong = (x0, y0, x1, y1) => {
        const cx = (x0 + x1) * 0.5
        const cy = (y0 + y1) * 0.5
        const rx = (x1 - x0) * 0.5
        const ry = (y1 - y0) * 0.5
        if (rx < 4 || ry < 4) return false
        let trong = 0
        let tong = 0
        const SO_DIEM = 28
        for (let k = 0; k < SO_DIEM; k += 1) {
          const goc = (k / SO_DIEM) * Math.PI * 2
          const cos = Math.cos(goc)
          const sin = Math.sin(goc)
          for (const banKinh of [0.78, 0.90]) {
            const px = Math.max(0, Math.min(rw - 1, Math.round(cx + rx * banKinh * cos)))
            const py = Math.max(0, Math.min(rh - 1, Math.round(cy + ry * banKinh * sin)))
            tong += 1
            if (laTrongBong(px, py)) trong += 1
          }
        }
        return tong > 0 && (trong / tong) >= 0.88
      }

      let bx0 = cx0
      let by0 = cy0
      let bx1 = cx1
      let by1 = cy1

      if (laBongKhepKin) {
        const tamX = demTrong > 0 ? Math.round((tongX / demTrong) * 0.65 + ((cx0 + cx1) * 0.5) * 0.35) : Math.round((cx0 + cx1) * 0.5)
        const tamY = demTrong > 0 ? Math.round((tongY / demTrong) * 0.65 + ((cy0 + cy1) * 0.5) * 0.35) : Math.round((cy0 + cy1) * 0.5)
        const banRongHat = Math.max(8, Math.round(wGoc * 0.42))
        const banCaoHat = Math.max(8, Math.round(hGoc * 0.42))
        const banRongNho = Math.max(6, Math.round(wGoc * 0.28))
        const banCaoNho = Math.max(6, Math.round(hGoc * 0.28))
        const dsHatGiong = [
          [
            Math.max(0, Math.min(cx0, tamX - banRongHat)),
            Math.max(0, Math.min(cy0, tamY - banCaoHat)),
            Math.min(rw, Math.max(cx1, tamX + banRongHat)),
            Math.min(rh, Math.max(cy1, tamY + banCaoHat)),
          ],
          [
            Math.max(0, tamX - banRongHat),
            Math.max(0, tamY - banCaoHat),
            Math.min(rw, tamX + banRongHat),
            Math.min(rh, tamY + banCaoHat),
          ],
          [
            Math.max(0, tamX - banRongNho),
            Math.max(0, tamY - banCaoNho),
            Math.min(rw, tamX + banRongNho),
            Math.min(rh, tamY + banCaoNho),
          ],
        ]

        const buocLon = Math.max(2, Math.round(Math.max(wGoc, hGoc) / 28))
        const CACH_NO = [
          ['trai', 'phai', 'tren', 'duoi'],
          ['trai', 'phai', 'trai', 'phai', 'tren', 'duoi'],
          ['tren', 'duoi', 'trai', 'phai'],
          ['tren', 'duoi', 'tren', 'duoi', 'trai', 'phai'],
        ]

        let tot = dsHatGiong[0]
        let diemTot = -1

        for (const hat of dsHatGiong) {
          for (const thuTu of CACH_NO) {
            let [x0, y0, x1, y1] = hat
            for (const buoc of [buocLon, 1]) {
              let conNhich = true
              while (conNhich) {
                conNhich = false
                for (const phia of thuTu) {
                  if (phia === 'trai') {
                    const moi = Math.max(0, x0 - buoc)
                    if (moi < x0 && daiTrongBong(moi, y0, x0, y1, 0.90, 0.16) && vanhElipTrongBong(moi, y0, x1, y1)) { x0 = moi; conNhich = true }
                  } else if (phia === 'phai') {
                    const moi = Math.min(rw, x1 + buoc)
                    if (moi > x1 && daiTrongBong(x1, y0, moi, y1, 0.90, 0.16) && vanhElipTrongBong(x0, y0, moi, y1)) { x1 = moi; conNhich = true }
                  } else if (phia === 'tren') {
                    const moi = Math.max(0, y0 - buoc)
                    if (moi < y0 && daiTrongBong(x0, moi, x1, y0, 0.90, 0.16) && vanhElipTrongBong(x0, moi, x1, y1)) { y0 = moi; conNhich = true }
                  } else {
                    const moi = Math.min(rh, y1 + buoc)
                    if (moi > y1 && daiTrongBong(x0, y1, x1, moi, 0.90, 0.16) && vanhElipTrongBong(x0, y0, x1, moi)) { y1 = moi; conNhich = true }
                  }
                }
              }
            }
            const wHop = x1 - x0
            const hHop = y1 - y0
            const tyLeCanDoi = Math.min(wHop, hHop) / Math.max(1, Math.max(wHop, hHop))
            const heSoCanDoi = 0.75 + 0.25 * Math.min(1, tyLeCanDoi / 0.55)
            const diem = wHop * 1.24 * hHop * heSoCanDoi
            if (diem > diemTot) {
              diemTot = diem
              tot = [x0, y0, x1, y1]
            }
          }
        }

        ;[bx0, by0, bx1, by1] = tot
        // Lùi nhẹ lề an toàn bên trong lòng bong bóng (~4.5%) để chữ không chạm sát đường viền đen
        const leTrongX = Math.max(3, Math.round((bx1 - bx0) * 0.045))
        const leTrongY = Math.max(3, Math.round((by1 - by0) * 0.045))
        if (bx1 - bx0 > Math.min(wGoc, 24) + leTrongX * 2) {
          bx0 += leTrongX
          bx1 -= leTrongX
        }
        if (by1 - by0 > Math.min(hGoc, 24) + leTrongY * 2) {
          by0 += leTrongY
          by1 -= leTrongY
        }
      } else if (laChuNoiTrenNen) {
        // Với chữ nổi không có bong bóng (trên nền screentone / tóc đen / bóng đổ):
        // Khung đặt chữ bao trọn hợp của hộp chữ gốc `[cx0..cy1]` và toàn bộ mặt nạ chữ + halo thực tế `[minX..maxY]`
        // (nhờ đó bao phủ cả dòng cuối bị thụt như "Tenpai..." hay "...?"), tuyệt đối không nở mù quáng theo `longTrang`.
        bx0 = coDiemXoa ? Math.max(cx0 - 16, Math.min(cx0, minX)) : cx0
        by0 = coDiemXoa ? Math.min(cy0, minY) : cy0
        bx1 = coDiemXoa ? Math.min(cx1 + 16, Math.max(cx1, maxX)) : cx1
        by1 = coDiemXoa ? Math.max(cy1, maxY) : cy1
        const nheX = Math.min(6, Math.max(2, Math.round((bx1 - bx0) * 0.04)))
        bx0 = Math.max(Math.max(0, cx0 - 16), bx0 - nheX)
        bx1 = Math.min(Math.min(rw, cx1 + 16), bx1 + nheX)
      } else {
        // Khi bong bóng có hình gai nhọn hở viền, hình đa giác đặc biệt hoặc bong bóng rất cao chạm 1 cạnh ROI:
        // Nới từng bước sang hai bên/trên/dưới nếu vùng kế cận thực sự là nền bong bóng sạch (`longTrang === 1`)
        const gioiHanLeX = Math.max(24, Math.round(Math.max(wGoc * 0.55, hGoc * 0.45)))
        const gioiHanLeY = Math.max(64, Math.round(Math.max(hGoc * 0.95, wGoc * 0.85)))
        const buocLon = Math.max(2, Math.round(Math.min(wGoc, hGoc) / 18))
        bx0 = coDiemXoa ? Math.min(cx0, minX) : cx0
        bx1 = coDiemXoa ? Math.max(cx1, maxX) : cx1
        by0 = coDiemXoa ? Math.min(cy0, minY) : cy0
        by1 = coDiemXoa ? Math.max(cy1, maxY) : cy1
        for (const buocNhe of [buocLon, 1]) {
          let conNhich = true
          while (conNhich) {
            conNhich = false
            if (bx0 - buocNhe >= Math.max(0, cx0 - gioiHanLeX) && daiTrongBong(bx0 - buocNhe, by0, bx0, by1, 0.90, 0.14)) {
              bx0 -= buocNhe; conNhich = true
            }
            if (bx1 + buocNhe <= Math.min(rw, cx1 + gioiHanLeX) && daiTrongBong(bx1, by0, bx1 + buocNhe, by1, 0.90, 0.14)) {
              bx1 += buocNhe; conNhich = true
            }
            if (by0 - buocNhe >= Math.max(0, cy0 - gioiHanLeY) && daiTrongBong(bx0, by0 - buocNhe, bx1, by0, 0.90, 0.14)) {
              by0 -= buocNhe; conNhich = true
            }
            if (by1 + buocNhe <= Math.min(rh, cy1 + gioiHanLeY) && daiTrongBong(bx0, by1, bx1, by1 + buocNhe, 0.90, 0.14)) {
              by1 += buocNhe; conNhich = true
            }
          }
        }
      }

      const gocW = Math.max(3, Math.round((bx1 - bx0) * 0.14))
      const gocH = Math.max(3, Math.round((by1 - by0) * 0.14))
      const bonGocSach = (
        daiTrongBong(bx0, by0, bx0 + gocW, by0 + gocH, 0.90, 0) &&
        daiTrongBong(bx1 - gocW, by0, bx1, by0 + gocH, 0.90, 0) &&
        daiTrongBong(bx0, by1 - gocH, bx0 + gocW, by1, 0.90, 0) &&
        daiTrongBong(bx1 - gocW, by1 - gocH, bx1, by1, 0.90, 0)
      )
      v._laHopChuNhat = Boolean(bonGocSach)

      v._khungCanvas = {
        x: rx0 + bx0,
        y: ry0 + by0,
        w: Math.max(16, bx1 - bx0),
        h: Math.max(16, by1 - by0),
      }
      return v._khungCanvas
    } catch {
      return null
    }
  }

  /**
   * Trả về ảnh PNG trong suốt đã xoá sạch 100% chữ gốc trong lòng bong bóng (`_anhCheDataUrl`)
   * được tính toán trực tiếp từ mặt nạ 2D `ngoaiBongBong === 0` trong `doKhungBongBongCanvas`.
   */
  function taoAnhCheChuCanvas(el, v, tatCaVung = []) {
    if (v._anhCheDataUrl !== undefined) return v._anhCheDataUrl
    doKhungBongBongCanvas(el, v, tatCaVung)
    return v._anhCheDataUrl || null
  }

  // E91 + E99 + E105 — Thanh công cụ nổi nhanh (Floating Mini-Toolbar) góc dưới trái:
  // ⚡ Dịch trang (Alt+Q) · 📚 Cả chapter (Alt+A) · 🔄 Tự dịch cuộn (Alt+W) · ✂️ Khoanh vùng (Alt+S) · 🔤 Đổi Font · A-/A+ · 👁 Xem gốc (Alt)
  function caiCongTacSoSanhGoc() {
    window[CO].heSoCoChu = window[CO].heSoCoChu || 1
    window[CO].fontChuHienTai = window[CO].fontChuHienTai || 'bangers'

    const datAnLopPhu = (an) => {
      window[CO].dangAnLopPhu = an
      document.querySelectorAll(`.${LOP_CLASS}`).forEach((el) => {
        el.style.opacity = an ? '0' : '1'
      })
      const nut = document.getElementById('translation-cong-tac-goc')
      if (nut) {
        nut.textContent = an ? '👁 Đang xem gốc (Alt)' : '👁 Xem gốc (Alt)'
        nut.style.background = an ? '#b45309' : 'rgba(30,41,59,.9)'
      }
    }

    if (!window[CO].daCaiPhimAlt) {
      window[CO].daCaiPhimAlt = true

      window.addEventListener('keydown', (e) => {
        if (window[CO].dangSuaBong) return
        if (e.key === 'Alt' && !e.repeat && !window[CO].dangAnLopPhu) datAnLopPhu(true)
        if (e.altKey && (e.key === 'q' || e.key === 'Q')) {
          e.preventDefault()
          datAnLopPhu(false)
          if (!window[CO].dangChayBulk) (window[CO].dichTrangHienTai || dichTrangHienTai)()
        }
        if (e.altKey && (e.key === 'a' || e.key === 'A')) {
          e.preventDefault()
          datAnLopPhu(false)
          if (!window[CO].dangChay) {
            window[CO].dangChay = true
            ;(window[CO].dichCaChapter || dichCaChapter)()
          }
        }
        if (e.altKey && (e.key === 'w' || e.key === 'W')) {
          e.preventDefault()
          datAnLopPhu(false)
          window[CO].tuDichKhiCuon = !window[CO].tuDichKhiCuon
          const nutCuon = document.getElementById('translation-nut-tu-dich-cuon')
          if (nutCuon) {
            const bat = Boolean(window[CO].tuDichKhiCuon)
            nutCuon.textContent = bat ? '🔄 Tự dịch khi cuộn: BẬT (Alt+W)' : '🔄 Tự dịch khi cuộn (Alt+W)'
            nutCuon.style.background = bat ? '#059669' : 'rgba(30,41,59,.9)'
            nutCuon.style.borderColor = bat ? '#10b981' : 'rgba(255,255,255,.18)'
          }
          xong(
            window[CO].tuDichKhiCuon
              ? 'Đã BẬT Tự động dịch khi cuộn (Alt+W). Cuộn tới đâu sẽ dịch tới đó.'
              : 'Đã TẮT Tự động dịch khi cuộn (Alt+W).',
            4,
          )
          if (window[CO].tuDichKhiCuon && !window[CO].dangChay) {
            dichTrangHienTai({ tuDongCuon: true })
          }
        }
        if (e.altKey && (e.key === 's' || e.key === 'S')) {
          e.preventDefault()
          datAnLopPhu(false)
          if (!window[CO].dangChay) {
            window[CO].dangChay = true
            khoanhVungDich()
          }
        }
      })
      window.addEventListener('keyup', (e) => {
        if (e.key === 'Alt' && window[CO].dangAnLopPhu) datAnLopPhu(false)
      })
      window.addEventListener('blur', () => {
        if (window[CO].dangAnLopPhu) datAnLopPhu(false)
      })

      // Tự động dịch khi cuộn tới trang mới (chỉ chạy khi người dùng bật công tắc `tuDichKhiCuon`)
      const henCuon = { id: null }
      window.addEventListener('scroll', () => {
        if (!window[CO].tuDichKhiCuon) return
        if (henCuon.id) clearTimeout(henCuon.id)
        henCuon.id = setTimeout(async () => {
          if (!window[CO].tuDichKhiCuon || window[CO].dangChay) return
          const chon = chonTrangTruyen(layMoTa(), { caoKhungNhin: window.innerHeight })
          if (!chon.anh) return
          const { cheDo, ngonNgu, ngonNguDich, engine } = await layCauHinhHienTai()
          const khoa = khoaCache(chon.anh.src, cheDo, ngonNgu, engine, ngonNguDich)
          if (!window[CO].daDich.has(khoa) && !window[CO].dangXepHang.has(khoa)) {
            dichTrangHienTai({ tuDongCuon: true })
          }
        }, 350)
      }, { passive: true, capture: true })
    }

    if (!document.getElementById('translation-thanh-nhanh')) {
      const thanh = document.createElement('div')
      thanh.id = 'translation-thanh-nhanh'
      thanh.style.cssText = [
        'position:fixed', 'z-index:2147483647', 'left:16px', 'bottom:16px',
        'display:flex', 'flex-wrap:nowrap', 'align-items:center', 'gap:6px',
        'max-width:calc(100vw - 32px)', 'overflow-x:auto', 'scrollbar-width:none',
        'padding:6px 8px', 'border-radius:999px', 'border:1px solid rgba(255,255,255,.22)',
        'background:rgba(15,23,42,.92)', 'color:#fff', 'font:12px/1.3 system-ui,sans-serif',
        'box-shadow:0 4px 16px rgba(0,0,0,.4)', 'backdrop-filter:blur(6px)',
        'transition:opacity .25s ease',
      ].join(';')

      const kieuNut = [
        'padding:5px 10px', 'border-radius:999px', 'border:1px solid rgba(255,255,255,.18)',
        'background:rgba(30,41,59,.9)', 'color:#f8fafc', 'font:12px/1.2 system-ui,sans-serif',
        'cursor:pointer', 'white-space:nowrap',
      ].join(';')

      const nutDich = document.createElement('button')
      nutDich.id = 'translation-nut-dich-nhanh'
      nutDich.type = 'button'
      nutDich.textContent = '⚡ Dịch trang (Alt+Q)'
      nutDich.style.cssText = `${kieuNut};background:#2563eb;border-color:#3b82f6;font-weight:600`
      nutDich.addEventListener('click', () => {
        if (!window[CO].dangChayBulk) (window[CO].dichTrangHienTai || dichTrangHienTai)()
      })

      const nutChapter = document.createElement('button')
      nutChapter.id = 'translation-nut-dich-chapter'
      nutChapter.type = 'button'
      nutChapter.textContent = '📚 Cả chapter (Alt+A)'
      nutChapter.style.cssText = kieuNut
      nutChapter.addEventListener('click', () => {
        if (!window[CO].dangChay) {
          window[CO].dangChay = true
          ;(window[CO].dichCaChapter || dichCaChapter)()
        }
      })

      const nutSnip = document.createElement('button')
      nutSnip.id = 'translation-nut-khoanh-vung'
      nutSnip.type = 'button'
      nutSnip.textContent = '✂️ Khoanh vùng (Alt+S)'
      nutSnip.style.cssText = kieuNut
      nutSnip.addEventListener('click', () => {
        if (!window[CO].dangChay) {
          window[CO].dangChay = true
          ;(window[CO].khoanhVungDich || khoanhVungDich)()
        }
      })

      const nutCuon = document.createElement('button')
      nutCuon.id = 'translation-nut-tu-dich-cuon'
      nutCuon.type = 'button'
      const capNhatNutCuon = () => {
        const bat = Boolean(window[CO].tuDichKhiCuon)
        nutCuon.textContent = bat ? '🔄 Tự dịch khi cuộn: BẬT (Alt+W)' : '🔄 Tự dịch khi cuộn (Alt+W)'
        nutCuon.style.background = bat ? '#059669' : 'rgba(30,41,59,.9)'
        nutCuon.style.borderColor = bat ? '#10b981' : 'rgba(255,255,255,.18)'
      }
      nutCuon.style.cssText = kieuNut
      capNhatNutCuon()
      nutCuon.addEventListener('click', () => {
        window[CO].tuDichKhiCuon = !window[CO].tuDichKhiCuon
        capNhatNutCuon()
        if (window[CO].tuDichKhiCuon && !window[CO].dangChay) {
          dichTrangHienTai({ tuDongCuon: true })
        }
      })

      // Nút đổi nhanh Ngôn ngữ dịch ra (9 Ngôn ngữ Quốc tế) ngay trên thanh nổi
      const nutDichRa = document.createElement('button')
      nutDichRa.id = 'translation-nut-ngon-ngu-dich'
      nutDichRa.type = 'button'
      nutDichRa.title = 'Bấm để đổi nhanh Ngôn ngữ dịch ra (9 Ngôn ngữ: VI, EN, ZH, TW, ID, ES, PT, TH, FR)'
      const capNhatNutDichRa = () => {
        const maDich = window[CO].ngonNguDichHienTai || 'vi'
        nutDichRa.textContent = NHAN_NGON_NGU_DICH_NOI[maDich] || '🇻🇳 VI'
        nutDichRa.style.cssText = `${kieuNut};background:rgba(14,116,144,.45);border-color:rgba(56,189,248,.5);font-weight:700`
      }
      capNhatNutDichRa()
      nutDichRa.addEventListener('click', async () => {
        const hienTaiDich = window[CO].ngonNguDichHienTai || 'vi'
        const idxDich = DS_MA_NGON_NGU_DICH.indexOf(hienTaiDich)
        const tiep = DS_MA_NGON_NGU_DICH[(idxDich + 1) % DS_MA_NGON_NGU_DICH.length]
        window[CO].ngonNguDichHienTai = tiep
        capNhatNutDichRa()
        try {
          await chrome.storage?.local?.set?.({ ngonNguDich: tiep })
        } catch {}
        if (!window[CO].dangChay) {
          ;(window[CO].dichTrangHienTai || dichTrangHienTai)()
        }
      })

      // Nút đổi nhanh Cấp độ Model AI (1 lượt / 2 lượt Pro / 3 lượt Ultra) ngay trên thanh nổi
      const nutModel = document.createElement('button')
      nutModel.id = 'translation-nut-doi-model'
      nutModel.type = 'button'
      nutModel.title = 'Bấm để đổi nhanh cấp độ Model AI:\n• ⚡ 1 Lượt: Nhanh & tiết kiệm\n• 🧠 2 Lượt Pro: Chữ viết tay & Sổ tay 60 từ\n• ✨ 3 Lượt Ultra: 2K Đa phương thức Gemini & DeepSeek'
      const capNhatNutModel = () => {
        const eng = window[CO].engineHienTai || 'local_ocr_gpu'
        nutModel.textContent = NHAN_ENGINE_AI_NOI[eng] || '⚡ 1 Lượt'
        const bg = eng === 'llm_context'
          ? 'rgba(217,119,6,.45)'
          : (eng === 'local_hybrid_pro' ? 'rgba(124,58,237,.42)' : 'rgba(14,165,233,.32)')
        const bd = eng === 'llm_context'
          ? 'rgba(251,191,36,.65)'
          : (eng === 'local_hybrid_pro' ? 'rgba(167,139,250,.55)' : 'rgba(56,189,248,.45)')
        nutModel.style.cssText = `${kieuNut};background:${bg};border-color:${bd}`
      }
      capNhatNutModel()
      chrome.storage?.local?.get?.({ engine: 'local_ocr_gpu' })
        ?.then?.((d) => {
          if (d?.engine && NHAN_ENGINE_AI_NOI[d.engine]) {
            window[CO].engineHienTai = d.engine
            capNhatNutModel()
          }
        })
        ?.catch?.(() => {})
      nutModel.addEventListener('click', async () => {
        const hienTaiEng = window[CO].engineHienTai || 'local_ocr_gpu'
        const idxEng = DS_MA_ENGINE_AI.indexOf(hienTaiEng)
        const tiepEng = DS_MA_ENGINE_AI[(idxEng + 1) % DS_MA_ENGINE_AI.length]
        window[CO].engineHienTai = tiepEng
        capNhatNutModel()
        try {
          await chrome.storage?.local?.set?.({ engine: tiepEng })
        } catch {}
        if (!window[CO].dangChay) {
          ;(window[CO].dichTrangHienTai || dichTrangHienTai)()
        }
      })

      // Nút đổi nhanh Font theo thể loại ngay trên thanh nổi
      const dsMaFont = Object.keys(KHO_FONT_TRUYEN)
      const nutFont = document.createElement('button')
      nutFont.id = 'translation-nut-doi-font'
      nutFont.type = 'button'
      nutFont.title = 'Bấm để đổi nhanh Font chữ theo thể loại truyện (Hành động / Ngôn tình / Cổ trang / Hài hước)'
      nutFont.textContent = layThongSoFont(window[CO].fontChuHienTai).ten
      nutFont.style.cssText = `${kieuNut};background:rgba(79,70,229,.35);border-color:rgba(129,140,248,.45)`
      nutFont.addEventListener('click', () => {
        const idxHienTai = dsMaFont.indexOf(window[CO].fontChuHienTai || 'bangers')
        const tiepTheo = dsMaFont[(idxHienTai + 1) % dsMaFont.length]
        window[CO].fontChuHienTai = tiepTheo
        nutFont.textContent = layThongSoFont(tiepTheo).ten
        chrome.storage?.local?.set?.({ fontChuTruyen: tiepTheo })?.catch?.(() => {})
        window.dispatchEvent(new CustomEvent('translation:ve-lai'))
      })

      const doiCoChu = (delta) => {
        const hienTai = window[CO].heSoCoChu || 1
        window[CO].heSoCoChu = Math.max(0.75, Math.min(1.45, Math.round((hienTai + delta) * 100) / 100))
        window.dispatchEvent(new CustomEvent('translation:ve-lai'))
      }
      const nutChuNho = document.createElement('button')
      nutChuNho.type = 'button'
      nutChuNho.textContent = 'A-'
      nutChuNho.title = 'Thu nhỏ chữ dịch trong bong bóng'
      nutChuNho.style.cssText = `${kieuNut};padding:5px 8px`
      nutChuNho.addEventListener('click', () => doiCoChu(-0.1))

      const nutChuTo = document.createElement('button')
      nutChuTo.type = 'button'
      nutChuTo.textContent = 'A+'
      nutChuTo.title = 'Phóng to chữ dịch trong bong bóng'
      nutChuTo.style.cssText = `${kieuNut};padding:5px 8px`
      nutChuTo.addEventListener('click', () => doiCoChu(0.1))

      // Nút Lưu trang truyện đang xem thành ảnh PNG độ phân giải cao (đã xoá chữ gốc + ghép chữ dịch)
      const nutLuuAnh = document.createElement('button')
      nutLuuAnh.id = 'translation-nut-luu-anh'
      nutLuuAnh.type = 'button'
      nutLuuAnh.textContent = '📥 Lưu ảnh'
      nutLuuAnh.title = 'Tải trang truyện đang xem (đã dịch & xoá chữ gốc) về máy dạng PNG chất lượng cao'
      nutLuuAnh.style.cssText = kieuNut
      nutLuuAnh.addEventListener('click', async () => {
        try {
          const chon = chonTrangTruyen(layMoTa(), { caoKhungNhin: window.innerHeight })
          const el = chon?.anh?.el
          if (!el) {
            xong('Chưa tìm thấy trang truyện trên màn hình để lưu.', 4)
            return
          }
          const ctxGoc = layCtxMau(el)
          const src = el.currentSrc || el.src || el.dataset?.translationCanvasId || ''
          const lop = src ? timLop(src) : document.querySelector(`.${LOP_CLASS}`)
          const W = el.naturalWidth || el.width || 0
          const H = el.naturalHeight || el.height || 0
          if (!ctxGoc || W < 50 || H < 50) {
            xong('Hãy dịch trang này trước khi bấm Lưu ảnh.', 4)
            return
          }
          const cOut = document.createElement('canvas')
          cOut.width = W
          cOut.height = H
          const ctxOut = cOut.getContext('2d')
          ctxOut.drawImage(ctxGoc.canvas, 0, 0, W, H)

          if (lop) {
            const rLop = lop.getBoundingClientRect()
            const tlX = W / Math.max(1, rLop.width)
            const tlY = H / Math.max(1, rLop.height)

            // Vẽ các lớp xoá chữ gốc (`translation-anh-sach`)
            const dsLopChe = lop.querySelectorAll('.translation-anh-sach')
            for (const lc of dsLopChe) {
              const bgUrl = (lc.style.backgroundImage || '').replace(/^url\(["']?/, '').replace(/["']?\)$/, '')
              const rChe = lc.getBoundingClientRect()
              const dx = (rChe.left - rLop.left) * tlX
              const dy = (rChe.top - rLop.top) * tlY
              const dw = rChe.width * tlX
              const dh = rChe.height * tlY
              if (bgUrl.startsWith('data:image/')) {
                const imgPatch = new Image()
                await new Promise((res) => { imgPatch.onload = res; imgPatch.onerror = res; imgPatch.src = bgUrl })
                ctxOut.drawImage(imgPatch, dx, dy, dw, dh)
              } else if (lc.style.backgroundColor || lc.style.background) {
                ctxOut.save()
                ctxOut.fillStyle = lc.style.backgroundColor || lc.style.background || '#ffffff'
                ctxOut.fillRect(dx, dy, dw, dh)
                ctxOut.restore()
              }
            }

            // Vẽ lớp Cọ vẽ tay Inpaint (`translation-co-ve`) nếu người dùng có tô xoá thủ công
            const canvasCoVe = lop.querySelector('.translation-co-ve')
            if (canvasCoVe && canvasCoVe.width > 0 && canvasCoVe.height > 0) {
              ctxOut.drawImage(canvasCoVe, 0, 0, W, H)
            }

            // Vẽ chữ dịch trong từng bóng thoại (`translation-hop-chu`)
            const dsHop = lop.querySelectorAll('.translation-hop-chu')
            for (const hop of dsHop) {
              const span = hop.querySelector('span')
              const text = (span?.innerText || hop.innerText || '').trim()
              if (!text) continue
              const rHop = hop.getBoundingClientRect()
              const cx = (rHop.left - rLop.left + rHop.width * 0.5) * tlX
              const cy = (rHop.top - rLop.top + rHop.height * 0.5) * tlY
              const maxW = Math.max(24, (rHop.width - 6) * tlX)
              const pxCss = parseFloat(getComputedStyle(hop).fontSize) || 14
              const pxCanvas = Math.max(12, Math.round(pxCss * tlX))
              const fontCss = getComputedStyle(hop).fontFamily || 'sans-serif'
              const nenToi = hop.dataset.nenToi === '1'

              ctxOut.save()
              ctxOut.font = `${pxCanvas}px ${fontCss}`
              ctxOut.textAlign = 'center'
              ctxOut.textBaseline = 'middle'

              const tu = text.split(/\s+/)
              const dong = []
              let dongHienTai = ''
              for (const w of tu) {
                const thu = dongHienTai ? `${dongHienTai} ${w}` : w
                if (ctxOut.measureText(thu).width > maxW && dongHienTai) {
                  dong.push(dongHienTai)
                  dongHienTai = w
                } else {
                  dongHienTai = thu
                }
              }
              if (dongHienTai) dong.push(dongHienTai)

              const caoDong = pxCanvas * 1.18
              const yBatDau = cy - ((dong.length - 1) * caoDong) * 0.5
              const laChuNoi = hop.dataset.chuNoi === '1'
              ctxOut.lineJoin = 'round'
              ctxOut.lineWidth = laChuNoi
                ? Math.max(3, Math.round(pxCanvas * 0.22))
                : Math.max(2, Math.round(pxCanvas * 0.14))
              ctxOut.strokeStyle = nenToi ? '#000000' : '#ffffff'
              ctxOut.fillStyle = nenToi ? '#ffffff' : '#000000'

              dong.forEach((d, i) => {
                const y = yBatDau + i * caoDong
                ctxOut.strokeText(d, cx, y)
                ctxOut.fillText(d, cx, y)
              })
              ctxOut.restore()
            }

            // Vẽ nhãn dịch nhỏ của chữ tượng thanh (`translation-nhan-sfx`) — giữ nguyên nét SFX gốc bên dưới
            for (const nhan of lop.querySelectorAll('.translation-nhan-sfx')) {
              const text = (nhan.textContent || '').trim()
              if (!text) continue
              const rN = nhan.getBoundingClientRect()
              const nx = (rN.left - rLop.left) * tlX
              const ny = (rN.top - rLop.top) * tlY
              const nw = rN.width * tlX
              const nh = rN.height * tlY
              const pxN = Math.max(11, Math.round((parseFloat(getComputedStyle(nhan).fontSize) || 12) * tlX))
              ctxOut.save()
              ctxOut.fillStyle = 'rgba(255,255,255,0.9)'
              ctxOut.strokeStyle = 'rgba(17,24,39,0.45)'
              ctxOut.lineWidth = Math.max(1, tlX)
              ctxOut.beginPath()
              if (ctxOut.roundRect) ctxOut.roundRect(nx, ny, nw, nh, 6 * tlX)
              else ctxOut.rect(nx, ny, nw, nh)
              ctxOut.fill()
              ctxOut.stroke()
              ctxOut.fillStyle = '#111827'
              ctxOut.font = `${pxN}px ${getComputedStyle(nhan).fontFamily || 'sans-serif'}`
              ctxOut.textAlign = 'center'
              ctxOut.textBaseline = 'middle'
              ctxOut.fillText(text, nx + nw / 2, ny + nh / 2, Math.max(10, nw - 4))
              ctxOut.restore()
            }
          }

          const urlPng = cOut.toDataURL('image/png')
          const a = document.createElement('a')
          a.href = urlPng
          a.download = `trang-truyen-da-dich-${Date.now()}.png`
          document.body.appendChild(a)
          a.click()
          a.remove()
          xong('✅ Đã lưu ảnh trang truyện đã dịch (PNG)!', 4)
        } catch (err) {
          xong(`Không lưu được ảnh: ${err?.message || err}`, 5)
        }
      })

      const nutCoVe = document.createElement('button')
      nutCoVe.id = 'translation-nut-co-ve'
      nutCoVe.type = 'button'
      nutCoVe.title = 'Bật/tắt Cọ vẽ tay xoá chữ gốc còn sót trên trang (Brush Inpaint trực tiếp trên Canvas)'
      const capNhatNutCoVe = () => {
        const bat = Boolean(window[CO].cheDoCoVe)
        nutCoVe.textContent = bat ? '🖌️ Cọ xoá: BẬT' : '🖌️ Cọ xoá'
        nutCoVe.style.cssText = bat
          ? `${kieuNut};background:#db2777;border-color:#f472b6;font-weight:700`
          : kieuNut
      }
      capNhatNutCoVe()
      nutCoVe.addEventListener('click', () => {
        window[CO].cheDoCoVe = !window[CO].cheDoCoVe
        if (!window[CO].cheDoCoVe) window[CO].mauCoVeUuTien = null
        capNhatNutCoVe()
        window.dispatchEvent(new CustomEvent('translation:ve-lai'))
        xong(
          window[CO].cheDoCoVe
            ? '🖌️ Đã BẬT Cọ xoá chữ: Kéo chuột lên nét chữ gốc còn sót để tô xoá tiệp màu nền. Bấm ↩️ để hoàn tác.'
            : 'Đã TẮT Cọ xoá chữ.',
          4,
        )
      })

      const nutHoanTacCo = document.createElement('button')
      nutHoanTacCo.id = 'translation-nut-hoan-tac-co'
      nutHoanTacCo.type = 'button'
      nutHoanTacCo.textContent = '↩️'
      nutHoanTacCo.title = 'Hoàn tác nét cọ xoá chữ vừa vẽ'
      nutHoanTacCo.style.cssText = `${kieuNut};padding:5px 8px`
      nutHoanTacCo.addEventListener('click', () => {
        const chon = chonTrangTruyen(layMoTa(), { caoKhungNhin: window.innerHeight })
        const el = chon?.anh?.el
        if (el && Array.isArray(el.__translationNhatKyCoVe) && el.__translationNhatKyCoVe.length > 0) {
          el.__translationNhatKyCoVe.pop()
          window.dispatchEvent(new CustomEvent('translation:ve-lai'))
        } else {
          xong('Chưa có nét cọ nào trên trang này để hoàn tác.', 3)
        }
      })

      const nut = document.createElement('button')
      nut.id = 'translation-cong-tac-goc'
      nut.type = 'button'
      nut.textContent = '👁 Xem gốc (Alt)'
      nut.style.cssText = kieuNut
      nut.addEventListener('click', () => datAnLopPhu(!window[CO].dangAnLopPhu))

      // Nút đổi chế độ xử lý chữ tượng thanh (SFX): Ghi chú nhỏ → Giữ gốc → Dịch đè
      const nutSfx = document.createElement('button')
      nutSfx.id = 'translation-nut-che-do-sfx'
      nutSfx.type = 'button'
      nutSfx.title = 'Cách xử lý chữ tiếng động vẽ trên tranh (STOMP, ズシン, BOOM...):\n• Ghi chú: giữ nét vẽ gốc + nhãn dịch nhỏ (khuyên dùng)\n• Giữ gốc: không dịch SFX\n• Dịch đè: xoá chữ gốc rồi đè chữ dịch (dễ nhoè)'
      const capNhatNutSfx = () => {
        nutSfx.textContent = NHAN_CHE_DO_SFX[window[CO].cheDoSfx || 'giu_nguyen']
        nutSfx.style.cssText = kieuNut
      }
      capNhatNutSfx()
      nutSfx.addEventListener('click', () => {
        const hienTai = window[CO].cheDoSfx || 'giu_nguyen'
        const tiep = DS_CHE_DO_SFX[(DS_CHE_DO_SFX.indexOf(hienTai) + 1) % DS_CHE_DO_SFX.length]
        window[CO].cheDoSfx = tiep
        capNhatNutSfx()
        chrome.storage?.local?.set?.({ cheDoSfx: tiep })?.catch?.(() => {})
        window.dispatchEvent(new CustomEvent('translation:ve-lai'))
      })

      // Nút thu gọn / mở rộng thanh công cụ (ghi nhớ trạng thái giữa các lần đọc)
      const nutThuGon = document.createElement('button')
      nutThuGon.id = 'translation-nut-thu-gon'
      nutThuGon.type = 'button'
      nutThuGon.style.cssText = `${kieuNut};padding:5px 9px;font-weight:700`
      const dsNutChinh = [nutDich, nutChapter, nutCuon, nutSnip, nutModel, nutDichRa, nutFont, nutChuNho, nutChuTo, nutSfx, nutCoVe, nutHoanTacCo, nutLuuAnh, nut]
      const apDungThuGon = (thuGon) => {
        window[CO].thanhThuGon = thuGon
        // Khi thu gọn chỉ giữ nút Dịch trang + nút mở rộng để không che nội dung truyện
        dsNutChinh.forEach((b) => { b.style.display = (thuGon && b !== nutDich) ? 'none' : '' })
        nutThuGon.textContent = thuGon ? '›' : '‹'
        nutThuGon.title = thuGon ? 'Mở rộng thanh công cụ' : 'Thu gọn thanh công cụ (Alt+H để ẩn hẳn)'
        thanh.style.padding = thuGon ? '4px 6px' : '6px 8px'
      }
      nutThuGon.addEventListener('click', () => {
        const moi = !window[CO].thanhThuGon
        apDungThuGon(moi)
        chrome.storage?.local?.set?.({ thanhNhanhThuGon: moi })?.catch?.(() => {})
      })
      apDungThuGon(Boolean(window[CO].thanhThuGon))
      chrome.storage?.local?.get?.({ thanhNhanhThuGon: false })
        ?.then?.((d) => apDungThuGon(Boolean(d?.thanhNhanhThuGon)))
        ?.catch?.(() => {})

      // Tự làm mờ thanh công cụ sau 3 giây không rê chuột để không làm phiền khi đọc
      let henMo = null
      const lamMo = () => {
        if (henMo) clearTimeout(henMo)
        henMo = setTimeout(() => { if (!thanh.matches(':hover')) thanh.style.opacity = '0.35' }, 3000)
      }
      thanh.addEventListener('mouseenter', () => { if (henMo) clearTimeout(henMo); thanh.style.opacity = '1' })
      thanh.addEventListener('mouseleave', lamMo)
      lamMo()

      thanh.append(nutThuGon, ...dsNutChinh)
      document.documentElement.appendChild(thanh)
    }

    // Alt+H: ẩn / hiện hoàn toàn thanh công cụ nổi
    if (!window[CO].daCaiPhimAnThanh) {
      window[CO].daCaiPhimAnThanh = true
      window.addEventListener('keydown', (e) => {
        if (window[CO].dangSuaBong) return
        if (e.altKey && (e.key === 'h' || e.key === 'H')) {
          e.preventDefault()
          const t = document.getElementById('translation-thanh-nhanh')
          if (!t) return
          const an = t.style.display !== 'none'
          t.style.display = an ? 'none' : 'flex'
          xong(an ? 'Đã ẩn thanh công cụ. Bấm Alt+H để hiện lại.' : 'Đã hiện thanh công cụ.', 3)
        }
      })
    }
  }

  /**
   * Lấy màu nền sạch xung quanh điểm đặt cọ `(nx, ny)` trên ảnh gốc `el`:
   * Tự động loại bỏ nét mực đen/chữ gốc dưới đầu cọ bằng cách lấy phân vị sáng (78%) cho nền sáng
   * hoặc phân vị tối (22%) cho nền tối.
   */
  function layMauNenTaiDiemCoVe(el, nx, ny, mauMacDinh = null) {
    if (mauMacDinh) return mauMacDinh
    const ctx = layCtxMau(el)
    if (!ctx) return '#ffffff'
    const W = ctx.canvas.width
    const H = ctx.canvas.height
    const cx = Math.max(0, Math.min(W - 1, Math.round(nx * W)))
    const cy = Math.max(0, Math.min(H - 1, Math.round(ny * H)))
    const R = 6
    const x0 = Math.max(0, cx - R)
    const y0 = Math.max(0, cy - R)
    const rw = Math.min(W - x0, R * 2 + 1)
    const rh = Math.min(H - y0, R * 2 + 1)
    try {
      const data = ctx.getImageData(x0, y0, rw, rh).data
      const mau = []
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i], g = data[i + 1], b = data[i + 2]
        const luma = 0.299 * r + 0.587 * g + 0.114 * b
        mau.push({ r, g, b, luma })
      }
      if (!mau.length) return '#ffffff'
      mau.sort((a, b) => a.luma - b.luma)
      const trungVi = mau[Math.floor(mau.length * 0.5)].luma
      const chon = trungVi >= 110
        ? mau[Math.min(mau.length - 1, Math.floor(mau.length * 0.8))]
        : mau[Math.max(0, Math.floor(mau.length * 0.2))]
      return `rgb(${chon.r}, ${chon.g}, ${chon.b})`
    } catch {
      return '#ffffff'
    }
  }

  /**
   * E105 (#6) — Khả năng sửa nhanh 1 bóng thoại bị dịch sai ngay trên tiện ích (Double-Click Inline Bubble Editor).
   *
   * Khi người dùng nhấp đúp (`dblclick`) vào bất kỳ bóng thoại nào:
   * - Mở chế độ sửa trực tiếp (`contentEditable = "true"`) ngay trong bóng thoại đó.
   * - Tự động co/giãn cỡ chữ vừa khít lòng bong bóng theo thời gian thực khi người dùng gõ sửa.
   * - Hiện thanh công cụ mini ngay trên đỉnh bóng thoại:
   *   `🔄 Dịch lại` · `A-` · `A+` · `⬛ Phủ kín` · `🖌️ Cọ xoá` · `✥ Kéo` · `✓ Xong`.
   */
  function moTrinhSuaBongThoai({ hop, noiDung, v, coChuVuaKhung, rLop }) {
    document.getElementById('translation-thanh-sua-bong')?.remove()
    window[CO].dangSuaBong = true

    noiDung.contentEditable = 'true'
    noiDung.spellcheck = false
    noiDung.style.outline = 'none'
    noiDung.style.cursor = 'text'
    hop.style.boxShadow = '0 0 0 2px #6366f1, 0 4px 14px rgba(79,70,229,.35)'
    hop.style.background = v.nen_toi ? 'rgba(15,23,42,.35)' : 'rgba(255,255,255,.35)'
    hop.style.zIndex = '10'
    noiDung.focus()

    // Đưa con trỏ về cuối câu hoặc bôi đen để sửa nhanh
    try {
      const sel = window.getSelection()
      const range = document.createRange()
      range.selectNodeContents(noiDung)
      sel.removeAllRanges()
      sel.addRange(range)
    } catch {}

    const rHop = hop.getBoundingClientRect()
    const thanhSua = document.createElement('div')
    thanhSua.id = 'translation-thanh-sua-bong'
    const topBar = Math.max(8, rHop.top - 40)
    const leftBar = Math.max(8, Math.min(window.innerWidth - 420, rHop.left + rHop.width * 0.5 - 200))
    thanhSua.style.cssText = [
      'position:fixed', 'z-index:2147483647',
      `left:${Math.round(leftBar)}px`, `top:${Math.round(topBar)}px`,
      'display:flex', 'align-items:center', 'gap:4px',
      'padding:4px 6px', 'border-radius:999px',
      'background:rgba(15,23,42,.95)', 'border:1px solid #818cf8',
      'box-shadow:0 6px 18px rgba(15,23,42,.45)', 'font:11.5px/1.2 system-ui,sans-serif',
      'color:#fff', 'user-select:none',
    ].join(';')

    const kieuNutMini = [
      'padding:4px 8px', 'border-radius:999px', 'border:1px solid rgba(255,255,255,.2)',
      'background:rgba(30,41,59,.95)', 'color:#f8fafc', 'font:600 11px/1.1 system-ui,sans-serif',
      'cursor:pointer', 'white-space:nowrap',
    ].join(';')

    const nutDichLai = document.createElement('button')
    nutDichLai.type = 'button'
    nutDichLai.textContent = '🔄 Dịch lại'
    nutDichLai.title = v.chu_goc ? `Dịch lại từ chữ gốc: ${v.chu_goc}` : 'Dịch lại bóng thoại này'
    nutDichLai.style.cssText = `${kieuNutMini};background:#4f46e5;border-color:#818cf8`
    nutDichLai.addEventListener('mousedown', (e) => e.preventDefault())
    nutDichLai.addEventListener('click', async (e) => {
      e.stopPropagation()
      nutDichLai.disabled = true
      nutDichLai.textContent = '⏳…'
      try {
        const kq = await chrome.runtime.sendMessage({
          viec: 'dich-lai-cau',
          chu_goc: v.chu_goc || '',
          chu_hien_tai: noiDung.textContent || v.ban_dich || '',
          ngon_ngu_dich: window[CO].ngonNguDichHienTai || 'vi',
        })
        if (kq?.ok && kq.ban_dich) {
          v.ban_dich = kq.ban_dich
          noiDung.textContent = kq.ban_dich
          coChuVuaKhung()
        }
      } catch {}
      nutDichLai.disabled = false
      nutDichLai.textContent = '🔄 Dịch lại'
    })

    const nutThuNho = document.createElement('button')
    nutThuNho.type = 'button'
    nutThuNho.textContent = 'A-'
    nutThuNho.title = 'Thu nhỏ chữ của riêng bóng thoại này'
    nutThuNho.style.cssText = kieuNutMini
    nutThuNho.addEventListener('mousedown', (e) => e.preventDefault())
    nutThuNho.addEventListener('click', (e) => {
      e.stopPropagation()
      v._heSoRieng = Math.max(0.65, Math.round(((v._heSoRieng || 1) - 0.1) * 100) / 100)
      coChuVuaKhung()
    })

    const nutPhongTo = document.createElement('button')
    nutPhongTo.type = 'button'
    nutPhongTo.textContent = 'A+'
    nutPhongTo.title = 'Phóng to chữ của riêng bóng thoại này'
    nutPhongTo.style.cssText = kieuNutMini
    nutPhongTo.addEventListener('mousedown', (e) => e.preventDefault())
    nutPhongTo.addEventListener('click', (e) => {
      e.stopPropagation()
      v._heSoRieng = Math.min(1.65, Math.round(((v._heSoRieng || 1) + 0.1) * 100) / 100)
      coChuVuaKhung()
    })

    // Nút Phủ kín hộp (`_phuKinHop`) — dùng khi bong bóng có chữ gốc thò quá dài hoặc nền phức tạp cần che kín 100%
    const nutPhuKin = document.createElement('button')
    nutPhuKin.type = 'button'
    const capNhatNutPhuKin = () => {
      nutPhuKin.textContent = v._phuKinHop ? '⬛ Đã phủ kín' : '⬛ Phủ kín'
      nutPhuKin.style.cssText = v._phuKinHop
        ? `${kieuNutMini};background:#0284c7;border-color:#38bdf8`
        : kieuNutMini
    }
    nutPhuKin.title = 'Bật/tắt phủ kín toàn bộ hộp bóng thoại để che sạch 100% chữ gốc còn sót ở rìa'
    capNhatNutPhuKin()
    nutPhuKin.addEventListener('mousedown', (e) => e.preventDefault())
    nutPhuKin.addEventListener('click', (e) => {
      e.stopPropagation()
      v._phuKinHop = !v._phuKinHop
      capNhatNutPhuKin()
      const nenMau = v._mauNenCss || (v.nen_toi ? '#000000' : '#ffffff')
      hop.style.background = v._phuKinHop ? nenMau : (v.nen_toi ? 'rgba(15,23,42,.35)' : 'rgba(255,255,255,.35)')
    })

    // Nút bật Cọ xoá (`🖌️ Cọ xoá`) lấy sẵn màu nền của đúng bóng thoại này
    const nutCoBong = document.createElement('button')
    nutCoBong.type = 'button'
    nutCoBong.textContent = '🖌️ Cọ xoá'
    nutCoBong.title = 'Dùng cọ vẽ tay tô xoá nét chữ gốc còn sót quanh bóng thoại này'
    nutCoBong.style.cssText = `${kieuNutMini};background:#be185d;border-color:#f472b6`
    nutCoBong.addEventListener('mousedown', (e) => e.preventDefault())
    nutCoBong.addEventListener('click', (e) => {
      e.stopPropagation()
      window[CO].cheDoCoVe = true
      window[CO].mauCoVeUuTien = v._mauNenCss || (v.nen_toi ? '#000000' : '#ffffff')
      const nutCoThanh = document.getElementById('translation-nut-co-ve')
      if (nutCoThanh) {
        nutCoThanh.textContent = '🖌️ Cọ xoá: BẬT'
        nutCoThanh.style.background = '#db2777'
        nutCoThanh.style.borderColor = '#f472b6'
      }
      hoanTatSua()
      xong('🖌️ Hãy kéo chuột tô lên phần chữ gốc còn sót để xoá. Bấm "🖌️ Cọ xoá: BẬT" lần nữa khi xong.', 4)
    })

    // Nút Kéo di chuyển vị trí bóng thoại (`✥ Kéo`)
    const nutKeo = document.createElement('button')
    nutKeo.type = 'button'
    nutKeo.textContent = '✥ Kéo'
    nutKeo.title = 'Giữ chuột và kéo để di chuyển vị trí chữ dịch sang chỗ khác'
    nutKeo.style.cssText = `${kieuNutMini};cursor:move`
    nutKeo.addEventListener('mousedown', (e) => {
      e.preventDefault()
      e.stopPropagation()
      const startX = e.clientX
      const startY = e.clientY
      const origLeft = parseFloat(hop.style.left) || 0
      const origTop = parseFloat(hop.style.top) || 0
      const origBarLeft = parseFloat(thanhSua.style.left) || 0
      const origBarTop = parseFloat(thanhSua.style.top) || 0
      const wLop = Math.max(1, rLop?.width || hop.parentElement?.clientWidth || 1)
      const hLop = Math.max(1, rLop?.height || hop.parentElement?.clientHeight || 1)
      const lechXBanDau = v._lechX || 0
      const lechYBanDau = v._lechY || 0

      const onMove = (ev) => {
        const dx = ev.clientX - startX
        const dy = ev.clientY - startY
        hop.style.left = `${origLeft + dx}px`
        hop.style.top = `${origTop + dy}px`
        thanhSua.style.left = `${origBarLeft + dx}px`
        thanhSua.style.top = `${origBarTop + dy}px`
        v._lechX = lechXBanDau + dx / wLop
        v._lechY = lechYBanDau + dy / hLop
      }
      const onUp = () => {
        window.removeEventListener('mousemove', onMove, true)
        window.removeEventListener('mouseup', onUp, true)
      }
      window.addEventListener('mousemove', onMove, true)
      window.addEventListener('mouseup', onUp, true)
    })

    const nutXong = document.createElement('button')
    nutXong.type = 'button'
    nutXong.textContent = '✓ Xong'
    nutXong.style.cssText = `${kieuNutMini};background:#059669;border-color:#10b981`

    const hoanTatSua = () => {
      if (!window[CO].dangSuaBong) return
      window[CO].dangSuaBong = false
      const chuMoi = String(noiDung.textContent || '').trim()
      if (chuMoi) {
        v.ban_dich = chuMoi
        if (v.chu_goc) {
          chrome.runtime?.sendMessage?.({
            viec: 'hoc-tu-sua',
            chu_goc: v.chu_goc,
            ban_dich: chuMoi,
          })?.catch?.(() => {})
        }
      }
      noiDung.contentEditable = 'false'
      noiDung.style.cursor = 'pointer'
      hop.style.boxShadow = 'none'
      hop.style.background = 'transparent'
      hop.style.zIndex = '2'
      thanhSua.remove()
      window.removeEventListener('mousedown', bamRaNgoai, true)
      coChuVuaKhung()
      window.dispatchEvent(new CustomEvent('translation:ve-lai'))
    }

    const bamRaNgoai = (ev) => {
      if (hop.contains(ev.target) || thanhSua.contains(ev.target)) return
      hoanTatSua()
    }

    nutXong.addEventListener('click', (e) => {
      e.stopPropagation()
      hoanTatSua()
    })

    noiDung.addEventListener('input', () => {
      const s = String(noiDung.textContent || '').trim()
      if (s) v.ban_dich = s
      coChuVuaKhung()
    })

    noiDung.addEventListener('keydown', (e) => {
      e.stopPropagation()
      if (e.key === 'Escape' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault()
        hoanTatSua()
      }
    })

    thanhSua.append(nutDichLai, nutThuNho, nutPhongTo, nutPhuKin, nutCoBong, nutKeo, nutXong)
    document.documentElement.appendChild(thanhSua)
    setTimeout(() => window.addEventListener('mousedown', bamRaNgoai, true), 20)
  }

  function vePhu(elBanDau, dulieu) {
    caiCongTacSoSanhGoc()
    const vung = Array.isArray(dulieu) ? dulieu : (dulieu?.vung || [])
    const anh_da_dich = Array.isArray(dulieu) ? null : (dulieu?.anh_da_dich || null)
    const ctxMauGoc = (!Array.isArray(dulieu) && dulieu?._ctxMau) || elBanDau?.__translationCtxMau || null

    let el = elBanDau
    if (ctxMauGoc && !el.__translationCtxMau) {
      el.__translationCtxMau = ctxMauGoc
      el.__translationCtxSrc = el.currentSrc || el.src || el.dataset?.translationCanvasId || ''
    }
    let src_khoa = el.currentSrc || el.src || el.dataset?.translationCanvasId || ''
    const rBanDau = el.getBoundingClientRect()
    const thongSoGoc = {
      naturalWidth: el.naturalWidth || el.width || dulieu?._naturalWidth || 0,
      naturalHeight: el.naturalHeight || el.height || dulieu?._naturalHeight || 0,
      docTop: (rBanDau.width >= 40 && rBanDau.height >= 40)
        ? (window.scrollY + rBanDau.top)
        : (typeof dulieu?._docTop === 'number' ? dulieu._docTop : el.__translationDocTop),
    }

    if (typeof el.__translationDungLopPhu === 'function') {
      try { el.__translationDungLopPhu() } catch {}
    }
    if (src_khoa) timLop(src_khoa)?.remove()
    const lop = document.createElement('div')
    lop.className = LOP_CLASS
    lop.dataset.src = src_khoa
    document.querySelectorAll(`#${LOP_CLASS}`).forEach((x) => x.removeAttribute('id'))
    lop.id = LOP_CLASS
    lop.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;transition:opacity .12s ease'
    if (window[CO].dangAnLopPhu) lop.style.opacity = '0'
    document.documentElement.appendChild(lop)

    const ro = new ResizeObserver(() => ve())
    const mo = typeof MutationObserver !== 'undefined'
      ? new MutationObserver(() => ve())
      : null
    const dung = () => {
      ro.disconnect()
      if (mo) mo.disconnect()
      el.removeEventListener('load', goiVe)
      window.removeEventListener('scroll', goiVe, true)
      window.removeEventListener('resize', goiVe)
      window.removeEventListener('translation:ve-lai', goiVe)
      if (el.__translationDungLopPhu === dung) el.__translationDungLopPhu = null
      lop.remove()
    }
    el.__translationDungLopPhu = dung
    const goiVe = () => ve()

    const ve = () => {
      if (window[CO].dangSuaBong || lop.__dangKeoCoVe) return
      let r = el.getBoundingClientRect()
      if (!el.isConnected || r.width < 40 || r.height < 40) {
        // Trong `vePhu`, luôn truyền `choPhepKhungNhin = false` để lớp phủ của trang ở cuối chapter
        // (ví dụ banner quảng cáo "ĐỌC ĐẦU TIÊN / MIỄN PHÍ!!") KHÔNG BAO GIỜ nhảy đè lên trang khác đang hiển thị trên màn hình!
        const elPhucHoi = timAnhThayThe(el, src_khoa, thongSoGoc, false)
        if (elPhucHoi && elPhucHoi !== el) {
          try { ro.unobserve(el) } catch {}
          el.removeEventListener('load', goiVe)
          if (el.__translationDungLopPhu === dung) el.__translationDungLopPhu = null
          el = elPhucHoi
          if (ctxMauGoc && !el.__translationCtxMau) {
            el.__translationCtxMau = ctxMauGoc
            el.__translationCtxSrc = el.currentSrc || el.src || el.dataset?.translationCanvasId || ''
          }
          el.__translationDungLopPhu = dung
          src_khoa = el.currentSrc || el.src || el.dataset?.translationCanvasId || src_khoa
          lop.dataset.src = src_khoa
          ro.observe(el)
          if (mo) mo.observe(el, { attributes: true, attributeFilter: ['src', 'srcset'] })
          el.addEventListener('load', goiVe)
          r = el.getBoundingClientRect()
        } else if (!el.isConnected) {
          // Trên MangaPlus hoặc trình đọc cuộn ảo (`blob:` / `canvas://`), khi cuộn xa trang có thể
          // tạm thời bị gỡ khỏi DOM rồi gắn lại khi cuộn ngược lên — chỉ ẩn đi thay vì huỷ vĩnh viễn.
          if (String(src_khoa).startsWith('blob:') || String(src_khoa).startsWith('canvas://') || typeof thongSoGoc.docTop === 'number') {
            lop.style.display = 'none'
            return
          }
          dung()
          return
        }
      }

      const srcHienTai = el.currentSrc || el.src || el.dataset?.translationCanvasId || ''
      if (src_khoa && srcHienTai && srcHienTai !== src_khoa) {
        const nwHienTai = el.naturalWidth || el.width || 0
        const nhHienTai = el.naturalHeight || el.height || 0
        const cungKichThuoc = thongSoGoc.naturalWidth > 0
          && nwHienTai === thongSoGoc.naturalWidth
          && nhHienTai === thongSoGoc.naturalHeight
        if (cungKichThuoc && (src_khoa.startsWith('blob:') || srcHienTai.startsWith('blob:'))) {
          src_khoa = srcHienTai
          lop.dataset.src = src_khoa
          if (ctxMauGoc) {
            el.__translationCtxMau = ctxMauGoc
            el.__translationCtxSrc = srcHienTai
          }
        } else {
          dung()
          return
        }
      }

      const LE = 800
      if (r.bottom < -LE || r.top > window.innerHeight + LE) {
        lop.style.display = 'none'
        return
      }
      lop.innerHTML = ''
      const nw = el.naturalWidth || el.width || thongSoGoc.naturalWidth || Math.round(r.width)
      const nh = el.naturalHeight || el.height || thongSoGoc.naturalHeight || Math.round(r.height)
      if (r.width < 1 || r.height < 1 || nw < 1 || nh < 1) { lop.style.display = 'none'; return }
      thongSoGoc.naturalWidth = nw
      thongSoGoc.naturalHeight = nh
      thongSoGoc.docTop = window.scrollY + r.top
      el.__translationDocTop = thongSoGoc.docTop
      lop.style.display = ''
      Object.assign(lop.style, {
        left: `${r.left}px`, top: `${r.top}px`,
        width: `${r.width}px`, height: `${r.height}px`,
      })

      const vungCoDich = vung.filter((v) => Boolean(v.ban_dich))
      const laCheDoPro = Boolean(
        (!Array.isArray(dulieu) && (dulieu?.che_do_pro || dulieu?.che_do_ultra)) ||
        window[CO].engineHienTai === 'local_hybrid_pro' ||
        window[CO].engineHienTai === 'llm_context'
      )
      for (let i = 0; i < vungCoDich.length; i += 1) {
        vungCoDich[i]._cheDoPro = laCheDoPro
      }
      if (anh_da_dich && !vungCoDich.length) {
        const anhPhu = document.createElement('img')
        anhPhu.src = anh_da_dich
        anhPhu.alt = 'Trang đã dịch'
        anhPhu.style.cssText = 'width:100%;height:100%;object-fit:fill;display:block;pointer-events:none;user-select:none'
        lop.appendChild(anhPhu)
        return
      }

      const coCanvas = Boolean(layCtxMau(el))
      const thongSoFont = layThongSoFont(window[CO].fontChuHienTai)
      const thongSoAnh = {
        naturalWidth: nw, naturalHeight: nh,
        clientWidth: r.width, clientHeight: r.height,
      }
      const dsOChe = vungCoDich.map((v) => {
        if (coCanvas) doKhungBongBongCanvas(el, v, vungCoDich)
        return quyDoi(v._khungCheCanvas || v, thongSoAnh)
      })
      const dsOGoc = vungCoDich.map((v) => {
        const khungThuc = coCanvas ? doKhungBongBongCanvas(el, v, vungCoDich) : null
        return {
          ...quyDoi(khungThuc || v, thongSoAnh),
          soKyTu: v.ban_dich.length,
        }
      })
      const dsOMoRong = dsOGoc

      const dsHopDaVe = []
      for (let idx = 0; idx < vungCoDich.length; idx += 1) {
        const v = vungCoDich[idx]
        const oChe = dsOChe[idx]
        const o = dsOMoRong[idx] || dsOGoc[idx]
        if (v.nen_toi === undefined) {
          v.nen_toi = laBongBongToi(el, v)
        }

        // Chữ tượng thanh (SFX) vẽ trên nền tranh: KHÔNG xoá nét vẽ gốc (xoá trên nền phức tạp sẽ để lại vệt nhoè),
        // chỉ gắn nhãn dịch nhỏ bên cạnh (hoặc bỏ qua hẳn) tuỳ `cheDoSfx`. Nhấp đúp nhãn để chuyển vùng đó sang dịch đè.
        const cheDoSfx = window[CO].cheDoSfx || 'giu_nguyen'
        if (cheDoSfx !== 'dich_de' && laVungSfx(v)) {
          if (cheDoSfx === 'ghi_chu' && v.ban_dich) {
            const nhan = document.createElement('div')
            nhan.className = 'translation-nhan-sfx'
            nhan.textContent = String(v.ban_dich).replace(/[.。]+$/, '')
            nhan.title = `💥 Tiếng động (SFX) — gốc: ${v.chu_goc || ''}\nNhấp đúp để xoá chữ gốc và dịch đè lên vùng này`
            const coNhan = Math.max(10, Math.min(15, Math.round(Math.min(o.width, o.height) * 0.22)))
            Object.assign(nhan.style, {
              position: 'absolute',
              zIndex: '2',
              left: `${Math.max(0, o.left + o.width * 0.5)}px`,
              top: `${Math.max(0, o.top + Math.min(o.height * 0.15, 18))}px`,
              transform: 'translateX(-50%)',
              maxWidth: `${Math.max(70, o.width * 1.4)}px`,
              padding: '1px 6px',
              borderRadius: '6px',
              background: 'rgba(255,255,255,.9)',
              color: '#111827',
              border: '1px solid rgba(17,24,39,.45)',
              boxShadow: '0 1px 3px rgba(0,0,0,.25)',
              fontFamily: thongSoFont.css,
              fontSize: `${coNhan}px`,
              lineHeight: '1.15',
              textAlign: 'center',
              whiteSpace: 'normal',
              pointerEvents: window[CO].cheDoCoVe ? 'none' : 'auto',
              cursor: 'pointer',
            })
            nhan.addEventListener('dblclick', (e) => {
              e.preventDefault()
              e.stopPropagation()
              v._sfxDichDe = true
              window.dispatchEvent(new CustomEvent('translation:ve-lai'))
            })
            lop.appendChild(nhan)
          }
          continue
        }
        const anhChe = coCanvas ? taoAnhCheChuCanvas(el, v, vungCoDich) : null
        if (v._laChuNoiTrenNen) {
          v.nen_toi = v._mauHaloGocCss
            ? (v._mauHaloGocCss === '#000000')
            : (!v._nenScreentone && !(v._nenMauChuNoi && (v._lumNenTrungVi ?? 128) >= 95))
        }
        const nenMau = v._laChuNoiTrenNen
          ? (v._mauNenChuNoiCss || (v.nen_toi ? '#000000' : '#ffffff'))
          : (v._mauNenCss || (v.nen_toi ? '#000000' : '#ffffff'))
        const chuMau = (v._laChuNoiTrenNen && v._mauChuGocCss)
          ? v._mauChuGocCss
          : (v.nen_toi ? '#ffffff' : '#000000')

        // Lớp 1 (`lopChe` / Clean-Image trên GPU/Canvas máy khách):
        // Xoá sạch 100% nét chữ gốc trên `oChe` trong khi bảo toàn mọi gai nhọn/đường viền của bong bóng.
        // Nếu người dùng bật `⬛ Phủ kín` (`v._phuKinHop`), phủ hộp màu nền đặc lên toàn bộ vùng `oChe` (nới nhẹ 4px) để che sạch chữ thò xa.
        // Đặt `zIndex: 1` cố định cho mọi lớp xoá nền để KHÔNG BAO GIỜ đè lên lớp chữ `hop` (`zIndex: 2`) của bóng thoại kế bên!
        const lopChe = document.createElement('div')
        lopChe.className = 'translation-anh-sach'
        if (v._phuKinHop) {
          const padKin = 4
          Object.assign(lopChe.style, {
            position: 'absolute',
            zIndex: '1',
            left: `${Math.max(0, oChe.left - padKin)}px`,
            top: `${Math.max(0, oChe.top - padKin)}px`,
            width: `${oChe.width + padKin * 2}px`,
            height: `${oChe.height + padKin * 2}px`,
            background: nenMau,
            borderRadius: v._laHopChuNhat ? '10%' : '28%',
            boxShadow: `0 0 4px 2px ${nenMau}`,
            opacity: '0.99',
            pointerEvents: 'none',
          })
        } else if (anhChe) {
          Object.assign(lopChe.style, {
            position: 'absolute',
            zIndex: '1',
            left: `${oChe.left}px`, top: `${oChe.top}px`,
            width: `${oChe.width}px`, height: `${oChe.height}px`,
            backgroundImage: `url(${anhChe})`,
            backgroundSize: '100% 100%',
            backgroundRepeat: 'no-repeat',
            pointerEvents: 'none',
          })
        } else {
          Object.assign(lopChe.style, {
            position: 'absolute',
            zIndex: '1',
            left: `${oChe.left}px`, top: `${oChe.top}px`,
            width: `${oChe.width}px`, height: `${oChe.height}px`,
            background: nenMau,
            borderRadius: '26%',
            opacity: '0.94',
            pointerEvents: 'none',
          })
        }
        lop.appendChild(lopChe)

        const padY = Math.max(2, Math.round(o.height * 0.02))
        const padX = Math.max(2, Math.round(o.width * 0.025))
        // Với chữ nổi không có bong bóng (`v._laChuNoiTrenNen`, ví dụ chữ đè trên nền cát screentone hoặc tóc đen),
        // tạo viền Halo sắc nét dày 2.5px ôm sát từng con chữ (giống hệt phong cách chữ nổi nguyên bản của manga)
        // mà KHÔNG tạo mảng trắng đục đè mất nền tranh!
        const mauHaloChuNoi = (v._laChuNoiTrenNen && v._mauHaloGocCss)
          ? v._mauHaloGocCss
          : (v.nen_toi ? '#000000' : '#ffffff')
        const vienSangChu = v._laChuNoiTrenNen
          ? [
              `-2px -2px 0 ${mauHaloChuNoi}`,
              `2px -2px 0 ${mauHaloChuNoi}`,
              `-2px 2px 0 ${mauHaloChuNoi}`,
              `2px 2px 0 ${mauHaloChuNoi}`,
              `-2.5px 0 0 ${mauHaloChuNoi}`,
              `2.5px 0 0 ${mauHaloChuNoi}`,
              `0 -2.5px 0 ${mauHaloChuNoi}`,
              `0 2.5px 0 ${mauHaloChuNoi}`,
              `0 0 3.5px ${mauHaloChuNoi}`,
            ].join(', ')
          : ((anhChe && !v._laNenPhucTap)
              ? `0 0 2px ${nenMau}, 0 0 3px ${nenMau}`
              : [
                  `-1px -1px 0 ${nenMau}`,
                  `1px -1px 0 ${nenMau}`,
                  `-1px 1px 0 ${nenMau}`,
                  `1px 1px 0 ${nenMau}`,
                  `0 0 4px ${nenMau}`,
                ].join(', '))

        const lechX = Math.round((v._lechX || 0) * r.width)
        const lechY = Math.round((v._lechY || 0) * r.height)

        const hop = document.createElement('div')
        hop.className = 'translation-hop-chu'
        hop.title = `✏️ Nhấp đúp (Double-click) để sửa câu / phủ kín / cọ xoá / kéo vị trí\nChữ gốc: ${v.chu_goc || '(không rõ)'}${v.kem_tin_cay ? '\n⚠️ OCR kém tin cậy — nên kiểm tra lại câu này' : ''}`
        hop.dataset.nenToi = v.nen_toi ? '1' : '0'
        hop.dataset.chuNoi = v._laChuNoiTrenNen ? '1' : '0'
        Object.assign(hop.style, {
          position: 'absolute',
          zIndex: '2',
          left: `${o.left + lechX}px`, top: `${o.top + lechY}px`,
          width: `${o.width}px`, height: `${o.height}px`,
          background: 'transparent',
          color: chuMau,
          textShadow: vienSangChu,
          webkitTextStroke: v._laChuNoiTrenNen ? `3px ${mauHaloChuNoi}` : '0px transparent',
          paintOrder: 'stroke fill',
          webkitFontSmoothing: 'antialiased',
          // Không vẽ viền vàng nét đứt cho vùng kém tin cậy nữa (người đọc thấy rối mắt); thông tin chuyển vào tooltip.
          border: 'none',
          borderRadius: '8px',
          fontFamily: thongSoFont.css,
          lineHeight: thongSoFont.lineHeight,
          letterSpacing: thongSoFont.letterSpacing,
          wordSpacing: thongSoFont.wordSpacing || '0.09em',
          padding: `${padY}px ${padX}px`, boxSizing: 'border-box',
          display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
          overflow: 'hidden',
          pointerEvents: window[CO].cheDoCoVe ? 'none' : 'auto',
          cursor: 'pointer',
        })

        const noiDung = document.createElement('span')
        noiDung.textContent = v.ban_dich
        noiDung.style.cssText = 'display:inline-block;max-width:100%;word-break:normal;overflow-wrap:normal;text-wrap:balance'
        hop.appendChild(noiDung)
        lop.appendChild(hop)

        const dtGoc = (v.w || 0) * (v.h || 0)
        const laChieuThucLon = (dtGoc >= nw * nh * 0.022) || ((v.w || 0) >= nw * 0.24 && (v.h || 0) >= nh * 0.08)
        const tranThoaiChuan = Math.max(13, Math.min(28, Math.round(r.width * 0.026)))
        const tranChieuThuc = Math.max(22, Math.min(44, Math.round(r.width * 0.044)))

        const coChuVuaKhung = () => {
          const doDaiChu = Math.max(1, (noiDung.textContent || v.ban_dich || '').length)
          const heSo = (window[CO].heSoCoChu || 1) * (v._heSoRieng || 1)
          const uocLuong = coChu(o, doDaiChu)
          const uocLuongThuc = Math.sqrt((o.height * o.width) / Math.max(doDaiChu, 1)) * 1.38
          const tranTren = laChieuThucLon
            ? tranChieuThuc
            : Math.min(
                tranThoaiChuan,
                Math.max(uocLuong + 6, Math.round(uocLuongThuc + 4)),
              )
          const coChuBanDau = Math.max(9, Math.round(tranTren * heSo))
          const sanPx = Math.max(8, Math.round(9 * Math.min(heSo, 1)))
          const rongNoiDungToiDa = Math.max(18, Math.floor(o.width - padX * 2))
          const caoNoiDungToiDa = Math.max(14, Math.floor(o.height - padY * 2))
          // Khi đã có `v._khungCanvas`, khung `o` đã được nội tiếp sẵn bên trong lòng elip của bong bóng (`vanhElipTrongBong`),
          // tuyệt đối không phạt kép `tranGocElip` làm mất 35% chiều cao của các bong bóng dọc!
          const laElipChuaNoiTiep = !v._khungCanvas && !v._laHopChuNhat

          // Đo cỡ chữ tối đa bằng `text-wrap: wrap` trước để `balance` không tự ý ngắt thêm dòng làm co nhỏ cỡ chữ,
          // sau khi tìm được `px` lớn nhất vừa khung mới bật lại `balance` nếu không bị tràn chiều cao.
          noiDung.style.overflowWrap = 'normal'
          noiDung.style.textWrap = 'wrap'
          let px = coChuBanDau
          hop.style.fontSize = `${px}px`
          while (px > sanPx) {
            const tranKhung = (
              hop.scrollHeight > hop.clientHeight ||
              hop.scrollWidth > hop.clientWidth ||
              noiDung.scrollWidth > rongNoiDungToiDa ||
              noiDung.offsetHeight > caoNoiDungToiDa
            )
            const tyLeRong = noiDung.offsetWidth / Math.max(1, o.width)
            const tyLeCao = noiDung.offsetHeight / Math.max(1, o.height)
            const tranGocElip = laElipChuaNoiTiep && noiDung.offsetHeight > px * 1.75 && (tyLeRong * tyLeRong + tyLeCao * tyLeCao) > 1.58
            if (!tranKhung && !tranGocElip) break
            px -= 1
            hop.style.fontSize = `${px}px`
          }
          noiDung.style.textWrap = 'balance'
          if (
            hop.scrollHeight > hop.clientHeight ||
            hop.scrollWidth > hop.clientWidth ||
            noiDung.scrollWidth > rongNoiDungToiDa ||
            noiDung.offsetHeight > caoNoiDungToiDa
          ) {
            noiDung.style.textWrap = 'wrap'
          }
          if (noiDung.scrollWidth > rongNoiDungToiDa || hop.scrollWidth > hop.clientWidth) {
            noiDung.style.overflowWrap = 'break-word'
          }
          return px
        }

        const pxDatDuoc = coChuVuaKhung()
        dsHopDaVe.push({ hop, v, px: pxDatDuoc, doDai: (v.ban_dich || '').length, laChieuThucLon })

        // E105 (#6) — Nhấp đúp chuột vào bất kỳ bóng thoại nào để sửa chữ / phóng to / dịch lại / phủ kín / cọ xoá tức thì
        hop.addEventListener('dblclick', (e) => {
          e.preventDefault()
          e.stopPropagation()
          moTrinhSuaBongThoai({ hop, noiDung, v, coChuVuaKhung, rLop: r })
        })
      }

      // Lớp 1.5 (`canvasCoVe` — Cọ vẽ tay Brush Inpaint trực tiếp trên Canvas tiện ích):
      // Nằm ở `zIndex: 1` (trên ảnh gốc & lớp xoá nền tự động, nhưng dưới lớp chữ dịch `zIndex: 2`)
      // để người dùng tô xoá bất kỳ chữ gốc/SFX nào còn sót mà không bao giờ xoá nhầm chữ đã dịch!
      const nhatKyCo = el.__translationNhatKyCoVe || []
      if (nhatKyCo.length > 0 || window[CO].cheDoCoVe) {
        const canvasCo = document.createElement('canvas')
        canvasCo.className = 'translation-co-ve'
        canvasCo.width = Math.max(1, Math.round(r.width))
        canvasCo.height = Math.max(1, Math.round(r.height))
        Object.assign(canvasCo.style, {
          position: 'absolute',
          left: '0px',
          top: '0px',
          width: `${r.width}px`,
          height: `${r.height}px`,
          zIndex: '1',
          pointerEvents: window[CO].cheDoCoVe ? 'auto' : 'none',
          cursor: window[CO].cheDoCoVe ? 'crosshair' : 'default',
          touchAction: window[CO].cheDoCoVe ? 'none' : 'auto',
        })
        const ctxCo = canvasCo.getContext('2d')
        const veLaiNhatKyCo = () => {
          ctxCo.clearRect(0, 0, canvasCo.width, canvasCo.height)
          const Wc = canvasCo.width
          const Hc = canvasCo.height
          for (const net of (el.__translationNhatKyCoVe || [])) {
            if (!net?.diem?.length) continue
            ctxCo.save()
            ctxCo.strokeStyle = net.mau || '#ffffff'
            ctxCo.fillStyle = net.mau || '#ffffff'
            ctxCo.lineCap = 'round'
            ctxCo.lineJoin = 'round'
            ctxCo.lineWidth = Math.max(6, Math.round((net.co || 0.022) * Wc))
            ctxCo.beginPath()
            const [d0x, d0y] = net.diem[0]
            ctxCo.moveTo(d0x * Wc, d0y * Hc)
            if (net.diem.length === 1) {
              ctxCo.arc(d0x * Wc, d0y * Hc, ctxCo.lineWidth * 0.5, 0, Math.PI * 2)
              ctxCo.fill()
            } else {
              for (let i = 1; i < net.diem.length; i += 1) {
                ctxCo.lineTo(net.diem[i][0] * Wc, net.diem[i][1] * Hc)
              }
              ctxCo.stroke()
            }
            ctxCo.restore()
          }
        }
        veLaiNhatKyCo()

        if (window[CO].cheDoCoVe) {
          canvasCo.addEventListener('mousedown', (ev) => {
            if (ev.button !== 0) return
            ev.preventDefault()
            ev.stopPropagation()
            const rectC = canvasCo.getBoundingClientRect()
            const nx0 = Math.max(0, Math.min(1, (ev.clientX - rectC.left) / Math.max(1, rectC.width)))
            const ny0 = Math.max(0, Math.min(1, (ev.clientY - rectC.top) / Math.max(1, rectC.height)))
            const mauVe = layMauNenTaiDiemCoVe(el, nx0, ny0, window[CO].mauCoVeUuTien)
            if (!Array.isArray(el.__translationNhatKyCoVe)) el.__translationNhatKyCoVe = []
            const netMoi = {
              mau: mauVe,
              co: 0.022,
              diem: [[nx0, ny0]],
            }
            el.__translationNhatKyCoVe.push(netMoi)
            lop.__dangKeoCoVe = true
            veLaiNhatKyCo()

            const onMoveCo = (mv) => {
              const rNow = canvasCo.getBoundingClientRect()
              const nx = Math.max(0, Math.min(1, (mv.clientX - rNow.left) / Math.max(1, rNow.width)))
              const ny = Math.max(0, Math.min(1, (mv.clientY - rNow.top) / Math.max(1, rNow.height)))
              netMoi.diem.push([nx, ny])
              veLaiNhatKyCo()
            }
            const onUpCo = () => {
              lop.__dangKeoCoVe = false
              window.removeEventListener('mousemove', onMoveCo, true)
              window.removeEventListener('mouseup', onUpCo, true)
            }
            window.addEventListener('mousemove', onMoveCo, true)
            window.addEventListener('mouseup', onUpCo, true)
          })
        }
        lop.appendChild(canvasCo)
      }

      // Đồng bộ cỡ chữ hài hoà toàn trang (`dongBoCoChuToanTrang`):
      // Giữ các bóng thoại thường trong dải đồng nhất xoay quanh P75 của trang (không bị bóng rộng phình quá cỡ so với bóng kế bên),
      // nhưng TUYỆT ĐỐI KHÔNG lấy bóng thoại hẹp làm chuẩn ép nhỏ cả trang, và KHÔNG đụng vào đại chiêu thức lớn (`laChieuThucLon`, ví dụ "CUỒNG SA ĐỊA NGỤC"!)
      const dsPxThoai = dsHopDaVe
        .filter((m) => !m.v._heSoRieng && !m.laChieuThucLon && m.doDai >= 12)
        .map((m) => m.px)
        .sort((a, b) => a - b)
      if (dsPxThoai.length >= 2) {
        const pxP75 = dsPxThoai[Math.min(dsPxThoai.length - 1, Math.floor(dsPxThoai.length * 0.75))]
        const tranThoaiChuanTrang = Math.max(13, Math.min(28, Math.round(r.width * 0.026)))
        const tran = Math.max(Math.round(r.width * 0.023), Math.min(tranThoaiChuanTrang, Math.round(pxP75 * 1.15)))
        for (const m of dsHopDaVe) {
          if (m.v._heSoRieng || m.laChieuThucLon) continue
          if (m.px > tran) {
            m.px = tran
            m.hop.style.fontSize = `${tran}px`
          }
        }
      }
    }

    ve()
    ro.observe(el)
    if (mo) mo.observe(el, { attributes: true, attributeFilter: ['src', 'srcset'] })
    el.addEventListener('load', goiVe)
    window.addEventListener('scroll', goiVe, { passive: true, capture: true })
    window.addEventListener('resize', goiVe, { passive: true })
    window.addEventListener('translation:ve-lai', goiVe)
    return lop
  }

  // Đọc ẢNH THẬT bằng canvas ngay tại đây trước khi nhờ service worker tải lại bằng URL.
  //
  // Bắt buộc phải thử ở ĐÂY: `blob:`/`data:` mà trang tự tạo (MangaPlus tự giải mã ảnh rồi phát
  // qua `blob:` — đo được 07/09) chỉ sống trong đúng tài liệu đã tạo ra nó. Service worker là một
  // ngữ cảnh THỰC THI khác (kể cả cùng origin), `fetch()` một `blob:` từ đó luôn ném lỗi mạng
  // trần trụi "Failed to fetch" — không phải lỗi cấu hình, không có cách nào sửa bằng quyền hay
  // header. Canvas ở ĐÚNG tài liệu đang hiển thị ảnh thì không bị coi là khác nguồn, nên đọc được.
  //
  // Ảnh https bình thường (đa số trang) thì NGƯỢC LẠI: rất nhiều máy chủ không gắn CORS header,
  // vẽ lên canvas ở đây sẽ "nhiễm bẩn" (`SecurityError` khi xuất byte) — đó là lý do bản đầu cố ý
  // tránh canvas, dồn hết việc tải xuống service worker. Nên thử canvas TRƯỚC, hỏng thì rơi về
  // đường cũ (gửi URL, để service worker tự tải bằng `host_permissions`) — không đoán trước loại
  // ảnh nào đi đường nào.
  async function blobSangBase64(blob) {
    const bytes = new Uint8Array(await blob.arrayBuffer())
    let nhi_phan = ''
    for (let i = 0; i < bytes.length; i += 0x8000) {
      nhi_phan += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
    }
    return { anh_base64: btoa(nhi_phan), anh_mime: blob.type || 'image/jpeg' }
  }

  async function docByteAnh(el) {
    const w = el.naturalWidth || el.width || 0
    const h = el.naturalHeight || el.height || 0
    const src = el.currentSrc || el.src || el.dataset?.translationLazySrc || ''

    // Lớp 1: Đọc trực tiếp qua Canvas 2D (nhanh nhất, ăn ngay với cùng tên miền, blob:, data:, hoặc thẻ <canvas>)
    if (w > 0 && h > 0) {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = w
        canvas.height = h
        const ctx = canvas.getContext('2d', { willReadFrequently: true })
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.drawImage(el, 0, 0, w, h)
        try {
          ctx.getImageData(0, 0, 1, 1)
          el.__translationCtxMau = ctx
          el.__translationCtxSrc = src
        } catch {}
        const blob = await new Promise((resolve, reject) => {
          canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('canvas rỗng'))), 'image/jpeg', 0.88)
        })
        return await blobSangBase64(blob)
      } catch {
        // Bị chặn CORS trên canvas -> chuyển sang Lớp 2
      }
    }

    // Lớp 2: Tải trực tiếp từ Content Script kèm Cookie + Referer của trang đang đọc
    // (Vượt qua các trang chặn Hotlink / kiểm tra Referer / bảo vệ Cloudflare Cookie)
    if (src && /^https?:\/\//i.test(src)) {
      try {
        const res = await fetch(src, {
          credentials: 'include',
          referrerPolicy: 'no-referrer-when-downgrade',
        })
        if (res.ok) {
          const blob = await res.blob()
          if (blob.size > 1024 && (!blob.type || blob.type.startsWith('image/') || blob.type.includes('octet-stream'))) {
            const kq = await blobSangBase64(blob)
            await napCanvasTuDataUrl(el, `data:${kq.anh_mime};base64,${kq.anh_base64}`)
            return kq
          }
        }
      } catch {
        // Nếu CDN chặn CORS cho fetch ở content script -> để Lớp 3 (Service Worker có host_permissions) xử lý
      }
    }

    // Lớp 3: Nếu là thẻ <canvas> bị khoá DRM/tainted hoặc ảnh blob: bị khoá -> Tự động chụp vùng hiển thị
    if (el.tagName === 'CANVAS' || src.startsWith('blob:')) {
      try {
        const r = el.getBoundingClientRect()
        if (r.width >= 120 && r.height >= 120) {
          const chup = await chrome.runtime.sendMessage({ viec: 'chup-man-hinh' })
          if (chup?.ok && chup?.data_url) {
            const anhChup = new Image()
            await new Promise((resolve, reject) => {
              anhChup.onload = resolve
              anhChup.onerror = reject
              anhChup.src = chup.data_url
            })
            const dpr = window.devicePixelRatio || 1
            const c = document.createElement('canvas')
            c.width = Math.max(1, Math.round(r.width * dpr))
            c.height = Math.max(1, Math.round(r.height * dpr))
            const ctx = c.getContext('2d')
            ctx.drawImage(
              anhChup,
              Math.max(0, Math.round(r.left * dpr)),
              Math.max(0, Math.round(r.top * dpr)),
              c.width,
              c.height,
              0,
              0,
              c.width,
              c.height,
            )
            const blob = await new Promise((resolve) => c.toBlob(resolve, 'image/jpeg', 0.88))
            if (blob) {
              const kq = await blobSangBase64(blob)
              await napCanvasTuDataUrl(el, `data:${kq.anh_mime};base64,${kq.anh_base64}`)
              return kq
            }
          }
        }
      } catch {
        // Bỏ qua nếu không chụp được
      }
    }

    // Rơi về gửi URL cho Service Worker tải bằng `host_permissions: <all_urls>`
    return { anh_base64: null, anh_mime: null }
  }

  /**
   * E98 — Xếp hàng dịch đón đầu trang kế tiếp (N+1) CHỈ KHI người dùng đang bật công tắc
   * "🔄 Tự dịch khi cuộn" và ở chế độ "Phủ hộp chữ nhanh" (`chi_chu`).
   *
   * Vì sao không tự chạy ngầm khi người dùng chỉ bấm "Dịch trang này" 1 lần:
   * 1. Máy chủ chạy 1 worker tuần tự: nếu tự động xếp thêm 2 trang N+1, N+2 (nhất là ở chế độ `day_du`
   *    tốn ~2 phút/trang xoá chữ LaMa), worker sẽ bị khoá cứng 4-5 phút, khiến lần bấm kế tiếp của
   *    chính người dùng phải chờ hàng đợi rất lâu.
   * 2. Tự động dịch ngầm khi chưa bật "Tự dịch khi cuộn" sẽ âm thầm trừ mất lượt miễn phí của khách.
   */
  function xepHangTrangKeTiep(mo_ta_hien_tai, boQuaSrc) {
    if (!window[CO].tuDichKhiCuon) return

    const danh_sach_ke = typeof chonCacTrangKeTiep === 'function'
      ? chonCacTrangKeTiep(mo_ta_hien_tai, { caoKhungNhin: window.innerHeight, boQuaSrc, toiDa: 1 })
      : [chonTrangKeTiep(mo_ta_hien_tai, { caoKhungNhin: window.innerHeight, boQuaSrc }).anh].filter(Boolean)

    if (!danh_sach_ke.length) return

    ;(async () => {
      const { cheDo, ngonNgu, ngonNguDich, engine } = await layCauHinhHienTai()
      for (const ke of danh_sach_ke) {
        if (!window[CO].tuDichKhiCuon) break
        const src = ke.src
        const khoa = khoaCache(src, cheDo, ngonNgu, engine, ngonNguDich)
        if (!src || window[CO].daDich.has(khoa) || window[CO].dangXepHang.has(khoa)) continue
        window[CO].dangXepHang.add(khoa)
        try {
          const { anh_base64, anh_mime } = await docByteAnh(ke.el)
          const tra_ke = await chrome.runtime.sendMessage({
            viec: 'dich-anh', url: src, anh_base64, anh_mime, ngam: true,
          })
          if (tra_ke?.ok) {
            const elSong = ke.el?.isConnected ? ke.el : timAnhTheoSrc(src)
            if (elSong && tra_ke.anh_goc_data_url) {
              await napCanvasTuDataUrl(elSong, tra_ke.anh_goc_data_url)
            }
            const goi = {
              vung: tra_ke.vung,
              anh_da_dich: tra_ke.anh_da_dich || null,
              anh_goc_data_url: tra_ke.anh_goc_data_url || null,
              _ctxMau: elSong?.__translationCtxMau || ke.el?.__translationCtxMau || null,
              _naturalWidth: ke.naturalWidth,
              _naturalHeight: ke.naturalHeight,
              _docTop: ke.docTop,
            }
            window[CO].daDich.set(khoaCache(src, tra_ke.che_do || cheDo, ngonNgu, engine, ngonNguDich), goi)
            vePhu(elSong || ke.el, goi)
          } else if (tra_ke?.ma === 429 || tra_ke?.ma === 401) {
            // Hết hạn mức hoặc hết phiên đăng nhập thì dừng luôn chuỗi nạp đón đầu.
            break
          }
        } catch {
          // Im lặng có chủ đích — bấm dịch lại trang đó sau này sẽ chạy như bình thường.
        } finally {
          window[CO].dangXepHang.delete(khoa)
        }
      }
    })()
  }

  // Tách hàm vì cần gọi LẠI sau khi chờ dịch xong (~45s) để xếp hàng trước trang kế tiếp — dùng
  // mô tả chụp từ ĐẦU quy trình lúc đó đã cũ 45 giây, đúng loại "phần tử có thể đã chết giữa
  // chừng" vừa gặp ở chính ảnh đang dịch (§E19.6e).
  function moKhoaChongDichVaChongCopy() {
    if (window[CO].daMoKhoaTrang) return
    window[CO].daMoKhoaTrang = true
    try {
      document.documentElement?.removeAttribute?.('translate')
      document.body?.removeAttribute?.('translate')
      document.querySelectorAll('[translate="no"], .notranslate').forEach((el) => {
        el.removeAttribute('translate')
        el.classList.remove('notranslate')
      })
      const styleMoKhoa = document.createElement('style')
      styleMoKhoa.id = 'translation-mo-khoa-css'
      styleMoKhoa.textContent = `
        body, article, main, p, .chapter-content, .reading-content, #novel_honbun {
          -webkit-user-select: text !important;
          user-select: text !important;
        }
      `
      document.head?.appendChild?.(styleMoKhoa)
    } catch {
      // Bỏ qua nếu trang khóa DOM
    }
  }

  function layMoTa() {
    moKhoaChongDichVaChongCopy()
    const ds = []
    for (const el of document.images) {
      // Đánh thức các trang gắn lazy-load (`data-src`, `data-original`, `data-lazy-src`) nhưng chưa nạp vào `src`
      const lazySrc =
        el.getAttribute('data-src') ||
        el.getAttribute('data-original') ||
        el.getAttribute('data-lazy-src') ||
        el.getAttribute('data-url')
      if (lazySrc && (!el.src || el.src.startsWith('data:image/gif') || el.src.startsWith('data:image/svg'))) {
        el.dataset.translationLazySrc = lazySrc
        try { el.src = lazySrc } catch {}
      }
      const r = el.getBoundingClientRect()
      if (r.width >= 40 && r.height >= 40) {
        el.__translationDocTop = window.scrollY + r.top
      }
      el.__translationCha1 = el.parentElement || null
      el.__translationCha2 = el.parentElement?.parentElement || null
      el.__translationCha3 = el.parentElement?.parentElement?.parentElement || null
      let mo = false
      for (let n = el, dem = 0; n instanceof Element && dem < 4; n = n.parentElement, dem++) {
        const f = getComputedStyle(n).filter
        // Chỉ coi là nền trang trí lightbox khi có hiệu ứng làm mờ `blur(...)`
        if (f && f.includes('blur(')) { mo = true; break }
      }
      ds.push({
        el,
        src: el.currentSrc || el.src || el.dataset?.translationLazySrc || '',
        naturalWidth: el.naturalWidth || Math.round(r.width),
        naturalHeight: el.naturalHeight || Math.round(r.height),
        clientWidth: r.width,
        clientHeight: r.height,
        top: r.top,
        bottom: r.bottom,
        docTop: window.scrollY + r.top,
        mo,
      })
    }

    // Hỗ trợ tự động các trang vẽ truyện lên thẻ <canvas> (MangaPlus, KakaoPage, Ridibooks, Bilibili...)
    const dsCanvas = document.getElementsByTagName('canvas')
    for (let idx = 0; idx < dsCanvas.length; idx += 1) {
      const cv = dsCanvas[idx]
      if (cv.closest(`.${LOP_CLASS}`)) continue
      const r = cv.getBoundingClientRect()
      const w = cv.width || Math.round(r.width)
      const h = cv.height || Math.round(r.height)
      if (w < 200 || h < 200 || r.width < 180 || r.height < 180) continue
      const docTopCv = window.scrollY + r.top
      cv.__translationDocTop = docTopCv
      cv.__translationCha1 = cv.parentElement || null
      cv.__translationCha2 = cv.parentElement?.parentElement || null
      cv.__translationCha3 = cv.parentElement?.parentElement?.parentElement || null
      if (!cv.dataset.translationCanvasId) {
        const viTriSlot = Math.round(docTopCv / 100) * 100
        cv.dataset.translationCanvasId = `canvas://page-top${viTriSlot}-${w}x${h}`
      }
      // Gắn thuộc tính tương thích với <img> để mọi hàm quy đổi toạ độ (`sanSangQuyDoi`, `vePhu`, `doKhungBongBongCanvas`) hoạt động 100% đồng nhất
      try {
        cv.naturalWidth = w
        cv.naturalHeight = h
        cv.src = cv.dataset.translationCanvasId
      } catch {}
      ds.push({
        el: cv,
        src: cv.dataset.translationCanvasId,
        naturalWidth: w,
        naturalHeight: h,
        clientWidth: r.width,
        clientHeight: r.height,
        top: r.top,
        bottom: r.bottom,
        docTop: docTopCv,
        mo: false,
      })
    }
    return ds
  }

  /**
   * E108 — Dịch trực tiếp các trang Truyện Chữ / Light Novel / Web Novel (Syosetu, Kakuyomu, 69shuba, Wattpad...)
   * khi trang không có ảnh truyện tranh mà chứa các đoạn văn bản truyện chữ.
   */
  async function dichTruyenChuTrenTrang({ caChapter = false } = {}) {
    const boChon = 'article p, main p, #novel_honbun p, .chapter-content p, .reading-content p, .novel-content p, .entry-content p, p'
    const tatCaDoan = [...document.querySelectorAll(boChon)].filter((el) => {
      if (el.closest(`.${LOP_CLASS}`) || el === bang || bang.contains(el)) return false
      if (el.dataset?.translationDaDichChu === '1') return false
      const r = el.getBoundingClientRect()
      if (r.width < 120 || r.height < 10) return false
      if (!caChapter && (r.bottom < -100 || r.top > window.innerHeight + 300)) return false
      const text = (el.innerText || el.textContent || '').trim()
      return text.length >= 18
    })

    if (tatCaDoan.length < 2) return false

    const { ngonNgu, ngonNguDich } = await layCauHinhHienTai()
    const gioiHan = caChapter ? Math.min(tatCaDoan.length, 160) : Math.min(tatCaDoan.length, 28)
    const dsMucTieu = tatCaDoan.slice(0, gioiHan)
    noi(`📖 Phát hiện trang Truyện chữ (${dsMucTieu.length} đoạn văn).\nĐang dịch sang ${ngonNguDich === 'en' ? 'Tiếng Anh (EN)' : 'Tiếng Việt (VI)'}…`)

    const KICH_THUOC_LO = 12
    let daXong = 0
    for (let i = 0; i < dsMucTieu.length; i += KICH_THUOC_LO) {
      const lo = dsMucTieu.slice(i, i + KICH_THUOC_LO)
      const dsText = lo.map((el) => (el.innerText || el.textContent || '').trim())
      const kq = await chrome.runtime.sendMessage({
        viec: 'dich-doan-van-truyen-chu',
        ds_doan: dsText,
        ngon_ngu: ngonNgu,
        ngon_ngu_dich: ngonNguDich,
      })
      if (kq?.ok && Array.isArray(kq.ds_ban_dich)) {
        lo.forEach((el, idx) => {
          const banDich = (kq.ds_ban_dich[idx] || '').trim()
          if (!banDich) return
          el.dataset.translationDaDichChu = '1'
          el.dataset.translationChuGoc = dsText[idx]
          el.textContent = banDich
          el.title = `Nguyên văn: ${dsText[idx]}`
          daXong += 1
        })
      }
      noi(`📖 Đang dịch Truyện chữ: ${daXong}/${dsMucTieu.length} đoạn…`)
    }

    caiCongTacSoSanhGoc()
    xong(`✅ Đã dịch xong ${daXong} đoạn văn Truyện chữ trên trang!`, 8)
    return daXong > 0
  }

  // ─────────────────────────────────────────────────────────────────────────────────────────
  // E59 — DỊCH CẢ CHAPTER
  //
  // Chủ dự án chốt (28-09-2026) xây hướng này, sau khi `ARCH.md §E19.6f` đã từ chối nó một lần.
  // Hai lý do từ chối lúc đó, và trạng thái nay:
  //
  //  1. "Không nhanh hơn" — VẪN ĐÚNG, và đã nói lại với chủ dự án. Máy chủ chạy 1 việc/lúc,
  //     CPU-bound, và 2,6 CPU đã là trần của gói. Xếp 24 trang thì trang cuối vẫn đợi ~18 phút.
  //     Cái tính năng này đổi là **không phải ngồi bấm từng trang**, không phải tổng thời gian.
  //  2. "Ranh giới bản quyền" — chủ dự án quyết định, và đã quyết.
  //
  // Vì (1) vẫn đúng, thông báo phải nói thẳng con số chứ không để người dùng tưởng nó nhanh.
  // ─────────────────────────────────────────────────────────────────────────────────────────

  //: Trần cứng số trang mỗi lượt. Trang cuộn vô tận (danh sách gợi ý, bình luận có ảnh) không có
  //: điểm kết thúc tự nhiên — thiếu trần này là một lượt bấm có thể chạy cả đêm.
  const TRAN_TRANG_MOI_LUOT = 200
  //: Trần số lượt cuộn-để-nạp-thêm khi không thấy trang mới. Bảo vệ cùng một chuyện.
  const TRAN_VONG_CUON = 80

  async function cuonDeNapThem(soSrcHienCo) {
    // Cuộn cho tới khi CÓ ẢNH MỚI hoặc HẾT TRANG — không phải cuộn một nhịp rồi bỏ.
    //
    // Bản đầu (0.1.13) cuộn đúng một nhịp `0,85 × khung nhìn` rồi trả `false` nếu chưa thấy ảnh
    // mới, và bên gọi `break` luôn. Đo trên trang thật: khung nhìn **437px**, tài liệu **5227px**
    // ⇒ một nhịp 371px không tới được ảnh kế tiếp, nên cả lượt quét dừng ở trang thứ 3 trong khi
    // còn **4790px chưa xem** và tập truyện còn 2 trang. Lỗi này không test đơn vị nào bắt được:
    // nó chỉ tồn tại khi có trang thật, nạp lười thật, và một khung nhìn thật.
    //
    // Nhịp tối thiểu 400px vì khung nhìn có thể rất thấp (cửa sổ nhỏ, headless) — lấy theo tỉ lệ
    // khung nhìn một mình thì trang cao 5000px cần hàng chục nhịp.
    const NHIP_TOI_DA = 60
    const den_day = () => (
      window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2
    )
    for (let nhip = 0; nhip < NHIP_TOI_DA; nhip++) {
      const truoc = Math.round(window.scrollY)
      window.scrollBy(0, Math.max(400, Math.round(window.innerHeight * 0.85)))
      await new Promise((r) => setTimeout(r, 350))
      if (chonMoiTrang(layMoTa()).danh_sach.length > soSrcHienCo) return true
      // Không nhích được nữa (đã ở đáy, hoặc trang chặn cuộn) ⇒ chờ thêm một nhịp cho ảnh cuối
      // kịp nạp RỒI mới kết luận. Kết luận ngay là bỏ sót đúng trang cuối chapter.
      if (den_day() || Math.round(window.scrollY) === truoc) {
        await new Promise((r) => setTimeout(r, 1500))
        return chonMoiTrang(layMoTa()).danh_sach.length > soSrcHienCo
      }
    }
    return false
  }

  // ─────────────────────────────────────────────────────────────────────────────────────────
  // E60 — KHOANH VÙNG DỊCH TRÊN MÀN HÌNH (dành cho trang vẽ bằng <canvas> / DRM chống sao chép)
  // ─────────────────────────────────────────────────────────────────────────────────────────
  async function khoanhVungDich() {
    noi('Kéo chuột chọn vùng truyện cần dịch (bấm Esc để huỷ)…')
    const manChe = document.createElement('div')
    manChe.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:2147483646',
      'cursor:crosshair', 'background:rgba(0,0,0,.22)', 'user-select:none',
    ].join(';')
    const khungChon = document.createElement('div')
    khungChon.style.cssText = [
      'position:fixed', 'border:2px dashed #38bdf8', 'background:rgba(56,189,248,.12)',
      'pointer-events:none', 'display:none',
    ].join(';')
    manChe.appendChild(khungChon)
    document.documentElement.appendChild(manChe)

    const vungChon = await new Promise((resolve) => {
      let x0 = 0
      let y0 = 0
      let dangKeo = false

      const huy = (e) => {
        if (e.key === 'Escape') {
          donDep()
          resolve(null)
        }
      }
      const batDau = (e) => {
        if (e.button !== 0) return
        dangKeo = true
        x0 = e.clientX
        y0 = e.clientY
        khungChon.style.display = 'block'
        khungChon.style.left = `${x0}px`
        khungChon.style.top = `${y0}px`
        khungChon.style.width = '0px'
        khungChon.style.height = '0px'
      }
      const diChuyen = (e) => {
        if (!dangKeo) return
        const left = Math.min(x0, e.clientX)
        const top = Math.min(y0, e.clientY)
        const width = Math.abs(e.clientX - x0)
        const height = Math.abs(e.clientY - y0)
        Object.assign(khungChon.style, {
          left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px`,
        })
      }
      const ketThuc = (e) => {
        if (!dangKeo) return
        dangKeo = false
        const left = Math.min(x0, e.clientX)
        const top = Math.min(y0, e.clientY)
        const width = Math.abs(e.clientX - x0)
        const height = Math.abs(e.clientY - y0)
        donDep()
        if (width < 24 || height < 24) {
          resolve(null)
          return
        }
        resolve({ left, top, width, height })
      }
      const donDep = () => {
        window.removeEventListener('keydown', huy)
        manChe.remove()
      }

      window.addEventListener('keydown', huy)
      manChe.addEventListener('mousedown', batDau)
      manChe.addEventListener('mousemove', diChuyen)
      manChe.addEventListener('mouseup', ketThuc)
    })

    if (!vungChon) {
      window[CO].dangChay = false
      xong('Đã huỷ khoanh vùng dịch.', 3)
      return
    }

    // Ẩn tạm bảng thông báo trước khi chụp màn hình để ảnh chụp không dính chính hộp thông báo.
    bang.style.display = 'none'
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
    const chup = await chrome.runtime.sendMessage({ viec: 'chup-man-hinh' })
    bang.style.display = ''

    if (!chup?.ok || !chup?.data_url) {
      window[CO].dangChay = false
      xong(`Không chụp được màn hình: ${chup?.loi || 'không rõ lý do'}`, 8)
      return
    }

    noi('Đang cắt vùng chọn và gửi dịch…')
    const anhChup = new Image()
    await new Promise((resolve, reject) => {
      anhChup.onload = resolve
      anhChup.onerror = reject
      anhChup.src = chup.data_url
    })

    const dpr = window.devicePixelRatio || 1
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(vungChon.width * dpr))
    canvas.height = Math.max(1, Math.round(vungChon.height * dpr))
    const ctxSnip = canvas.getContext('2d')
    ctxSnip.fillStyle = '#ffffff'
    ctxSnip.fillRect(0, 0, canvas.width, canvas.height)
    ctxSnip.drawImage(
      anhChup,
      Math.round(vungChon.left * dpr),
      Math.round(vungChon.top * dpr),
      canvas.width,
      canvas.height,
      0,
      0,
      canvas.width,
      canvas.height,
    )
    const dataUrl = canvas.toDataURL('image/jpeg', 0.88)
    const anh_base64 = dataUrl.split(',')[1]

    const tra = await chrome.runtime.sendMessage({
      viec: 'dich-anh',
      url: `snip://${Date.now()}`,
      anh_base64,
      anh_mime: 'image/jpeg',
    })
    window[CO].dangChay = false

    if (!tra?.ok) {
      xong(`Không dịch được vùng đã chọn.\n${tra?.loi || 'không rõ lý do'}`, 12)
      return
    }

    caiCongTacSoSanhGoc()
    const hopSnip = document.createElement('div')
    hopSnip.className = LOP_CLASS
    hopSnip.style.cssText = [
      'position:fixed', 'z-index:2147483646',
      `left:${vungChon.left}px`, `top:${vungChon.top}px`,
      `width:${vungChon.width}px`, `height:${vungChon.height}px`,
      'box-shadow:0 4px 18px rgba(0,0,0,.35)', 'border:1px solid #38bdf8', 'border-radius:6px',
    ].join(';')

    const nutDong = document.createElement('button')
    nutDong.type = 'button'
    nutDong.textContent = '✕'
    nutDong.title = 'Đóng khung dịch vùng này'
    nutDong.style.cssText = [
      'position:absolute', 'right:-10px', 'top:-10px', 'z-index:2',
      'width:22px', 'height:22px', 'border-radius:999px', 'border:none',
      'background:#ef4444', 'color:#fff', 'font:bold 12px/22px system-ui,sans-serif',
      'cursor:pointer', 'pointer-events:auto',
    ].join(';')
    nutDong.addEventListener('click', () => hopSnip.remove())
    hopSnip.appendChild(nutDong)

    if (tra.anh_da_dich) {
      const img = document.createElement('img')
      img.src = tra.anh_da_dich
      img.style.cssText = 'width:100%;height:100%;object-fit:fill;display:block;border-radius:5px'
      hopSnip.appendChild(img)
    } else {
      const elAo = {
        naturalWidth: canvas.width,
        naturalHeight: canvas.height,
        currentSrc: 'snip://canvas',
        __translationCtxMau: ctxSnip,
        __translationCtxSrc: 'snip://canvas',
      }
      const vungSnip = (tra.vung || []).filter((v) => Boolean(v.ban_dich))
      const thongSoSnip = {
        naturalWidth: canvas.width,
        naturalHeight: canvas.height,
        clientWidth: vungChon.width,
        clientHeight: vungChon.height,
      }
      const dsOChe = vungSnip.map((v) => {
        doKhungBongBongCanvas(elAo, v, vungSnip)
        return quyDoi(v._khungCheCanvas || v, thongSoSnip)
      })
      const dsOGoc = vungSnip.map((v) => ({
        ...quyDoi(doKhungBongBongCanvas(elAo, v, vungSnip) || v, thongSoSnip),
        soKyTu: v.ban_dich.length,
      }))

      for (let idx = 0; idx < vungSnip.length; idx += 1) {
        const v = vungSnip[idx]
        const oChe = dsOChe[idx]
        const o = dsOGoc[idx]
        const anhChe = taoAnhCheChuCanvas(elAo, v, vungSnip)
        const nenMau = v._mauNenCss || (v.nen_toi ? '#000000' : '#ffffff')
        const chuMau = v.nen_toi ? '#ffffff' : '#000000'

        const lopChe = document.createElement('div')
        if (anhChe) {
          Object.assign(lopChe.style, {
            position: 'absolute',
            zIndex: '1',
            left: `${oChe.left}px`, top: `${oChe.top}px`,
            width: `${oChe.width}px`, height: `${oChe.height}px`,
            backgroundImage: `url(${anhChe})`,
            backgroundSize: '100% 100%',
            backgroundRepeat: 'no-repeat',
            pointerEvents: 'none',
          })
        } else {
          Object.assign(lopChe.style, {
            position: 'absolute',
            zIndex: '1',
            left: `${oChe.left}px`, top: `${oChe.top}px`,
            width: `${oChe.width}px`, height: `${oChe.height}px`,
            background: nenMau,
            borderRadius: '38%',
            pointerEvents: 'none',
          })
        }
        hopSnip.appendChild(lopChe)

        const padY = Math.max(2, Math.round(o.height * 0.055))
        const padX = Math.max(3, Math.round(o.width * 0.07))
        const uocLuong = coChu(o, v.ban_dich.length)
        const coChuBanDau = Math.min(28, Math.max(uocLuong + 6, Math.round(Math.min(o.width, o.height) * 0.46)))
        const vienSangChu = (anhChe && !v._laNenPhucTap)
          ? `0 0 2px ${nenMau}, 0 0 3px ${nenMau}`
          : [
              `-1px -1px 0 ${nenMau}`,
              `1px -1px 0 ${nenMau}`,
              `-1px 1px 0 ${nenMau}`,
              `1px 1px 0 ${nenMau}`,
              `0 0 4px ${nenMau}`,
            ].join(', ')
        const thongSoFontSnip = layThongSoFont(window[CO].fontChuHienTai)
        const hop = document.createElement('div')
        hop.className = 'translation-hop-chu'
        hop.title = `✏️ Nhấp đúp (Double-click) để sửa nhanh câu này\nChữ gốc: ${v.chu_goc || '(không rõ)'}`
        Object.assign(hop.style, {
          position: 'absolute',
          zIndex: '2',
          left: `${o.left}px`, top: `${o.top}px`,
          width: `${o.width}px`, height: `${o.height}px`,
          background: 'transparent', color: chuMau,
          textShadow: vienSangChu,
          border: 'none', borderRadius: v._laHopChuNhat ? '12%' : '46%',
          fontFamily: thongSoFontSnip.css,
          fontSize: `${coChuBanDau}px`,
          lineHeight: thongSoFontSnip.lineHeight,
          letterSpacing: thongSoFontSnip.letterSpacing,
          padding: `${padY}px ${padX}px`, boxSizing: 'border-box',
          display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
          overflow: 'hidden', pointerEvents: 'auto', cursor: 'pointer',
        })
        const noiDung = document.createElement('span')
        noiDung.textContent = v.ban_dich
        noiDung.style.cssText = 'display:inline-block;max-width:100%;word-break:normal;overflow-wrap:normal;text-wrap:balance'
        hop.appendChild(noiDung)
        hopSnip.appendChild(hop)
        const coChuSnip = () => {
          let px = Math.round(coChuBanDau * (v._heSoRieng || 1))
          hop.style.fontSize = `${px}px`
          while (
            px > 9 &&
            (hop.scrollHeight > hop.clientHeight + 1 ||
              hop.scrollWidth > hop.clientWidth + 1 ||
              noiDung.scrollWidth > noiDung.clientWidth + 1)
          ) {
            px -= 1
            hop.style.fontSize = `${px}px`
          }
        }
        hop.addEventListener('dblclick', (e) => {
          e.preventDefault()
          e.stopPropagation()
          moTrinhSuaBongThoai({ hop, noiDung, v, coChuVuaKhung: coChuSnip })
        })
      }
    }

    document.documentElement.appendChild(hopSnip)
    // Sau khi hopSnip đã gắn vào DOM, co cỡ chữ vừa khít từng ô
    hopSnip.querySelectorAll('div > span').forEach((noiDung) => {
      const hop = noiDung.parentElement
      let px = parseInt(hop.style.fontSize, 10) || 16
      while (
        px > 9 &&
        (hop.scrollHeight > hop.clientHeight + 1 ||
          hop.scrollWidth > hop.clientWidth + 1 ||
          noiDung.scrollWidth > noiDung.clientWidth + 1)
      ) {
        px -= 1
        hop.style.fontSize = `${px}px`
      }
      noiDung.style.overflowWrap = 'break-word'
    })
    const co_chu = (tra.vung || []).filter((v) => v.ban_dich).length
    xong(`Xong khoanh vùng: ${co_chu}/${(tra.vung || []).length} bong bóng có bản dịch.`, 8)
  }

  async function dichCaChapter() {
    window[CO].dangChayBulk = true
    await layCauHinhHienTai()
    caiCongTacSoSanhGoc()
    const vi_tri_dau = window.scrollY
    let dung_lai = false

    // Nút DỪNG. Một lượt quét có thể chạy 20 phút và tiêu hạn mức — không có đường dừng thì cách
    // duy nhất là đóng tab, và đóng tab mất luôn mọi bản dịch đã phủ.
    const nut = document.createElement('button')
    nut.textContent = 'Dừng'
    Object.assign(nut.style, {
      marginTop: '8px', padding: '4px 10px', borderRadius: '6px', border: '1px solid #666',
      background: '#333', color: '#fff', font: '12px system-ui,sans-serif', cursor: 'pointer',
    })
    nut.addEventListener('click', () => { dung_lai = true; nut.disabled = true; nut.textContent = 'Đang dừng…' })

    const noiBulk = (t) => { bang.textContent = `[v${V}] ${t}`; bang.appendChild(nut) }

    const da_thu = new Set()
    let xong_so = 0
    let loi_so = 0
    let lai_so = 0        // lấy từ bản dịch đã có sẵn
    let ket_thuc = null   // lý do dừng sớm, nếu có

    // Đọc sẵn byte ảnh của các trang kế tiếp bằng cả danh sách liền kề lẫn IntersectionObserver (2000px):
    // 1. Tận dụng thời gian chờ máy chủ (~30-45s/trang) để mã hoá canvas PNG phía trình duyệt.
    // 2. Chống mất ảnh khi người dùng cuộn trang làm trình đọc truyện ảo hoá (gỡ <img> khỏi DOM)
    //    nhưng KHÔNG tiêu trước hạn mức máy chủ nếu người dùng bấm "Dừng" giữa chừng.
    const {
      cheDo: cheDoHienTai,
      ngonNgu: ngonNguHienTai,
      ngonNguDich: ngonNguDichHienTai,
      engine: engineHienTai,
    } = await layCauHinhHienTai()
    const bo_nho_byte = new Map()
    const chuanBiByte = (muc) => {
      if (!muc || bo_nho_byte.has(muc.src) || window[CO].daDich.has(khoaCache(muc.src, cheDoHienTai, ngonNguHienTai, engineHienTai, ngonNguDichHienTai))) return
      bo_nho_byte.set(muc.src, docByteAnh(muc.el))
    }
    const io = typeof IntersectionObserver !== 'undefined'
      ? new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          const el = entry.target
          const src = el.currentSrc || el.src
          if (src && el.naturalWidth > 200) chuanBiByte({ el, src })
        }
      }, { rootMargin: '2000px 0px' })
      : null

    for (let vong = 0; vong < TRAN_VONG_CUON && !dung_lai && !ket_thuc; vong++) {
      const moTaChapter = layMoTa()
      let { danh_sach } = chonMoiTrang(moTaChapter)
      if (!danh_sach.length) {
        const daThaySrc = new Set()
        danh_sach = moTaChapter.filter((m) => {
          if (!m.src || m.mo || daThaySrc.has(m.src)) return false
          const duLon = ((m.naturalWidth || 0) >= 350 && (m.naturalHeight || 0) >= 450)
            || ((m.clientWidth || 0) >= 220 && (m.clientHeight || 0) >= 260)
          if (!duLon) return false
          daThaySrc.add(m.src)
          return true
        }).sort((a, b) => a.top - b.top)
      }
      if (io) danh_sach.forEach((a) => io.observe(a.el))
      const moi = danh_sach.filter((a) => !da_thu.has(a.src))

      if (!moi.length) {
        noiBulk(`Đã xong ${xong_so} trang. Đang cuộn tìm trang tiếp…`)
        if (!(await cuonDeNapThem(danh_sach.length))) break
        continue
      }

      for (let idx = 0; idx < moi.length; idx++) {
        const a = moi[idx]
        if (dung_lai) { ket_thuc = 'bạn đã bấm Dừng'; break }
        if (xong_so + lai_so >= TRAN_TRANG_MOI_LUOT) {
          ket_thuc = `đã đạt trần ${TRAN_TRANG_MOI_LUOT} trang một lượt`
          break
        }
        da_thu.add(a.src)

        const co_san = window[CO].daDich.get(khoaCache(a.src, cheDoHienTai, ngonNguHienTai, engineHienTai, ngonNguDichHienTai))
        if (co_san) {
          const elSong = a.el?.isConnected ? a.el : timAnhTheoSrc(a.src)
          if (elSong) {
            if (co_san.anh_goc_data_url) await napCanvasTuDataUrl(elSong, co_san.anh_goc_data_url)
            vePhu(elSong, co_san)
          }
          lai_so++
          continue
        }

        chuanBiByte(a)
        chuanBiByte(moi[idx + 1])
        chuanBiByte(moi[idx + 2])

        noiBulk(
          `Đang dịch trang ${xong_so + 1}… (máy chủ dịch một trang một lúc)\n`
          + `Xong ${xong_so} · lỗi ${loi_so} · còn thấy ${danh_sach.length - da_thu.size} trang.\n`
          + `Cứ để tab này mở rồi làm việc khác.`,
        )

        let tra
        try {
          const { anh_base64, anh_mime } = await (bo_nho_byte.get(a.src) || docByteAnh(a.el))
          bo_nho_byte.delete(a.src)
          tra = await chrome.runtime.sendMessage({
            viec: 'dich-anh', url: a.src, anh_base64, anh_mime,
          })
        } catch (e) {
          bo_nho_byte.delete(a.src)
          loi_so++
          continue
        }

        if (!tra?.ok) {
          // 429 và 401 là lỗi TOÀN CỤC: trang sau chắc chắn cũng hỏng như vậy. Đi tiếp là gửi
          // thêm hàng chục request chắc chắn bị từ chối.
          if (tra?.ma === 429) {
            const ct = tra?.chi_tiet
            ket_thuc = ct?.reset_luc
              ? `hết lượt dịch hôm nay (trần ${ct.tran ?? '?'}), có lại lúc ${new Date(ct.reset_luc).toLocaleString('vi-VN')}`
              : 'hết lượt dịch hôm nay'
            break
          }
          if (tra?.ma === 401) {
            ket_thuc = 'phiên đăng nhập đã hết — mở Tuỳ chọn của tiện ích để đăng nhập lại'
            break
          }
          loi_so++
          continue
        }

        const elSong = timAnhThayThe(
          a.el,
          a.src,
          { naturalWidth: a.naturalWidth, naturalHeight: a.naturalHeight, docTop: a.docTop },
          false,
        ) || (a.el?.isConnected ? a.el : timAnhTheoSrc(a.src))
        if (tra.anh_goc_data_url) {
          await napCanvasTuDataUrl(elSong || a.el, tra.anh_goc_data_url)
        }
        const goi_ket_qua = {
          vung: tra.vung,
          anh_da_dich: tra.anh_da_dich || null,
          anh_goc_data_url: tra.anh_goc_data_url || null,
          _ctxMau: elSong?.__translationCtxMau || a.el?.__translationCtxMau || null,
          _naturalWidth: a.naturalWidth,
          _naturalHeight: a.naturalHeight,
          _docTop: a.docTop,
        }
        window[CO].daDich.set(khoaCache(a.src, tra.che_do || cheDoHienTai, ngonNguHienTai, engineHienTai, ngonNguDichHienTai), goi_ket_qua)
        const srcSong = elSong?.currentSrc || elSong?.src || elSong?.dataset?.translationCanvasId
        if (srcSong && srcSong !== a.src) {
          window[CO].daDich.set(khoaCache(srcSong, tra.che_do || cheDoHienTai, ngonNguHienTai, engineHienTai, ngonNguDichHienTai), goi_ket_qua)
        }
        // Luôn đăng ký `vePhu(elSong || a.el, goi_ket_qua)`: ngay cả khi trang đang tạm gỡ khỏi DOM
        // do cuộn xa trong lúc dịch chapter, khi người dùng cuộn quay lại vị trí `_docTop` lớp phủ sẽ tự động gắn và hiện ngay!
        vePhu(elSong || a.el, goi_ket_qua)
        xong_so++
      }
    }

    if (io) io.disconnect()
    window[CO].dangChay = false
    window[CO].dangChayBulk = false
    window.scrollTo({ top: vi_tri_dau, behavior: 'instant' })

    const phan = [`Dịch cả chapter: xong ${xong_so} trang`]
    if (lai_so) phan.push(`${lai_so} trang lấy lại từ bản đã dịch`)
    if (loi_so) phan.push(`${loi_so} trang lỗi`)
    let chu = `${phan.join(' · ')}.`
    if (ket_thuc) chu += `\n\nDỪNG SỚM: ${ket_thuc}.`
    if (!xong_so && !lai_so) {
      const daDichChu = await dichTruyenChuTrenTrang({ caChapter: true })
      if (daDichChu) return
      chu += `\n\nKhông dịch được trang nào. Nếu trang khoá vùng hiển thị đặc biệt, hãy dùng nút "Khoanh vùng dịch" (Alt+S).`
    }
    bang.textContent = `[v${V}] ${chu}`
    setTimeout(() => bang.remove(), 30000)
  }

  async function dichTrangHienTai({ tuDongCuon = false } = {}) {
    window[CO].dangChay = true
    await layCauHinhHienTai()
    caiCongTacSoSanhGoc()
    if (!bang.isConnected) document.body.appendChild(bang)
    bang.style.display = ''

    const mo_ta = layMoTa()
    let chon = chonTrangTruyen(mo_ta, { caoKhungNhin: window.innerHeight })
    if (!chon.anh) {
      // Dự phòng trực tiếp theo khung nhìn: trên MangaDex hoặc màn hình laptop DPI 125%-150%,
      // ảnh bản scan độ phân giải cao (1800px-2400px) thu vừa chiều cao màn hình (`clientWidth` ~ 450px-600px)
      // từng bị bộ lọc cũ loại nhầm là thumbnail (`w / clientWidth > 3`). Nếu có ảnh/canvas đang hiển thị
      // rõ trên màn hình (`clientWidth >= 200 && clientHeight >= 240`), chọn ngay ảnh chiếm khung nhìn lớn nhất!
      const ungVienHienThi = mo_ta.filter((m) => (
        !m.mo
        && m.bottom > 20
        && m.top < window.innerHeight - 20
        && (m.clientWidth || 0) >= 200
        && (m.clientHeight || 0) >= 240
      ))
      if (ungVienHienThi.length > 0) {
        const diemHien = (a) => (
          Math.max(0, Math.min(a.bottom, window.innerHeight) - Math.max(a.top, 0)) * (a.clientWidth || 1)
        )
        const totNhat = ungVienHienThi.reduce((a, b) => (diemHien(b) > diemHien(a) ? b : a))
        if (!totNhat.naturalWidth || totNhat.naturalWidth < 200) {
          totNhat.naturalWidth = Math.round(totNhat.clientWidth * (window.devicePixelRatio || 1))
        }
        if (!totNhat.naturalHeight || totNhat.naturalHeight < 200) {
          totNhat.naturalHeight = Math.round(totNhat.clientHeight * (window.devicePixelRatio || 1))
        }
        chon = {
          anh: totNhat,
          ly_do: `chọn theo khung hiển thị thực tế (${Math.round(totNhat.clientWidth)}x${Math.round(totNhat.clientHeight)})`,
          bi_loai: chon.bi_loai || [],
        }
      }
    }
    if (!chon.anh) {
      // Nếu trang không có ảnh truyện tranh lớn, kiểm tra ngay xem đây có phải trang Truyện Chữ (Web Novel / Light Novel) không
      const daDichTruyenChu = await dichTruyenChuTrenTrang({ caChapter: false })
      window[CO].dangChay = false
      if (daDichTruyenChu) return
      if (!tuDongCuon) {
        xong(
          `Không tìm thấy trang truyện trên màn hình.\n${chon.ly_do}.\n`
          + `Đã xem ${mo_ta.length} ảnh/canvas.`
          + (chon.bi_loai.length ? `\nVí dụ bị loại: ${chon.bi_loai[0].ly_do.join(', ')}.` : '')
          + `\n\nNếu trang khoá vùng hiển thị đặc biệt, hãy dùng nút "Khoanh vùng dịch" (Alt+S) trong popup.`,
          12,
        )
      }
      return
    }

    const anh = chon.anh
    // Dọn ngay mọi lớp phủ của các trang cũ không còn trên màn hình (trình đọc SPA lật trang `/11` -> `/15`
    // thường tái sử dụng thẻ <img> hoặc đổi URL mà không tải lại tài liệu).
    const tapSrcHienTai = new Set(mo_ta.map((m) => m.src).filter(Boolean))
    document.querySelectorAll(`.${LOP_CLASS}`).forEach((lopCu) => {
      const srcCu = lopCu.dataset?.src
      if (srcCu && !tapSrcHienTai.has(srcCu)) lopCu.remove()
    })
    if (typeof anh.el.__translationDungLopPhu === 'function') {
      try { anh.el.__translationDungLopPhu() } catch {}
    }

    const {
      cheDo: cheDoHienTai,
      ngonNgu: ngonNguHienTai,
      ngonNguDich: ngonNguDichHienTai,
      engine: engineHienTai,
    } = await layCauHinhHienTai()
    // Nhớ theo (chế độ + ngôn ngữ + ngôn ngữ đích + engine + URL ảnh): bấm lại đúng trang đó ở cùng cấu hình thì
    // vẽ lại ngay, còn nếu người dùng vừa đổi ngôn ngữ hoặc đổi ngôn ngữ đích (Việt -> Anh) trong
    // Popup thì chạy lại đúng cấu hình mới thay vì trả lại kết quả cũ.
    const da_co = window[CO].daDich.get(khoaCache(anh.src, cheDoHienTai, ngonNguHienTai, engineHienTai, ngonNguDichHienTai))
    if (da_co) {
      if (da_co.anh_goc_data_url) await napCanvasTuDataUrl(anh.el, da_co.anh_goc_data_url)
      vePhu(anh.el, da_co)
      window[CO].dangChay = false
      xong('Đã phủ lại bản dịch có sẵn.', 3)
      xepHangTrangKeTiep(layMoTa(), anh.src)
      return
    }

    noi(`Đang chuẩn bị ảnh trang truyện…\n(${chon.ly_do})`)

    if (anh.el?.tagName === 'IMG' && (!anh.el.complete || (anh.el.naturalWidth || 0) < 160)) {
      const lazySrc = anh.el.getAttribute('data-src') || anh.el.getAttribute('data-original') || anh.el.getAttribute('data-lazy-src')
      if (lazySrc && (!anh.el.src || anh.el.src.startsWith('data:'))) {
        anh.el.src = lazySrc
      }
      await new Promise((resolve) => {
        let xongCho = false
        const ketThuc = () => {
          if (xongCho) return
          xongCho = true
          resolve()
        }
        anh.el.addEventListener('load', ketThuc, { once: true })
        anh.el.addEventListener('error', ketThuc, { once: true })
        setTimeout(ketThuc, 1500)
      })
    }

    const { anh_base64, anh_mime } = await docByteAnh(anh.el)
    window[CO].anhDangDich = anh.el
    window[CO].srcDangDich = anh.src
    window[CO].cheDoDangDich = cheDoHienTai
    const batDauMs = Date.now()
    if (!window[CO].daCaiTienDo && chrome.runtime?.onMessage) {
      window[CO].daCaiTienDo = true
      chrome.runtime.onMessage.addListener((tin) => {
        if (tin?.viec !== 'tien-do' || !window[CO].dangChay) return
        if (tin.url && window[CO].srcDangDich && tin.url !== window[CO].srcDangDich) return
        const giay = Math.max(1, Math.round((Date.now() - (window[CO].batDauDichMs || Date.now())) / 1000))
        if (tin.giai_doan === 'dang-gui') {
          if (tin.anh_goc_data_url && window[CO].anhDangDich) {
            napCanvasTuDataUrl(window[CO].anhDangDich, tin.anh_goc_data_url)
          }
          noi(`Đang tải ảnh lên máy chủ… (${giay}s)`)
          return
        }
        if (tin.giai_doan === 'dang-xu-ly') {
          const td = tin.tien_do || {}
          const choTruoc = Number(td.so_viec_cho_truoc || 0)
          const tenBuoc = {
            detect: 'Nhận diện khung thoại & dịch ngữ cảnh AI',
            ocr: 'Đang đọc chữ trên trang',
            inpaint: 'Đang tái tạo nền & làm sạch bóng thoại',
            translate: 'Đang dịch thuật chuẩn ngữ cảnh AI',
            typeset: 'Đang căn chữ vào bong bóng',
          }[td.buoc] || 'Máy chủ đang xử lý trang truyện'
          const dongCho = (!td.dang_chay && choTruoc > 0)
            ? `\n⏳ Đang chờ hàng đợi máy chủ (còn ${choTruoc} việc phía trước)…`
            : ''
          const vungCoDich = Array.isArray(tin.vung) ? tin.vung.filter((v) => Boolean(v.ban_dich)) : []
          if (vungCoDich.length > 0 && window[CO].anhDangDich) {
            const elTienDo = timAnhThayThe(
              window[CO].anhDangDich,
              window[CO].srcDangDich,
              {
                naturalWidth: window[CO].anhDangDich.naturalWidth,
                naturalHeight: window[CO].anhDangDich.naturalHeight,
                docTop: window[CO].anhDangDich.__translationDocTop,
              },
              true,
            )
            if (elTienDo) {
              window[CO].anhDangDich = elTienDo
              vePhu(elTienDo, { vung: tin.vung, anh_da_dich: null })
            }
          }
          noi(
            `⏳ ${tenBuoc}… (${giay}s)${dongCho}`
            + (vungCoDich.length ? `\nĐã dịch xong ${vungCoDich.length}/${tin.vung.length} bong bóng.` : ''),
          )
        }
      })
    }
    window[CO].batDauDichMs = batDauMs

    let tra
    try {
      tra = await chrome.runtime.sendMessage({ viec: 'dich-anh', url: anh.src, anh_base64, anh_mime })
    } catch (e) {
      if (window[CO].luotChayId !== maLuotHienTai) return
      window[CO].dangChay = false
      window[CO].anhDangDich = null
      xong(`Không gọi được tiện ích nền: ${e}`, 10)
      return
    }
    if (window[CO].luotChayId !== maLuotHienTai) return
    window[CO].dangChay = false
    window[CO].anhDangDich = null

    if (!tra?.ok) {
      if (tra?.ma === 429 && window[CO].tuDichKhiCuon) {
        window[CO].tuDichKhiCuon = false
        const nutCuon = document.getElementById('translation-nut-tu-dich-cuon')
        if (nutCuon) {
          nutCuon.textContent = '🔄 Tự dịch khi cuộn'
          nutCuon.style.background = 'rgba(30,41,59,.9)'
        }
      }
      const them = tra?.ma === 401
        ? '\n\nPhiên đăng nhập đã hết. Mở Tuỳ chọn của tiện ích để đăng nhập lại.'
        : ''
      const do_do = [
        `thẻ: <${anh.el.tagName.toLowerCase()}>`,
        `src: ${String(anh.src).slice(0, 60)}${anh.src.length > 60 ? '…' : ''}`,
        `ảnh thật: ${anh.el.naturalWidth}x${anh.el.naturalHeight}`,
        `số <img>: ${document.images.length} · số <canvas>: ${document.getElementsByTagName('canvas').length}`,
      ].join('\n')
      xong(`Không dịch được.\n${tra?.loi || 'không rõ lý do'}${them}\n\n${do_do}`, 20)
      return
    }

    if (tra.anh_goc_data_url) {
      await napCanvasTuDataUrl(anh.el, tra.anh_goc_data_url)
    }
    const elVe = timAnhThayThe(
      anh.el,
      anh.src,
      { naturalWidth: anh.naturalWidth, naturalHeight: anh.naturalHeight, docTop: anh.docTop },
      true,
    ) || anh.el
    if (tra.anh_goc_data_url && elVe !== anh.el) {
      await napCanvasTuDataUrl(elVe, tra.anh_goc_data_url)
    }
    const srcMoi = elVe.currentSrc || elVe.src || elVe.dataset?.translationCanvasId || anh.src
    const goi_ket_qua = {
      vung: tra.vung,
      anh_da_dich: tra.anh_da_dich || null,
      anh_goc_data_url: tra.anh_goc_data_url || null,
      _ctxMau: elVe?.__translationCtxMau || anh.el?.__translationCtxMau || null,
      _naturalWidth: anh.naturalWidth,
      _naturalHeight: anh.naturalHeight,
      _docTop: anh.docTop,
    }
    window[CO].daDich.set(khoaCache(anh.src, tra.che_do || cheDoHienTai, ngonNguHienTai, engineHienTai, ngonNguDichHienTai), goi_ket_qua)
    if (srcMoi && srcMoi !== anh.src) {
      window[CO].daDich.set(khoaCache(srcMoi, tra.che_do || cheDoHienTai, ngonNguHienTai, engineHienTai, ngonNguDichHienTai), goi_ket_qua)
    }
    const lop = vePhu(elVe, goi_ket_qua)
    xepHangTrangKeTiep(layMoTa(), srcMoi)
    const co_chu = tra.vung.filter((v) => v.ban_dich).length

    const r = elVe.getBoundingClientRect()
    const lop_r = lop?.getBoundingClientRect()
    const so_do = [
      `ảnh: ${Math.round(r.left)},${Math.round(r.top)} ${Math.round(r.width)}x${Math.round(r.height)}`,
      `lớp phủ: ${lop_r ? `${Math.round(lop_r.left)},${Math.round(lop_r.top)} ${Math.round(lop_r.width)}x${Math.round(lop_r.height)}` : 'KHÔNG CÓ'}`,
      `ảnh thật: ${elVe.naturalWidth || anh.naturalWidth}x${elVe.naturalHeight || anh.naturalHeight}`,
      `số <img> đủ lớn: ${1 + chon.bi_loai.length} xét, chọn 1`,
    ].join('\n')

    if (!elVe.isConnected || !lop?.isConnected) {
      xong(
        `Dịch xong (${co_chu}/${tra.vung.length} bong bóng có bản dịch) NHƯNG không vẽ được lên `
        + `trang: ảnh đã biến mất khỏi trang trong lúc chờ (trang tự vẽ lại/đổi ảnh khi bạn cuộn `
        + `hoặc trang tự làm mới nội dung). Cuộn về đúng trang rồi bấm dịch lại — với ảnh dạng `
        + `\`blob:\` (MangaPlus và tương tự), ảnh mới sẽ có địa chỉ khác nên có thể phải chờ lại `
        + `từ đầu, không dùng lại được bản dịch vừa xong.\n\n${so_do}`,
        20,
      )
      return
    }

    xong(`Xong: ${co_chu}/${tra.vung.length} bong bóng có bản dịch.\n\n${so_do}`, 40)
  }

  window[CO].dichTrangHienTai = dichTrangHienTai
  window[CO].dichCaChapter = dichCaChapter
  window[CO].khoanhVungDich = khoanhVungDich

  // Popup hoặc phím tắt toàn cục đặt cờ ngay trước khi tiêm. ĐỌC LÀ XOÁ: để lại thì lần bấm
  // "Dịch trang này" sau đó sẽ chạy nhầm chế độ trước đó.
  const {
    __e60_snip: snip,
    __e59_bulk: bulk,
    __e102_auto_scroll: autoScroll,
  } = await chrome.storage.local.get(['__e60_snip', '__e59_bulk', '__e102_auto_scroll'])
  if (snip) {
    await chrome.storage.local.remove('__e60_snip')
    await khoanhVungDich()
    return
  }
  if (bulk) {
    await chrome.storage.local.remove('__e59_bulk')
    await dichCaChapter()
    return
  }
  if (autoScroll) {
    await chrome.storage.local.remove('__e102_auto_scroll')
    caiCongTacSoSanhGoc()
    window[CO].tuDichKhiCuon = !window[CO].tuDichKhiCuon
    const nutCuon = document.getElementById('translation-nut-tu-dich-cuon')
    if (nutCuon) {
      const bat = Boolean(window[CO].tuDichKhiCuon)
      nutCuon.textContent = bat ? '🔄 Tự dịch khi cuộn: BẬT (Alt+W)' : '🔄 Tự dịch khi cuộn (Alt+W)'
      nutCuon.style.background = bat ? '#059669' : 'rgba(30,41,59,.9)'
      nutCuon.style.borderColor = bat ? '#10b981' : 'rgba(255,255,255,.18)'
    }
    if (!window[CO].tuDichKhiCuon) {
      window[CO].dangChay = false
      xong('Đã TẮT Tự động dịch khi cuộn (Alt+W).', 4)
      return
    }
    xong('Đã BẬT Tự động dịch khi cuộn (Alt+W). Đang dịch trang hiện tại…', 4)
  }

  await dichTrangHienTai()
})()
// Trả về `undefined` đồng bộ ở biểu thức cuối tệp để `chrome.scripting.executeScript` trong Popup
// giải quyết ngay lập tức (<5ms) và đóng Popup, thay vì treo ở nút "Đang mở…" chờ cả lượt dịch xong.
undefined
