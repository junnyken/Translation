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
      css: "'TranslationBangers', 'Bangers', system-ui, -apple-system, sans-serif",
      lineHeight: '1.25',
      letterSpacing: '0.055em',
      wordSpacing: '0.11em',
    },
    shantell: {
      ten: '🌸 Ngôn tình',
      fontFace: 'TranslationShantell',
      tep: 'src/fonts/ShantellSans-Regular.ttf',
      css: "'TranslationShantell', 'Shantell Sans', system-ui, -apple-system, sans-serif",
      lineHeight: '1.26',
      letterSpacing: '0.032em',
      wordSpacing: '0.085em',
    },
    mansalva: {
      ten: '🏮 Cổ trang',
      fontFace: 'TranslationMansalva',
      tep: 'src/fonts/Mansalva-Regular.ttf',
      css: "'TranslationMansalva', 'Mansalva', cursive, system-ui, sans-serif",
      lineHeight: '1.25',
      letterSpacing: '0.036em',
      wordSpacing: '0.09em',
    },
    sigmar: {
      ten: '💥 Hài hước',
      fontFace: 'TranslationSigmar',
      tep: 'src/fonts/SigmarOne-Regular.ttf',
      css: "'TranslationSigmar', 'Sigmar One', system-ui, sans-serif",
      lineHeight: '1.22',
      letterSpacing: '0.042em',
      wordSpacing: '0.09em',
    },
  }
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
        if (nutNnDich) nutNnDich.textContent = thayDoi.ngonNguDich.newValue === 'en' ? '🇺🇸 EN' : '🇻🇳 VI'
      }
    })
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

      // Mở ROI đủ rộng quanh bbox chữ gốc để bao trọn cả các chữ cái/dấu câu bị Gemini khoanh hụt 15-25%
      const padCheX = Math.max(12, Math.min(38, Math.round(wGoc * 0.25)))
      const padCheY = Math.max(12, Math.min(38, Math.round(hGoc * 0.25)))
      const moX = Math.max(padCheX + 12, Math.min(Math.max(Math.round(canhDai * 0.62), Math.round(W * 0.06)), Math.round(W * 0.16)))
      const moY = Math.max(padCheY + 12, Math.min(Math.max(Math.round(canhDai * 0.62), Math.round(H * 0.05)), Math.round(H * 0.16)))
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
          // (`saiSoRow > 30` hoặc lệch độ sáng `> 16`) đều phải tính là chữ gốc (`laNenMask = 0`) để xoá sạch 100%,
          // không bao giờ để sót bóng mờ chữ màu như "WHAT IS THIS?!" hay "FOR ME!"!
          if (trongHopMoRong && (saiSoRow > 30 || Math.abs(lum - lumDong) > 16)) {
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

      for (let py = cy0; py < cy1; py += 1) {
        const ny = (py - tamGocY) / banCaoGoc
        for (let px = cx0; px < cx1; px += 1) {
          const nx = (px - tamGocX) / banRongGoc
          if (nx * nx + ny * ny > 0.88) continue
          const pos = py * rw + px
          if (laNenMask[pos] && !vungBienBaoVe[pos] && !longTrang[pos]) {
            longTrang[pos] = 1
            hangDoi[cuoi++] = pos
          }
        }
      }

      const laNenAnToan = (px, py) => {
        const pos = py * rw + px
        if (!laNenMask[pos] || vungBienBaoVe[pos]) return false
        const nx = (px - tamGocX) / banRongGoc
        const ny = (py - tamGocY) / banCaoGoc
        if (nx * nx + ny * ny <= 0.90) return true
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
        if (px > 0 && !longTrang[pos - 1] && laNenMask[pos - 1] && !vungBienBaoVe[pos - 1]) { longTrang[pos - 1] = 1; demLongTrang += 1 }
        if (px + 1 < rw && !longTrang[pos + 1] && laNenMask[pos + 1] && !vungBienBaoVe[pos + 1]) { longTrang[pos + 1] = 1; demLongTrang += 1 }
        if (py > 0 && !longTrang[pos - rw] && laNenMask[pos - rw] && !vungBienBaoVe[pos - rw]) { longTrang[pos - rw] = 1; demLongTrang += 1 }
        if (py + 1 < rh && !longTrang[pos + rw] && laNenMask[pos + rw] && !vungBienBaoVe[pos + rw]) { longTrang[pos + rw] = 1; demLongTrang += 1 }
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
        demLongTrang > dienTichHopGoc * 5.2
      )
      const laNenPhucTap = (tyLeNenTrongHop < 0.28) || (roRiBien && !laBongMauDongNhat) || (doLechMauNen > 44)
      const laBongKhepKin = !roRiBien && !laNenPhucTap && laBongMauDongNhat
      v._laNenPhucTap = laNenPhucTap

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
            dayBienHop(baseY + nx)
          }
        }
      }

      const laChuGoc = new Uint8Array(N)
      let demNetTrongHop = 0
      let demChuCoLap = 0
      for (let py = ey0; py < ey1; py += 1) {
        const base = py * rw
        for (let px = ex0; px < ex1; px += 1) {
          const pos = base + px
          if (laNenMask[pos] || vungBienBaoVe[pos]) continue
          const trongHopChinh = px >= cx0 && px < cx1 && py >= cy0 && py < cy1
          if (trongHopChinh) demNetTrongHop += 1
          if (ketNoiBienHop[pos] === 0 || (laBongKhepKin && ngoaiBongBong[pos] === 0)) {
            laChuGoc[pos] = 1
            if (trongHopChinh) demChuCoLap += 1
          }
        }
      }

      // Phân tích thành phần liên thông 2D (CCA) cho các cụm nét mực bị chạm mép `ex0..ey1` (`ketNoiBienHop === 1`):
      // Một ký tự / dấu câu / chữ Hán / chữ Hàn bị Gemini khoanh thiếu và cắt qua biên `ex0..ey1` sẽ có kích thước
      // bao quanh `(compW, compH)` nhỏ gọn (không bao giờ dài bằng cả khung viền bong bóng) và không chạm biên ngoài ROI.
      const daDuyetCca = new Uint8Array(N)
      const ccaPadCore = Math.max(8, Math.round(Math.min(wGoc, hGoc) * 0.14))
      const maxCompW = Math.max(48, Math.round(wGoc * 0.76))
      const maxCompH = Math.max(48, Math.round(hGoc * 0.76))
      const maxCompArea = Math.max(220, Math.round(dienTichHopGoc * 0.42))

      for (let py = ey0; py < ey1; py += 1) {
        const base = py * rw
        for (let px = ex0; px < ex1; px += 1) {
          const startPos = base + px
          if (laNenMask[startPos] || laChuGoc[startPos] || daDuyetCca[startPos] || vungBienBaoVe[startPos]) continue
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

      // Nếu trong một bong bóng khép kín hoàn toàn (`laBongKhepKin`) có chữ cái hoặc dấu câu nằm hơi lệch
      // ra ngoài `ex0..ey1` nhưng vẫn bị bao vây kín bởi `longTrang === 1` (`ngoaiBongBong === 0`), gom luôn nét chữ đó:
      if (laBongKhepKin) {
        for (let idx = 0; idx < N; idx += 1) {
          if (!laNenMask[idx] && !vungBienBaoVe[idx] && ngoaiBongBong[idx] === 0) {
            laChuGoc[idx] = 1
          }
        }
      }

      // Xử lý trường hợp chữ đè lên nền kẻ sọc/screentone hoặc chữ in đậm chạm nhẹ vào đường viền bong bóng
      // trong vùng mở rộng quanh lõi chữ `[cx0 - padRescue .. cx1 + padRescue]`:
      const tyLeChuCoLap = demChuCoLap / Math.max(1, demNetTrongHop)
      const banKinhLoiChoPhep = tyLeChuCoLap < 0.72 ? 1.08 : 0.86
      const doDayNetToiDa = tyLeChuCoLap < 0.72 ? 11 : 8
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
          for (let d = 1; d <= doDayNetToiDa; d += 1) {
            if (px - d >= ex0 && laNenMask[pos - d]) tTrai = true
            if (px + d < ex1 && laNenMask[pos + d]) tPhai = true
            if (py - d >= ey0 && laNenMask[pos - d * rw]) tTren = true
            if (py + d < ey1 && laNenMask[pos + d * rw]) tDuoi = true
          }
          if ((tTrai && tPhai) || (tTren && tDuoi)) {
            laChuGoc[pos] = 1
          }
        }
      }

      // Nở mặt nạ `laChuGoc` thêm 4px (`dx*dx + dy*dy <= 18`) để xoá sạch 100% bóng mờ chống răng cưa JPEG/WebP
      // và viền chữ dày quanh từng ký tự, nhưng TUYỆT ĐỐI KHÔNG ăn lẹm vào các nét mực viền/gai nhọn nối với biên!
      const vungXoaChu = new Uint8Array(N)
      let zx0 = ex0, zy0 = ey0, zx1 = ex1, zy1 = ey1
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

      // Nối liền các khe hở nhỏ giữa các chữ cái trên cùng dòng (<= 14px ngang) và giữa các dòng chữ (<= 10px dọc)
      // nằm hoàn toàn bên trong lòng bong bóng (`longTrang === 1`) để vùng xoá tạo thành mảng mịn đồng nhất,
      // triệt tiêu hoàn toàn hiện tượng in hằn bóng chữ gốc (stencil "WHAT IS THIS?!") trên các bong bóng có màu/gradient!
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

      // Dựng ảnh xoá chữ `_anhCheDataUrl`:
      // - Luôn dùng độ đục tuyệt đối `alpha = 255` (tuyệt đối không dùng `248` làm lộ 3% chữ đen bên dưới).
      // - Lấy màu nền theo đúng từng dòng `bgRowR[roiY], bgRowG[roiY], bgRowB[roiY]` kết hợp lấy mẫu sát mép đoạn xoá
      //   NHƯNG bắt buộc điểm mẫu phải nằm TRONG lòng bong bóng (`laNenMask === 1 && longTrang === 1`),
      //   tuyệt đối không bao giờ lấy nhầm màu nền cam/đỏ bên ngoài vách bong bóng thuôn nhọn (sửa triệt để lỗi sọc nhòe "FOR ME!")!
      const cwChe = Math.max(4, maxX - minX)
      const chChe = Math.max(4, maxY - minY)
      const cOut = document.createElement('canvas')
      cOut.width = cwChe
      cOut.height = chChe
      const ctxOut = cOut.getContext('2d')
      const outImg = ctxOut.createImageData(cwChe, chChe)
      const outData = outImg.data

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
        ]

        const buoc = Math.max(2, Math.round(Math.max(wGoc, hGoc) / 28))
        const CACH_NO = [
          ['trai', 'phai', 'tren', 'duoi'],
          ['trai', 'phai', 'trai', 'phai', 'tren', 'duoi'],
          ['tren', 'duoi', 'trai', 'phai'],
        ]

        let tot = dsHatGiong[0]
        let diemTot = -1

        for (const hat of dsHatGiong) {
          for (const thuTu of CACH_NO) {
            let [x0, y0, x1, y1] = hat
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
        const leTrongX = Math.max(2, Math.round((bx1 - bx0) * 0.025))
        const leTrongY = Math.max(2, Math.round((by1 - by0) * 0.025))
        if (bx1 - bx0 > wGoc + leTrongX * 2) {
          bx0 += leTrongX
          bx1 -= leTrongX
        }
        if (by1 - by0 > hGoc + leTrongY * 2) {
          by0 += leTrongY
          by1 -= leTrongY
        }
      } else {
        // Khi bong bóng có hình gai nhọn hở viền, hình đa giác đặc biệt hoặc đè trên nền screentone:
        // Nới từng bước sang hai bên/trên/dưới nếu vùng kế cận thực sự là nền bong bóng sạch (`longTrang === 1`)
        const gioiHanLeX = Math.max(6, Math.round(wGoc * 0.22))
        const gioiHanLeY = Math.max(4, Math.round(hGoc * 0.16))
        const buocNhe = Math.max(2, Math.round(Math.min(wGoc, hGoc) / 18))
        bx0 = cx0
        bx1 = cx1
        by0 = cy0
        by1 = cy1
        while (bx0 - buocNhe >= Math.max(0, cx0 - gioiHanLeX) && daiTrongBong(bx0 - buocNhe, by0, bx0, by1, 0.88, 0.14)) {
          bx0 -= buocNhe
        }
        while (bx1 + buocNhe <= Math.min(rw, cx1 + gioiHanLeX) && daiTrongBong(bx1, by0, bx1 + buocNhe, by1, 0.88, 0.14)) {
          bx1 += buocNhe
        }
        while (by0 - buocNhe >= Math.max(0, cy0 - gioiHanLeY) && daiTrongBong(bx0, by0 - buocNhe, bx1, by0, 0.88, 0.14)) {
          by0 -= buocNhe
        }
        while (by1 + buocNhe <= Math.min(rh, cy1 + gioiHanLeY) && daiTrongBong(bx0, by1, bx1, by1 + buocNhe, 0.88, 0.14)) {
          by1 += buocNhe
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
        'display:flex', 'flex-wrap:wrap', 'align-items:center', 'gap:6px',
        'padding:6px 8px', 'border-radius:999px', 'border:1px solid rgba(255,255,255,.22)',
        'background:rgba(15,23,42,.92)', 'color:#fff', 'font:12px/1.3 system-ui,sans-serif',
        'box-shadow:0 4px 16px rgba(0,0,0,.4)', 'backdrop-filter:blur(6px)',
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

      // Nút đổi nhanh Ngôn ngữ dịch ra (VI ⇄ EN) ngay trên thanh nổi
      const nutDichRa = document.createElement('button')
      nutDichRa.id = 'translation-nut-ngon-ngu-dich'
      nutDichRa.type = 'button'
      nutDichRa.title = 'Bấm để đổi nhanh Ngôn ngữ dịch ra: Tiếng Việt (VI) ⇄ Tiếng Anh Quốc tế (EN)'
      const capNhatNutDichRa = () => {
        const laEnDich = (window[CO].ngonNguDichHienTai || 'vi') === 'en'
        nutDichRa.textContent = laEnDich ? '🇺🇸 EN' : '🇻🇳 VI'
        nutDichRa.style.cssText = `${kieuNut};background:rgba(14,116,144,.45);border-color:rgba(56,189,248,.5);font-weight:700`
      }
      capNhatNutDichRa()
      nutDichRa.addEventListener('click', async () => {
        const tiep = (window[CO].ngonNguDichHienTai || 'vi') === 'en' ? 'vi' : 'en'
        window[CO].ngonNguDichHienTai = tiep
        capNhatNutDichRa()
        try {
          await chrome.storage?.local?.set?.({ ngonNguDich: tiep })
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
              ctxOut.lineJoin = 'round'
              ctxOut.lineWidth = Math.max(2, Math.round(pxCanvas * 0.14))
              ctxOut.strokeStyle = nenToi ? '#000000' : '#ffffff'
              ctxOut.fillStyle = nenToi ? '#ffffff' : '#000000'

              dong.forEach((d, i) => {
                const y = yBatDau + i * caoDong
                ctxOut.strokeText(d, cx, y)
                ctxOut.fillText(d, cx, y)
              })
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

      thanh.append(nutDich, nutChapter, nutCuon, nutSnip, nutDichRa, nutFont, nutChuNho, nutChuTo, nutCoVe, nutHoanTacCo, nutLuuAnh, nut)
      document.documentElement.appendChild(thanh)
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
        const anhChe = coCanvas ? taoAnhCheChuCanvas(el, v, vungCoDich) : null
        const nenMau = v._mauNenCss || (v.nen_toi ? '#000000' : '#ffffff')
        const chuMau = v.nen_toi ? '#ffffff' : '#000000'

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

        const padY = Math.max(2, Math.round(o.height * 0.035))
        const padX = Math.max(3, Math.round(o.width * 0.045))
        // Khi đã có `anhChe` phủ sạch nền bong bóng, dùng bóng sáng dịu `0 0 2px` thay vì viền cứng 1.5px
        // để các chữ in hoa sát nhau của font Hành động (Bangers) như "THUỘC", "CẤP" không bị viền trắng cắt lẹm vào nhau.
        const vienSangChu = (anhChe && !v._laNenPhucTap)
          ? `0 0 2px ${nenMau}, 0 0 3px ${nenMau}`
          : [
              `-1px -1px 0 ${nenMau}`,
              `1px -1px 0 ${nenMau}`,
              `-1px 1px 0 ${nenMau}`,
              `1px 1px 0 ${nenMau}`,
              `0 0 4px ${nenMau}`,
            ].join(', ')

        const lechX = Math.round((v._lechX || 0) * r.width)
        const lechY = Math.round((v._lechY || 0) * r.height)

        const hop = document.createElement('div')
        hop.className = 'translation-hop-chu'
        hop.title = `✏️ Nhấp đúp (Double-click) để sửa câu / phủ kín / cọ xoá / kéo vị trí\nChữ gốc: ${v.chu_goc || '(không rõ)'}`
        hop.dataset.nenToi = v.nen_toi ? '1' : '0'
        Object.assign(hop.style, {
          position: 'absolute',
          zIndex: '2',
          left: `${o.left + lechX}px`, top: `${o.top + lechY}px`,
          width: `${o.width}px`, height: `${o.height}px`,
          background: 'transparent',
          color: chuMau,
          textShadow: vienSangChu,
          border: v.kem_tin_cay ? '1px dashed #e0a800' : 'none',
          borderRadius: v._laHopChuNhat ? '12%' : '46%',
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

        const coChuVuaKhung = () => {
          const doDaiChu = Math.max(1, (noiDung.textContent || v.ban_dich || '').length)
          const heSo = (window[CO].heSoCoChu || 1) * (v._heSoRieng || 1)
          const uocLuong = coChu(o, doDaiChu)
          const tranTren = Math.min(
            30,
            Math.max(uocLuong + 8, Math.round(Math.min(o.width, o.height) * 0.48)),
          )
          const coChuBanDau = Math.max(9, Math.round(tranTren * heSo))
          const sanPx = Math.max(8, Math.round(9 * Math.min(heSo, 1)))
          const rongNoiDungToiDa = Math.max(18, Math.floor(o.width - padX * 2))
          const caoNoiDungToiDa = Math.max(14, Math.floor(o.height - padY * 2))
          const laElip = !v._laHopChuNhat

          // Giữ `overflow-wrap: normal` trong suốt vòng đo cỡ chữ và dùng ngưỡng chặt (`> rongNoiDungToiDa`, không cộng `+ 1`)
          // để các từ đơn có dấu câu như "CÁI..." không bao giờ bị ngắt lẻ dấu "." xuống dòng hai!
          noiDung.style.overflowWrap = 'normal'
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
            const tranGocElip = laElip && noiDung.offsetHeight > px * 1.75 && (tyLeRong * tyLeRong + tyLeCao * tyLeCao) > 1.24
            if (!tranKhung && !tranGocElip) break
            px -= 1
            hop.style.fontSize = `${px}px`
          }
          if (noiDung.scrollWidth > rongNoiDungToiDa || hop.scrollWidth > hop.clientWidth) {
            noiDung.style.overflowWrap = 'break-word'
          }
          return px
        }

        const pxDatDuoc = coChuVuaKhung()
        dsHopDaVe.push({ hop, v, px: pxDatDuoc, doDai: (v.ban_dich || '').length })

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
      // Giữ cho các bóng thoại hội thoại thông thường trên cùng 1 trang có kích thước chữ đồng đều,
      // tránh hiện tượng 1 bóng thoại trống trải phình chữ quá to so với bóng thoại bên cạnh.
      const dsPxThoai = dsHopDaVe
        .filter((m) => !m.v._heSoRieng && m.doDai >= 10)
        .map((m) => m.px)
        .sort((a, b) => a - b)
      if (dsPxThoai.length >= 2) {
        const pxTrungVi = dsPxThoai[Math.floor(dsPxThoai.length * 0.5)]
        const tranThoai = Math.max(12, Math.round(pxTrungVi * 1.18))
        const tranCamThan = Math.max(14, Math.round(pxTrungVi * 1.32))
        for (const m of dsHopDaVe) {
          if (m.v._heSoRieng) continue
          const tran = m.doDai >= 10 ? tranThoai : tranCamThan
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
