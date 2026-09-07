/** Quy đổi toạ độ ảnh gốc → toạ độ hiển thị. Sai chỗ này thì lớp phủ lệch khỏi bong bóng. */
import { describe, expect, it } from 'vitest'
import { coChu, quyDoi, sanSangQuyDoi } from '../src/lib/toa-do.js'

const anh = (o = {}) => ({
  naturalWidth: 1200, naturalHeight: 1700, clientWidth: 600, clientHeight: 850, ...o,
})

describe('quy đổi toạ độ', () => {
  it('ảnh bị co một nửa thì toạ độ cũng co một nửa', () => {
    expect(quyDoi({ x: 100, y: 200, w: 300, h: 80 }, anh()))
      .toEqual({ left: 50, top: 100, width: 150, height: 40 })
  })

  it('ảnh hiện đúng cỡ thật thì giữ nguyên', () => {
    const a = anh({ clientWidth: 1200, clientHeight: 1700 })
    expect(quyDoi({ x: 10, y: 20, w: 30, h: 40 }, a))
      .toEqual({ left: 10, top: 20, width: 30, height: 40 })
  })

  it('co ngang và co dọc KHÁC nhau thì mỗi trục dùng tỉ lệ riêng', () => {
    // Trang web đặt width/height cứng làm ảnh méo — hiếm nhưng có.
    const a = anh({ clientWidth: 600, clientHeight: 1700 })
    const r = quyDoi({ x: 0, y: 100, w: 1200, h: 100 }, a)
    expect(r.width).toBe(600)
    expect(r.height).toBe(100)
  })

  it('ảnh CHƯA tải xong thì không cho quy đổi', () => {
    // naturalWidth = 0 lúc chưa tải; quy đổi khi đó cho ra vô nghĩa.
    expect(sanSangQuyDoi({ naturalWidth: 0, clientWidth: 600 })).toBe(false)
    expect(sanSangQuyDoi(anh())).toBe(true)
    expect(sanSangQuyDoi(null)).toBe(false)
  })
})

describe('cỡ chữ trong bong bóng', () => {
  it('câu dài hơn thì chữ nhỏ hơn', () => {
    const o = { width: 120, height: 90 }
    expect(coChu(o, 60)).toBeLessThan(coChu(o, 10))
  })

  it('không bao giờ nhỏ tới mức không đọc được, cũng không to quá khung', () => {
    expect(coChu({ width: 20, height: 15 }, 200)).toBeGreaterThanOrEqual(9)
    expect(coChu({ width: 900, height: 900 }, 1)).toBeLessThanOrEqual(22)
  })

  it('không chia cho 0 khi bong bóng rỗng chữ', () => {
    expect(Number.isFinite(coChu({ width: 100, height: 100 }, 0))).toBe(true)
  })
})
