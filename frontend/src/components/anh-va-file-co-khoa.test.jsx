/** Hai đường KHÔNG mang được mã phiên — bắt được bằng cách bấm tay trên bản chạy thật (04/09).
 *
 * `<img src>` và `<a href>` do trình duyệt tự tải, không cách nào gắn header `Authorization`.
 * Từ slice B mọi endpoint `/api/v1` đòi mã phiên, nên:
 *   - ảnh trang trả 401 ⇒ màn sửa tay trắng trơn, không nhìn được trang, không kéo được khung
 *   - file xuất trả 401 ⇒ nút "Tải file về" bấm vào không ra gì
 *
 * Đo thật: `GET /pages/{id}/typeset-preview` không mã ⇒ 401 · có mã ⇒ 200, 2,1MB PNG.
 *
 * Bộ test cũ KHÔNG bắt được vì nó không bao giờ tải ảnh thật — đây đúng là loại lỗi chỉ lộ ra
 * khi mở trình duyệt vào bản đang chạy.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api.js'
import ExportPanel from './ExportPanel.jsx'

beforeEach(() => {
  vi.restoreAllMocks()
  globalThis.URL.createObjectURL = vi.fn(() => 'blob:gia-lap')
  globalThis.URL.revokeObjectURL = vi.fn()
})

describe('tải tài nguyên có khoá', () => {
  it('gửi mã phiên khi tải ảnh, và trả blob URL', async () => {
    api.luuMaPhien('ma-phien-that')
    const goi = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, blob: async () => new Blob(['x']),
    })

    const url = await api.taiVeBlobUrl('https://may-chu/anh.png')

    expect(url).toBe('blob:gia-lap')
    expect(goi.mock.calls[0][1].headers.Authorization).toBe('Bearer ma-phien-that')
    api.xoaMaPhien()
  })

  it('máy chủ từ chối thì NÓI RA, không trả blob rỗng', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 401 })
    await expect(api.taiVeBlobUrl('https://may-chu/anh.png')).rejects.toThrow(/401/)
  })

  it('tải file xuất: lấy tên file từ Content-Disposition của máy chủ', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      headers: { get: () => 'attachment; filename="chuong-1.cbz"' },
      blob: async () => new Blob(['x']),
    })
    const the = { href: '', download: '', click: vi.fn(), remove: vi.fn() }
    vi.spyOn(document, 'createElement').mockReturnValue(the)
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => the)

    expect(await api.taiFileXuatVe('job-1')).toBe('chuong-1.cbz')
    expect(the.download).toBe('chuong-1.cbz')
    expect(the.click).toHaveBeenCalled()
  })
})

describe('bảng xuất chapter', () => {
  const xemTruoc = (kw = {}) => ({
    page_count: 1, total_page_count: 1, skipped_page_count: 0,
    overflow_warning_count: 0, font_missing_count: 0, ...kw,
  })

  it('KHÔNG được nói "không có cảnh báo nào" khi có bong bóng trống', async () => {
    // Bắt được bằng mắt trên bản chạy: cùng một màn hình, phía trên báo "1 bong bóng sẽ trống",
    // bảng xuất phía dưới vẫn khẳng định "Không có cảnh báo nào."
    vi.spyOn(api, 'xemTruocXuat').mockResolvedValue(xemTruoc({ font_missing_count: 1 }))
    vi.spyOn(api, 'layCanhBaoXuat').mockResolvedValue({ needs_manual_count: 0 })

    render(<ExportPanel projectId="p1" tenProject="C" />)

    await waitFor(() => expect(screen.getByText(/font không có ký tự/)).toBeInTheDocument())
    expect(screen.queryByText(/Không có cảnh báo nào/)).not.toBeInTheDocument()
  })

  it('sạch thật thì mới được nói là sạch', async () => {
    vi.spyOn(api, 'xemTruocXuat').mockResolvedValue(xemTruoc())
    vi.spyOn(api, 'layCanhBaoXuat').mockResolvedValue({ needs_manual_count: 0 })

    render(<ExportPanel projectId="p1" tenProject="C" />)

    await waitFor(() => expect(screen.getByText(/Không có cảnh báo nào/)).toBeInTheDocument())
  })

  it('nút tải file gọi đường CÓ mã phiên, không phải link trần', async () => {
    vi.spyOn(api, 'xemTruocXuat').mockResolvedValue(xemTruoc())
    vi.spyOn(api, 'layCanhBaoXuat').mockResolvedValue({ needs_manual_count: 0, acknowledged: true })
    vi.spyOn(api, 'xuatChapter').mockResolvedValue({ job_id: 'j1' })
    vi.spyOn(api, 'choXuatXong').mockResolvedValue({
      id: 'j1', status: 'done', format: 'cbz', page_count: 1,
    })
    const tai = vi.spyOn(api, 'taiFileXuatVe').mockResolvedValue('c.cbz')

    render(<ExportPanel projectId="p1" tenProject="C" />)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Xuất chapter' })).toBeEnabled())
    await userEvent.click(screen.getByRole('button', { name: 'Xuất chapter' }))

    const nut = await screen.findByRole('button', { name: /Tải file về/ })
    await userEvent.click(nut)
    expect(tai).toHaveBeenCalledWith('j1')
  })
})
