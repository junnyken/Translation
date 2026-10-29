/** P3i — cổng xuất phải NÓI khi chapter chưa chốt thuật ngữ nào.
 *
 * Đo được ở pilot hosted 2026-09-03: nhân vật *Pepper* bị dịch thành "Hạt tiêu" (tên gia vị),
 * và cổng xuất KHÔNG hé một lời nào — vì khối "Nhất quán thuật ngữ" chỉ hiện khi CÓ việc rà
 * soát, mà không có thuật ngữ thì không sinh việc nào. Hệ thống im lặng đúng lúc rủi ro cao nhất.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ExportWarningModal from './ExportWarningModal.jsx'

const canhBao = (kw = {}) => ({
  overflow_warning_count: 0, needs_manual_count: 0, acknowledged: false, acknowledged_at: null,
  shape_fallback_count: 0, shape_needs_review_count: 0,
  orientation_vertical_rendered_count: 0, orientation_review_count: 0,
  orientation_unknown_count: 0,
  quality_needs_review_count: 0, quality_unassessed_count: 0, quality_reviewed_skip_count: 0,
  glossary_approved_count: 0, ...kw,
})
const khongViec = {
  open_count: 0, accepted_count: 0, rejected_count: 0, stale_count: 0,
  resolved_no_change_count: 0, by_type: {},
}

describe('cảnh báo chưa chốt thuật ngữ', () => {
  it('chapter TRỐNG thuật ngữ vẫn phải hiện khối nhất quán và nói rõ rủi ro', () => {
    render(<ExportWarningModal canhBao={canhBao()} nhatQuan={khongViec} dinhDang="cbz"
                               onHuy={vi.fn()} onDongY={vi.fn()} />)
    expect(screen.getByRole('heading', { name: /Nhất quán thuật ngữ/ })).toBeInTheDocument()
    expect(screen.getByText(/Chưa chốt thuật ngữ nào/)).toBeInTheDocument()
    // Phải nêu HẬU QUẢ cụ thể, không chỉ nói "chưa có gì".
    expect(screen.getByText(/nghĩa đen/)).toBeInTheDocument()
  })

  it('nêu ví dụ có thật để người dùng nhận ra vấn đề', () => {
    render(<ExportWarningModal canhBao={canhBao()} nhatQuan={khongViec} dinhDang="cbz"
                               onHuy={vi.fn()} onDongY={vi.fn()} />)
    expect(screen.getByText(/Pepper/)).toBeInTheDocument()
    expect(screen.getByText(/Hạt tiêu/)).toBeInTheDocument()
  })

  it('ĐÃ có thuật ngữ duyệt thì KHÔNG lải nhải cảnh báo này nữa', () => {
    render(<ExportWarningModal canhBao={canhBao({ glossary_approved_count: 3 })}
                               nhatQuan={khongViec} dinhDang="cbz"
                               onHuy={vi.fn()} onDongY={vi.fn()} />)
    expect(screen.queryByText(/Chưa chốt thuật ngữ nào/)).not.toBeInTheDocument()
  })

  it('không nuốt mất cảnh báo cũ khi thuật ngữ trống', () => {
    render(<ExportWarningModal canhBao={canhBao({ overflow_warning_count: 2 })}
                               nhatQuan={khongViec} dinhDang="cbz"
                               onHuy={vi.fn()} onDongY={vi.fn()} />)
    expect(screen.getByText(/Chưa chốt thuật ngữ nào/)).toBeInTheDocument()
    expect(screen.getByText(/tràn ra ngoài khung/)).toBeInTheDocument()
  })
})
