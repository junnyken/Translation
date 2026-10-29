/** Service worker MV3 — CHỈ nối dây sự kiện.
 *
 * Chrome tắt worker này sau một lúc không việc rồi dựng lại từ đầu khi có sự kiện. Nên ở đây
 * **không có biến toàn cục nào giữ trạng thái**: không cache chapter, không đếm job, không hẹn
 * giờ hỏi máy chủ. Thứ duy nhất được nhớ nằm ở `chrome.storage.local`; trạng thái backend thì
 * hỏi lại mỗi lần panel mở.
 *
 * Có đúng hai việc: bấm biểu tượng thì mở Side Panel, và lần cài đầu thì ghi cài đặt mặc định.
 */

import { caiDatMacDinh } from './lib/storage-schema.js'
import { ghiCaiDat, layCaiDat } from './lib/settings.js'

// Bấm biểu tượng trên thanh công cụ = mở Side Panel. Đặt một lần lúc worker dựng lại cũng
// không sao — đây là lệnh đặt cấu hình, không phải trạng thái tích luỹ.
chrome.sidePanel
  ?.setPanelBehavior({ openPanelOnActionClick: true })
  .catch((e) => console.error('[Translation Companion] không đặt được hành vi Side Panel:', e))

chrome.runtime.onInstalled.addListener(async () => {
  try {
    // `layCaiDat` tự lọc bản hỏng về mặc định, nên ghi lại là đủ để có kho hợp khuôn.
    const cai_dat = await layCaiDat()
    await ghiCaiDat(cai_dat)
  } catch (e) {
    console.error('[Translation Companion] không dựng được cài đặt mặc định:', e)
    try { await ghiCaiDat(caiDatMacDinh()) } catch { /* hết đường thì để panel tự xử */ }
  }
})
