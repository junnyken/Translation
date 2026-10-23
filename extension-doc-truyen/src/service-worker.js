/** Service worker (E19-4).
 *
 * Làm ĐÚNG hai việc content script không tự làm trọn được:
 *
 * 1. **Tải byte ảnh — khi content script chưa tự đọc được.** Ảnh `https://` bình thường phần lớn
 *    KHÔNG gắn CORS header, nên đọc qua canvas ở content script sẽ dính `SecurityError` (nhiễm
 *    bẩn); service worker có `host_permissions` nên `fetch()` thẳng được, không qua CORS. NGƯỢC
 *    LẠI với `blob:`/`data:` do chính trang tạo ra (đo được 07/09 trên MangaPlus: trang tự giải
 *    mã ảnh rồi phát qua `blob:`) — canvas ở content script đọc được (cùng tài liệu, không nhiễm
 *    bẩn), còn `fetch()` một `blob:` từ NGỮ CẢNH KHÁC (service worker) luôn hỏng, không cách nào
 *    sửa bằng quyền hay header. Content script thử canvas trước, hỏng mới rơi về gửi URL cho đây.
 * 2. **Giữ vòng hỏi lại.** Một trang tốn ~45 giây; content script chết theo trang khi người
 *    dùng chuyển tab hoặc trang tự làm mới.
 *
 * MV3 tắt service worker khi rảnh rồi dựng lại từ đầu, nên ở đây **không giữ trạng thái nào ở
 * biến module** — mọi thứ cần nhớ đều nằm trong `chrome.storage.session`.
 */
import {
  LoiApi,
  docCauHinh,
  guiTrang,
  layTrang,
  lyDoThieuCauHinh,
  taiAnhDaDichDataUrl,
} from './lib/api.js'

/** Nhịp hỏi lại thích ứng: 1.2 giây trong 20 giây đầu để bắt kịp kết quả gộp 1 lượt (E96 ~3-5s)
 *  ngay khi xong; sau 20 giây hạ xuống 2.2 giây cho các việc nặng (xoá chữ LaMa / hàng đợi dài). */
const NHIP_HOI_NHANH_MS = 1200
const NHIP_HOI_THUONG_MS = 2200
/** Bỏ cuộc sau 5 phút. Không có trần thì một việc kẹt sẽ hỏi lại mãi mãi. */
const TRAN_CHO_MS = 5 * 60 * 1000

async function taiAnh(url) {
  const res = await fetch(url, { credentials: 'omit' })
  if (!res.ok) throw new LoiApi(res.status, `Không tải được ảnh (${res.status})`)
  const blob = await res.blob()
  if (!blob.type.startsWith('image/')) {
    throw new LoiApi(0, `Địa chỉ này không trả về ảnh (${blob.type || 'không rõ kiểu'})`)
  }
  return blob
}

/** Giải base64 content script đã đọc sẵn bằng canvas — dùng khi `url` là `blob:`/`data:` của
 *  trang (MangaPlus và tương tự): service worker `fetch()` một `blob:` do TÀI LIỆU KHÁC tạo ra
 *  luôn hỏng ("Failed to fetch" trần trụi), vì blob URL chỉ sống trong đúng ngữ cảnh đã tạo nó. */
function base64ThanhBlob(b64, mime) {
  const nhi_phan = atob(b64)
  const bytes = new Uint8Array(nhi_phan.length)
  for (let i = 0; i < nhi_phan.length; i++) bytes[i] = nhi_phan.charCodeAt(i)
  return new Blob([bytes], { type: mime || 'image/png' })
}

async function blobThanhDataUrl(blob) {
  try {
    const bytes = new Uint8Array(await blob.arrayBuffer())
    let nhi_phan = ''
    for (let i = 0; i < bytes.length; i += 0x8000) {
      nhi_phan += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
    }
    return `data:${blob.type || 'image/jpeg'};base64,${btoa(nhi_phan)}`
  } catch {
    return null
  }
}

const luotDichTheoTab = new Map()
const viecDangChayTheoUrl = new Map()
const REGEX_DAU_TIENG_VIET = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i

async function dichCauNhanhGtx(chu, sl = 'auto', tl = 'vi') {
  const s = String(chu || '').trim()
  if (!s) return ''
  const maNguon = sl === 'zh' ? 'zh-CN' : (sl || 'auto')
  const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${encodeURIComponent(maNguon)}&tl=${encodeURIComponent(tl || 'vi')}&dt=t&q=${encodeURIComponent(s)}`
  const res = await fetch(url, { credentials: 'omit' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  const doan = Array.isArray(data?.[0]) ? data[0].map((x) => x?.[0] || '').join('') : ''
  return doan.trim() || s
}

async function damBaoNgonNguDich(dsVung, ngonNguGoc, ngonNguDich) {
  if (!Array.isArray(dsVung) || !dsVung.length) return dsVung
  if (ngonNguDich !== 'en') return dsVung
  // Nếu máy chủ đã cập nhật trả thẳng tiếng Anh (không còn dấu tiếng Việt) thì giữ nguyên.
  // Nếu máy chủ từ xa chưa redeploy nên vẫn trả tiếng Việt khi khách chọn `en`, dịch tức thì sang tiếng Anh (~180ms).
  const canChuyenAnh = dsVung.some((v) => v?.ban_dich && REGEX_DAU_TIENG_VIET.test(v.ban_dich))
  if (!canChuyenAnh) return dsVung
  await Promise.all(dsVung.map(async (v) => {
    if (!v || (!v.chu_goc && !v.ban_dich)) return
    try {
      const nguon = v.chu_goc ? (ngonNguGoc || 'auto') : 'vi'
      const goc = v.chu_goc || v.ban_dich
      v.ban_dich = await dichCauNhanhGtx(goc, nguon, 'en')
    } catch {
      // Giữ nguyên nếu mạng lỗi
    }
  }))
  return dsVung
}

async function dichMotTrang(url, anhBase64, anhMime, bao, daBiHuy = () => false) {
  bao({ giai_doan: 'dang-tai-anh', url })
  const blob = anhBase64 ? base64ThanhBlob(anhBase64, anhMime) : await taiAnh(url)
  if (daBiHuy()) throw new LoiApi(0, 'Đã chuyển sang dịch trang mới.')

  // Khi content script bị chặn CORS (`!anhBase64`), trả kèm `anh_goc_data_url` để trình duyệt của
  // khách vẽ lên Canvas/WebGL2 nội bộ mà không dính `SecurityError` — giúp dò khung bong bóng và xoá chữ
  // gốc bằng GPU/Canvas máy khách trên 100% trang web truyện.
  const anh_goc_data_url = anhBase64 ? null : await blobThanhDataUrl(blob)

  const { ngonNgu, ngonNguDich, engine, cheDo } = await docCauHinh()
  bao({ giai_doan: 'dang-gui', url, che_do: cheDo, anh_goc_data_url })
  const { page_id } = await guiTrang(blob, ngonNgu, engine, cheDo, ngonNguDich)

  const lucBatDau = Date.now()
  const han = lucBatDau + TRAN_CHO_MS
  // Chờ 900ms trước lượt hỏi đầu tiên: máy chủ vừa nhận ảnh (202 Accepted), hỏi ngay ở 0ms chắc chắn
  // chưa xong và chỉ tốn 1 vòng mạng vô ích.
  await new Promise((r) => setTimeout(r, 900))
  for (;;) {
    if (daBiHuy()) throw new LoiApi(0, 'Đã chuyển sang dịch trang mới.')
    const d = await layTrang(page_id)
    if (daBiHuy()) throw new LoiApi(0, 'Đã chuyển sang dịch trang mới.')
    if (Array.isArray(d.vung) && d.vung.length && ngonNguDich === 'en') {
      await damBaoNgonNguDich(d.vung, ngonNgu, ngonNguDich)
    }
    bao({ giai_doan: 'dang-xu-ly', url, che_do: d.che_do || cheDo, tien_do: d.tien_do, vung: d.vung })
    if (d.loi) throw new LoiApi(0, d.loi)
    if (d.xong) {
      let anh_da_dich_data_url = null
      if (d.che_do === 'day_du' && d.anh_da_dich && ngonNguDich !== 'en') {
        try {
          anh_da_dich_data_url = await taiAnhDaDichDataUrl(page_id)
        } catch {
          anh_da_dich_data_url = null
        }
      }
      return { ...d, anh_da_dich_data_url, anh_goc_data_url }
    }
    if (Date.now() > han) {
      throw new LoiApi(0, 'Quá 5 phút chưa xong — máy chủ đang quá tải hoặc việc bị kẹt.')
    }
    const daCho = Date.now() - lucBatDau
    const nhip = daCho < 20000 ? NHIP_HOI_NHANH_MS : NHIP_HOI_THUONG_MS
    await new Promise((r) => setTimeout(r, nhip))
  }
}

/** Chưa cấu hình thì MỞ THẲNG trang tuỳ chọn, đừng bắt người dùng đi tìm.
 *
 * Bản đầu chỉ trả về "Chưa đặt địa chỉ máy chủ Translation." — đúng nhưng vô dụng: trang tuỳ
 * chọn của tiện ích MV3 nằm sau `chrome://extensions` → Chi tiết → kéo xuống cuối, và người
 * dùng thật đã không tìm ra. Một câu báo lỗi đúng mà không đưa người ta tới chỗ sửa được thì
 * chỉ là một câu báo lỗi.
 *
 * Trả `true` nghĩa là "thiếu cấu hình, đã mở trang tuỳ chọn rồi".
 */
async function thieuCauHinh() {
  const ly_do = lyDoThieuCauHinh({ ...(await docCauHinh()), choPhepKhach: true })
  if (ly_do) chrome.runtime.openOptionsPage()
  return ly_do
}


async function chayLenhPhimTat(lenh, tabId) {
  try {
    let targetTabId = tabId
    if (!targetTabId) {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
      targetTabId = tab?.id
    }
    if (!targetTabId) return
    await chrome.storage.local.remove(['__e60_snip', '__e59_bulk', '__e102_auto_scroll'])
    if (lenh === 'khoanh-vung-dich') {
      await chrome.storage.local.set({ __e60_snip: true })
    } else if (lenh === 'dich-ca-chapter') {
      await chrome.storage.local.set({ __e59_bulk: true })
    } else if (lenh === 'tu-dich-khi-cuon') {
      await chrome.storage.local.set({ __e102_auto_scroll: true })
    }
    await chrome.scripting.executeScript({
      target: { tabId: targetTabId },
      files: ['src/content/index.js'],
    })
  } catch {
    // Tab hệ thống (chrome://, Web Store) không cho tiêm script — bỏ qua an toàn.
  }
}

chrome.runtime.onMessage.addListener((tin, gui_tu, traLoi) => {
  if (tin?.viec === 'phim-tat' && tin?.lenh) {
    chayLenhPhimTat(tin.lenh, gui_tu?.tab?.id).finally(() => traLoi({ ok: true }))
    return true
  }

  if (tin?.viec === 'chup-man-hinh') {
    chrome.tabs
      .captureVisibleTab(gui_tu.tab?.windowId, { format: 'png' })
      .then((dataUrl) => traLoi({ ok: true, data_url: dataUrl }))
      .catch((e) => traLoi({ ok: false, loi: String(e?.message || e) }))
    return true
  }

  if (tin?.viec === 'dich-lai-cau') {
    ;(async () => {
      try {
        const { ngonNgu, ngonNguDich } = await docCauHinh()
        const chuGoc = String(tin.chu_goc || tin.chu_hien_tai || '').trim()
        if (!chuGoc) {
          traLoi({ ok: false, loi: 'Không có chữ gốc để dịch lại.' })
          return
        }
        const sl = tin.chu_goc ? (tin.ngon_ngu || ngonNgu || 'auto') : 'auto'
        const tl = tin.ngon_ngu_dich || ngonNguDich || 'vi'
        const ban_dich = await dichCauNhanhGtx(chuGoc, sl, tl)
        traLoi({ ok: true, ban_dich })
      } catch (e) {
        traLoi({ ok: false, loi: String(e?.message || e) })
      }
    })()
    return true
  }

  if (tin?.viec !== 'dich-anh') return false

  const tabId = gui_tu?.tab?.id
  const laNgam = Boolean(tin?.ngam)
  const khoaUrl = `${tabId ?? 0}::${tin.url || ''}`

  // Nếu trang này đang được dịch dở (ví dụ: luồng nạp đón đầu vừa gửi 2 giây trước rồi người dùng
  // cuộn tới hoặc bấm Alt+Q), dùng chung luôn Promise đang chạy thay vì huỷ đi gửi lại từ đầu!
  if (tin.url && viecDangChayTheoUrl.has(khoaUrl)) {
    viecDangChayTheoUrl.get(khoaUrl)
      .then((ketQua) => traLoi(ketQua))
      .catch((err) => traLoi(err))
    return true
  }

  let maLuot = luotDichTheoTab.get(tabId) || 0
  if (!laNgam && tabId !== undefined) {
    maLuot += 1
    luotDichTheoTab.set(tabId, maLuot)
  }
  const daBiHuy = () => !laNgam && tabId !== undefined && luotDichTheoTab.get(tabId) !== maLuot

  const bao = (p) => {
    if (daBiHuy() || !tabId) return
    // Trang có thể đã đóng giữa chừng — bỏ qua, không để nó làm hỏng cả lượt dịch.
    chrome.tabs.sendMessage(tabId, { viec: 'tien-do', ...p }).catch(() => {})
  }

  const loiHua = thieuCauHinh()
    .then((thieu) => {
      if (thieu) return { ok: false, ma: 0, loi: thieu, da_mo_cai_dat: true }
      return dichMotTrang(tin.url, tin.anh_base64, tin.anh_mime, bao, daBiHuy)
        .then((d) => ({
          ok: true,
          vung: d.vung,
          che_do: d.che_do,
          anh_da_dich: d.anh_da_dich_data_url || null,
          anh_goc_data_url: d.anh_goc_data_url || null,
        }))
    })
    .catch((e) => {
      // Phiên hết hạn giữa chừng cũng đưa thẳng tới chỗ đăng nhập lại.
      if (e?.ma === 401) chrome.runtime.openOptionsPage()
      // `chi_tiet` đi kèm để content script nói được câu tử tế cho 429 (trần, giờ reset) —
      // thiếu nó thì chế độ dịch cả chapter chỉ báo được "hết lượt" mà không nói bao giờ có lại.
      return { ok: false, ma: e?.ma ?? 0, loi: String(e?.message || e), chi_tiet: e?.chiTiet ?? null }
    })
    .finally(() => {
      viecDangChayTheoUrl.delete(khoaUrl)
    })

  if (tin.url) viecDangChayTheoUrl.set(khoaUrl, loiHua)
  loiHua.then((kq) => traLoi(kq))
  return true // giữ kênh mở cho phản hồi bất đồng bộ
})

// E99 + E102 — Phím tắt toàn cục:
// - `Alt+Q` (`dich-trang-nay`): Dịch 1 trang hiện tại
// - `Alt+A` (`dich-ca-chapter`): Dịch toàn bộ chapter
// - `Alt+W` (`tu-dich-khi-cuon`): Bật/tắt tự động dịch khi cuộn trang
// - `Alt+S` (`khoanh-vung-dich`): Khoanh vùng dịch trên màn hình
if (chrome.commands?.onCommand) {
  chrome.commands.onCommand.addListener(async (lenh) => {
    await chayLenhPhimTat(lenh)
  })
}
