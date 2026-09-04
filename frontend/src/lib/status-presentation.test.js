import { describe, expect, it } from 'vitest'
import { TAT_CA_BANG, dienGiaiTrangThai } from './status-presentation.js'

/** Danh sách enum LẤY THẲNG từ docs/API.md — sửa backend mà quên cập nhật giao diện thì test đỏ.
 *  Đây là tấm lưới an toàn quan trọng nhất của E11: không màn nào được tự bịa chữ cho trạng thái. */
const ENUM_BACKEND = {
  trang: ['queued', 'detecting', 'detected', 'detection_failed', 'ocr_done', 'inpainted',
          'inpaint_needs_review', 'translated', 'typeset_done', 'ready_for_export'],
  viec: ['queued', 'running', 'done', 'failed'],
  me: ['queued', 'running', 'completed', 'partial_failed', 'blocked_quota', 'failed', 'cancelled'],
  muc_me: ['pending', 'running', 'completed', 'failed', 'blocked_quota', 'skipped'],
  canh_chu: ['pending', 'fit_ok', 'overflow_warning', 'font_missing_glyph'],
  doc_chu: ['pending', 'ok', 'needs_manual'],
  dich: ['pending', 'ok', 'fallback_used'],
  vung: ['pending', 'low_confidence', 'confirmed'],
}

describe('bảng dịch trạng thái', () => {
  for (const [loai, gia_tri] of Object.entries(ENUM_BACKEND)) {
    it(`phủ đủ mọi giá trị của "${loai}"`, () => {
      for (const tt of gia_tri) {
        const d = dienGiaiTrangThai(loai, tt)
        expect(d.nhan, `${loai}.${tt} thiếu nhãn`).toBeTruthy()
        expect(d.nhan).not.toContain('chưa được hỗ trợ')
        expect(d.icon, `${loai}.${tt} thiếu icon`).toBeTruthy()
      }
    })

    it(`không thừa giá trị lạ ở "${loai}"`, () => {
      expect(Object.keys(TAT_CA_BANG[loai]).sort()).toEqual([...gia_tri].sort())
    })
  }

  it('trạng thái lạ KHÔNG được đoán là thành công', () => {
    const d = dienGiaiTrangThai('trang', 'healthy')
    expect(d.nhan).toBe('Trạng thái chưa được hỗ trợ')
    expect(d.sac).toBe('canh')
    expect(d.thoi).toBe('healthy')   // giữ mã thô để còn lần ra
  })

  it('mọi trạng thái đều có icon, không chỉ có màu', () => {
    for (const [loai, bang] of Object.entries(TAT_CA_BANG)) {
      for (const tt of Object.keys(bang)) {
        expect(dienGiaiTrangThai(loai, tt).icon, `${loai}.${tt}`).toBeTruthy()
      }
    }
  })
})

describe('không nói quá về trạng thái', () => {
  it('căn chữ xong mà còn vùng tràn khung thì KHÔNG gọi là hoàn tất', () => {
    const d = dienGiaiTrangThai('trang', 'typeset_done', { soTran: 2 })
    expect(d.sac).toBe('canh')
    expect(d.nhan).toContain('còn vùng cần sửa')
    expect(d.mo_ta).toContain('2 vùng chữ tràn khung')
  })

  it('còn vùng chưa đọc được chữ cũng vậy', () => {
    const d = dienGiaiTrangThai('trang', 'ready_for_export', { soCanDocLai: 3 })
    expect(d.sac).toBe('canh')
    expect(d.mo_ta).toContain('3 vùng chưa đọc được chữ')
  })

  it('mẻ xong nhưng còn cảnh báo cũng bị hạ xuống mức cảnh báo', () => {
    expect(dienGiaiTrangThai('me', 'completed', { soTran: 1 }).sac).toBe('canh')
  })

  it('không có cảnh báo thì giữ nguyên mức thành công', () => {
    expect(dienGiaiTrangThai('trang', 'typeset_done').sac).toBe('ok')
    expect(dienGiaiTrangThai('me', 'completed').sac).toBe('ok')
  })

  it('trạng thái tạm dừng vì hạn mức KHÔNG phải là hỏng', () => {
    expect(dienGiaiTrangThai('me', 'blocked_quota').sac).toBe('canh')
    expect(dienGiaiTrangThai('me', 'blocked_quota').nhan).not.toMatch(/hỏng|thất bại/i)
  })
})
