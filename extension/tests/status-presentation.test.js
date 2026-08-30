import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  KHONG_RO, TRANG, TRANG_RA_SOAT_DUOC, TRANG_XUAT_DUOC,
  nhanChapter, nhanThoiGian, nhanTrang, tomTatChapter,
} from '../src/lib/status-presentation.js'

/** 10 trạng thái trang chốt ở M1 (`backend/app/models/enums.py::PageStatus`). */
const TRANG_THAI_TRANG = [
  'queued', 'detecting', 'detected', 'detection_failed', 'ocr_done',
  'inpainted', 'inpaint_needs_review', 'translated', 'typeset_done', 'ready_for_export',
]

describe('bảng trạng thái phủ đủ và không nói quá', () => {
  it('có đủ 10 trạng thái trang', () => {
    expect(Object.keys(TRANG).sort()).toEqual([...TRANG_THAI_TRANG].sort())
  })

  it.each(TRANG_THAI_TRANG)('%s có nhãn + sắc thái', (ma) => {
    const b = nhanTrang(ma)
    expect(b.nhan.length).toBeGreaterThan(0)
    expect(['ok', 'tin', 'canh', 'loi', 'trung']).toContain(b.sac)
    expect(b).not.toBe(KHONG_RO)
  })

  it.each([
    ['trạng thái chưa từng có', 'da_xong_het'],
    ['chuỗi rỗng', ''],
    ['null', null],
    ['số', 7],
    ['khoá của Object.prototype', 'toString'],
    ['constructor', 'constructor'],
  ])('trạng thái lạ (%s) -> "Không rõ", KHÔNG BAO GIỜ rơi vào nhánh thành công', (_ten, ma) => {
    const b = nhanTrang(ma)
    expect(b).toBe(KHONG_RO)
    expect(b.nhan).toBe('Không rõ trạng thái')
    expect(b.sac).not.toBe('ok')
  })

  it('trạng thái chapter chỉ có active/archived', () => {
    expect(nhanChapter('active').nhan).toBe('Đang làm')
    expect(nhanChapter('archived').nhan).toBe('Đã lưu trữ')
    expect(nhanChapter('done')).toBe(KHONG_RO)
  })

  it('chữ KHÔNG lệch với web app — chép từ frontend/src/lib/status-presentation.js', () => {
    // Một trạng thái mà panel gọi "Xong" còn web app gọi "Cần rà soát" là cách nhanh nhất để
    // người dùng mất lòng tin vào cả hai. Test này canh đúng chỗ đó.
    const nguon = readFileSync(
      join(process.cwd(), '../frontend/src/lib/status-presentation.js'), 'utf8')
    for (const ma of TRANG_THAI_TRANG) {
      const khop = nguon.match(new RegExp(`\\n  ${ma}: B\\('([^']+)'`))
      expect(khop, `web app không có trạng thái ${ma}`).not.toBeNull()
      expect(nhanTrang(ma).nhan, `lệch chữ ở trạng thái ${ma}`).toBe(khop[1])
    }
  })
})

describe('điều kiện bật nút — lấy từ backend, không đoán', () => {
  it('trang xuất được đúng bằng bộ lọc của routes.py::export_preview', () => {
    expect([...TRANG_XUAT_DUOC].sort()).toEqual(['ready_for_export', 'typeset_done'])
  })

  it('chapter không có trang nào -> tắt cả hai nút', () => {
    const t = tomTatChapter({ trang: [] })
    expect(t.coTheXuat).toBe(false)
    expect(t.coTheRaSoat).toBe(false)
    expect(t.trangRaSoat).toBeNull()
  })

  it('chapter toàn trang đang chờ -> tắt cả hai nút', () => {
    const t = tomTatChapter({ trang: [{ id: 'a', trangThai: 'queued' },
      { id: 'b', trangThai: 'detecting' }] })
    expect(t.coTheXuat).toBe(false)
    expect(t.coTheRaSoat).toBe(false)
  })

  it('có trang đã căn chữ -> bật cả hai, và trỏ đúng trang đầu tiên', () => {
    const t = tomTatChapter({ trang: [
      { id: 'a', trangThai: 'queued' },
      { id: 'b', trangThai: 'typeset_done' },
      { id: 'c', trangThai: 'ready_for_export' },
    ] })
    expect(t.coTheXuat).toBe(true)
    expect(t.soTrangXuatDuoc).toBe(2)
    expect(t.trangRaSoat).toBe('b')
  })

  it('trang xoá chữ chưa sạch thì rà soát được nhưng CHƯA xuất được', () => {
    const t = tomTatChapter({ trang: [{ id: 'a', trangThai: 'inpaint_needs_review' }] })
    expect(t.coTheRaSoat).toBe(true)
    expect(t.coTheXuat).toBe(false)
  })

  it('trạng thái lạ không tự bật nút nào', () => {
    const t = tomTatChapter({ trang: [{ id: 'a', trangThai: 'hoan_tat_het_roi' }] })
    expect(t.coTheXuat).toBe(false)
    expect(t.coTheRaSoat).toBe(false)
  })

  it.each([[null], [undefined], [{}], [{ trang: 'x' }]])(
    'dữ liệu hỏng (%s) không làm sập bộ tóm tắt', (vao) => {
      const t = tomTatChapter(vao)
      expect(t.soTrang).toBe(0)
      expect(t.coTheXuat).toBe(false)
    })

  it('mỗi trang xuất được cũng phải rà soát được (không có nút Xuất mồ côi)', () => {
    for (const tt of TRANG_XUAT_DUOC) expect(TRANG_RA_SOAT_DUOC.has(tt)).toBe(true)
  })
})

describe('nhãn thời gian — bản chụp luôn phải có tuổi', () => {
  const t0 = Date.parse('2026-08-30T12:00:00.000Z')
  it.each([
    [30_000, 'vừa xong'],
    [5 * 60_000, '5 phút trước'],
    [3 * 3600_000, '3 giờ trước'],
    [2 * 86400_000, '2 ngày trước'],
  ])('cách %i ms -> "%s"', (lech, mong_doi) => {
    expect(nhanThoiGian(new Date(t0 - lech).toISOString(), t0)).toBe(mong_doi)
  })

  it.each([[null], [''], ['hôm qua'], [123]])('giá trị hỏng (%s) -> chuỗi rỗng', (vao) => {
    expect(nhanThoiGian(vao, t0)).toBe('')
  })
})
