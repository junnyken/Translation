import { describe, expect, it } from 'vitest'
import { chuThoiGianGiu } from './thoi-gian-giu.js'

describe('chuThoiGianGiu', () => {
  it('dưới 60 phút giữ nguyên đơn vị phút', () => {
    expect(chuThoiGianGiu(0)).toBe('0 phút')
    expect(chuThoiGianGiu(30)).toBe('30 phút')
    expect(chuThoiGianGiu(59)).toBe('59 phút')
  })
  it('bội của 1440 ⇒ ngày', () => {
    expect(chuThoiGianGiu(1440)).toBe('1 ngày')
    expect(chuThoiGianGiu(4320)).toBe('3 ngày')
  })
  it('bội của 60 (không phải ngày tròn) ⇒ giờ', () => {
    expect(chuThoiGianGiu(60)).toBe('1 giờ')
    expect(chuThoiGianGiu(720)).toBe('12 giờ')
    expect(chuThoiGianGiu(2160)).toBe('36 giờ')
  })
  it('còn lại ⇒ giờ + phút', () => {
    expect(chuThoiGianGiu(90)).toBe('1 giờ 30 phút')
    expect(chuThoiGianGiu(1500)).toBe('25 giờ')  // 1500 = 25*60: bội của 60
    expect(chuThoiGianGiu(1501)).toBe('25 giờ 1 phút')
  })
  it('giá trị không hợp lệ ⇒ chuỗi rỗng, không in "NaN phút"', () => {
    expect(chuThoiGianGiu(null)).toBe('')
    expect(chuThoiGianGiu(undefined)).toBe('')
    expect(chuThoiGianGiu(-5)).toBe('')
    expect(chuThoiGianGiu('abc')).toBe('')
    expect(chuThoiGianGiu(NaN)).toBe('')
  })
})
