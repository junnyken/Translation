import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import QualityPanel from './chapter/QualityPanel.jsx'
import RegionQualityBox from './RegionQualityBox.jsx'

const tomTat = (kw = {}) => ({
  tong_vung: 4, ro_rang: 2, can_ra_soat: 1, chua_danh_gia: 1, da_bo_qua: 0,
  vung_tran_khung: 0, theo_phan_loai: { likely_translatable: 2, possible_sfx: 1 }, ...kw,
})

const danhGia = (kw = {}) => ({
  region_id: 'r1', relevance: 'possible_sfx', review_status: 'needs_review',
  overall_band: 'attention', ocr_confidence_state: 'available',
  ly_do: [{ ma: 'short_stylized_text', nhan: 'Chữ rất ngắn — có thể là tiếng động hoặc chữ cách điệu.' }],
  ...kw,
})

describe('bảng chất lượng của chapter', () => {
  it('đếm riêng "chưa đánh giá", KHÔNG gộp vào "rõ ràng"', () => {
    render(<QualityPanel tomTat={tomTat()} trangDau="p1" />)
    expect(screen.getByText(/chưa đánh giá được/)).toBeInTheDocument()
    expect(screen.getByText(/không có dấu hiệu bất thường/)).toBeInTheDocument()
  })

  it('không dùng chữ hứa hẹn "bản dịch chuẩn" hay "đạt chất lượng"', () => {
    render(<QualityPanel tomTat={tomTat()} trangDau="p1" />)
    expect(document.body.textContent).not.toMatch(/bản dịch chuẩn|đạt chất lượng|dịch đúng hoàn toàn/i)
    expect(screen.getByText(/không phải/)).toBeInTheDocument()
  })

  it('có nút dẫn thẳng vào chỗ rà soát', async () => {
    render(<QualityPanel tomTat={tomTat()} trangDau="p1" />)
    expect(screen.getByRole('button', { name: /Rà soát 1 vùng/ })).toBeInTheDocument()
  })

  it('chapter chưa có vùng nào thì không hiện gì', () => {
    const { container } = render(<QualityPanel tomTat={tomTat({ tong_vung: 0 })} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('hộp đánh giá trong màn sửa tay', () => {
  it('liệt kê lý do bằng câu đọc được, không phải mã', () => {
    render(<RegionQualityBox danhGia={danhGia()} onQuyetDinh={() => {}} />)
    expect(screen.getByText(/Chữ rất ngắn/)).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('short_stylized_text')
  })

  it('nói rõ "bỏ qua" KHÔNG xoá dữ liệu', () => {
    render(<RegionQualityBox danhGia={danhGia()} onQuyetDinh={() => {}} />)
    expect(screen.getByText(/vẫn được giữ/)).toBeInTheDocument()
  })

  it('hai quyết định đều là của người dùng, bấm được', async () => {
    const goi = vi.fn()
    render(<RegionQualityBox danhGia={danhGia()} onQuyetDinh={goi} />)
    await userEvent.click(screen.getByRole('button', { name: 'Bỏ qua vùng này' }))
    expect(goi).toHaveBeenCalledWith('skip')
    await userEvent.click(screen.getByRole('button', { name: 'Giữ để dịch' }))
    expect(goi).toHaveBeenCalledWith('keep')
  })

  it('không có điểm tin cậy thì nói là KHÔNG CÓ, không hiện 0%', () => {
    render(<RegionQualityBox danhGia={danhGia({ ocr_confidence_state: 'unavailable' })}
                             onQuyetDinh={() => {}} />)
    expect(screen.getByText(/không cung cấp điểm tin cậy/)).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('0%')
  })

  it('vùng chưa chấm thì nói chưa chấm, không nói là sạch', () => {
    render(<RegionQualityBox danhGia={null} onQuyetDinh={() => {}} />)
    expect(screen.getByText(/Chưa đánh giá/)).toBeInTheDocument()
    expect(document.body.textContent).toMatch(/không.*có nghĩa là không có vấn đề/i)
  })
})
