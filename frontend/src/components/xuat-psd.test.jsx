/** E78 — lựa chọn xuất PSD nhiều lớp.
 *
 * Canh ba thứ: lựa chọn CÓ trong danh sách với đúng nhãn, câu giải thích nói rõ lớp chữ là lớp
 * ảnh (chưa gõ sửa được), và bấm xuất thì gửi ĐÚNG `psd` lên máy chủ rồi cho tải file về.
 */
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ExportPanel from './ExportPanel.jsx'

const ok = (than) => Promise.resolve(
  { ok: true, status: 200, statusText: '', json: () => Promise.resolve(than) },
)

function dungFetch() {
  const daGui = []
  vi.spyOn(globalThis, 'fetch').mockImplementation((url, opt) => {
    const u = String(url)
    if (u.includes('export-preview')) {
      return ok({ page_count: 2, total_page_count: 2, skipped_page_count: 0,
                  overflow_warning_count: 0, font_missing_count: 0 })
    }
    if (u.includes('/export-jobs/')) {
      return ok({ id: 'j1', status: 'done', format: daGui.at(-1), page_count: 2,
                  output_path: '/x_psd_chapter.zip', error_log: null })
    }
    if (u.endsWith('/export') && opt?.method === 'POST') {
      daGui.push(JSON.parse(opt.body).format)
      return ok({ job_id: 'j1' })
    }
    return ok({ overflow_warning_count: 0, needs_manual_count: 0, font_missing_count: 0,
                acknowledged: true, acknowledged_at: '2026-10-15T07:00:00Z',
                glossary_approved_count: 0 })
  })
  return daGui
}

const nut = (ten) => screen.getByRole('button', { name: new RegExp(ten, 'i') })

beforeEach(() => { vi.restoreAllMocks() })

describe('E78 — xuất PSD nhiều lớp', () => {
  it('có lựa chọn PSD với nhãn nói rõ mở bằng Photoshop/Photopea', async () => {
    dungFetch()
    render(<ExportPanel projectId="p1" tenProject="t" chuKyTrang="typeset_done,typeset_done" />)
    await waitFor(() => expect(nut('Xuất chapter')).toBeEnabled())

    const opt = screen.getByRole('option', { name: /PSD — nhiều lớp, mở bằng Photoshop\/Photopea/ })
    expect(opt).toHaveValue('psd')
  })

  it('chọn PSD thì giải thích các lớp và nói trước chữ chưa gõ sửa được', async () => {
    dungFetch()
    render(<ExportPanel projectId="p1" tenProject="t" chuKyTrang="typeset_done,typeset_done" />)
    await waitFor(() => expect(nut('Xuất chapter')).toBeEnabled())

    await userEvent.selectOptions(screen.getByRole('combobox'), 'psd')
    expect(screen.getByText(/ảnh gốc \(đang ẩn\), ảnh đã xoá chữ/i)).toBeInTheDocument()
    expect(screen.getByText(/chưa gõ sửa chữ được/i)).toBeInTheDocument()
  })

  it('bấm xuất gửi ĐÚNG psd và xong thì cho tải file về', async () => {
    const daGui = dungFetch()
    render(<ExportPanel projectId="p1" tenProject="t" chuKyTrang="typeset_done,typeset_done" />)
    await waitFor(() => expect(nut('Xuất chapter')).toBeEnabled())

    await userEvent.selectOptions(screen.getByRole('combobox'), 'psd')
    await userEvent.click(nut('Xuất chapter'))
    await waitFor(() => expect(nut('Tải file về')).toBeInTheDocument())
    expect(daGui).toEqual(['psd'])
    // Hướng dẫn riêng của CBZ không được hiện nhầm cho PSD.
    expect(screen.queryByText(/thực chất là/i)).not.toBeInTheDocument()
  })
})
