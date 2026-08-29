import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ConsistencyPanel from './ConsistencyPanel.jsx'
import ConsistencyReviewQueue from './ConsistencyReviewQueue.jsx'
import GlossaryManager from './GlossaryManager.jsx'
import VoiceProfileManager from './VoiceProfileManager.jsx'
import ExportWarningModal from '../ExportWarningModal.jsx'

const tomTat = (kw = {}) => ({
  open_count: 2, accepted_count: 1, rejected_count: 0, stale_count: 0,
  resolved_no_change_count: 0, by_type: { glossary_missing: 1, prohibited_variant: 1 },
  approved_glossary_count: 3, active_voice_profile_count: 0, ...kw,
})

const muc = (kw = {}) => ({
  id: 'g1', source_term: 'magic potion', target_term: 'bình thuốc phép',
  term_type: 'item', definition: 'Lọ thuốc phù thuỷ pha', usage_note: null,
  prohibited_variants: [], status: 'draft', ...kw,
})

const viec = (kw = {}) => ({
  id: 't1', region_id: 'r1', task_type: 'glossary_missing', status: 'open',
  current_text_snapshot: 'Tôi uống lọ thuốc ma thuật', proposed_text: null,
  evidence: {
    thuat_ngu_nguon: 'magic potion', thuat_ngu_da_duyet: 'bình thuốc phép',
    dinh_nghia: 'Lọ thuốc phù thuỷ pha',
    ly_do: 'Chữ gốc có “magic potion” — thuật ngữ này đã được chốt là “bình thuốc phép”, nhưng bản dịch hiện tại chưa dùng.',
  },
  ...kw,
})

describe('bảng nhất quán của chapter', () => {
  it('nói rõ đây là gợi ý, KHÔNG khẳng định bản dịch sai', () => {
    render(<ConsistencyPanel tomTat={tomTat()} onQuet={vi.fn()} onMoHangDoi={vi.fn()} />)
    expect(screen.getByText(/không khẳng định bản dịch sai/)).toBeInTheDocument()
  })

  it('không bao giờ hiện điểm chất lượng dạng số phần trăm', () => {
    render(<ConsistencyPanel tomTat={tomTat()} onQuet={vi.fn()} onMoHangDoi={vi.fn()} />)
    expect(document.body.textContent).not.toMatch(/\d+\s*(%|\/100)|điểm chất lượng|chất lượng: \d/i)
  })

  it('chưa duyệt thuật ngữ nào thì KHÔNG được trình bày như "đã ổn"', () => {
    render(<ConsistencyPanel tomTat={tomTat({ open_count: 0, approved_glossary_count: 0 })}
                             onQuet={vi.fn()} onMoHangDoi={vi.fn()} />)
    expect(screen.getByText(/KHÔNG có nghĩa là bản dịch đã ổn/i)).toBeInTheDocument()
  })

  it('khoá nút rà soát kèm lý do khi chưa có thuật ngữ đã duyệt', () => {
    render(<ConsistencyPanel tomTat={tomTat({ approved_glossary_count: 0 })}
                             onQuet={vi.fn()} onMoHangDoi={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Rà soát nhất quán/ })).toBeDisabled()
    expect(screen.getByText(/Duyệt ít nhất một thuật ngữ/)).toBeInTheDocument()
  })

  it('gợi ý đã cũ được nêu riêng, không trộn vào số việc cần xem', () => {
    render(<ConsistencyPanel tomTat={tomTat({ open_count: 0, stale_count: 3 })}
                             onQuet={vi.fn()} onMoHangDoi={vi.fn()} />)
    // Nêu ở cả danh sách lẫn ô nhắc là có chủ đích — miễn KHÔNG bị cộng vào "cần xem".
    expect(screen.getAllByText(/đã cũ/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Không còn chỗ nào cần xem/)).toBeInTheDocument()
  })
})

describe('bảng thuật ngữ', () => {
  it('nói rõ chỉ mục đã duyệt mới được dùng khi rà soát', () => {
    render(<GlossaryManager danhSach={[muc()]} onThem={vi.fn()} onDuyet={vi.fn()}
                            onCat={vi.fn()} onSua={vi.fn()} />)
    expect(screen.getByText(/chỉ mục đã duyệt mới được dùng/)).toBeInTheDocument()
  })

  it('cột trạng thái hiện bằng CHỮ, không chỉ bằng màu', () => {
    render(<GlossaryManager danhSach={[muc()]} onThem={vi.fn()} onDuyet={vi.fn()}
                            onCat={vi.fn()} onSua={vi.fn()} />)
    expect(screen.getByText('Nháp')).toBeInTheDocument()
  })

  it('bắt buộc nhập giải nghĩa — không cho lưu thuật ngữ trần trụi', async () => {
    const onThem = vi.fn()
    render(<GlossaryManager danhSach={[]} onThem={onThem} onDuyet={vi.fn()}
                            onCat={vi.fn()} onSua={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Thêm thuật ngữ/ }))
    await userEvent.type(screen.getByLabelText(/Thuật ngữ gốc/), 'Pepper')
    await userEvent.type(screen.getByLabelText(/Cách dịch đã chốt/), 'Pepper')
    await userEvent.click(screen.getByRole('button', { name: /^Thêm$/ }))
    expect(onThem).not.toHaveBeenCalled()
    expect(screen.getByText(/Thiếu giải nghĩa/)).toBeInTheDocument()
  })

  it('cảnh báo rõ khi sửa mục đã duyệt', async () => {
    render(<GlossaryManager danhSach={[muc({ status: 'approved' })]} onThem={vi.fn()}
                            onDuyet={vi.fn()} onCat={vi.fn()} onSua={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Sửa/ }))
    expect(screen.getByText(/sẽ cần duyệt lại/i)).toBeInTheDocument()
  })

  it('nói rõ danh sách cấm chỉ để cảnh báo, không tự thay chữ', async () => {
    render(<GlossaryManager danhSach={[]} onThem={vi.fn()} onDuyet={vi.fn()}
                            onCat={vi.fn()} onSua={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /Thêm thuật ngữ/ }))
    expect(screen.getByText(/không bao giờ tự thay chữ/)).toBeInTheDocument()
  })

  it('trạng thái rỗng KHÔNG được trình bày như đã hoàn tất', () => {
    render(<GlossaryManager danhSach={[]} onThem={vi.fn()} onDuyet={vi.fn()}
                            onCat={vi.fn()} onSua={vi.fn()} />)
    expect(screen.getByText(/Chưa có thuật ngữ nào/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/hoàn tất|đã xong|đạt chuẩn/i)
  })
})

describe('hồ sơ giọng nhân vật', () => {
  it('nói rõ đây là hướng dẫn của người, máy không tự sửa lời thoại', () => {
    render(<VoiceProfileManager danhSach={[]} onThem={vi.fn()} onBat={vi.fn()} onCat={vi.fn()} />)
    expect(screen.getByText(/hướng dẫn của bạn/)).toBeInTheDocument()
    expect(screen.getByText(/không.*tự.*sửa lời thoại/i)).toBeInTheDocument()
  })

  it('KHÔNG hiện thanh "độ tin cậy của AI"', () => {
    render(<VoiceProfileManager
      danhSach={[{ id: 'v1', character_name: 'Pepper', speech_register: 'casual',
                   vietnamese_pronoun_guidance: 'xưng tớ', tone_note: null, status: 'active' }]}
      onThem={vi.fn()} onBat={vi.fn()} onCat={vi.fn()} />)
    expect(document.body.textContent).not.toMatch(/độ tin cậy|confidence|AI chắc chắn/i)
  })
})

describe('hàng đợi rà soát', () => {
  it('hiện lý do và bản dịch hiện tại để người dùng tự quyết', () => {
    render(<ConsistencyReviewQueue viec={[viec()]} onAp={vi.fn()} onGiuNguyen={vi.fn()}
                                   onBoQua={vi.fn()} />)
    expect(screen.getByText(/đã được chốt là/)).toBeInTheDocument()
    // Bản dịch hiện tại hiện ở phần bằng chứng, và cũng là nội dung sẵn trong ô sửa.
    expect(screen.getAllByText('Tôi uống lọ thuốc ma thuật').length).toBeGreaterThan(0)
    expect(screen.getByLabelText(/Bản dịch cho vùng này/))
      .toHaveValue('Tôi uống lọ thuốc ma thuật')
    expect(screen.getByText('bình thuốc phép')).toBeInTheDocument()
  })

  it('báo trước hậu quả: căn chữ lại và có thể tràn khung', () => {
    render(<ConsistencyReviewQueue viec={[viec()]} onAp={vi.fn()} onGiuNguyen={vi.fn()}
                                   onBoQua={vi.fn()} />)
    expect(screen.getByText(/căn chữ lại/)).toBeInTheDocument()
    expect(screen.getByText(/tràn khung/)).toBeInTheDocument()
  })

  it('gợi ý đã cũ thì KHÔNG cho áp dụng', () => {
    render(<ConsistencyReviewQueue viec={[viec({ status: 'stale' })]} onAp={vi.fn()}
                                   onGiuNguyen={vi.fn()} onBoQua={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Áp dụng/ })).not.toBeInTheDocument()
    expect(screen.getByText(/Bản dịch đã thay đổi từ lần quét/)).toBeInTheDocument()
  })

  it('người dùng sửa được bản dịch rồi mới áp', async () => {
    const onAp = vi.fn()
    render(<ConsistencyReviewQueue viec={[viec()]} onAp={onAp} onGiuNguyen={vi.fn()}
                                   onBoQua={vi.fn()} />)
    const o = screen.getByLabelText(/Bản dịch cho vùng này/)
    await userEvent.clear(o)
    await userEvent.type(o, 'Tôi uống bình thuốc phép')
    await userEvent.click(screen.getByRole('button', { name: /Áp dụng bản đã sửa/ }))
    expect(onAp).toHaveBeenCalledWith('t1', 'Tôi uống bình thuốc phép')
  })

  it('hết việc thì nói rõ "không còn chỗ lệch thuật ngữ", KHÔNG nói "dịch đúng"', () => {
    render(<ConsistencyReviewQueue viec={[]} onAp={vi.fn()} onGiuNguyen={vi.fn()}
                                   onBoQua={vi.fn()} />)
    // Câu bị thẻ <b> cắt ngang nên phải so trên toàn bộ chữ hiển thị.
    expect(document.body.textContent).toMatch(/không.*có nghĩa là bản dịch đã đúng nghĩa/i)
    expect(document.body.textContent).not.toMatch(/dịch chuẩn|dịch đúng hoàn toàn/i)
  })
})

describe('cảnh báo trước khi xuất', () => {
  const canhBao = { overflow_warning_count: 1, needs_manual_count: 0,
                    quality_needs_review_count: 0, quality_unassessed_count: 0,
                    quality_reviewed_skip_count: 0, acknowledged: false }

  it('đếm việc nhất quán TÁCH RIÊNG khỏi tràn khung và bản quyền', () => {
    render(<ExportWarningModal canhBao={canhBao} nhatQuan={tomTat()} dinhDang="cbz"
                               onHuy={vi.fn()} onDongY={vi.fn()} />)
    // Ba khối phải TÁCH RIÊNG: nhất quán ≠ bố cục (tràn khung) ≠ pháp lý (bản quyền).
    expect(screen.getByRole('heading', { name: /Nhất quán thuật ngữ/ })).toBeInTheDocument()
    expect(screen.getByText(/tràn ra ngoài khung/)).toBeInTheDocument()
    expect(screen.getAllByText(/trách nhiệm về bản quyền/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/chưa rà soát/)).toBeInTheDocument()
  })

  it('gợi ý đã từ chối KHÔNG bị tính là việc còn tồn', () => {
    render(<ExportWarningModal canhBao={canhBao}
                               nhatQuan={tomTat({ open_count: 0, rejected_count: 2 })}
                               dinhDang="cbz" onHuy={vi.fn()} onDongY={vi.fn()} />)
    expect(screen.getByText(/không tính là việc còn tồn/)).toBeInTheDocument()
  })

  it('vẫn cho xuất, và nói thẳng là đang xuất khi còn việc chưa rà soát', () => {
    render(<ExportWarningModal canhBao={canhBao} nhatQuan={tomTat()} dinhDang="cbz"
                               onHuy={vi.fn()} onDongY={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Xuất dù còn 2 chỗ cần rà soát/ })).toBeInTheDocument()
  })
})

describe('ngữ cảnh giọng nhân vật trong lúc rà soát', () => {
  const giong = [
    { id: 'v1', character_name: 'Pepper', speech_register: 'casual',
      vietnamese_pronoun_guidance: "xưng 'tớ', gọi Carrot là 'cậu'", tone_note: null,
      status: 'active' },
    { id: 'v2', character_name: 'Cumin', speech_register: 'formal',
      vietnamese_pronoun_guidance: 'xưng ta', tone_note: null, status: 'archived' },
  ]

  it('hiện hồ sơ đang bật để người sửa tự cân nhắc', () => {
    render(<ConsistencyReviewQueue viec={[viec()]} hoSoGiong={giong} onAp={vi.fn()}
                                   onGiuNguyen={vi.fn()} onBoQua={vi.fn()} />)
    expect(screen.getByText('Pepper')).toBeInTheDocument()
    expect(screen.getByText(/xưng 'tớ'/)).toBeInTheDocument()
    // Phải là nhãn tiếng Việt, không phải mã enum lọt ra màn hình.
    expect(screen.getByText(/Thân mật/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/\bcasual\b/)
  })

  it('hồ sơ đã cất KHÔNG hiện ra như đang có hiệu lực', () => {
    render(<ConsistencyReviewQueue viec={[viec()]} hoSoGiong={giong} onAp={vi.fn()}
                                   onGiuNguyen={vi.fn()} onBoQua={vi.fn()} />)
    expect(screen.queryByText('Cumin')).not.toBeInTheDocument()
  })

  it('nói thẳng là máy KHÔNG tự sửa lời thoại theo hồ sơ', () => {
    render(<ConsistencyReviewQueue viec={[viec()]} hoSoGiong={giong} onAp={vi.fn()}
                                   onGiuNguyen={vi.fn()} onBoQua={vi.fn()} />)
    expect(screen.getByText(/tự sửa lời thoại theo/)).toBeInTheDocument()
  })

  it('hồ sơ giọng KHÔNG được tự chèn vào ô bản dịch', () => {
    render(<ConsistencyReviewQueue viec={[viec()]} hoSoGiong={giong} onAp={vi.fn()}
                                   onGiuNguyen={vi.fn()} onBoQua={vi.fn()} />)
    expect(screen.getByLabelText(/Bản dịch cho vùng này/))
      .toHaveValue('Tôi uống lọ thuốc ma thuật')
  })
})
