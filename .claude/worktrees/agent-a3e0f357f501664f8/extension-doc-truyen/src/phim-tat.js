/** Bộ lắng nghe phím tắt siêu nhẹ trên trang (`Alt+Q`, `Alt+A`, `Alt+W`, `Alt+S`).
 *
 * Vì sao cần tệp này bên cạnh `commands` trong `manifest.json`:
 * Khi người dùng cập nhật tiện ích bằng nút "Tải lại (Reload)" trong `chrome://extensions`, Chrome
 * thường bỏ trống phím tắt của các lệnh mới thêm (`Alt+A`, `Alt+W`) cho tới khi người dùng gỡ ra
 * cài lại hoặc tự vào `chrome://extensions/shortcuts` gán tay.
 *
 * Tệp này hoàn toàn ngủ yên (0 tốn RAM/DOM), chỉ bắt đúng tổ hợp `Alt+Q / A / W / S` khi người dùng
 * bấm phím trên trang đọc truyện và chưa tiêm `src/content/index.js`.
 */
;(() => {
  if (window.__translation_phim_tat_da_cai__) return
  window.__translation_phim_tat_da_cai__ = true

  window.addEventListener('keydown', (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.repeat) return
    const tag = (e.target?.tagName || '').toLowerCase()
    if (tag === 'input' || tag === 'textarea' || e.target?.isContentEditable) return

    // Nếu `src/content/index.js` đã được tiêm trên trang thì bộ lắng nghe bên trong đó tự xử lý.
    if (window.__translation_doc_truyen__?.daCaiPhimAlt) return

    const k = (e.key || '').toLowerCase()
    const bangLenh = {
      q: 'dich-trang-nay',
      a: 'dich-ca-chapter',
      w: 'tu-dich-khi-cuon',
      s: 'khoanh-vung-dich',
    }
    const lenh = bangLenh[k]
    if (!lenh) return

    e.preventDefault()
    try {
      chrome.runtime?.sendMessage?.({ viec: 'phim-tat', lenh })?.catch?.(() => {})
    } catch {
      // Bỏ qua nếu ngữ cảnh tiện ích vừa tải lại
    }
  })
})()
