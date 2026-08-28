import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../api.js'
import ChapterCreateForm, { lyDoChuaTaoDuoc } from './ChapterCreateForm.jsx'

const anh = (ten) => new File(['x'], ten, { type: 'image/png' })

afterEach(() => vi.restoreAllMocks())

describe('điều kiện tạo chapter', () => {
  it('nói đúng thứ còn thiếu, theo thứ tự người dùng gặp', () => {
    expect(lyDoChuaTaoDuoc({ ten: '', mucDich: '', files: [] })).toMatch(/tên/i)
    expect(lyDoChuaTaoDuoc({ ten: 'A', mucDich: '', files: [] })).toMatch(/mục đích/i)
    expect(lyDoChuaTaoDuoc({ ten: 'A', mucDich: 'study', files: [] }))
      .toMatch(/ít nhất một ảnh/i)
    expect(lyDoChuaTaoDuoc({ ten: 'A', mucDich: 'study', files: [anh('a.png')] })).toBeNull()
  })

  it('tên chỉ có khoảng trắng vẫn là thiếu tên', () => {
    expect(lyDoChuaTaoDuoc({ ten: '   ', mucDich: 'study', files: [anh('a.png')] }))
      .toMatch(/tên/i)
  })
})

describe('form tạo chapter', () => {
  it('KHÔNG chọn sẵn mục đích sử dụng — người dùng phải tự khai', () => {
    render(<ChapterCreateForm onXong={() => {}} />)
    expect(screen.getByLabelText(/Mục đích sử dụng/)).toHaveValue('')
  })

  it('nút bị khoá kèm lý do cho tới khi đủ điều kiện', async () => {
    render(<ChapterCreateForm onXong={() => {}} />)
    const nut = screen.getByRole('button', { name: /Tạo chapter & bắt đầu dịch/ })
    expect(nut).toBeDisabled()
    expect(screen.getByText(/Cần đặt tên cho chapter/)).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/Tên chapter/), 'Chương 1')
    expect(screen.getByText(/Cần chọn mục đích sử dụng/)).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    expect(screen.getByText(/Cần chọn ít nhất một ảnh/)).toBeInTheDocument()
  })

  it('gửi đúng hợp đồng API hiện có và tải trang theo đúng thứ tự đã chọn', async () => {
    const taoProject = vi.spyOn(api, 'taoProject').mockResolvedValue({ id: 'du-an-1' })
    const taiTrangLen = vi.spyOn(api, 'taiTrangLen').mockResolvedValue({ page_id: 'p' })
    const onXong = vi.fn()
    const { container } = render(<ChapterCreateForm onXong={onXong} />)

    await userEvent.type(screen.getByLabelText(/Tên chapter/), 'Chương 1')
    await userEvent.selectOptions(screen.getByLabelText(/Ngôn ngữ gốc/), 'ja')
    await userEvent.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'personal')
    await userEvent.upload(container.querySelector('input[type="file"]'),
                           [anh('01.png'), anh('02.png')])

    await userEvent.click(screen.getByRole('button', { name: /Tạo chapter & bắt đầu dịch/ }))

    await waitFor(() => expect(onXong).toHaveBeenCalledWith('du-an-1'))
    expect(taoProject).toHaveBeenCalledWith({
      name: 'Chương 1', source_lang: 'ja', intended_use: 'personal',
    })
    expect(taiTrangLen.mock.calls.map((c) => c[1].name)).toEqual(['01.png', '02.png'])
  })

  it('lỗi khi tạo thì GIỮ nguyên tên và danh sách file đã chọn', async () => {
    vi.spyOn(api, 'taoProject').mockRejectedValue(new Error('500: máy chủ lỗi'))
    const { container } = render(<ChapterCreateForm onXong={() => {}} />)

    await userEvent.type(screen.getByLabelText(/Tên chapter/), 'Chương 9')
    await userEvent.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await userEvent.upload(container.querySelector('input[type="file"]'), [anh('01.png')])
    await userEvent.click(screen.getByRole('button', { name: /Tạo chapter & bắt đầu dịch/ }))

    await screen.findByText(/500: máy chủ lỗi/)
    expect(screen.getByLabelText(/Tên chapter/)).toHaveValue('Chương 9')
    expect(screen.getByText('01.png')).toBeInTheDocument()
  })

  it('không hứa thời gian xử lý cụ thể', () => {
    render(<ChapterCreateForm onXong={() => {}} />)
    expect(screen.getByText(/Xử lý chạy nền/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/\d+\s*[-–]\s*\d+\s*phút/)
  })
})
