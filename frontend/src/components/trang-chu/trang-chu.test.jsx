import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { chuDemNguoc, conLaiMs, mocHetHanGiuTep } from '../../lib/dem-nguoc'
import TheHanMuc from './TheHanMuc'
import TrangChu from './TrangChu'

/** E53 — trang chủ: bốn chỗ dễ nói SAI, và bài canh cho từng chỗ.
 *
 * 1. `con_lai` KHÔNG bằng `tran - da_dung` — tự tính lại là mời người ta thả tệp rồi nhận 429.
 * 2. Chốt `khach_ip` phải nói "địa chỉ mạng dùng chung", không nói "bạn đã hết lượt".
 * 3. Luật 30 phút phải nói ĐÚNG MỨC hậu quả (§2.9), không nói mơ hồ kiểu "tệp sẽ được dọn".
 * 4. Nút tải thủ công phải LUÔN có — trình duyệt chặn lượt tải không do người bấm, và JavaScript
 *    không có cách nào biết nó đã bị chặn.
 */

const HAN_MUC_CON = {
  co_tai_khoan: false, tran: 6, da_dung: 2, con_lai: 4,
  // E54 — chính sách giữ tệp do MÁY CHỦ nói, giao diện không gõ cứng. `null` = không tự xoá.
  giu_ket_qua_phut: 30,
  reset_luc: '2026-09-28T00:00:00+07:00', reset_sau_giay: 3600,
  chot: [
    { loai: 'khach_cookie', da_dung: 2, con_lai: 4, tran: 6 },
    { loai: 'khach_ip', da_dung: 5, con_lai: 20, tran: 25 },
  ],
}

/** Ô `<input type="file">` THẬT của Dropzone.
 *
 * `id` của Dropzone gắn vào DIV vùng thả (nó là `role="button"`), còn ô file thật bị ẩn khỏi mắt
 * và không có nhãn — nên phải lấy theo kiểu phần tử. Nhắm vào DIV thì user-event báo
 * "The given DIV element does not accept file uploads".
 */
const oFile = () => document.querySelector('input[type="file"]')

function dapUng(body, status = 200) {
  return Promise.resolve({
    ok: status < 400, status,
    json: () => Promise.resolve(body),
    headers: { get: () => null },
  })
}

afterEach(() => vi.restoreAllMocks())

describe('đồng hồ đếm ngược', () => {
  it('nhận MỐC nên không sai khi tab để mở lâu', () => {
    const moc = new Date(Date.now() + 90 * 60_000).toISOString()
    expect(chuDemNguoc(moc)).toBe('1 giờ 30 phút')
    // Cùng một mốc, "bây giờ" trôi đi 60 phút ⇒ tự đúng, không cần ai cập nhật.
    expect(chuDemNguoc(moc, Date.now() + 60 * 60_000)).toBe('30 phút')
  })

  it('hết giờ thì nói HẾT GIỜ chứ không ra số âm', () => {
    expect(chuDemNguoc(new Date(Date.now() - 1000).toISOString())).toBe('hết giờ')
    expect(conLaiMs(new Date(Date.now() - 5000).toISOString())).toBe(0)
  })

  it('CHƯA XONG thì KHÔNG có mốc hết hạn', () => {
    // §2.3 — đếm từ lúc XONG. Trả "bây giờ + 30 phút" khi chưa xong là để một chapter 24 trang
    // hết hạn trước khi dịch xong.
    expect(mocHetHanGiuTep(null)).toBeNull()
    expect(mocHetHanGiuTep(undefined)).toBeNull()
  })

  it('mốc hết hạn tính từ lúc xong, không từ bây giờ', () => {
    const xong = '2026-09-27T10:00:00+07:00'
    expect(mocHetHanGiuTep(xong, 30)).toBe(new Date('2026-09-27T10:30:00+07:00').toISOString())
  })
})

describe('thẻ hạn mức', () => {
  it('hiện ĐÚNG con_lai của máy chủ, KHÔNG tự tính tran - da_dung', () => {
    // Bài canh: chốt cookie còn 4 nhưng máy chủ nói con_lai = 1 (vì chốt khác thấp hơn).
    // Tự tính `6 - 2 = 4` là mời người dùng thả 4 tệp rồi nhận 429.
    render(<TheHanMuc hanMuc={{ ...HAN_MUC_CON, con_lai: 1 }} />)
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText(/\/ 6 trang còn lại/)).toBeInTheDocument()
  })

  it('bị chốt IP chặn thì nói ĐỊA CHỈ MẠNG, không nói "bạn đã hết lượt"', () => {
    render(<TheHanMuc hanMuc={{
      ...HAN_MUC_CON, con_lai: 0,
      chot: [
        { loai: 'khach_cookie', da_dung: 1, con_lai: 5, tran: 6 },
        { loai: 'khach_ip', da_dung: 25, con_lai: 0, tran: 25 },
      ],
    }} />)
    expect(screen.getByText(/Địa chỉ mạng này đã hết lượt chung/)).toBeInTheDocument()
    expect(screen.queryByText(/^Bạn đã hết lượt hôm nay$/)).not.toBeInTheDocument()
  })

  it('chính mình hết lượt thì nói đúng là của mình', () => {
    render(<TheHanMuc hanMuc={{
      ...HAN_MUC_CON, con_lai: 0,
      chot: [
        { loai: 'khach_cookie', da_dung: 6, con_lai: 0, tran: 6 },
        { loai: 'khach_ip', da_dung: 6, con_lai: 19, tran: 25 },
      ],
    }} />)
    expect(screen.getByText('Bạn đã hết lượt hôm nay')).toBeInTheDocument()
  })

  it('luôn nói BAO GIỜ có lại — không có câu này người dùng tưởng hỏng', () => {
    render(<TheHanMuc hanMuc={HAN_MUC_CON} />)
    expect(screen.getByText(/Có lại sau/)).toBeInTheDocument()
    expect(screen.getByText(/0h00 giờ Việt Nam/)).toBeInTheDocument()
  })

  it('lấy hạn mức lỗi thì NÓI RA kèm nút thử lại, không im lặng', () => {
    render(<TheHanMuc loi={new Error('mạng lỗi')} onTaiLai={() => {}} />)
    expect(screen.getByText('Chưa lấy được hạn mức')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Thử lại' })).toBeInTheDocument()
  })
})

describe('trang chủ', () => {
  it('nói ĐÚNG MỨC hậu quả của luật 30 phút, không nói mơ hồ', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(HAN_MUC_CON))
    render(<TrangChu />)
    await screen.findByText(/Lượt dịch hôm nay/)

    // §2.9 — phải nói rõ là MẤT HẲN và không chạy lại được, chứ không phải "tệp sẽ được dọn".
    expect(screen.getByText(/chỉ giữ 30 phút/)).toBeInTheDocument()
    expect(screen.getByText(/không chạy lại được/)).toBeInTheDocument()
    expect(screen.getByText(/tốn thêm lượt/)).toBeInTheDocument()
  })

  it('nói trước là mỗi trang mất ~30 giây', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(HAN_MUC_CON))
    render(<TrangChu />)
    // Thiếu câu này thì người dùng tưởng máy treo, bấm lại, và tốn hạn mức oan.
    expect(await screen.findByText(/khoảng 30 giây/)).toBeInTheDocument()
  })

  it('chọn nhiều trang hơn số lượt còn lại thì CHẶN TRƯỚC, không để nhận 429', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng({ ...HAN_MUC_CON, con_lai: 1 }))
    render(<TrangChu />)
    await screen.findByText(/Lượt dịch hôm nay/)

    const o = oFile()
    await userEvent.upload(o, [
      new File(['a'], 'a.png', { type: 'image/png' }),
      new File(['b'], 'b.png', { type: 'image/png' }),
    ])

    // Câu này hiện ở HAI chỗ có chủ đích: cảnh báo trên màn, và lý do nút bị khoá. Dùng
    // `findAllByText` thay vì `findByText` — không thì truy vấn mơ hồ và bài test đỏ vì chính nó.
    expect(await screen.findAllByText(/Nhiều hơn số lượt còn lại/)).not.toHaveLength(0)
    // Khẳng định thêm điều QUAN TRỌNG hơn: nút thật sự bị khoá, không chỉ có chữ cảnh báo.
    expect(screen.getByRole('button', { name: /Dịch 2 trang/ })).toBeDisabled()
  })

  it('gửi trang kèm che_do=day_du — thiếu nó là KHÔNG có ảnh nào để tải', async () => {
    const goi = vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts) => {
      if (String(url).includes('/han-muc')) return dapUng(HAN_MUC_CON)
      if (String(url).includes('/doc-truyen/trang') && opts?.method === 'POST') {
        return dapUng({ page_id: 'p1', project_id: 'c1', trang_thai: 'queued', xong: false, tien_do: {} })
      }
      return dapUng({
        page_id: 'p1', project_id: 'c1', trang_thai: 'typeset_done', xong: true,
        che_do: 'day_du', tien_do: {},
      })
    })
    render(<TrangChu />)
    await screen.findByText(/Lượt dịch hôm nay/)

    await userEvent.upload(
      oFile(),
      [new File(['a'], 'a.png', { type: 'image/png' })],
    )
    await userEvent.click(screen.getByRole('button', { name: /Dịch/ }))

    await waitFor(() => {
      const gui = goi.mock.calls.find(([u, o]) => String(u).includes('/doc-truyen/trang') && o?.method === 'POST')
      expect(gui).toBeTruthy()
      expect(gui[1].body.get('che_do')).toBe('day_du')
    })
  })

  it('E54 — máy chủ nói KHÔNG tự xoá thì giao diện KHÔNG hứa xoá sau 30 phút', async () => {
    // Đây đúng trạng thái bản chạy 27-09: `BAT_LICH_DON_TEP` tắt, tệp KHÔNG bị xoá, mà màn hình
    // vẫn hứa "chỉ giữ 30 phút". Không mất dữ liệu, nhưng là một câu SAI về dữ liệu của người dùng.
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => dapUng({ ...HAN_MUC_CON, giu_ket_qua_phut: null }),
    )
    render(<TrangChu />)
    await screen.findByText(/Lượt dịch hôm nay/)

    expect(screen.queryByText(/chỉ giữ 30 phút/)).not.toBeInTheDocument()
    expect(screen.getByText(/không tự xoá/)).toBeInTheDocument()
    // Vẫn phải nhắc tải về — "không tự xoá" KHÔNG đồng nghĩa "chỗ lưu trữ lâu dài".
    expect(screen.getByText(/không phải chỗ lưu trữ lâu dài/)).toBeInTheDocument()
  })

  it('E54 — máy chủ đổi số phút thì giao diện nói theo, không gõ cứng 30', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => dapUng({ ...HAN_MUC_CON, giu_ket_qua_phut: 45 }),
    )
    render(<TrangChu />)
    await screen.findByText(/Lượt dịch hôm nay/)
    expect(screen.getByText(/chỉ giữ 45 phút/)).toBeInTheDocument()
  })

  it('xong rồi thì LUÔN có nút tải thủ công — không có cách nào dò được trình duyệt đã chặn', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts) => {
      if (String(url).includes('/han-muc')) return dapUng(HAN_MUC_CON)
      if (String(url).includes('/doc-truyen/trang') && opts?.method === 'POST') {
        return dapUng({ page_id: 'p1', project_id: 'c1', trang_thai: 'queued', xong: false, tien_do: {} })
      }
      if (String(url).includes('/anh')) {
        return Promise.resolve({ ok: true, status: 200, blob: () => Promise.resolve(new Blob(['x'])) })
      }
      return dapUng({
        page_id: 'p1', project_id: 'c1', trang_thai: 'typeset_done', xong: true,
        che_do: 'day_du', tien_do: {},
      })
    })
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
    globalThis.URL.revokeObjectURL = vi.fn()

    render(<TrangChu />)
    await screen.findByText(/Lượt dịch hôm nay/)
    await userEvent.upload(
      oFile(),
      [new File(['a'], 'a.png', { type: 'image/png' })],
    )
    await userEvent.click(screen.getByRole('button', { name: /Dịch/ }))

    expect(await screen.findByRole('button', { name: /Tải ảnh đã dịch về/ }, { timeout: 5000 }))
      .toBeInTheDocument()
    expect(screen.getByText(/Tải về trước khi hết giờ/)).toBeInTheDocument()
  })
})

/** E57 — "Tự nhận" ngôn ngữ trên trang chủ.
 *
 * ## Bài canh nặng nhất
 *
 * `KHONG_gui_duoc_khi_o_chon_con_o_tu_nhan` — `tu-nhan` KHÔNG phải một `source_lang` hợp lệ. Gửi nó
 * lên đường dịch là nhận 422, tức người dùng đọc một lỗi kỹ thuật cho một lựa chọn mà **chính giao
 * diện mời họ chọn**. Bài này khẳng định vào `fetch`: không có lượt gửi trang nào.
 *
 * `khong_ket_luan_thi_HOI_LAI_chu_khong_chon_bua` — đây là lý do cả cách A tồn tại (REPORT_E57 §5).
 * Nếu không kết luận được mà giao diện im lặng chọn `ja`, người dùng nhận bản dịch vô nghĩa và
 * không hiểu vì sao.
 */
describe('E57 — tự nhận ngôn ngữ', () => {
  const ANH = () => new File([new Uint8Array([137, 80, 78, 71])], 'p1.png', { type: 'image/png' })

  /** Định tuyến theo URL. `ketQua` là bản ghi mà `GET /nhan-dang-ngon-ngu/{id}` trả về. */
  function nhaiFetch({ ketQua, loiGui } = {}) {
    return vi.spyOn(globalThis, 'fetch').mockImplementation((url, tuyChon = {}) => {
      const u = String(url)
      if (u.includes('/han-muc')) return dapUng(HAN_MUC_CON)
      if (u.includes('/nhan-dang-ngon-ngu/')) return dapUng(ketQua)
      if (u.includes('/nhan-dang-ngon-ngu')) {
        if (loiGui) return dapUng({ detail: loiGui }, 429)
        return dapUng({ id: 'yc-1', trang_thai: 'queued', xong: false })
      }
      return dapUng({})
    })
  }

  const XONG_JA = {
    id: 'yc-1', trang_thai: 'done', xong: true, ngon_ngu: 'ja', ly_do: 'co_11_kana',
    bang_chung: { kana: 11, han: 5, latin: 0, tong_co_nghia: 16 },
  }

  async function chonTuNhanVaThaTep(u) {
    await u.upload(oFile(), ANH())
    await u.selectOptions(screen.getByLabelText(/Chữ trên ảnh là tiếng gì/), 'tu-nhan')
  }

  it('có lựa chọn "Tự nhận" trong ô chọn ngôn ngữ', async () => {
    nhaiFetch()
    render(<TrangChu />)
    const o = await screen.findByLabelText(/Chữ trên ảnh là tiếng gì/)
    expect([...o.options].map((x) => x.value)).toContain('tu-nhan')
  })

  it('KHONG_gui_duoc_khi_o_chon_con_o_tu_nhan', async () => {
    const f = nhaiFetch()
    const u = userEvent.setup()
    render(<TrangChu />)
    await screen.findByLabelText(/Chữ trên ảnh là tiếng gì/)
    await chonTuNhanVaThaTep(u)

    const nut = screen.getByRole('button', { name: /^Dịch/ })
    expect(nut).toBeDisabled()
    await u.click(nut)
    // Khẳng định vào HÀNH VI: không có lượt gửi trang nào.
    expect(f.mock.calls.filter(([x]) => String(x).includes('/doc-truyen/trang'))).toHaveLength(0)
  })

  it('chưa chọn tệp thì nút đọc thử bị khoá — đọc thử cần một ảnh', async () => {
    nhaiFetch()
    const u = userEvent.setup()
    render(<TrangChu />)
    await screen.findByLabelText(/Chữ trên ảnh là tiếng gì/)
    await u.selectOptions(screen.getByLabelText(/Chữ trên ảnh là tiếng gì/), 'tu-nhan')
    expect(screen.getByRole('button', { name: /Đọc thử trang đầu/ })).toBeDisabled()
  })

  it('đoán được thì ĐỔI ô chọn và hiện SỐ ĐO, không chỉ nói "đã nhận dạng"', async () => {
    nhaiFetch({ ketQua: XONG_JA })
    const u = userEvent.setup()
    render(<TrangChu />)
    await screen.findByLabelText(/Chữ trên ảnh là tiếng gì/)
    await chonTuNhanVaThaTep(u)
    await u.click(screen.getByRole('button', { name: /Đọc thử trang đầu/ }))

    expect(await screen.findByText(/Máy đoán: Tiếng Nhật/, {}, { timeout: 5000 })).toBeInTheDocument()
    // Một kết luận không kèm bằng chứng thì người dùng không biết nên tin bao nhiêu.
    expect(screen.getByText(/11/)).toBeInTheDocument()
    expect(screen.getByText(/Sai thì bạn sửa lại/)).toBeInTheDocument()
    // Ô chọn phải đổi theo, không thì nút Dịch vẫn bị khoá và người dùng bế tắc.
    expect(screen.getByLabelText(/Chữ trên ảnh là tiếng gì/)).toHaveValue('ja')
  })

  it('đoán được rồi thì nút Dịch MỞ ra', async () => {
    nhaiFetch({ ketQua: XONG_JA })
    const u = userEvent.setup()
    render(<TrangChu />)
    await screen.findByLabelText(/Chữ trên ảnh là tiếng gì/)
    await chonTuNhanVaThaTep(u)
    expect(screen.getByRole('button', { name: /^Dịch/ })).toBeDisabled()

    await u.click(screen.getByRole('button', { name: /Đọc thử trang đầu/ }))
    await screen.findByText(/Máy đoán: Tiếng Nhật/, {}, { timeout: 5000 })
    expect(screen.getByRole('button', { name: /^Dịch/ })).not.toBeDisabled()
  })

  it('khong_ket_luan_thi_HOI_LAI_chu_khong_chon_bua', async () => {
    nhaiFetch({
      ketQua: {
        id: 'yc-1', trang_thai: 'done', xong: true, ngon_ngu: null,
        ly_do: 'khong_doc_duoc_chu_nao', bang_chung: { kana: 0, han: 0, tong_co_nghia: 0 },
      },
    })
    const u = userEvent.setup()
    render(<TrangChu />)
    await screen.findByLabelText(/Chữ trên ảnh là tiếng gì/)
    await chonTuNhanVaThaTep(u)
    await u.click(screen.getByRole('button', { name: /Đọc thử trang đầu/ }))

    expect(await screen.findByText(/Máy không đoán được/, {}, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByText(/không đọc ra chữ nào/)).toBeInTheDocument()
    // KHÔNG được âm thầm chọn một ngôn ngữ — ô chọn phải ở nguyên "tự nhận" để người dùng tự chọn.
    expect(screen.getByLabelText(/Chữ trên ảnh là tiếng gì/)).toHaveValue('tu-nhan')
    expect(screen.getByRole('button', { name: /^Dịch/ })).toBeDisabled()
  })

  it('hết lượt đọc thử thì nói ra và bảo chọn tay, không im lặng', async () => {
    nhaiFetch({ loiGui: { loi: 'vuot_han_muc', tran: 20, con_lai: 0, chot: 'khach_cookie' } })
    const u = userEvent.setup()
    render(<TrangChu />)
    await screen.findByLabelText(/Chữ trên ảnh là tiếng gì/)
    await chonTuNhanVaThaTep(u)
    await u.click(screen.getByRole('button', { name: /Đọc thử trang đầu/ }))

    expect(await screen.findByText(/Chưa đọc thử được/, {}, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByText(/chọn tay ở ô trên/)).toBeInTheDocument()
  })

  it('nói rõ đọc thử KHÔNG tính vào lượt dịch', async () => {
    nhaiFetch()
    const u = userEvent.setup()
    render(<TrangChu />)
    await screen.findByLabelText(/Chữ trên ảnh là tiếng gì/)
    await u.selectOptions(screen.getByLabelText(/Chữ trên ảnh là tiếng gì/), 'tu-nhan')
    // Không nói ra thì người dùng tưởng bấm là mất lượt, và sẽ tránh dùng.
    expect(screen.getByText(/Không tính vào lượt dịch/)).toBeInTheDocument()
  })
})
