/** E40 — người dùng tải file về mà KHÔNG mở được.
 *
 * Ca thật (14/09): chạy xong một chapter, chọn định dạng mặc định `CBZ`, bấm "Tải file về", ra
 * `chapter-….cbz` — và Windows không mở được vì không có ứng dụng nào nhận đuôi `.cbz`. Bảng
 * xuất lúc đó chỉ nói CBZ "đọc bằng ứng dụng truyện tranh", không nói thẳng là **bấm đúp sẽ
 * không ra gì**, cũng không chỉ đường ra khỏi tình huống.
 *
 * Backend đã có `zip` từ M8 — nên đây là lỗi CHỈ ĐƯỜNG, không phải thiếu tính năng. Bộ này canh
 * hai thứ: lời cảnh báo phải có TRƯỚC khi xuất, và phải có đúng một cú bấm để lấy lại cùng nội
 * dung ở dạng mở được.
 */
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ExportPanel from './ExportPanel.jsx'

const ok = (than) => Promise.resolve(
  { ok: true, status: 200, statusText: '', json: () => Promise.resolve(than) },
)

/** Giả lập đủ vòng: xem trước → xuất → job xong. Ghi lại định dạng ĐÃ GỬI LÊN. */
function dungFetch() {
  const daGui = []
  vi.spyOn(globalThis, 'fetch').mockImplementation((url, opt) => {
    const u = String(url)
    if (u.includes('export-preview')) {
      return ok({ page_count: 2, total_page_count: 2, skipped_page_count: 0,
                  overflow_warning_count: 0, font_missing_count: 0 })
    }
    if (u.includes('/export-jobs/')) {
      return ok({ id: 'j1', status: 'done', format: daGui.at(-1),
                  output_path: `/x.${daGui.at(-1)}`, error_log: null })
    }
    if (u.endsWith('/export') && opt?.method === 'POST') {
      daGui.push(JSON.parse(opt.body).format)
      return ok({ job_id: 'j1' })
    }
    return ok({ overflow_warning_count: 0, needs_manual_count: 0, font_missing_count: 0,
                acknowledged: true, acknowledged_at: '2026-09-14T07:29:06Z',
                glossary_approved_count: 0 })
  })
  return daGui
}

const nut = (ten) => screen.getByRole('button', { name: new RegExp(ten, 'i') })

beforeEach(() => { vi.restoreAllMocks() })

describe('E40 — file xuất ra phải mở được', () => {
  it('nói thẳng CBZ không mở sẵn được, TRƯỚC khi người dùng bấm xuất', async () => {
    dungFetch()
    render(<ExportPanel projectId="p1" tenProject="t" chuKyTrang="typeset_done,typeset_done" />)

    await waitFor(() => expect(nut('Xuất chapter')).toBeEnabled())
    expect(screen.getByText(/KHÔNG mở sẵn đuôi \.cbz/i)).toBeInTheDocument()
  })

  it('chọn ZIP thì nói rõ là mở được ngay, không cần cài gì', async () => {
    dungFetch()
    render(<ExportPanel projectId="p1" tenProject="t" chuKyTrang="typeset_done,typeset_done" />)
    await waitFor(() => expect(nut('Xuất chapter')).toBeEnabled())

    await userEvent.selectOptions(screen.getByRole('combobox'), 'zip')
    expect(screen.getByText(/Cùng nội dung với CBZ/i)).toBeInTheDocument()
  })

  it('xuất CBZ xong thì chỉ cách mở file, không để người dùng tự đoán', async () => {
    dungFetch()
    render(<ExportPanel projectId="p1" tenProject="t" chuKyTrang="typeset_done,typeset_done" />)
    await waitFor(() => expect(nut('Xuất chapter')).toBeEnabled())

    await userEvent.click(nut('Xuất chapter'))
    await waitFor(() => expect(nut('Tải file về')).toBeInTheDocument())
    expect(screen.getByText(/thực chất là/i)).toBeInTheDocument()
  })

  it('"Xuất lại bằng ZIP" phải gửi ĐÚNG zip, không gửi lại cbz', async () => {
    // Bẫy thật: `setDinhDang` của React chỉ có hiệu lực ở lượt vẽ SAU, nên nút dựa vào state sẽ
    // gửi lại đúng `cbz` vừa xuất — người dùng bấm mà không có gì đổi.
    const daGui = dungFetch()
    render(<ExportPanel projectId="p1" tenProject="t" chuKyTrang="typeset_done,typeset_done" />)
    await waitFor(() => expect(nut('Xuất chapter')).toBeEnabled())

    await userEvent.click(nut('Xuất chapter'))
    await waitFor(() => expect(nut('Xuất lại bằng ZIP')).toBeInTheDocument())
    expect(daGui).toEqual(['cbz'])

    await userEvent.click(nut('Xuất lại bằng ZIP'))
    await waitFor(() => expect(daGui).toEqual(['cbz', 'zip']))
    // Xuất dạng mở được rồi thì không còn lời chỉ đường về .cbz nữa.
    await waitFor(() => expect(screen.queryByRole('button', { name: /Xuất lại bằng ZIP/i })).toBeNull())
  })
})
