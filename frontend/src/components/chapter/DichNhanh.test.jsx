import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../api.js'
import DichNhanh, {
  choChapterXong, datTenTuDong, demTienDo, lyDoChuaChayDuoc,
} from './DichNhanh.jsx'

const anh = (ten) => new File(['x'], ten, { type: 'image/png' })
const goi = (ten) => new File(['PK'], ten, { type: '' })   // .cbz hay bị trình duyệt trả type rỗng

afterEach(() => vi.restoreAllMocks())

describe('điều kiện chạy', () => {
  it('nói đúng thứ còn thiếu, theo thứ tự người dùng gặp', () => {
    expect(lyDoChuaChayDuoc({ mucDich: '', files: [] })).toMatch(/mục đích/i)
    expect(lyDoChuaChayDuoc({ mucDich: 'study', files: [] })).toMatch(/ít nhất một ảnh/i)
    expect(lyDoChuaChayDuoc({ mucDich: 'study', files: [anh('a.png')] })).toBeNull()
  })

  it('một gói cũng đủ để chạy, không bắt phải có ảnh lẻ', () => {
    expect(lyDoChuaChayDuoc({ mucDich: 'study', files: [goi('ch.cbz')] })).toBeNull()
  })
})

describe('đếm tiến độ', () => {
  it('trang HỎNG không được tính là xong', () => {
    const t = demTienDo([
      { status: 'ready_for_export' }, { status: 'detection_failed' }, { status: 'ocr_done' },
    ])
    expect(t).toMatchObject({ xong: 1, hong: 1, tong: 3, chayXong: false })
  })

  it('xong + hỏng = tổng ⇒ coi là chạy xong (không đợi trang hỏng mãi mãi)', () => {
    const t = demTienDo([{ status: 'ready_for_export' }, { status: 'detection_failed' }])
    expect(t.chayXong).toBe(true)
    expect(t.xong).toBe(1)   // vẫn chỉ 1 trang có trong file xuất ra
  })

  it('chapter rỗng KHÔNG phải là đã chạy xong', () => {
    expect(demTienDo([]).chayXong).toBe(false)
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

describe('chờ chapter xong', () => {
  it('dừng ngay khi mọi trang đã xong', async () => {
    vi.spyOn(api, 'layProject').mockResolvedValue({ pages: [{ status: 'ready_for_export' }] })
    const t = await choChapterXong('p1', null, { nhipMs: 0 })
    expect(t.chayXong).toBe(true)
    expect(api.layProject).toHaveBeenCalledTimes(1)
  })

  it('người dùng rời màn thì DỪNG HẲN, không hỏi thêm lượt nào', async () => {
    vi.spyOn(api, 'layProject').mockResolvedValue({ pages: [{ status: 'ocr_done' }] })
    const t = await choChapterXong('p1', null, { soLanToiDa: 50, nhipMs: 0, nenDung: () => true })
    expect(api.layProject).not.toHaveBeenCalled()
    expect(t.chayXong).toBe(false)   // dừng KHÔNG phải là xong
  })

  it('hết trần mà chưa xong thì trả số đo THẬT, không báo là đã xong', async () => {
    vi.spyOn(api, 'layProject').mockResolvedValue({
      pages: [{ status: 'ready_for_export' }, { status: 'ocr_done' }],
    })
    const t = await choChapterXong('p1', null, { soLanToiDa: 3, nhipMs: 0 })
    expect(t).toMatchObject({ xong: 1, tong: 2, chayXong: false })
    expect(api.layProject).toHaveBeenCalledTimes(3)
  })
})

describe('màn Dịch nhanh', () => {
  it('KHÔNG chọn sẵn mục đích sử dụng — M10 giữ nguyên ở đường nhanh', () => {
    render(<DichNhanh />)
    expect(screen.getByLabelText(/Mục đích sử dụng/)).toHaveValue('')
  })

  it('mặc định là engine MIỄN PHÍ — không bao giờ tự tiêu token của người dùng', () => {
    render(<DichNhanh />)
    expect(screen.getByLabelText(/Cách dịch/)).toHaveValue('google_fast')
  })

  it('vùng thả nhận cả gói ZIP/CBZ, không chỉ ảnh', () => {
    const { container } = render(<DichNhanh />)
    expect(container.querySelector('input[type=file]').accept).toMatch(/\.cbz/)
  })

  it('gói đi đường GÓI, ảnh lẻ đi đường ảnh — và engine đi kèm cả hai', async () => {
    const u = userEvent.setup()
    vi.spyOn(api, 'taoProject').mockResolvedValue({ id: 'proj-1' })
    vi.spyOn(api, 'taiGoiLen').mockResolvedValue({ so_trang: 2, bo_qua: 1, trang: [] })
    vi.spyOn(api, 'taiTrangLen').mockResolvedValue({ page_id: 'pg-1' })
    vi.spyOn(api, 'layProject').mockResolvedValue({
      pages: [{ status: 'ready_for_export' }, { status: 'ready_for_export' }, { status: 'ready_for_export' }],
    })
    vi.spyOn(api, 'xuatChapter').mockResolvedValue({ job_id: 'ex-1' })
    vi.spyOn(api, 'choXuatXong').mockResolvedValue({})
    vi.spyOn(api, 'taiFileXuatVe').mockResolvedValue('chapter.zip')

    const { container } = render(<DichNhanh />)
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [goi('ch.cbz'), anh('p1.png')])
    await u.click(screen.getByRole('button', { name: /Dịch ngay/i }))

    await waitFor(() => expect(screen.getByText(/^Xong$/)).toBeInTheDocument())
    expect(api.taiGoiLen).toHaveBeenCalledWith('proj-1', expect.any(File), 'google_fast')
    expect(api.taiTrangLen).toHaveBeenCalledWith('proj-1', expect.any(File), 'google_fast')
    // 2 trang từ gói + 1 ảnh lẻ = 3; và 1 mục trong gói bị bỏ qua phải được NÓI ra
    expect(screen.getByText(/bỏ qua 1 mục/i)).toBeInTheDocument()
  })

  it('tắt "tự tải về" thì KHÔNG xuất file, và nói thẳng là chưa tải về', async () => {
    const u = userEvent.setup()
    vi.spyOn(api, 'taoProject').mockResolvedValue({ id: 'proj-2' })
    vi.spyOn(api, 'taiTrangLen').mockResolvedValue({ page_id: 'pg-1' })
    vi.spyOn(api, 'layProject').mockResolvedValue({ pages: [{ status: 'ready_for_export' }] })
    vi.spyOn(api, 'xuatChapter').mockResolvedValue({ job_id: 'ex-1' })

    const { container } = render(<DichNhanh />)
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'personal')
    await u.upload(container.querySelector('input[type=file]'), [anh('p1.png')])
    await u.click(screen.getByLabelText(/Tự tải về khi xong/))
    await u.click(screen.getByRole('button', { name: /Dịch ngay/i }))

    await waitFor(() => expect(screen.getByText(/Chưa tải về/i)).toBeInTheDocument())
    expect(api.xuatChapter).not.toHaveBeenCalled()
  })

  it('trang hỏng thì báo THIẾU TRANG chứ không báo xong xuôi', async () => {
    const u = userEvent.setup()
    vi.spyOn(api, 'taoProject').mockResolvedValue({ id: 'proj-3' })
    vi.spyOn(api, 'taiTrangLen').mockResolvedValue({ page_id: 'pg-1' })
    vi.spyOn(api, 'layProject').mockResolvedValue({
      pages: [{ status: 'ready_for_export' }, { status: 'detection_failed' }],
    })
    vi.spyOn(api, 'xuatChapter').mockResolvedValue({ job_id: 'ex-1' })
    vi.spyOn(api, 'choXuatXong').mockResolvedValue({})
    vi.spyOn(api, 'taiFileXuatVe').mockResolvedValue('chapter.zip')

    const { container } = render(<DichNhanh />)
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png'), anh('b.png')])
    await u.click(screen.getByRole('button', { name: /Dịch ngay/i }))

    await waitFor(() => expect(screen.getByText(/Xong, nhưng thiếu trang/i)).toBeInTheDocument())
    expect(screen.getByText(/không nhận diện được/i)).toBeInTheDocument()
  })

  it('lỗi giữa chừng vẫn chỉ được chỗ chapter đã tạo, không để người dùng tưởng mất trắng', async () => {
    const u = userEvent.setup()
    const moChapter = vi.fn()
    vi.spyOn(api, 'taoProject').mockResolvedValue({ id: 'proj-4' })
    vi.spyOn(api, 'taiTrangLen').mockRejectedValue(new Error('mạng hỏng'))

    const { container } = render(<DichNhanh onMoChapter={moChapter} />)
    await u.selectOptions(screen.getByLabelText(/Mục đích sử dụng/), 'study')
    await u.upload(container.querySelector('input[type=file]'), [anh('a.png')])
    await u.click(screen.getByRole('button', { name: /Dịch ngay/i }))

    await waitFor(() => expect(screen.getByText(/mạng hỏng/)).toBeInTheDocument())
    await u.click(screen.getByRole('button', { name: /Mở chapter đã tạo/i }))
    expect(moChapter).toHaveBeenCalledWith('proj-4')
  })
})
