/** E17 tầng 3b (giao diện) — tra CSDL nhân vật.
 *
 * Nguyên tắc phải nhìn thấy được trên màn hình: **chapter quyết định cần gì, CSDL chỉ trả lời
 * viết thế nào** — và khi nguồn ngoài hỏng thì phải NÓI RA, không để ô kết quả trống trông như
 * "không có gì".
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import TermCandidatePanel from './TermCandidatePanel.jsx'

const ketQuaTim = () => ({
  ung_vien: [{ source_term: 'Nami', term_key: 'nami', count: 2, pages: [1],
               quotes: [], type_guess: 'character_name', reasons: ['viết hoa giữa câu'] }],
  so_vung_da_quet: 5, so_vung_co_chu: 5, trang_thai: 'co_ung_vien', so_bi_loc_vi_da_co: 0,
})

async function moPanel(onDoiChieuTen) {
  render(<TermCandidatePanel onTim={vi.fn().mockResolvedValue(ketQuaTim())}
                             onChon={vi.fn()} onDoiChieuTen={onDoiChieuTen} />)
  await userEvent.click(screen.getByRole('button', { name: /Tìm trong chapter/ }))
  await waitFor(() => expect(screen.getByText('Nami')).toBeInTheDocument())
}

describe('tra CSDL nhân vật', () => {
  it('CHƯA nhập tên bộ truyện thì nút bị khoá, kèm lý do', async () => {
    await moPanel(vi.fn())
    expect(screen.getByRole('button', { name: /Tra CSDL/ })).toBeDisabled()
  })

  it('khớp thì hiện cách viết chính thức KÈM tên gốc và lý do khớp', async () => {
    const tra = vi.fn().mockResolvedValue({
      tim_thay_bo_truyen: 'ONE PIECE', bo_qua: 22, khong_dung_duoc: null,
      khop: [{ danh_xung: 'Nami', ten_day_du: 'Nami', ten_goc: 'ナミ',
               ten_khac: [], ly_do: 'khớp tên đầy đủ trong CSDL AniList' }],
    })
    await moPanel(tra)
    await userEvent.type(screen.getByLabelText(/Tên bộ truyện/), 'One Piece')
    await userEvent.click(screen.getByRole('button', { name: /Tra CSDL/ }))
    await waitFor(() => expect(screen.getByText(/ナミ/)).toBeInTheDocument())
    expect(screen.getByText(/khớp tên đầy đủ/)).toBeInTheDocument()
  })

  it('NÓI RA số nhân vật CSDL có mà chapter không có', async () => {
    // Con số này là lý do vì sao không đổ cả CSDL vào glossary — giấu đi là mất lập luận.
    const tra = vi.fn().mockResolvedValue({
      tim_thay_bo_truyen: 'ONE PIECE', bo_qua: 22, khong_dung_duoc: null,
      khop: [{ danh_xung: 'Nami', ten_day_du: 'Nami', ten_goc: 'ナミ', ten_khac: [], ly_do: 'x' }],
    })
    await moPanel(tra)
    await userEvent.type(screen.getByLabelText(/Tên bộ truyện/), 'One Piece')
    await userEvent.click(screen.getByRole('button', { name: /Tra CSDL/ }))
    await waitFor(() => expect(screen.getByText(/22/)).toBeInTheDocument())
  })

  it('nguồn ngoài hỏng thì NÓI RA, và trấn an bảng danh xưng vẫn dùng được', async () => {
    const tra = vi.fn().mockResolvedValue({
      khop: [], bo_qua: 0, khong_dung_duoc: 'không kết nối được tới AniList',
    })
    await moPanel(tra)
    await userEvent.type(screen.getByLabelText(/Tên bộ truyện/), 'One Piece')
    await userEvent.click(screen.getByRole('button', { name: /Tra CSDL/ }))
    await waitFor(() => expect(screen.getByText(/không kết nối được/)).toBeInTheDocument())
    expect(screen.getByText(/vẫn dùng bình thường/)).toBeInTheDocument()
  })

  it('lỗi mạng ném ra cũng phải hiện, không để ô kết quả trống', async () => {
    await moPanel(vi.fn().mockRejectedValue(new Error('500: sập')))
    await userEvent.type(screen.getByLabelText(/Tên bộ truyện/), 'One Piece')
    await userEvent.click(screen.getByRole('button', { name: /Tra CSDL/ }))
    await waitFor(() => expect(screen.getByText(/Không tra được/)).toBeInTheDocument())
  })

  it('không khớp gì thì nói THẲNG, không im lặng', async () => {
    const tra = vi.fn().mockResolvedValue({ khop: [], bo_qua: 500, khong_dung_duoc: null })
    await moPanel(tra)
    await userEvent.type(screen.getByLabelText(/Tên bộ truyện/), 'One Piece')
    await userEvent.click(screen.getByRole('button', { name: /Tra CSDL/ }))
    await waitFor(() =>
      expect(screen.getByText(/Không danh xưng nào của chapter khớp CSDL/)).toBeInTheDocument())
  })
})
