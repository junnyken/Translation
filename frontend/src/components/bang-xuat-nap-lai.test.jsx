/** Bảng xuất phải nạp lại con số khi trang chạy xong (05/09).
 *
 * ## Ca đã hỏng trên bản chạy thật
 *
 * Người dùng mở chapter lúc pipeline còn chạy. Bảng xuất ghi *"0 / 2 trang sẽ được xuất"* và
 * khoá nút. Pipeline xong, badge trang đổi thành *"Đã căn chữ, cần rà soát"* — nhưng bảng xuất
 * **vẫn 0/2 và nút vẫn khoá**, cho tới khi tải lại cả trang.
 *
 * API không sai: đo cùng lúc, `export-preview` trả đúng `2/2`. Lỗi nằm ở chỗ `nap()` chỉ phụ
 * thuộc `projectId`, mà `projectId` thì không đổi — nên `useEffect` không chạy lại lần nào,
 * kể cả khi `ChapterProgress` đã nạp lại chapter mỗi 4 giây và trạng thái trang đã đổi.
 */
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import ExportPanel from './ExportPanel.jsx'

/** Con số nằm trong `<b>0</b> / 2 trang…` nên bị tách qua nhiều thẻ — phải so trên textContent
 *  của cả dòng, không so trên một nút chữ. */
const dongDem = () =>
  [...document.querySelectorAll('li')].find((e) => e.textContent.includes('trang sẽ được xuất'))

beforeEach(() => { vi.restoreAllMocks() })

function traLoi(soXong) {
  return (url) => {
    const u = String(url)
    const than = u.includes('export-preview')
      ? { page_count: soXong.n, total_page_count: 2, skipped_page_count: 2 - soXong.n,
          overflow_warning_count: 0, font_missing_count: 0 }
      : { overflow_warning_count: 0, needs_manual_count: 0, font_missing_count: 0,
          acknowledged: false, acknowledged_at: null, glossary_approved_count: 0 }
    return Promise.resolve({ ok: true, status: 200, statusText: '', json: () => Promise.resolve(than) })
  }
}

describe('bảng xuất nạp lại theo trạng thái trang', () => {
  it('trang chạy xong thì con số và nút phải ĐỔI, không đợi tải lại trang', async () => {
    const dem = { n: 0 }
    vi.spyOn(globalThis, 'fetch').mockImplementation(traLoi(dem))

    const { rerender } = render(
      <ExportPanel projectId="p1" tenProject="test" chuKyTrang="queued,queued" />
    )
    await waitFor(() => expect(dongDem()?.textContent).toMatch(/0 \/ 2/))
    expect(screen.getByRole('button', { name: 'Xuất chapter' })).toBeDisabled()

    // Pipeline xong: App truyền chữ ký trạng thái MỚI xuống (projectId KHÔNG đổi).
    dem.n = 2
    rerender(
      <ExportPanel projectId="p1" tenProject="test" chuKyTrang="typeset_done,typeset_done" />
    )

    await waitFor(() => expect(dongDem()?.textContent).toMatch(/2 \/ 2/))
    expect(screen.getByRole('button', { name: 'Xuất chapter' })).toBeEnabled()
  })

  it('trạng thái KHÔNG đổi thì không gọi lại API — tránh hỏi 4 giây một lần vô ích', async () => {
    const dem = { n: 2 }
    const goi = vi.spyOn(globalThis, 'fetch').mockImplementation(traLoi(dem))
    const { rerender } = render(
      <ExportPanel projectId="p1" tenProject="test" chuKyTrang="typeset_done,typeset_done" />
    )
    await waitFor(() => expect(dongDem()?.textContent).toMatch(/2 \/ 2/))
    const truoc = goi.mock.calls.length
    rerender(<ExportPanel projectId="p1" tenProject="test" chuKyTrang="typeset_done,typeset_done" />)
    await new Promise((r) => setTimeout(r, 50))
    expect(goi.mock.calls.length).toBe(truoc)
  })
})
