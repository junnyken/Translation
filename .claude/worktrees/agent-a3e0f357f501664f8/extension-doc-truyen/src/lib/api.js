/** Gọi máy chủ Translation (E19-5).
 *
 * Mã phiên lấy từ `chrome.storage.local`, do người dùng đăng nhập ở trang tuỳ chọn. KHÔNG có
 * đường nào để tiện ích tự tạo tài khoản: việc đó cần khoá chung của hệ thống và nó thuộc về
 * bản web.
 */

import { giaiPow } from './giai-pow.js'

export const KHOA_LUU = {
  dia_chi: 'diaChi', ma_phien: 'maPhien', email: 'email', ma_khach: 'maKhach',
  //: Ngôn ngữ CHỮ TRÊN ẢNH (không phải ngôn ngữ đích) — quyết định chọn engine OCR. `ja` là mặc
  //: định trung thực nhất với hành vi trước khi có lựa chọn này, không phải "loại phổ biến nhất".
  ngon_ngu: 'ngonNgu',
  //: Ngôn ngữ ĐÍCH dịch ra (`vi` = Tiếng Việt, `en` = Tiếng Anh quốc tế).
  ngon_ngu_dich: 'ngonNguDich',
  //: Engine dịch. `llm_context` là mặc định chuẩn ngữ cảnh.
  engine: 'engine',
  //: Chế độ xử lý: mặc định `chi_chu` để máy chủ chạy gộp 1 lượt Gemini (~3-4s, 0% nghẽn CPU khi
  //: nhiều người dùng cùng lúc) và giao toàn bộ việc Xoá chữ (Inpaint) + Dựng lớp chữ DOM tương tác
  //: cho GPU/Canvas của máy khách.
  che_do: 'cheDoGpuKhach',
  //: Font chữ theo thể loại truyện (`bangers` | `shantell` | `mansalva` | `sigmar`).
  font_chu: 'fontChuTruyen',
}
export const NGON_NGU_MAC_DINH = 'ja'
export const NGON_NGU_DICH_MAC_DINH = 'vi'
export const ENGINE_MAC_DINH = 'llm_context'
export const CHE_DO_MAC_DINH = 'chi_chu'
export const FONT_CHU_MAC_DINH = 'bangers'
//: Địa chỉ máy chủ mặc định trỏ sẵn vào máy chủ API chính thức để người dùng cài xong là dịch ngay.
export const DIA_CHI_MAC_DINH = 'https://translation-api.vibe1.tinhgon.xyz'

function sinhMaKhachNgauNhien() {
  const mang = new Uint8Array(18)
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(mang)
  } else {
    for (let i = 0; i < mang.length; i++) mang[i] = Math.floor(Math.random() * 256)
  }
  return Array.from(mang, (b) => b.toString(16).padStart(2, '0')).join('')
}

/** Chuẩn hoá địa chỉ máy chủ:
 *  Nếu người dùng dán địa chỉ trang giao diện Web (`https://comic.io.vn` hoặc
 *  `https://translation.vibe1.tinhgon.xyz`) thay vì máy chủ API (`https://translation-api.vibe1.tinhgon.xyz`),
 *  tự động chuyển sang địa chỉ API để không bị Nginx chặn 405 Not Allowed.
 */
export function chuanHoaDiaChi(raw) {
  let s = String(raw || '').trim().replace(/\/+$/, '')
  if (!s) return ''
  if (/^(https?:\/\/)?(www\.)?comic\.io\.vn$/i.test(s)) {
    return 'https://translation-api.vibe1.tinhgon.xyz'
  }
  return s.replace(/^https?:\/\/translation\.vibe1\.tinhgon\.xyz$/i, 'https://translation-api.vibe1.tinhgon.xyz')
}

export async function docCauHinh() {
  const d = await chrome.storage.local.get(Object.values(KHOA_LUU))
  let maKhach = d[KHOA_LUU.ma_khach] || ''
  if (maKhach.length < 16) {
    maKhach = sinhMaKhachNgauNhien()
    await chrome.storage.local.set({ [KHOA_LUU.ma_khach]: maKhach })
  }
  return {
    diaChi: chuanHoaDiaChi(d[KHOA_LUU.dia_chi] || DIA_CHI_MAC_DINH || ''),
    maPhien: d[KHOA_LUU.ma_phien] || '',
    email: d[KHOA_LUU.email] || '',
    maKhach,
    ngonNgu: d[KHOA_LUU.ngon_ngu] || NGON_NGU_MAC_DINH,
    ngonNguDich: d[KHOA_LUU.ngon_ngu_dich] || NGON_NGU_DICH_MAC_DINH,
    engine: d[KHOA_LUU.engine] || ENGINE_MAC_DINH,
    cheDo: d[KHOA_LUU.che_do] || CHE_DO_MAC_DINH,
    fontChu: d[KHOA_LUU.font_chu] || FONT_CHU_MAC_DINH,
  }
}

export async function luuCauHinh(c) {
  const hien = await docCauHinh()
  await chrome.storage.local.set({
    [KHOA_LUU.dia_chi]: c.diaChi !== undefined ? chuanHoaDiaChi(c.diaChi) : hien.diaChi,
    [KHOA_LUU.ma_phien]: c.maPhien ?? hien.maPhien,
    [KHOA_LUU.email]: c.email ?? hien.email,
    [KHOA_LUU.ngon_ngu]: c.ngonNgu ?? hien.ngonNgu,
    [KHOA_LUU.ngon_ngu_dich]: c.ngonNguDich ?? hien.ngonNguDich,
    [KHOA_LUU.engine]: c.engine ?? hien.engine,
    [KHOA_LUU.che_do]: c.cheDo ?? hien.cheDo,
    [KHOA_LUU.font_chu]: c.fontChu ?? hien.fontChu,
  })
}

/** Lỗi mang theo mã HTTP, để bên gọi phân biệt "hết phiên" với "hỏng thật".
 *
 * `chiTiet` giữ nguyên `detail` khi máy chủ trả OBJECT (E59). Hạn mức 429 trả một object đủ thông
 * tin để nói câu tử tế — trần bao nhiêu, bao giờ có lại. Bản trước chỉ giữ chuỗi nên object rơi về
 * `res.statusText`, tức người dùng đọc đúng chữ **"Too Many Requests"** và không biết gì thêm.
 * Cùng lỗi mà bản web đã phải vá ở E53.
 */
export class LoiApi extends Error {
  constructor(ma, thongDiep, chiTiet = null) {
    super(thongDiep)
    this.ma = ma
    this.chiTiet = chiTiet
  }
}

async function doc(res) {
  if (res.status === 204) return null
  let than = null
  try { than = await res.json() } catch { /* không phải JSON */ }
  if (!res.ok) {
    const chi_tiet = than?.detail
    if (chi_tiet && typeof chi_tiet === 'object') {
      // Lấy câu người đọc được nếu máy chủ có gửi, và GIỮ nguyên object cho bên gọi dùng.
      const cau = chi_tiet.thong_diep ?? chi_tiet.loi ?? (res.statusText || `Lỗi HTTP ${res.status}`)
      throw new LoiApi(res.status, String(cau), chi_tiet)
    }
    if (typeof chi_tiet === 'string' && chi_tiet.trim()) {
      throw new LoiApi(res.status, chi_tiet)
    }
    if (res.status === 405) {
      throw new LoiApi(
        405,
        'Địa chỉ đang nhập là trang Giao diện Web (không phải máy chủ API). Hãy thêm "-api" vào tên miền (ví dụ: https://translation-api.vibe1.tinhgon.xyz).',
      )
    }
    throw new LoiApi(res.status, res.statusText || `Máy chủ trả lỗi HTTP ${res.status}`)
  }
  return than
}

async function goi(duong, opts = {}) {
  const { diaChi, maPhien, maKhach } = await docCauHinh()
  if (!diaChi) throw new LoiApi(0, 'Chưa đặt địa chỉ máy chủ Translation.')
  const headers = { ...(opts.headers || {}) }
  if (maPhien) headers.Authorization = `Bearer ${maPhien}`
  else if (maKhach) headers['X-Ma-Khach'] = maKhach
  return doc(await fetch(`${diaChi}/api/v1${duong}`, { ...opts, headers }))
}

export async function dangNhap(diaChi, email, matKhau) {
  const goc = chuanHoaDiaChi(diaChi)
  const UngVienKey = String(matKhau || '').trim().startsWith('tr_live_')
    ? String(matKhau).trim()
    : (String(email || '').trim().startsWith('tr_live_') ? String(email).trim() : '')
  if (UngVienKey) {
    const resKey = await fetch(`${goc}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${UngVienKey}` },
    })
    const nguoi = await doc(resKey)
    await luuCauHinh({ diaChi: goc, maPhien: UngVienKey, email: nguoi.email })
    return nguoi
  }
  const res = await fetch(`${goc}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, mat_khau: matKhau }),
  })
  const d = await doc(res)
  await luuCauHinh({ diaChi: goc, maPhien: d.ma_phien, email: d.nguoi_dung.email })
  return d.nguoi_dung
}

export async function dangKy(diaChi, email, tenHien, matKhau) {
  const goc = chuanHoaDiaChi(diaChi)
  let thachThuc = null
  try {
    const rBot = await fetch(`${goc}/api/v1/auth/thach-thuc-bot`)
    if (rBot && rBot.ok) thachThuc = await rBot.json()
  } catch { /* bỏ qua nếu môi trường test mock chỉ định tuyến /auth/register */ }
  const payload = { email, ten_hien: tenHien || '', mat_khau: matKhau }
  if (thachThuc?.ma_thach_thuc) {
    // Máy chủ đòi lời giải PoW thật — mã trơn không còn đủ để qua.
    payload.ma_thach_thuc = thachThuc.ma_thach_thuc
    payload.dap_an_thach_thuc = await giaiPow(thachThuc.ma_thach_thuc, thachThuc.do_kho_pow ?? 16)
  }
  const res = await fetch(`${goc}/api/v1/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  await doc(res)
  return dangNhap(goc, email, matKhau)
}

/** Mở trang web chính thức kèm tự động chuyển hướng sang `https://translation.vibe1.tinhgon.xyz`
 *  nếu mạng hiện tại của người dùng (như 4G Viettel) đang chặn DNS `comic.io.vn`.
 */
export async function moTrangWebThongMinh() {
  let url = 'https://comic.io.vn'
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 1400)
    await fetch('https://comic.io.vn/favicon.ico', { mode: 'no-cors', cache: 'no-store', signal: ctrl.signal })
    clearTimeout(timer)
  } catch {
    url = 'https://translation.vibe1.tinhgon.xyz'
  }
  if (globalThis.chrome?.tabs?.create) {
    chrome.tabs.create({ url })
  } else {
    window.open(url, '_blank', 'noopener')
  }
}

export async function layHanMuc() {
  return goi('/han-muc')
}

export async function toiLaAi() {
  return goi('/auth/me')
}

export async function dangXuat() {
  try { await goi('/auth/logout', { method: 'POST' }) } finally {
    await luuCauHinh({ diaChi: (await docCauHinh()).diaChi, maPhien: '', email: '' })
  }
}

/** Gửi BYTE ảnh lên. Nhận `Blob` chứ không nhận URL: máy chủ không với tới trang truyện được,
 *  và cũng không nên với tới.
 *
 * `ngonNgu` là chữ TRÊN ẢNH (chọn ở trang Tuỳ chọn/popup), không phải ngôn ngữ đích — chọn sai
 * không báo lỗi gì, chỉ ra chữ vô nghĩa (đo được 07/09 trên MangaPlus bản tiếng Anh với `ja`).
 *
 * `engine`: `google_fast` (mặc định, miễn phí, dịch rời rạc) hoặc `llm_context` (Gemini, tốn
 * token — người dùng tự bật ở popup). Bản miễn phí không tự sửa được lỗi đọc chữ dính/sai trên
 * font cách điệu (đo 08/09 trên MangaPlus: vài dòng ra nguyên tiếng Anh hoặc dịch sai nghĩa).
 */
export async function guiTrang(blob, ngonNgu, engine, cheDo, ngonNguDich = NGON_NGU_DICH_MAC_DINH, tuDienRieng = '') {
  const form = new FormData()
  form.append('file', blob, 'trang.png')
  form.append('source_lang', ngonNgu || NGON_NGU_MAC_DINH)
  form.append('target_lang', ngonNguDich || NGON_NGU_DICH_MAC_DINH)
  form.append('engine', engine || ENGINE_MAC_DINH)
  form.append('che_do', cheDo || CHE_DO_MAC_DINH)
  if (tuDienRieng && String(tuDienRieng).trim()) {
    form.append('tu_dien_rieng', String(tuDienRieng).trim())
  }
  return goi('/doc-truyen/trang', { method: 'POST', body: form })
}

/**
 * Chạy Offline 100% trên máy khách bằng mô hình GGUF cục bộ (Ollama `127.0.0.1:11434` hoặc LM Studio / llama.cpp `127.0.0.1:1234`).
 * - Hoàn toàn KHÔNG gọi máy chủ của chúng ta -> 0% tải máy chủ, 0 tốn phí API, không trừ lượt.
 * - Tận dụng 100% GPU/CPU trên máy tính của khách hàng.
 */
export async function dichTrangLocalGguf(blob, { ngonNgu = 'ja', ngonNguDich = 'vi', tuDienRieng = '' } = {}) {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  let nhiPhan = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    nhiPhan += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  const anhBase64 = btoa(nhiPhan)
  const mime = blob.type || 'image/jpeg'

  let W = 1000
  let H = 1400
  if (typeof createImageBitmap === 'function') {
    try {
      const bmp = await createImageBitmap(blob)
      W = bmp.width || W
      H = bmp.height || H
      bmp.close?.()
    } catch {}
  }

  const tenNgonNguDich = ngonNguDich === 'en' ? 'English' : 'Tiếng Việt tự nhiên, chuẩn phong cách truyện tranh'
  const doanNguCanh = tuDienRieng
    ? `\nNgữ cảnh xưng hô & thuật ngữ từ các trang trước (hãy giữ đồng nhất):\n${tuDienRieng}\n`
    : ''
  const prompt = [
    `Bạn là AI nhận diện và dịch truyện tranh chuyên nghiệp (ngôn ngữ gốc: ${ngonNgu} -> dịch sang: ${tenNgonNguDich}).`,
    doanNguCanh,
    'Hãy tìm TẤT CẢ các bóng thoại trong trang truyện này, đọc chữ gốc và dịch sang ngôn ngữ đích.',
    'Trả về DUY NHẤT một mảng JSON hợp lệ theo cấu trúc:',
    '[{"box_2d":[ymin,xmin,ymax,xmax],"chu_goc":"...","ban_dich":"..."}]',
    'Trong đó ymin, xmin, ymax, xmax được chuẩn hoá trên thang 0..1000.',
  ].join('\n')

  let rawText = ''

  // 1. Thử kết nối Ollama cục bộ trên máy khách (http://127.0.0.1:11434)
  let daChayLocal = false
  try {
    const rTags = await fetch('http://127.0.0.1:11434/api/tags')
    if (rTags.ok) {
      const dTags = await rTags.json()
      const dsModel = (dTags?.models || []).map((m) => m.name || '')
      const modelVision = dsModel.find((m) => /qwen2\.5vl|qwen2-vl|gemma3|minicpm-v|llava|llama3\.2-vision|internvl|pixtral/i.test(m))
        || dsModel[0]
      if (!modelVision) {
        throw new LoiApi(
          0,
          'Ollama trên máy bạn chưa cài model GGUF Vision nào. Hãy mở Terminal chạy: ollama run qwen2.5vl:7b (hoặc gemma3:4b)',
        )
      }
      const rChat = await fetch('http://127.0.0.1:11434/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: modelVision,
          stream: false,
          format: 'json',
          messages: [
            {
              role: 'user',
              content: prompt,
              images: [anhBase64],
            },
          ],
        }),
      })
      if (rChat.ok) {
        const dChat = await rChat.json()
        rawText = dChat?.message?.content || dChat?.response || ''
        daChayLocal = true
      }
    }
  } catch (e) {
    if (e instanceof LoiApi) throw e
  }

  // 2. Nếu chưa bật Ollama, thử LM Studio / llama.cpp GGUF server (http://127.0.0.1:1234)
  if (!daChayLocal) {
    try {
      const rModels = await fetch('http://127.0.0.1:1234/v1/models')
      if (rModels.ok) {
        const dModels = await rModels.json()
        const modelId = dModels?.data?.[0]?.id || 'local-gguf-vision'
        const rComp = await fetch('http://127.0.0.1:1234/v1/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: modelId,
            temperature: 0.2,
            messages: [
              {
                role: 'user',
                content: [
                  { type: 'text', text: prompt },
                  { type: 'image_url', image_url: { url: `data:${mime};base64,${anhBase64}` } },
                ],
              },
            ],
          }),
        })
        if (rComp.ok) {
          const dComp = await rComp.json()
          rawText = dComp?.choices?.[0]?.message?.content || ''
          daChayLocal = true
        }
      }
    } catch {}
  }

  if (!daChayLocal) {
    throw new LoiApi(
      0,
      'Chưa phát hiện phần mềm chạy GGUF cục bộ trên máy bạn (Ollama cổng 11434 hoặc LM Studio cổng 1234). Hãy bật Ollama (`ollama run qwen2.5vl:7b`) hoặc LM Studio Local Server trên máy tính của bạn để dịch Offline 0đ!',
    )
  }

  // Bóc mảng JSON từ phản hồi của model GGUF cục bộ
  let danhSach = []
  try {
    const khopMang = String(rawText).match(/\[[\s\S]*\]/)
    const parsed = JSON.parse(khopMang ? khopMang[0] : rawText)
    danhSach = Array.isArray(parsed) ? parsed : (parsed?.regions || parsed?.vung || parsed?.bubbles || [])
  } catch {
    danhSach = []
  }

  const vung = []
  for (const m of danhSach) {
    const banDich = String(m.ban_dich || m.translation || m.text || '').trim()
    if (!banDich) continue
    const chuGoc = String(m.chu_goc || m.original || m.source || '').trim()
    let x = 0, y = 0, w = 0, h = 0
    if (Array.isArray(m.box_2d) && m.box_2d.length === 4) {
      let [ymin, xmin, ymax, xmax] = m.box_2d.map(Number)
      const thang = Math.max(ymin, xmin, ymax, xmax) <= 1.05 ? 1 : 1000
      x = Math.round((xmin / thang) * W)
      y = Math.round((ymin / thang) * H)
      w = Math.round(((xmax - xmin) / thang) * W)
      h = Math.round(((ymax - ymin) / thang) * H)
    } else if (typeof m.x === 'number' && typeof m.y === 'number') {
      const thang = Math.max(m.x, m.y, m.w || 0, m.h || 0) <= 1.05 ? 1 : (Math.max(m.x + (m.w || 0), m.y + (m.h || 0)) <= 1000 ? 1000 : 0)
      if (thang > 0) {
        x = Math.round((m.x / thang) * W)
        y = Math.round((m.y / thang) * H)
        w = Math.round(((m.w || 120) / thang) * W)
        h = Math.round(((m.h || 80) / thang) * H)
      } else {
        x = Math.round(m.x)
        y = Math.round(m.y)
        w = Math.round(m.w || 120)
        h = Math.round(m.h || 80)
      }
    }
    if (w >= 12 && h >= 12) {
      vung.push({ x, y, w, h, chu_goc: chuGoc, ban_dich: banDich })
    }
  }

  return { vung, che_do: 'chi_chu' }
}

export async function layTrang(pageId) {
  return goi(`/doc-truyen/trang/${pageId}`)
}

/** Tải ảnh PNG đã xoá chữ + căn chữ (`che_do = day_du`) và đổi sang Data URL để content script
 *  hiển thị trực tiếp trên mọi trang web mà không bị chặn CORS/CSP nguồn ngoài. */
export async function taiAnhDaDichDataUrl(pageId) {
  const { diaChi, maPhien, maKhach } = await docCauHinh()
  if (!diaChi) throw new LoiApi(0, 'Chưa đặt địa chỉ máy chủ Translation.')
  const headers = {}
  if (maPhien) headers.Authorization = `Bearer ${maPhien}`
  else if (maKhach) headers['X-Ma-Khach'] = maKhach
  const res = await fetch(`${diaChi}/api/v1/doc-truyen/trang/${pageId}/anh`, { headers })
  if (!res.ok) return null
  const blob = await res.blob()
  const bytes = new Uint8Array(await blob.arrayBuffer())
  let nhi_phan = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    nhi_phan += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return `data:${blob.type || 'image/png'};base64,${btoa(nhi_phan)}`
}


/** Thiếu cấu hình thì thiếu cái gì — trả câu nói cho người dùng, hoặc `null` nếu đủ.
 *
 * Tách khỏi phần gọi Chrome API để test được bằng số. Câu chữ ở đây quan trọng hơn nó trông:
 * bản đầu chỉ nói "Chưa đặt địa chỉ máy chủ Translation." — đúng nhưng vô dụng, vì nó không
 * đưa người dùng tới chỗ sửa được, và người dùng thật đã không tìm ra trang tuỳ chọn.
 */
export function lyDoThieuCauHinh({ diaChi, maPhien, choPhepKhach = false }) {
  if (!diaChi) {
    return 'Chưa đặt địa chỉ máy chủ Translation. Đã mở trang cài đặt — nhập địa chỉ rồi đăng nhập.'
  }
  if (!maPhien && !choPhepKhach) {
    return 'Chưa đăng nhập. Đã mở trang cài đặt — đăng nhập rồi bấm dịch lại.'
  }
  return null
}
