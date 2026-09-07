/** Service worker (E19-4).
 *
 * Làm ĐÚNG hai việc content script không làm được:
 *
 * 1. **Tải byte ảnh.** Content script đọc ảnh qua canvas sẽ dính `SecurityError` — ảnh khác
 *    nguồn làm nhiễm bẩn canvas và `toDataURL` bị chặn. Service worker có `host_permissions`
 *    nên `fetch` thẳng được, không qua CORS.
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

async function dichMotTrang(url, bao) {
  bao({ giai_doan: 'dang-tai-anh' })
  const blob = await taiAnh(url)

  bao({ giai_doan: 'dang-gui' })
  const { page_id } = await guiTrang(blob)

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
      return dichMotTrang(tin.url, bao)
        .then((d) => traLoi({ ok: true, vung: d.vung }))
    })
    .catch((e) => {
      // Phiên hết hạn giữa chừng cũng đưa thẳng tới chỗ đăng nhập lại.
      if (e?.ma === 401) chrome.runtime.openOptionsPage()
      traLoi({ ok: false, ma: e?.ma ?? 0, loi: String(e?.message || e) })
    })
  return true // giữ kênh mở cho phản hồi bất đồng bộ
})

chrome.action.onClicked.addListener(async (tab) => {
  // Tiêm khi bấm chứ không tiêm sẵn vào mọi trang: `<all_urls>` đã là quyền rộng nhất Chrome
  // cấp, không cần chạy mã ở mọi tab người dùng mở.
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['src/content/index.js'],
    })
  } catch (e) {
    // Trang nội bộ của Chrome (chrome://, cửa hàng tiện ích) không cho tiêm — nói ra thay vì im.
    console.warn('Không chạy được trên trang này:', e)
  }
})
