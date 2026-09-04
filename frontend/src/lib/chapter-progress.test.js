import { describe, expect, it } from 'vitest'
import { tinhTienDoChapter } from './chapter-progress.js'

const trang = (...tt) => tt.map((status, i) => ({ id: `p${i}`, order: i + 1, status }))
const buoc = (kq, ma) => kq.buoc.find((b) => b.ma === ma)

describe('dòng thời gian pipeline của chapter', () => {
  it('mọi trang vừa tải lên: chỉ bước đầu là xong', () => {
    const kq = tinhTienDoChapter(trang('queued', 'queued'))
    expect(buoc(kq, 'tai_len').tinh_trang).toBe('xong')
    expect(buoc(kq, 'detect').tinh_trang).toBe('chua')
    expect(kq.san_sang_ra_soat).toBe(false)
  })

  it('một trang đang nhận diện thì bước đó là ĐANG CHẠY, không phải xong', () => {
    const kq = tinhTienDoChapter(trang('detecting', 'queued'))
    expect(buoc(kq, 'detect').tinh_trang).toBe('dang_chay')
  })

  it('mới xong một nửa thì KHÔNG được báo xong', () => {
    const kq = tinhTienDoChapter(trang('typeset_done', 'translated'))
    expect(buoc(kq, 'typeset').tinh_trang).toBe('dang_chay')
    expect(kq.san_sang_ra_soat).toBe(false)
    expect(kq.so_xong).toBe(1)
  })

  it('mọi trang căn chữ xong thì sẵn sàng rà soát', () => {
    const kq = tinhTienDoChapter(trang('typeset_done', 'ready_for_export'))
    expect(buoc(kq, 'typeset').tinh_trang).toBe('xong')
    expect(kq.san_sang_ra_soat).toBe(true)
  })

  it('xong hết NHƯNG còn vùng lỗi thì bước cuối là cảnh báo, không phải xong', () => {
    const kq = tinhTienDoChapter(trang('typeset_done'), { soTran: 2 })
    expect(buoc(kq, 'typeset').tinh_trang).toBe('canh_bao')
  })

  it('bong bóng bị bỏ trống vì font thiếu glyph CŨNG là cảnh báo (F1)', () => {
    // Trước F1 chỉ nhìn số tràn khung và số chưa đọc được chữ, nên một trang mất chữ thật vẫn
    // được báo là "xong" — đúng kiểu nói quá mà E11 sinh ra để chống.
    const kq = tinhTienDoChapter(trang('typeset_done'), { soThieuFont: 1 })
    expect(buoc(kq, 'typeset').tinh_trang).toBe('canh_bao')
  })

  it('trang hỏng lúc nhận diện được đếm riêng, không lẫn vào số đã xong', () => {
    const kq = tinhTienDoChapter(trang('detection_failed', 'typeset_done'))
    expect(kq.so_hong).toBe(1)
    expect(buoc(kq, 'detect').mo_ta).toContain('1 trang hỏng')
    expect(kq.san_sang_ra_soat).toBe(false)
  })

  it('hỏng sạch thì bước nhận diện là hỏng', () => {
    expect(buoc(tinhTienDoChapter(trang('detection_failed')), 'detect').tinh_trang).toBe('hong')
  })

  it('chapter rỗng không làm sập và không báo sẵn sàng', () => {
    const kq = tinhTienDoChapter([])
    expect(kq.tong).toBe(0)
    expect(kq.san_sang_ra_soat).toBe(false)
    expect(kq.buoc.every((b) => b.tinh_trang === 'chua')).toBe(true)
  })

  it('xoá chữ chưa sạch vẫn tính là đã qua bước xoá chữ (M4 cho đi tiếp)', () => {
    const kq = tinhTienDoChapter(trang('inpaint_needs_review'))
    expect(buoc(kq, 'inpaint').tinh_trang).toBe('xong')
    expect(buoc(kq, 'translate').tinh_trang).toBe('chua')
  })
})
