import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import GlossaryManager from './GlossaryManager.jsx'
import TermCandidatePanel from './TermCandidatePanel.jsx'
import VoiceProfileManager from './VoiceProfileManager.jsx'

const ungVien = (kw = {}) => ({
  source_term: 'Pepper', term_key: 'pepper', count: 3, pages: [1, 2],
  quotes: [{ page_order: 1, region_id: 'r1', text: 'I met Pepper today' }],
  type_guess: 'character_name', reasons: ['viết hoa giữa câu'], ...kw,
})

const ketQua = (kw = {}) => ({
  ung_vien: [ungVien()], so_vung_da_quet: 8, so_vung_co_chu: 6,
  trang_thai: 'co_ung_vien', so_bi_loc_vi_da_co: 0, ghi_chu_ngon_ngu: null,
  so_vung_khong_chac: 0, ...kw,
})

const tinHieu = (kw = {}) => ({
  tin_hieu: [{
    ma: 'ja_sama', nhan: 'hậu tố 様/さま', goi_y_xung_ho: 'ngài / đại nhân',
    speech_register_goi_y: 'formal', count: 2, ten_lien_quan: ['ペッパー'],
    quotes: [{ page_order: 1, region_id: 'r1', text: 'ペッパー様、お待ちください' }],
  }],
  so_vung_da_quet: 5, so_vung_co_chu: 5, trang_thai: 'co_tin_hieu', so_vung_khong_chac: 0,
  ...kw,
})

const nut = (ten) => screen.getByRole('button', { name: new RegExp(ten, 'i') })

describe('E17 — bảng ứng viên thuật ngữ', () => {
  it('hiện bằng chứng: số lần, trang, trích nguyên văn, và vì sao được nêu', async () => {
    render(<TermCandidatePanel onTim={vi.fn().mockResolvedValue(ketQua())} onChon={vi.fn()} />)
    await userEvent.click(nut('Tìm trong chapter'))

    expect(await screen.findByText('Pepper')).toBeInTheDocument()
    expect(screen.getByText(/I met Pepper today/)).toBeInTheDocument()
    expect(screen.getByText(/viết hoa giữa câu/)).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('KHÔNG có nút duyệt hàng loạt — cách dịch là quyết định của người', async () => {
    render(<TermCandidatePanel onTim={vi.fn().mockResolvedValue(ketQua())} onChon={vi.fn()} />)
    await userEvent.click(nut('Tìm trong chapter'))
    await screen.findByText('Pepper')
    expect(screen.queryByRole('button', { name: /duyệt tất cả|thêm tất cả|duyệt hết/i }))
      .not.toBeInTheDocument()
  })

  describe('ba trạng thái rỗng KHÔNG được gộp', () => {
    it('chưa đọc chữ ≠ không có gì', async () => {
      render(<TermCandidatePanel onChon={vi.fn()}
        onTim={vi.fn().mockResolvedValue(ketQua({ ung_vien: [], trang_thai: 'chua_doc_chu',
                                                  so_vung_co_chu: 0 }))} />)
      await userEvent.click(nut('Tìm trong chapter'))
      expect(await screen.findByText(/Chưa đọc được chữ trong chapter/)).toBeInTheDocument()
      expect(screen.getByText(/chưa thể kết luận/)).toBeInTheDocument()
    })

    it('đã tìm mà không thấy gì thì nói đúng như vậy', async () => {
      render(<TermCandidatePanel onChon={vi.fn()}
        onTim={vi.fn().mockResolvedValue(ketQua({ ung_vien: [], trang_thai: 'khong_thay' }))} />)
      await userEvent.click(nut('Tìm trong chapter'))
      expect(await screen.findByText(/Đã tìm, không thấy danh xưng nào/)).toBeInTheDocument()
    })

    it('đều đã có trong danh sách là trạng thái riêng', async () => {
      render(<TermCandidatePanel onChon={vi.fn()}
        onTim={vi.fn().mockResolvedValue(ketQua({ ung_vien: [], trang_thai: 'deu_da_co',
                                                  so_bi_loc_vi_da_co: 4 }))} />)
      await userEvent.click(nut('Tìm trong chapter'))
      expect(await screen.findByText(/đều đã có trong danh sách/i)).toBeInTheDocument()
    })
  })

  it('nói ra số vùng chữ đọc chưa chắc chắn thay vì lặng lẽ bỏ', async () => {
    render(<TermCandidatePanel onChon={vi.fn()}
      onTim={vi.fn().mockResolvedValue(ketQua({ so_vung_khong_chac: 3 }))} />)
    await userEvent.click(nut('Tìm trong chapter'))
    expect(await screen.findByText(/Bỏ qua 3 vùng chữ đọc chưa chắc chắn/)).toBeInTheDocument()
  })

  it('nói rõ đang dùng luật nào khi chữ lồng toàn chữ hoa', async () => {
    render(<TermCandidatePanel onChon={vi.fn()}
      onTim={vi.fn().mockResolvedValue(ketQua({
        ghi_chu_ngon_ngu: 'chữ hoa 98% — chữ lồng gần như toàn chữ hoa nên KHÔNG dùng được tín hiệu viết hoa',
      }))} />)
    await userEvent.click(nut('Tìm trong chapter'))
    expect(await screen.findByText(/KHÔNG dùng được tín hiệu viết hoa/)).toBeInTheDocument()
  })
})

describe('E17 tầng 3 — gợi ý theo tên bộ truyện', () => {
  const luot = (kw = {}) => ({
    id: 'run1', status: 'done', asked_count: 2, dropped_count: 0,
    suggestions: [{ source_term: 'Pepper', target_term: 'Pepper', term_type: 'character_name',
                    note: 'cô phù thuỷ nhỏ', nguon: 'goi_y_mo_hinh_chua_duyet' }],
    error_log: null, ...kw,
  })

  it('luôn dán nhãn chưa duyệt lên gợi ý của mô hình', async () => {
    const doc = vi.fn().mockResolvedValue(luot())
    render(<TermCandidatePanel onChon={vi.fn()} onTim={vi.fn().mockResolvedValue(ketQua())}
                               onXinGoiY={vi.fn().mockResolvedValue({ id: 'run1', status: 'queued' })}
                               onDocGoiY={doc} />)
    await userEvent.click(nut('Tìm trong chapter'))
    await screen.findByText('Pepper')
    await userEvent.type(screen.getByLabelText(/Tên bộ truyện/), 'Pepper&Carrot')
    await userEvent.click(nut('Xin gợi ý'))

    await waitFor(() => expect(screen.getByText(/gợi ý · chưa duyệt/)).toBeInTheDocument(),
                  { timeout: 4000 })
  })

  it('nói ra số mục bị loại vì chapter không có', async () => {
    const doc = vi.fn().mockResolvedValue(luot({ dropped_count: 2 }))
    render(<TermCandidatePanel onChon={vi.fn()} onTim={vi.fn().mockResolvedValue(ketQua())}
                               onXinGoiY={vi.fn().mockResolvedValue({ id: 'run1', status: 'queued' })}
                               onDocGoiY={doc} />)
    await userEvent.click(nut('Tìm trong chapter'))
    await screen.findByText('Pepper')
    await userEvent.type(screen.getByLabelText(/Tên bộ truyện/), 'X')
    await userEvent.click(nut('Xin gợi ý'))

    await waitFor(() => expect(screen.getByText(/loại 2 mục/i)).toBeInTheDocument(),
                  { timeout: 4000 })
  })

  it('mô hình hỏng thì nói bảng danh xưng vẫn dùng được', async () => {
    const doc = vi.fn().mockResolvedValue(luot({ status: 'failed', suggestions: null,
                                                 error_log: 'HTTP 429' }))
    render(<TermCandidatePanel onChon={vi.fn()} onTim={vi.fn().mockResolvedValue(ketQua())}
                               onXinGoiY={vi.fn().mockResolvedValue({ id: 'run1', status: 'queued' })}
                               onDocGoiY={doc} />)
    await userEvent.click(nut('Tìm trong chapter'))
    await screen.findByText('Pepper')
    await userEvent.type(screen.getByLabelText(/Tên bộ truyện/), 'X')
    await userEvent.click(nut('Xin gợi ý'))

    await waitFor(() => expect(screen.getByText(/vẫn dùng bình thường/)).toBeInTheDocument(),
                  { timeout: 4000 })
  })
})

describe('E17 — nối vào form thuật ngữ', () => {
  it('điền sẵn thuật ngữ gốc nhưng để TRỐNG cách dịch và giải nghĩa', async () => {
    render(<GlossaryManager danhSach={[]} onThem={vi.fn()} onDuyet={vi.fn()} onCat={vi.fn()}
                            onSua={vi.fn()} onTimUngVien={vi.fn().mockResolvedValue(ketQua())} />)
    await userEvent.click(nut('Tìm trong chapter'))
    await screen.findByText('Pepper')
    await userEvent.click(nut('Thêm thành thuật ngữ'))

    expect(screen.getByLabelText(/Thuật ngữ gốc/)).toHaveValue('Pepper')
    expect(screen.getByLabelText(/Cách dịch đã chốt/)).toHaveValue('')
    expect(screen.getByLabelText(/Giải nghĩa/)).toHaveValue('')
  })

  it('hiện bằng chứng ngay trong form để quyết được mà không phải nhớ lại', async () => {
    render(<GlossaryManager danhSach={[]} onThem={vi.fn()} onDuyet={vi.fn()} onCat={vi.fn()}
                            onSua={vi.fn()} onTimUngVien={vi.fn().mockResolvedValue(ketQua())} />)
    await userEvent.click(nut('Tìm trong chapter'))
    await screen.findByText('Pepper')
    await userEvent.click(nut('Thêm thành thuật ngữ'))

    expect(screen.getByText(/Tìm thấy 3 lần trong chapter/)).toBeInTheDocument()
  })
})

describe('E17 tầng 2 — tín hiệu xưng hô', () => {
  it('hiện tín hiệu kèm câu gốc và không hứa biết ai nói câu nào', async () => {
    render(<VoiceProfileManager danhSach={[]} onThem={vi.fn()} onBat={vi.fn()} onCat={vi.fn()}
                                onTimTinHieu={vi.fn().mockResolvedValue(tinHieu())} />)
    await userEvent.click(nut('Tìm tín hiệu xưng hô'))

    expect(await screen.findByText(/ngài \/ đại nhân/)).toBeInTheDocument()
    expect(screen.getByText(/ペッパー様、お待ちください/)).toBeInTheDocument()
    expect(screen.getByText(/không phải “nhân vật X xưng thế này với Y”/)).toBeInTheDocument()
  })

  it('điền sẵn hồ sơ từ tín hiệu, ghi rõ nguồn là bản gốc', async () => {
    render(<VoiceProfileManager danhSach={[]} onThem={vi.fn()} onBat={vi.fn()} onCat={vi.fn()}
                                onTimTinHieu={vi.fn().mockResolvedValue(tinHieu())} />)
    await userEvent.click(nut('Tìm tín hiệu xưng hô'))
    await userEvent.click(await screen.findByRole('button', { name: /Tạo hồ sơ cho ペッパー/ }))

    expect(screen.getByLabelText(/Tên nhân vật/)).toHaveValue('ペッパー')
    expect(screen.getByLabelText(/Cách xưng hô tiếng Việt/)).toHaveValue('ngài / đại nhân')
    expect(screen.getByLabelText(/Ghi chú giọng điệu/).value)
      .toMatch(/Rút từ bản gốc: hậu tố .* \(2 lần\)/)
  })

  it('chưa đọc chữ thì KHÔNG được nói là chapter không có tín hiệu nào', async () => {
    render(<VoiceProfileManager danhSach={[]} onThem={vi.fn()} onBat={vi.fn()} onCat={vi.fn()}
                                onTimTinHieu={vi.fn().mockResolvedValue(
                                  tinHieu({ tin_hieu: [], trang_thai: 'chua_doc_chu' }))} />)
    await userEvent.click(nut('Tìm tín hiệu xưng hô'))
    expect(await screen.findByText(/Chưa đọc được chữ trong chapter/)).toBeInTheDocument()
    expect(screen.getByText(/chưa kết luận được/)).toBeInTheDocument()
  })
})
