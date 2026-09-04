/** F1 giao diện — việc hỏng phải TỰ hiện ra, không đợi người dùng bấm mới biết.
 *
 * Sự cố thật 04/09: bước căn chữ chết sau 34 mili giây vì font thiếu glyph. Trang đứng ở
 * `translated`, mà `translated` không nằm trong danh sách "đã xong" nên màn tiến độ cứ quay
 * "đang cập nhật…". Người dùng ngồi đợi 10 phút một việc đã chết, vì lý do bị giấu sau một
 * nút phải bấm mới hiện.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChapterProgress from './ChapterProgress.jsx'
import ChapterSummary from './ChapterSummary.jsx'
import * as api from '../../api.js'

const project = (trangThai = 'translated') => ({
  id: 'p1', name: 'test 2', source_lang: 'ja', intended_use: 'personal',
  pages: [{ id: 'pg1', order: 1, status: trangThai }],
})

const VIEC_HONG = {
  id: 'j1', page_id: 'pg1', type: 'typeset', status: 'failed',
  error_log: "MissingGlyph: font thiếu glyph cho '．'",
}

beforeEach(() => vi.restoreAllMocks())

describe('lỗi tự hiện ở màn tiến độ', () => {
  it('hiện BƯỚC nào hỏng và LÝ DO mà không cần bấm gì', async () => {
    vi.spyOn(api, 'layViecHongCuaChapter').mockResolvedValue([VIEC_HONG])
    render(<ChapterProgress project={project()} onNapLai={vi.fn()} />)

    await waitFor(() => expect(screen.getByText(/căn chữ/)).toBeInTheDocument())
    expect(screen.getByText(/font thiếu glyph/)).toBeInTheDocument()
    // và không còn bắt người dùng đi tìm nút "Vì sao?" nữa
    expect(screen.queryByRole('button', { name: /Vì sao/ })).not.toBeInTheDocument()
  })

  it('trang có việc hỏng thì KHÔNG được coi là "đang cập nhật…" nữa', async () => {
    vi.spyOn(api, 'layViecHongCuaChapter').mockResolvedValue([VIEC_HONG])
    render(<ChapterProgress project={project()} onNapLai={vi.fn()} />)

    await waitFor(() =>
      expect(screen.getByText(/có bước đã hỏng/)).toBeInTheDocument())
    expect(screen.queryByText(/đang cập nhật/)).not.toBeInTheDocument()
  })

  it('không có việc nào hỏng thì giữ nguyên hành vi cũ: vẫn quay, vẫn có nút Vì sao', async () => {
    vi.spyOn(api, 'layViecHongCuaChapter').mockResolvedValue([])
    vi.spyOn(api, 'layLyDoDung').mockResolvedValue(null)
    render(<ChapterProgress project={project('ocr_done')} onNapLai={vi.fn()} />)

    expect(screen.getByText(/đang cập nhật/)).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Vì sao/ })).toBeInTheDocument())
  })

  it('hỏi danh sách việc hỏng mà lỗi thì màn tiến độ vẫn chạy, không trắng trang', async () => {
    vi.spyOn(api, 'layViecHongCuaChapter').mockRejectedValue(new Error('mạng hỏng'))
    vi.spyOn(api, 'layLyDoDung').mockResolvedValue(null)
    render(<ChapterProgress project={project()} onNapLai={vi.fn()} />)

    expect(screen.getByText(/Tiến độ xử lý/)).toBeInTheDocument()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Vì sao/ })).toBeInTheDocument())
  })
})

describe('bong bóng trống vì font thiếu glyph', () => {
  const tienDoXong = {
    tong: 1, so_xong: 1, so_hong: 0, san_sang_ra_soat: true, buoc: [],
  }

  it('đếm riêng, KHÔNG gộp vào số vùng tràn khung', () => {
    render(<ChapterSummary
      tienDo={tienDoXong}
      canhBao={{ overflow_warning_count: 0, needs_manual_count: 0, font_missing_count: 3 }}
      trangDau="pg1" onXuat={vi.fn()} />)

    expect(screen.getByText(/còn chỗ cần sửa/)).toBeInTheDocument()
    expect(screen.getByText(/font không có ký tự/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /còn 3 vùng cần sửa/ })).toBeInTheDocument()
  })

  it('không có vùng nào hỏng thì không doạ người dùng', () => {
    render(<ChapterSummary
      tienDo={tienDoXong}
      canhBao={{ overflow_warning_count: 0, needs_manual_count: 0, font_missing_count: 0 }}
      trangDau="pg1" onXuat={vi.fn()} />)

    expect(screen.getByText(/Không có vùng nào bị đánh dấu cần sửa/)).toBeInTheDocument()
  })
})
