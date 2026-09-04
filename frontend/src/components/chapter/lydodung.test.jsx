/** P3j giao diện — "Vì sao trang này đứng im?"
 *
 * Trước P3j, trang dừng vì worker chết nhìn **y hệt** trang đang chạy chậm: cùng nhãn trạng thái,
 * không một chữ nào về lý do. Người vận hành chỉ còn cách đoán hoặc mở log máy chủ — thứ họ không
 * có quyền và cũng không nên cần.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChapterProgress from './ChapterProgress.jsx'
import * as api from '../../api.js'

const project = (kw = {}) => ({
  id: 'p1', name: 'C', source_lang: 'en', intended_use: 'study',
  pages: [{ id: 'pg1', order: 1, status: 'ocr_done' }], ...kw,
})

beforeEach(() => vi.restoreAllMocks())

describe('vì sao trang đứng im', () => {
  it('KHÔNG hỏi máy chủ cho tới khi người dùng bấm', () => {
    const spy = vi.spyOn(api, 'layLyDoDung').mockResolvedValue(null)
    render(<ChapterProgress project={project()} onNapLai={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Vì sao/ })).toBeInTheDocument()
    expect(spy).not.toHaveBeenCalled()
  })

  it('bấm rồi thì nói rõ BƯỚC NÀO hỏng và LÝ DO', async () => {
    vi.spyOn(api, 'layLyDoDung').mockResolvedValue({
      type: 'inpaint', status: 'failed',
      error_log: 'worker_died: tiến trình xử lý bị dừng giữa chừng…',
    })
    render(<ChapterProgress project={project()} onNapLai={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Vì sao/ }))
    await waitFor(() => expect(screen.getByText(/xoá chữ gốc/)).toBeInTheDocument())
    expect(screen.getByText(/worker_died/)).toBeInTheDocument()
  })

  it('trang CHƯA xong: nói thẳng là đang chờ, không im lặng', async () => {
    vi.spyOn(api, 'layLyDoDung').mockResolvedValue(null)
    render(<ChapterProgress project={project()} onNapLai={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Vì sao/ }))
    await waitFor(() => expect(screen.getByText(/đang chờ tới lượt/)).toBeInTheDocument())
  })

  it('trang ĐÃ XONG thì KHÔNG được bảo là "đang chờ tới lượt"', async () => {
    // Bắt được khi kiểm chứng live: trang typeset_done vẫn báo "đang chờ tới lượt" — nó không
    // chờ gì cả, và câu đó khiến người dùng ngồi đợi một thứ không bao giờ tới.
    vi.spyOn(api, 'layLyDoDung').mockResolvedValue(null)
    render(<ChapterProgress
      project={project({ pages: [{ id: 'pg1', order: 1, status: 'typeset_done' }] })}
      onNapLai={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Vì sao/ }))
    await waitFor(() => expect(screen.getByText(/đã xong/)).toBeInTheDocument())
    expect(screen.queryByText(/đang chờ tới lượt/)).not.toBeInTheDocument()
  })

  it('hỏi máy chủ hỏng thì nói ra, KHÔNG giả vờ là "không có gì hỏng"', async () => {
    vi.spyOn(api, 'layLyDoDung').mockRejectedValue(new Error('mạng hỏng'))
    render(<ChapterProgress project={project()} onNapLai={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Vì sao/ }))
    await waitFor(() => expect(screen.getByText(/Không hỏi được máy chủ/)).toBeInTheDocument())
    expect(screen.queryByText(/đang chờ tới lượt/)).not.toBeInTheDocument()
  })

  it('chỉ hỏi MỘT lần dù bấm nhiều lần', async () => {
    const spy = vi.spyOn(api, 'layLyDoDung').mockResolvedValue(null)
    render(<ChapterProgress project={project()} onNapLai={vi.fn()} />)
    const nut = screen.getByRole('button', { name: /Vì sao/ })
    await userEvent.click(nut)
    await waitFor(() => expect(screen.getByText(/đang chờ tới lượt/)).toBeInTheDocument())
    expect(spy).toHaveBeenCalledTimes(1)
  })
})
