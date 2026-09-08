/** Popup khi bấm icon (E19-4).
 *
 * Trước đây bấm icon chạy thẳng `chrome.scripting.executeScript` trong `service-worker.js`
 * (không có popup). Có `default_popup` khai trong manifest thì Chrome **không còn gửi**
 * `chrome.action.onClicked` nữa — nên việc tiêm content script phải chuyển hẳn vào đây, không
 * phải thêm, để tránh có hai chỗ cùng làm một việc và một chỗ chết lặng lẽ.
 *
 * Ngôn ngữ đổi ngay tại đây (không phải mở riêng trang Tuỳ chọn): đây là thuộc tính của TRANG
 * đang đọc, đổi theo từng trang web, không phải một lần cấu hình rồi để yên như địa chỉ máy chủ.
 */
import { docCauHinh, luuCauHinh } from '../lib/api.js'

const $ = (id) => document.getElementById(id)
const bao = (chu, loai) => {
  const h = $('bao')
  h.textContent = chu
  h.className = `hop ${loai}`
  h.hidden = false
}

async function ve() {
  const { ngonNgu, engine } = await docCauHinh()
  $('ngon-ngu').value = ngonNgu
  $('engine').value = engine
}

$('ngon-ngu').addEventListener('change', async (e) => {
  await luuCauHinh({ ngonNgu: e.target.value })
})

$('engine').addEventListener('change', async (e) => {
  await luuCauHinh({ engine: e.target.value })
})

$('mo-cai-dat').addEventListener('click', (e) => {
  e.preventDefault()
  chrome.runtime.openOptionsPage()
  window.close()
})

$('nut-dich').addEventListener('click', async () => {
  const nut = $('nut-dich')
  nut.disabled = true
  nut.textContent = 'Đang mở…'
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['src/content/index.js'] })
    // Từ đây content script tự vẽ thông báo NGAY TRÊN TRANG — popup đóng lại, không cần đứng
    // canh: quá trình dịch tốn ~45s, giữ popup mở tới lúc đó chỉ tổ chặn người dùng đọc tiếp.
    window.close()
  } catch (err) {
    nut.disabled = false
    nut.textContent = 'Dịch trang này'
    // Trang nội bộ của Chrome (chrome://, cửa hàng tiện ích) không cho tiêm — nói thẳng lý do
    // thay vì im lặng, đây đúng là ca `Không chạy được trên trang này` trước kia chỉ log console.
    bao(`Không chạy được trên trang này.\n${err?.message || err}`, 'loi')
  }
})

ve()
