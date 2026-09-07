/** Chọn trang truyện giữa một mớ ảnh — phần đoán mò nhất của tiện ích.
 *
 * Người dùng chọn "bất kỳ trang web nào", nên không có bảng luật riêng cho từng trang. Test này
 * dựng đúng những thứ hay bị nhầm: banner ngang, ảnh thu nhỏ trong danh sách, icon, và ảnh nằm
 * ngoài khung nhìn.
 */
import { describe, expect, it } from 'vitest'
import { chonTrangTruyen } from '../src/lib/chon-anh.js'

const anh = (o) => ({
  src: 'x', naturalWidth: 900, naturalHeight: 1300,
  clientWidth: 900, clientHeight: 1300, top: 0, bottom: 1300, ...o,
})
const chon = (ds, cao = 900) => chonTrangTruyen(ds, { caoKhungNhin: cao })

describe('chọn trang truyện', () => {
  it('một trang truyện đứng một mình thì chọn nó', () => {
    const kq = chon([anh({ src: 'trang.png' })])
    expect(kq.anh.src).toBe('trang.png')
  })

  it('KHÔNG chọn banner quảng cáo dù nó rất rộng', () => {
    const kq = chon([
      anh({ src: 'banner.jpg', naturalWidth: 1600, naturalHeight: 300, clientHeight: 300, bottom: 300 }),
      anh({ src: 'trang.png' }),
    ])
    expect(kq.anh.src).toBe('trang.png')
    expect(kq.bi_loai.find((b) => b.src === 'banner.jpg').ly_do).toContain('quá dẹt — nhiều khả năng là banner')
  })

  it('KHÔNG chọn icon / avatar', () => {
    const kq = chon([
      anh({ src: 'avatar.png', naturalWidth: 64, naturalHeight: 64, clientWidth: 64, clientHeight: 64, bottom: 64 }),
      anh({ src: 'trang.png' }),
    ])
    expect(kq.anh.src).toBe('trang.png')
  })

  it('KHÔNG chọn ảnh thu nhỏ trong danh sách chapter', () => {
    // Ảnh gốc to nhưng bị CSS ép còn một góc — dấu hiệu của thumbnail.
    const kq = chon([
      anh({ src: 'thumb.jpg', clientWidth: 150, clientHeight: 210, bottom: 210 }),
      anh({ src: 'trang.png' }),
    ])
    expect(kq.anh.src).toBe('trang.png')
    expect(kq.bi_loai.find((b) => b.src === 'thumb.jpg').ly_do)
      .toContain('bị thu nhỏ nhiều — nhiều khả năng là ảnh thu nhỏ')
  })

  it('bỏ qua ảnh nằm HOÀN TOÀN ngoài khung nhìn', () => {
    const kq = chon([
      anh({ src: 'duoi-chan-trang.png', top: 5000, bottom: 6300 }),
      anh({ src: 'dang-doc.png' }),
    ])
    expect(kq.anh.src).toBe('dang-doc.png')
  })

  it('nhiều trang truyện cùng lúc thì lấy trang CHIẾM KHUNG NHÌN nhiều nhất', () => {
    // Đúng cảnh đọc truyện cuộn dọc: nhiều trang xếp liên tiếp, chỉ một trang đang ở giữa màn.
    const kq = chon([
      anh({ src: 'tren.png', top: -1200, bottom: 100 }),
      anh({ src: 'giua.png', top: 100, bottom: 1400 }),
      anh({ src: 'duoi.png', top: 1400, bottom: 2700 }),
    ], 900)
    expect(kq.anh.src).toBe('giua.png')
  })

  it('KHÔNG có ảnh nào hợp lệ thì nói THẲNG, không chọn bừa', () => {
    const kq = chon([anh({ naturalWidth: 50, naturalHeight: 50, clientWidth: 50, clientHeight: 50, bottom: 50 })])
    expect(kq.anh).toBeNull()
    expect(kq.ly_do).toMatch(/không có ảnh nào/)
  })

  it('luôn kèm lý do loại từng ảnh — để chọn nhầm còn mở ra xem được', () => {
    const kq = chon([anh({ src: 'banner.jpg', naturalWidth: 1600, naturalHeight: 200, clientHeight: 200, bottom: 200 })])
    expect(kq.bi_loai).toHaveLength(1)
    expect(kq.bi_loai[0].ly_do.length).toBeGreaterThan(0)
  })

  it('trang đôi (rộng hơn cao) vẫn được nhận', () => {
    const kq = chon([anh({ src: 'trang-doi.png', naturalWidth: 1800, naturalHeight: 1300, clientWidth: 1800, clientHeight: 1300 })])
    expect(kq.anh.src).toBe('trang-doi.png')
  })

  it('KHÔNG chọn ảnh nền mờ của lightbox dù nó chiếm khung nhìn nhiều hơn ảnh thật', () => {
    // Số đo thật trên reddit.com/r/translator 07/09: nền mờ dùng CHÍNH src của ảnh đang xem,
    // phóng to phủ khung, nên "chiếm khung nhìn" của nó thắng ảnh thật 750x750 hiển thị vừa khung.
    const kq = chon([
      anh({
        src: 'trang.png', mo: true,
        naturalWidth: 750, naturalHeight: 750, clientWidth: 2304, clientHeight: 1134,
        top: -94, bottom: 1040,
      }),
      anh({ src: 'trang.png', naturalWidth: 750, naturalHeight: 750, clientWidth: 830, clientHeight: 830, bottom: 830 }),
    ])
    expect(kq.anh.mo).toBeFalsy()
    expect(kq.bi_loai.find((b) => b.ly_do.some((l) => l.includes('mờ')))).toBeTruthy()
  })
})
