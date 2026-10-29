import { afterEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api.js'
import { choChapterXong, demTienDo, demVungDangNgo } from './tu-tai-ve.js'

afterEach(() => vi.restoreAllMocks())

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

describe('đếm vùng đáng ngờ (P1)', () => {
  it('cộng đủ bốn loại cờ từ cảnh báo xuất ĐÃ CÓ của backend', () => {
    expect(demVungDangNgo({
      needs_manual_count: 2, quality_needs_review_count: 1,
      overflow_warning_count: 3, font_missing_count: 1,
    })).toBe(7)
  })

  it('không có cảnh báo hoặc sạch hoàn toàn thì bằng 0', () => {
    expect(demVungDangNgo(null)).toBe(0)
    expect(demVungDangNgo({})).toBe(0)
    expect(demVungDangNgo({ needs_manual_count: 0, overflow_warning_count: 0 })).toBe(0)
  })

  it('bỏ qua các số KHÔNG phải cờ cần rà soát', () => {
    // `shape_fallback_count` là "không biết lòng bong bóng ở đâu" — đã căn bằng khung dự phòng,
    // không phải lỗi cần người sửa. Cộng vào sẽ thổi số và làm người dùng bỏ qua cảnh báo thật.
    expect(demVungDangNgo({ needs_manual_count: 1, shape_fallback_count: 99 })).toBe(1)
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


describe('chayTuTaiVe — sống sót sau khi form bị tháo', () => {
  it('chờ xong → xuất ZIP → tải về, rồi báo kết quả', async () => {
    const { chayTuTaiVe, datLaiTuTaiVe } = await import('./tu-tai-ve.js')
    datLaiTuTaiVe()
    vi.spyOn(api, 'layProject').mockResolvedValue({ pages: [{ status: 'ready_for_export' }] })
    vi.spyOn(api, 'xuatChapter').mockResolvedValue({ job_id: 'ex-1' })
    vi.spyOn(api, 'choXuatXong').mockResolvedValue({})
    vi.spyOn(api, 'taiFileXuatVe').mockResolvedValue('c.zip')
    vi.spyOn(api, 'layCanhBaoXuat').mockResolvedValue({ needs_manual_count: 2 })
    await chayTuTaiVe('p-1', { nhipMs: 0 })
    expect(api.xuatChapter).toHaveBeenCalledWith('p-1', 'zip')
    expect(api.taiFileXuatVe).toHaveBeenCalledWith('ex-1', 'zip')
  })
})
