import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import OrientationBox from './OrientationBox.jsx'
import OrientationSummaryCard from './OrientationSummaryCard.jsx'
import {
  HUONG_CHU, LOC_HUONG_CHU, LY_DO_HUONG_CHU, NGUON_HUONG_CHU, TT_HUONG_CHU, nhanHuongChu,
} from '../lib/status-presentation.js'

/** 15 mã lý do của backend (`app/services/orientation/decision.py::LyDo.TAT_CA`). */
const MA_LY_DO_BACKEND = [
  'ocr_line_geometry_vertical', 'ocr_line_geometry_horizontal', 'ocr_layout_unavailable',
  'ctd_geometry_unavailable', 'roi_rotated_text_evidence', 'bbox_aspect_vertical_signal',
  'bbox_aspect_horizontal_signal', 'possible_sfx_from_quality_gate',
  'safe_area_fallback_rectangle', 'vertical_renderer_unavailable',
  'vertical_font_glyph_unavailable', 'vertical_layout_overflow',
  'rotated_text_manual_review_only', 'orientation_evidence_conflict', 'orientation_unknown',
]

const HUONG = ['horizontal_ltr', 'vertical_ttb', 'rotated_horizontal', 'unknown']
const TRANG_THAI = ['ready', 'needs_review', 'unavailable', 'failed']

describe('bảng dịch hướng chữ phủ đủ enum backend', () => {
  it('phủ đủ 4 hướng', () => {
    expect(Object.keys(HUONG_CHU).sort()).toEqual([...HUONG].sort())
  })

  it('phủ đủ 4 trạng thái', () => {
    expect(Object.keys(TT_HUONG_CHU).sort()).toEqual([...TRANG_THAI].sort())
  })

  it('phủ đủ 5 nguồn bằng chứng', () => {
    expect(Object.keys(NGUON_HUONG_CHU).sort()).toEqual([
      'ctd_geometry', 'fallback_unknown', 'image_heuristic', 'manual_reserved', 'ocr_layout',
    ])
  })

  it('dịch đủ 15 mã lý do — không thiếu, không thừa', () => {
    // Thiếu một mã thì người dùng nhìn thấy chuỗi máy; thừa một mã là dịch cho thứ backend
    // không bao giờ gửi, tức là tài liệu nói dối.
    expect(Object.keys(LY_DO_HUONG_CHU).sort()).toEqual([...MA_LY_DO_BACKEND].sort())
  })

  it.each(MA_LY_DO_BACKEND)('mã %s có câu tiếng Việt không rỗng', (m) => {
    expect(LY_DO_HUONG_CHU[m]).toBeTruthy()
    expect(LY_DO_HUONG_CHU[m]).not.toBe(m)
  })
})

describe('nhanHuongChu — không rơi vào nhãn lạ im lặng', () => {
  it.each(HUONG.flatMap((h) => TRANG_THAI.map((t) => [h, t])))(
    '%s + %s luôn có nhãn đọc được', (h, t) => {
      const d = nhanHuongChu(h, t, [])
      expect(d.nhan).toBeTruthy()
      expect(['ok', 'tin', 'canh', 'loi', 'trung']).toContain(d.sac)
      expect(d.nhan).not.toContain('undefined')
    })

  it('chữ ngang -> "Chữ ngang"', () => {
    expect(nhanHuongChu('horizontal_ltr', 'ready', []).nhan).toBe('Chữ ngang')
  })

  it('chữ dọc + ready -> "đã căn theo cột", sắc thái thành công', () => {
    const d = nhanHuongChu('vertical_ttb', 'ready', [])
    expect(d.nhan).toBe('Chữ dọc — đã căn theo cột')
    expect(d.sac).toBe('ok')
  })

  it.each(['needs_review', 'unavailable', 'failed'])(
    'chữ dọc + %s -> "cần kiểm tra thủ công", TUYỆT ĐỐI không phải sắc thái thành công', (t) => {
      // Đây là chỗ dễ nói quá nhất của cả E15: nhận ra hướng KHÔNG bằng dựng được theo hướng đó.
      const d = nhanHuongChu('vertical_ttb', t, ['vertical_renderer_unavailable'])
      expect(d.nhan).toBe('Chữ dọc — cần kiểm tra thủ công')
      expect(d.sac).not.toBe('ok')
    })

  it('chữ nghiêng -> "cần đặt thủ công"', () => {
    expect(nhanHuongChu('rotated_horizontal', 'needs_review', []).nhan)
      .toBe('Chữ nghiêng/cách điệu — cần đặt thủ công')
  })

  it('unknown -> "Chưa xác định hướng chữ", không phải lỗi cũng không phải xong', () => {
    const d = nhanHuongChu('unknown', 'needs_review', ['orientation_unknown'])
    expect(d.nhan).toBe('Chưa xác định hướng chữ')
    expect(d.sac).not.toBe('ok')
    expect(d.sac).not.toBe('loi')
  })

  it('mã mâu thuẫn thắng mọi nhãn khác', () => {
    const d = nhanHuongChu('unknown', 'needs_review',
      ['orientation_evidence_conflict', 'orientation_unknown'])
    expect(d.nhan).toBe('Dấu hiệu hướng chữ mâu thuẫn')
  })

  it.each([
    ['hướng lạ', 'diagonal_ttb', 'ready'],
    ['trạng thái lạ', 'vertical_ttb', 'da_xong_het'],
  ])('%s hiện rõ là chưa hỗ trợ, KHÔNG đoán thành công', (_t, h, tt) => {
    const d = nhanHuongChu(h, tt, [])
    expect(d.nhan).toContain('chưa được hỗ trợ')
    expect(d.sac).not.toBe('ok')
    expect(d.tho).toBeTruthy()
  })

  it('reason_codes không phải mảng cũng không làm sập', () => {
    expect(nhanHuongChu('horizontal_ltr', 'ready', null).nhan).toBe('Chữ ngang')
    expect(nhanHuongChu('horizontal_ltr', 'ready', undefined).nhan).toBe('Chữ ngang')
  })
})

describe('bộ lọc hướng chữ', () => {
  const v = (o, s) => ({ orientation: o, status: s })

  it('có đủ 5 mục theo spec', () => {
    expect(LOC_HUONG_CHU.map((l) => l.ma))
      .toEqual(['tat_ca', 'doc', 'nghieng', 'chua_biet', 'can_kiem'])
  })

  it('lọc "Chữ dọc" bắt đúng vùng dọc', () => {
    const l = LOC_HUONG_CHU.find((x) => x.ma === 'doc')
    expect(l.hop(v('vertical_ttb', 'unavailable'))).toBe(true)
    expect(l.hop(v('horizontal_ltr', 'ready'))).toBe(false)
  })

  it('lọc "Cần kiểm tra" gồm cả vùng CHƯA phân tích', () => {
    // Vùng chưa kiểm mà bị coi là "không sao" là cách im lặng nhất để bỏ sót.
    const l = LOC_HUONG_CHU.find((x) => x.ma === 'can_kiem')
    expect(l.hop(null)).toBe(true)
    expect(l.hop(undefined)).toBe(true)
    expect(l.hop(v('vertical_ttb', 'unavailable'))).toBe(true)
    expect(l.hop(v('horizontal_ltr', 'ready'))).toBe(false)
  })

  it('lọc "Tất cả" nhận mọi thứ kể cả null', () => {
    const l = LOC_HUONG_CHU[0]
    expect(l.hop(null)).toBe(true)
    expect(l.hop(v('unknown', 'needs_review'))).toBe(true)
  })
})

describe('OrientationBox', () => {
  it('chưa phân tích thì nói rõ, KHÔNG suy thành chữ ngang', () => {
    const { container } = render(<OrientationBox huongChu={null} />)
    expect(screen.getByText('Chưa nhận biết hướng chữ')).toBeInTheDocument()
    // Câu này bị thẻ <b> cắt thành nhiều node nên phải soi trên toàn khối, không phải getByText.
    expect(container.textContent).toMatch(/không.*có nghĩa là chữ ngang/i)
  })

  it('dịch mã lý do sang tiếng Việt, không hiện chuỗi máy', () => {
    render(<OrientationBox huongChu={{
      orientation: 'vertical_ttb', status: 'unavailable', source: 'ocr_layout',
      reason_codes: ['ocr_line_geometry_vertical', 'vertical_renderer_unavailable'],
      line_count_estimate: 3,
    }} />)
    expect(screen.getByText(LY_DO_HUONG_CHU.vertical_renderer_unavailable)).toBeInTheDocument()
    expect(screen.queryByText('vertical_renderer_unavailable')).not.toBeInTheDocument()
    expect(screen.getByText('Đường bao dòng chữ của bước đọc chữ')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('mã lạ hiện nguyên mã thô để còn lần ra, không bị nuốt', () => {
    render(<OrientationBox huongChu={{
      orientation: 'unknown', status: 'needs_review', source: 'ocr_layout',
      reason_codes: ['ma_backend_moi_them'],
    }} />)
    expect(screen.getByText('ma_backend_moi_them')).toBeInTheDocument()
  })

  it('lưới cột chữ CHỈ hiện khi status=ready', () => {
    const { rerender } = render(<OrientationBox huongChu={{
      orientation: 'vertical_ttb', status: 'unavailable', source: 'ocr_layout',
      reason_codes: [],
    }} />)
    expect(screen.queryByLabelText(/lưới cột chữ/i)).not.toBeInTheDocument()

    rerender(<OrientationBox huongChu={{
      orientation: 'vertical_ttb', status: 'ready', source: 'ocr_layout', reason_codes: [],
    }} />)
    expect(screen.getByLabelText(/lưới cột chữ/i)).toBeInTheDocument()
  })

  it('bật lưới gọi đúng callback', async () => {
    const onDoiLuoi = vi.fn()
    render(<OrientationBox
      huongChu={{ orientation: 'vertical_ttb', status: 'ready', source: 'ocr_layout',
        reason_codes: [] }}
      hienLuoi={false}
      onDoiLuoi={onDoiLuoi}
    />)
    await userEvent.click(screen.getByLabelText(/lưới cột chữ/i))
    expect(onDoiLuoi).toHaveBeenCalledWith(true)
  })

  it('chữ nghiêng nói THẲNG là bản này chưa tự xoay + kèm góc', () => {
    render(<OrientationBox huongChu={{
      orientation: 'rotated_horizontal', status: 'needs_review', source: 'image_heuristic',
      reason_codes: ['rotated_text_manual_review_only'], rotation_degrees: 27.5,
    }} />)
    expect(screen.getByText(/chưa tự xoay chữ/i)).toBeInTheDocument()
    expect(screen.getByText('27.5°')).toBeInTheDocument()
  })

  it('KHÔNG có nhãn "unknown label" nào lọt ra giao diện', () => {
    for (const h of HUONG) {
      for (const t of TRANG_THAI) {
        const { container, unmount } = render(
          <OrientationBox huongChu={{ orientation: h, status: t, source: 'ocr_layout',
            reason_codes: [] }} />)
        expect(container.textContent).not.toMatch(/undefined|\[object/)
        unmount()
      }
    }
  })
})

describe('OrientationSummaryCard', () => {
  const nen = {
    total_regions: 10, horizontal_count: 6, vertical_ready_count: 0,
    vertical_review_count: 2, rotated_review_count: 1, unknown_count: 1,
    unavailable_count: 2, not_analyzed_count: 0,
  }

  it('không có dữ liệu thì không vẽ gì', () => {
    const { container } = render(<OrientationSummaryCard tomTat={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('hiện đủ 4 con số spec yêu cầu + số chưa kiểm', () => {
    render(<OrientationSummaryCard tomTat={nen} />)
    for (const nhan of ['Chữ ngang', 'Chữ dọc — đã căn theo cột', 'Chữ dọc — cần kiểm tra',
      'Chữ nghiêng/cách điệu', 'Chưa xác định hướng', 'Chưa kiểm hướng chữ']) {
      expect(screen.getByText(nhan)).toBeInTheDocument()
    }
  })

  it('nói rõ số vùng chữ dọc CHƯA DỰNG ĐƯỢC vẫn đang bị căn ngang', () => {
    render(<OrientationSummaryCard tomTat={nen} />)
    expect(screen.getByText(/chưa dựng được/i)).toBeInTheDocument()
    expect(screen.getByText(/vẫn đang được căn ngang/i)).toBeInTheDocument()
  })

  it('"chưa kiểm" được nói tách khỏi "đã kiểm và không sao"', () => {
    render(<OrientationSummaryCard tomTat={{ ...nen, not_analyzed_count: 3 }} />)
    expect(screen.getByText(/khác với/i)).toBeInTheDocument()
  })

  it('không vùng nào cần xem thì nói thẳng, không im lặng', () => {
    render(<OrientationSummaryCard tomTat={{
      ...nen, vertical_review_count: 0, rotated_review_count: 0, unknown_count: 0,
      unavailable_count: 0,
    }} />)
    expect(screen.getByText(/Không vùng nào bị đánh dấu cần xem lại/i)).toBeInTheDocument()
  })

  it('nút chạy lại gọi đúng callback và khoá khi đang bận', async () => {
    const onChayLai = vi.fn()
    const { rerender } = render(
      <OrientationSummaryCard tomTat={nen} onChayLai={onChayLai} />)
    await userEvent.click(screen.getByRole('button', { name: /Chạy lại nhận biết hướng chữ/i }))
    expect(onChayLai).toHaveBeenCalledOnce()

    rerender(<OrientationSummaryCard tomTat={nen} dangBan onChayLai={onChayLai} />)
    expect(screen.getByRole('button', { name: /Đang chạy lại/i })).toBeDisabled()
  })
})
