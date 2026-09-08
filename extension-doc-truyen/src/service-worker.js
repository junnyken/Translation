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
import { LoiApi, docCauHinh, guiTrang, layTrang, lyDoThieuCauHinh } from './lib/api.js'

/** Hỏi lại mỗi 3 giây. Ngắn hơn thì tốn lượt gọi vô ích cho một việc dài ~45s; dài hơn thì
 *  người dùng thấy chữ hiện ra chậm hơn thực tế. */
const NHIP_HOI_MS = 3000
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

async function dichMotTrang(url, anhBase64, anhMime, bao) {
  bao({ giai_doan: 'dang-tai-anh' })
  const blob = anhBase64 ? base64ThanhBlob(anhBase64, anhMime) : await taiAnh(url)

  bao({ giai_doan: 'dang-gui' })
  const { ngonNgu, engine } = await docCauHinh()
  const { page_id } = await guiTrang(blob, ngonNgu, engine)

  const han = Date.now() + TRAN_CHO_MS
  for (;;) {
    const d = await layTrang(page_id)
    bao({ giai_doan: 'dang-xu-ly', tien_do: d.tien_do, vung: d.vung })
    if (d.loi) throw new LoiApi(0, d.loi)
    if (d.xong) return d
    if (Date.now() > han) {
      throw new LoiApi(0, 'Quá 5 phút chưa xong — máy chủ đang quá tải hoặc việc bị kẹt.')
    }
    await new Promise((r) => setTimeout(r, NHIP_HOI_MS))
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
  const ly_do = lyDoThieuCauHinh(await docCauHinh())
  if (ly_do) chrome.runtime.openOptionsPage()
  return ly_do
}


chrome.runtime.onMessage.addListener((tin, gui_tu, traLoi) => {
  if (tin?.viec !== 'dich-anh') return false

  const bao = (p) => {
    // Trang có thể đã đóng giữa chừng — bỏ qua, không để nó làm hỏng cả lượt dịch.
    chrome.tabs.sendMessage(gui_tu.tab.id, { viec: 'tien-do', ...p }).catch(() => {})
  }
  thieuCauHinh()
    .then((thieu) => {
      if (thieu) return traLoi({ ok: false, ma: 0, loi: thieu, da_mo_cai_dat: true })
      return dichMotTrang(tin.url, tin.anh_base64, tin.anh_mime, bao)
        .then((d) => traLoi({ ok: true, vung: d.vung }))
    })
    .catch((e) => {
      // Phiên hết hạn giữa chừng cũng đưa thẳng tới chỗ đăng nhập lại.
      if (e?.ma === 401) chrome.runtime.openOptionsPage()
      traLoi({ ok: false, ma: e?.ma ?? 0, loi: String(e?.message || e) })
    })
  return true // giữ kênh mở cho phản hồi bất đồng bộ
})

// KHÔNG có `chrome.action.onClicked` ở đây: manifest khai `action.default_popup`, nên Chrome
// không bao giờ gửi sự kiện đó nữa (có popup thì bấm icon luôn mở popup, không phát `onClicked`).
// Việc tiêm content script khi bấm "Dịch trang này" nằm trong `src/popup/index.js` — đứng ở đây
// sẽ là mã chết, không lỗi gì cả nên rất dễ tưởng nhầm là vẫn còn chạy.
