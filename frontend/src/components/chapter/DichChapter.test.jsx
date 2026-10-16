import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../api.js'
import { datLaiTuTaiVe } from '../../lib/tu-tai-ve.js'
import DichChapter, { datTenTuDong, lyDoChuaChayDuoc } from './DichChapter.jsx'

const anh = (ten) => new File(['x'], ten, { type: 'image/png' })
const goi = (ten) => new File(['PK'], ten, { type: '' })   // .cbz hay bị trình duyệt trả type rỗng
const NUT = /Tạo chapter & dịch/

beforeEach(() => {
  datLaiTuTaiVe()
  // Mặc định: máy chủ CHƯA cấu hình AI ⇒ giữ engine miễn phí.
  vi.spyOn(api, 'layCauHinhMe').mockResolvedValue({ llm_configured: false })
})
afterEach(() => vi.restoreAllMocks())

/** Dựng các lời gọi API để một lượt chạy trọn vẹn thành công. */
function gia({ trang = [{ status: 'ready_for_export' }], id = 'proj-1' } = {}) {
  vi.spyOn(api, 'taoProject').mockResolvedValue({ id })
  vi.spyOn(api, 'taiGoiLen').mockResolvedValue({ so_trang: 2, bo_qua: 1, trang: [] })
  vi.spyOn(api, 'taiTrangLen').mockResolvedValue({ page_id: 'pg-1' })
  vi.spyOn(api, 'layProject').mockResolvedValue({ pages: trang })
  vi.spyOn(api, 'xuatChapter').mockResolvedValue({ job_id: 'ex-1' })
  vi.spyOn(api, 'choXuatXong').mockResolvedValue({})
  vi.spyOn(api, 'taiFileXuatVe').mockResolvedValue('chapter.zip')
  vi.spyOn(api, 'layCanhBaoXuat').mockResolvedValue({})
}

describe('điều kiện chạy', () => {
  it('nói đúng thứ còn thiếu, theo thứ tự người dùng gặp', () => {
    expect(lyDoChuaChayDuoc({ mucDich: '', files: [] })).toMatch(/mục đích/i)
    expect(lyDoChuaChayDuoc({ mucDich: 'study', files: [] })).toMatch(/ít nhất một ảnh/i)
    expect(lyDoChuaChayDuoc({ mucDich: 'study', files: [anh('a.png')] })).toBeNull()
  })

  it('một gói cũng đủ để chạy, không bắt phải có ảnh lẻ', () => {
    expect(lyDoChuaChayDuoc({ mucDich: 'study', files: [goi('ch.cbz')] })).toBeNull()
  })

  it('TÊN không còn bắt buộc (khác ChapterCreateForm cũ)', () => {
    // Hàm không nhận `ten` nữa: để trống tên không bao giờ là lý do khoá nút.
    expect(lyDoChuaChayDuoc({ mucDich: 'study', files: [anh('a.png')], ten: '' })).toBeNull()
  })
})

describe('đặt tên tự động', () => {
  it('bỏ đuôi file và gắn ngày để không đẻ ra 12 chapter trùng tên', () => {
    const ten = datTenTuDong([anh('One Piece ch1.png')], new Date(2026, 8, 22))
    expect(ten).toBe('One Piece ch1 (22-09)')
  })

  it('không có file thì vẫn ra tên dùng được', () => {
    expect(datTenTuDong([], new Date(2026, 8, 22))).toBe('Chapter (22-09)')
  })
})

describe('form gộp một luồng', () => {
  it('KHÔNG còn hàng tab, chỉ MỘT nút chính', () => {
    render(<DichChapter />)
    expect(screen.queryByRole('tablist')).toBeNull()
    expect(screen.queryByRole('tab')).toBeNull()
    expect(screen.getAllByRole('button', { name: NUT })).toHaveLength(1)
    expect(screen.queryByRole('button', { name: /Dịch ngay/ })).toBeNull()
  })

  it('thứ tự: vùng thả → ngôn ngữ → cách dịch → mục đích → tên → tự tải về → nút', () => {
    const { container } = render(<DichChapter />)
    const thu = [
      '#vung-tha-nhanh', null, null, null, null, 'input[type=checkbox]', '#nut-tao',
    ]
    const nhanVaTen = ['Ngôn ngữ gốc', 'Cách dịch', 'Mục đích sử dụng', 'Tên chapter']
    const vitri = (el) => Array.from(container.querySelectorAll('*')).indexOf(el)
    const moc = [
      container.querySelector(thu[0]),
      ...nhanVaTen.map((n) => screen.getByLabelText(new RegExp(n))),
      container.querySelector(thu[5]),
      container.querySelector(thu[6]),
    ].map(vitri)
    expect(moc).toEqual([...moc].sort((a, b) => a - b))
    expect(moc.every((v) => v >= 0)).toBe(true)
  })

  it('KHÔNG chọn sẵn mục đích sử dụng — M10 giữ nguyên', () => {
    render(<DichChapter />)
    expect(screen.getByLabelText(/Mục đích sử dụng/)).toHaveValue('')
  })

  it('"Tự tải về khi xong" mặc định BẬT', () => {
    render(<DichChapter />)
    expect(screen.getByLabelText(/Tự tải về khi xong/)).toBeChecked()
  })

  it('nút khoá kèm lý do cho tới khi đủ mục đích + file; tên để trống vẫn được', async () => {
    const u = userEvent.setup()
    const { container } = render(<DichChapter />)
    const nut = screen.getByRole('button', { name: NUT })
    expect(nut).toBeDisabled()
    expect(screen.getByText(/Cần chọn mục đích sử dụng/)).toBeInTheDocument()
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    expect(screen.getByText(/Cần chọn ít nhất một ảnh/)).toBeInTheDocument()
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png')])
    expect(nut).toBeEnabled()
  })

  it('chưa chọn mục đích thì KHÔNG gửi gì lên máy chủ', async () => {
    const u = userEvent.setup()
    gia()
    const { container } = render(<DichChapter />)
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png')])
    await u.click(screen.getByRole('button', { name: NUT }))
    expect(api.taoProject).not.toHaveBeenCalled()
  })

  it('vùng thả nhận ảnh, gói ZIP/CBZ và PDF — cả thuộc tính accept lẫn chữ hiển thị', () => {
    const { container } = render(<DichChapter />)
    const accept = container.querySelector('input[type=file]').accept
    expect(accept).toMatch(/\.cbz/)
    expect(accept).toMatch(/\.zip/)
    expect(accept).toMatch(/\.pdf/)
    expect(accept).toMatch(/image\/webp/)
    expect(screen.getByText(/Hỗ trợ.*\.cbz/i)).toBeInTheDocument()
  })

  it('PDF đi đường GÓI (một tệp = cả chapter)', async () => {
    const u = userEvent.setup()
    gia()
    const { container } = render(<DichChapter onMoChapter={() => {}} />)
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [goi('truyen.pdf')])
    await u.click(screen.getByRole('button', { name: NUT }))
    await waitFor(() => expect(api.taiGoiLen).toHaveBeenCalled())
    expect(api.taiTrangLen).not.toHaveBeenCalled()
  })

  it('chọn một GÓI thì không được đếm thành "1 trang"', async () => {
    const u = userEvent.setup()
    const { container } = render(<DichChapter />)
    await u.upload(container.querySelector('input[type=file]'), [goi('ch.cbz')])
    expect(screen.getByText(/1 gói/)).toBeInTheDocument()
    expect(screen.getByText(/số trang thật biết được sau khi mở gói/i)).toBeInTheDocument()
  })

  it('chỉ chọn ảnh lẻ thì vẫn đếm theo TRANG như cũ (không hồi quy)', async () => {
    const u = userEvent.setup()
    const { container } = render(<DichChapter />)
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png'), anh('b.png')])
    expect(screen.getByText(/chính là thứ tự trang/i)).toBeInTheDocument()
    expect(screen.queryByText(/\d+\s*gói/)).toBeNull()
  })
})

describe('chạy: tạo chapter + tải trang + mở màn chapter', () => {
  it('gói đi đường GÓI, ảnh lẻ đi đường ảnh, engine đi kèm, rồi MỞ chapter', async () => {
    const u = userEvent.setup()
    gia()
    const moChapter = vi.fn()
    const { container } = render(<DichChapter onMoChapter={moChapter} />)
    await u.selectOptions(screen.getByLabelText(/Ngôn ngữ gốc/), 'en')
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'personal')
    await u.upload(container.querySelector('input[type=file]'), [goi('ch.cbz'), anh('p1.png')])
    await u.click(screen.getByRole('button', { name: NUT }))

    await waitFor(() => expect(moChapter).toHaveBeenCalledWith('proj-1'))
    expect(api.taoProject).toHaveBeenCalledWith({
      name: expect.stringMatching(/^ch \(\d\d-\d\d\)$/), source_lang: 'en', intended_use: 'personal',
    })
    expect(api.taiGoiLen).toHaveBeenCalledWith('proj-1', expect.any(File), 'google_fast')
    expect(api.taiTrangLen).toHaveBeenCalledWith('proj-1', expect.any(File), 'google_fast')
  })

  it('tên để trống ⇒ tự đặt theo tên tệp đầu + ngày; có gõ tên ⇒ dùng đúng tên đó', async () => {
    const u = userEvent.setup()
    gia()
    const { container, unmount } = render(<DichChapter onMoChapter={() => {}} />)
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [anh('One Piece 01.png')])
    await u.click(screen.getByRole('button', { name: NUT }))
    await waitFor(() => expect(api.taoProject).toHaveBeenCalled())
    expect(api.taoProject.mock.calls[0][0].name).toMatch(/^One Piece 01 \(\d\d-\d\d\)$/)
    unmount()

    api.taoProject.mockClear()
    const r2 = render(<DichChapter onMoChapter={() => {}} />)
    await u.type(screen.getByLabelText(/Tên chapter/), '  Chương 1  ')
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(r2.container.querySelector('input[type=file]'), [anh('a.png')])
    await u.click(screen.getByRole('button', { name: NUT }))
    await waitFor(() => expect(api.taoProject).toHaveBeenCalled())
    expect(api.taoProject.mock.calls[0][0].name).toBe('Chương 1')
  })

  it('"Tự tải về" BẬT ⇒ khi xong gọi xuất ZIP + taiFileXuatVe (dù form đã bị tháo)', async () => {
    const u = userEvent.setup()
    gia()
    const { container, unmount } = render(
      <DichChapter onMoChapter={() => unmount()} />,   // mô phỏng App đổi sang màn chapter
    )
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png')])
    await u.click(screen.getByRole('button', { name: NUT }))

    await waitFor(() => expect(api.taiFileXuatVe).toHaveBeenCalledWith('ex-1', 'zip'))
    expect(api.xuatChapter).toHaveBeenCalledWith('proj-1', 'zip')
  })

  it('tắt "Tự tải về" ⇒ vẫn mở chapter nhưng KHÔNG xuất file', async () => {
    const u = userEvent.setup()
    gia()
    const moChapter = vi.fn()
    const { container } = render(<DichChapter onMoChapter={moChapter} />)
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'personal')
    await u.upload(container.querySelector('input[type=file]'), [anh('p1.png')])
    await u.click(screen.getByLabelText(/Tự tải về khi xong/))
    await u.click(screen.getByRole('button', { name: NUT }))

    await waitFor(() => expect(moChapter).toHaveBeenCalledWith('proj-1'))
    await new Promise((r) => setTimeout(r, 30))
    expect(api.xuatChapter).not.toHaveBeenCalled()
    expect(api.layProject).not.toHaveBeenCalled()
  })

  it('lỗi giữa chừng: GIỮ tên + file, báo lỗi, chỉ được chỗ chapter đã tạo, KHÔNG mở chapter', async () => {
    const u = userEvent.setup()
    const moChapter = vi.fn()
    vi.spyOn(api, 'taoProject').mockResolvedValue({ id: 'proj-4' })
    vi.spyOn(api, 'taiTrangLen').mockRejectedValue(new Error('mạng hỏng'))

    const { container } = render(<DichChapter onMoChapter={moChapter} />)
    await u.type(screen.getByLabelText(/Tên chapter/), 'Chương 9')
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png')])
    await u.click(screen.getByRole('button', { name: NUT }))

    await waitFor(() => expect(screen.getByText(/mạng hỏng/)).toBeInTheDocument())
    expect(moChapter).not.toHaveBeenCalled()
    expect(screen.getByLabelText(/Tên chapter/)).toHaveValue('Chương 9')
    expect(screen.getByText('a.png')).toBeInTheDocument()
    await u.click(screen.getByRole('button', { name: /Mở chapter đã tạo/i }))
    expect(moChapter).toHaveBeenCalledWith('proj-4')
  })

  it('lỗi khi tạo chapter (chưa có id) thì không có nút mở chapter', async () => {
    const u = userEvent.setup()
    vi.spyOn(api, 'taoProject').mockRejectedValue(new Error('500: máy chủ lỗi'))
    const { container } = render(<DichChapter onMoChapter={() => {}} />)
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png')])
    await u.click(screen.getByRole('button', { name: NUT }))
    await screen.findByText(/500: máy chủ lỗi/)
    expect(screen.queryByRole('button', { name: /Mở chapter đã tạo/i })).toBeNull()
  })
})

describe('cách dịch mặc định', () => {
  it('chưa cấu hình AI ⇒ engine MIỄN PHÍ', async () => {
    render(<DichChapter />)
    await waitFor(() => expect(api.layCauHinhMe).toHaveBeenCalled())
    expect(screen.getByLabelText(/Cách dịch/)).toHaveValue('google_fast')
  })

  it('đã cấu hình AI (llm_configured) ⇒ mặc định "Dịch theo ngữ cảnh"', async () => {
    api.layCauHinhMe.mockResolvedValue({ llm_configured: true })
    render(<DichChapter />)
    await waitFor(() => expect(screen.getByLabelText(/Cách dịch/)).toHaveValue('llm_context'))
  })

  it('lấy cấu hình lỗi ⇒ giữ engine miễn phí, không vỡ form', async () => {
    api.layCauHinhMe.mockRejectedValue(new Error('mạng'))
    render(<DichChapter />)
    await waitFor(() => expect(api.layCauHinhMe).toHaveBeenCalled())
    expect(screen.getByLabelText(/Cách dịch/)).toHaveValue('google_fast')
  })

  it('người dùng đã tự chọn thì kết quả về muộn KHÔNG đè lựa chọn', async () => {
    const u = userEvent.setup()
    let xong
    api.layCauHinhMe.mockReturnValue(new Promise((r) => { xong = r }))
    render(<DichChapter />)
    await u.selectOptions(screen.getByLabelText(/Cách dịch/), 'google_fast')
    xong({ llm_configured: true })
    await new Promise((r) => setTimeout(r, 10))
    expect(screen.getByLabelText(/Cách dịch/)).toHaveValue('google_fast')
  })

  it('engine đã chọn được gửi cùng trang tải lên', async () => {
    const u = userEvent.setup()
    api.layCauHinhMe.mockResolvedValue({ llm_configured: true })
    gia()
    const { container } = render(<DichChapter onMoChapter={() => {}} />)
    await waitFor(() => expect(screen.getByLabelText(/Cách dịch/)).toHaveValue('llm_context'))
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png')])
    await u.click(screen.getByRole('button', { name: NUT }))
    await waitFor(() => expect(api.taiTrangLen).toHaveBeenCalledWith('proj-1', expect.any(File), 'llm_context'))
  })
})
