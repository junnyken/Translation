/** E21: gõ đè `raw_text` + phóng to đối chiếu ảnh gốc, ngay tại màn sửa tay (M7).
 *
 * REPORT_E20a/E20b đo được: chữ mảnh trên nền tranh phức tạp không path OCR tự động nào (kể cả
 * Tesseract + 4 kiểu tiền xử lý) tự sửa được — lối thoát duy nhất là người dùng tự gõ lại, đúng
 * chữ, sau khi đối chiếu ảnh gốc phóng to.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api.js'
import RegionPanel from './RegionPanel.jsx'

const vungGoc = () => ({
  id: 'r1', reading_order: 1, bbox: { x: 10, y: 20, w: 100, h: 40 },
  fit_status: 'fit_ok', ocr_status: 'ok', status: 'ok', translation_status: 'ok',
  raw_text: 'HELLO', ocr_edited_by_user: false,
  translated_text: 'Xin chào', translation_edited_by_user: false,
  font_family: 'Bangers', font_size: 24, typeset_edited_by_user: false,
})

const dungChung = { fontFamilies: ['Bangers', 'Roboto'], coMin: 8, coMax: 40, dangBan: false }

beforeEach(() => {
  vi.restoreAllMocks()
})

describe('chữ gốc — sửa tay (E21)', () => {
  it('hiện raw_text trong ô SỬA ĐƯỢC, không còn là chữ tĩnh', async () => {
    render(<RegionPanel pageId="p1" region={vungGoc()} {...dungChung}
                        onLuu={vi.fn()} onDichLai={vi.fn()} onDocLai={vi.fn()} onCanhLai={vi.fn()} />)

    const o = screen.getByPlaceholderText('Chưa đọc được chữ nào…')
    expect(o).toHaveValue('HELLO')
    expect(o.tagName).toBe('TEXTAREA')
    expect(o).not.toBeDisabled()
  })

  it('trạng thái "máy đọc" / "đã sửa tay" theo ocr_edited_by_user', () => {
    const { rerender } = render(
      <RegionPanel pageId="p1" region={vungGoc()} {...dungChung}
                   onLuu={vi.fn()} onDichLai={vi.fn()} onDocLai={vi.fn()} onCanhLai={vi.fn()} />,
    )
    expect(screen.getByText('máy đọc')).toBeInTheDocument()

    rerender(
      <RegionPanel pageId="p1" region={{ ...vungGoc(), ocr_edited_by_user: true }} {...dungChung}
                   onLuu={vi.fn()} onDichLai={vi.fn()} onDocLai={vi.fn()} onCanhLai={vi.fn()} />,
    )
    expect(screen.getByText('đã sửa tay')).toBeInTheDocument()
  })

  it('sửa raw_text rồi Lưu gửi ĐÚNG trường raw_text, KHÔNG kèm translated_text chưa đổi', async () => {
    const onLuu = vi.fn()
    render(<RegionPanel pageId="p1" region={vungGoc()} {...dungChung}
                        onLuu={onLuu} onDichLai={vi.fn()} onDocLai={vi.fn()} onCanhLai={vi.fn()} />)

    const o = screen.getByPlaceholderText('Chưa đọc được chữ nào…')
    await userEvent.clear(o)
    await userEvent.type(o, 'HELLO THERE')

    const nutLuu = screen.getByRole('button', { name: /Lưu & canh lại/ })
    expect(nutLuu).toBeEnabled()
    await userEvent.click(nutLuu)

    expect(onLuu).toHaveBeenCalledWith('r1', { raw_text: 'HELLO THERE' })
  })

  it('không sửa gì thì nút Lưu vẫn khoá', () => {
    render(<RegionPanel pageId="p1" region={vungGoc()} {...dungChung}
                        onLuu={vi.fn()} onDichLai={vi.fn()} onDocLai={vi.fn()} onCanhLai={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Lưu & canh lại/ })).toBeDisabled()
  })
})

describe('phóng to đối chiếu ảnh gốc (E21)', () => {
  beforeEach(() => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:gia-lap')
    globalThis.URL.revokeObjectURL = vi.fn()
    // jsdom không có canvas 2D thật — giả một context tối thiểu để code vẽ không ném lỗi.
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage: vi.fn(), strokeRect: vi.fn(), imageSmoothingEnabled: true,
      strokeStyle: '', lineWidth: 0,
    })
    // jsdom Image không tự có natural size / decode() thật — set tay để mô phỏng ảnh 800x600.
    Object.defineProperty(HTMLImageElement.prototype, 'naturalWidth', { configurable: true, value: 800 })
    Object.defineProperty(HTMLImageElement.prototype, 'naturalHeight', { configurable: true, value: 600 })
    HTMLImageElement.prototype.decode = vi.fn().mockResolvedValue(undefined)
  })

  it('bấm "Phóng to đối chiếu" mở modal, tải ảnh gốc ĐÚNG page đang mở', async () => {
    const taiVe = vi.spyOn(api, 'taiVeBlobUrl').mockResolvedValue('blob:anh-goc')

    render(<RegionPanel pageId="page-42" region={vungGoc()} {...dungChung}
                        onLuu={vi.fn()} onDichLai={vi.fn()} onDocLai={vi.fn()} onCanhLai={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Phóng to đối chiếu' }))

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText(/Ảnh gốc — chưa xoá chữ/)).toBeInTheDocument()
    await waitFor(() => expect(taiVe).toHaveBeenCalledWith(api.duongDanAnhGoc('page-42')))
  })

  it('đóng modal bằng nút Đóng', async () => {
    vi.spyOn(api, 'taiVeBlobUrl').mockResolvedValue('blob:anh-goc')
    render(<RegionPanel pageId="p1" region={vungGoc()} {...dungChung}
                        onLuu={vi.fn()} onDichLai={vi.fn()} onDocLai={vi.fn()} onCanhLai={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Phóng to đối chiếu' }))
    await screen.findByRole('dialog')
    await userEvent.click(screen.getByRole('button', { name: 'Đóng' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('tải ảnh gốc lỗi thì báo rõ, không im lặng trắng trơn', async () => {
    vi.spyOn(api, 'taiVeBlobUrl').mockRejectedValue(new Error('401: chưa đăng nhập'))
    render(<RegionPanel pageId="p1" region={vungGoc()} {...dungChung}
                        onLuu={vi.fn()} onDichLai={vi.fn()} onDocLai={vi.fn()} onCanhLai={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: 'Phóng to đối chiếu' }))

    expect(await screen.findByText(/Không tải được ảnh gốc/)).toBeInTheDocument()
  })
})
