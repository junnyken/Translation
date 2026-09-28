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
  veMayChu()
}

/** Nói ra BƯỚC NÀO đang tốn tiền, đọc từ `/healthz` của chính máy chủ đang cấu hình.
 *
 * Lý do tồn tại: đo được 28-09-2026 rằng production chạy `DETECT_ENGINE=ai_gemini`, tức **bước
 * nhận diện bong bóng cũng gọi mô hình ngoài** — mỗi trang tốn hai lượt trả tiền, không phải một.
 * Ô "Chất lượng dịch" ở trên chỉ chọn được engine DỊCH, nên người dùng chọn "Miễn phí" rất dễ
 * tưởng cả lượt là miễn phí. Với nút "Dịch cả chapter" thì hiểu nhầm đó nhân lên theo số trang.
 *
 * Hỏng thì IM LẶNG (ẩn dòng này) chứ không báo lỗi: đây là thông tin thêm, không phải thứ chặn
 * người dùng dịch. Nhưng cũng KHÔNG đoán bừa "miễn phí" khi không đọc được.
 */
async function veMayChu() {
  const o = $('may-chu')
  try {
    const { diaChi } = await docCauHinh()
    if (!diaChi) return
    const r = await fetch(`${diaChi}/healthz`, { cache: 'no-store' })
    if (!r.ok) return
    const d = await r.json()
    const ton_tien = []
    if (d.detect_engine && d.detect_engine !== 'ctd') ton_tien.push('nhận diện bong bóng')
    if ($('engine').value === 'llm_context') ton_tien.push('dịch')
    o.textContent = ton_tien.length
      ? `Máy chủ: ${ton_tien.join(' và ')} đang dùng mô hình ngoài — TỐN PHÍ mỗi trang `
        + `(detect_engine=${d.detect_engine}).`
      : `Máy chủ: chạy hoàn toàn cục bộ, không tốn phí mỗi trang.`
    o.hidden = false
  } catch {
    /* không đọc được thì thôi — không đoán bừa là miễn phí */
  }
}

$('engine').addEventListener('change', () => veMayChu())

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

/** Tiêm content script. `bulk` bật chế độ dịch cả chapter (E59).
 *
 * Cờ đặt qua `chrome.storage.local` chứ không truyền tham số: `executeScript` với `files:` không
 * nhận đối số, và content script ĐỌC LÀ XOÁ cờ — để lại thì lần bấm "Dịch trang này" sau đó sẽ
 * chạy nguyên cả chapter, tiêu hạn mức cho một việc người dùng không yêu cầu.
 */
async function tiem(bulk) {
  if (bulk) await chrome.storage.local.set({ __e59_bulk: true })
  else await chrome.storage.local.remove('__e59_bulk')
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['src/content/index.js'] })
}

$('nut-dich-chapter').addEventListener('click', async () => {
  const nut = $('nut-dich-chapter')
  nut.disabled = true
  nut.textContent = 'Đang mở…'
  try {
    await tiem(true)
    window.close()
  } catch (err) {
    nut.disabled = false
    nut.textContent = 'Dịch cả chapter'
    // Cờ đã đặt nhưng không tiêm được ⇒ phải xoá, không thì lần bấm "Dịch trang này" kế tiếp sẽ
    // vô tình chạy cả chapter.
    await chrome.storage.local.remove('__e59_bulk')
    bao(`Không chạy được trên trang này.\n${err?.message || err}`, 'loi')
  }
})

$('nut-dich').addEventListener('click', async () => {
  const nut = $('nut-dich')
  nut.disabled = true
  nut.textContent = 'Đang mở…'
  try {
    await tiem(false)
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
