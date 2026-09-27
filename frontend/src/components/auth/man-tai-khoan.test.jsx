import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ManTaiKhoan from './ManTaiKhoan'

/** E54 — màn tài khoản (§4.4): hiện ĐÚNG những gì có thật.
 *
 * Bài canh nặng nhất là `test_KHONG_bia_so_lieu_khong_co_that`: §4.4 nói rõ "không bịa thêm hạng
 * thành viên hay số liệu chưa có thật". Hệ thống KHÔNG lưu tổng số trang đã dịch, số chapter, ngày
 * tham gia hay chuỗi ngày liên tiếp — bày chúng ra là bịa.
 */

const NGUOI = { email: 'a@x.test', ten_hien: 'An', la_quan_tri: false }
const HAN_MUC = {
  co_tai_khoan: true, tran: 10, da_dung: 3, con_lai: 7, giu_ket_qua_phut: 30,
  reset_luc: new Date(Date.now() + 3600_000).toISOString(), reset_sau_giay: 3600,
  chot: [{ loai: 'nguoi_dung', da_dung: 3, con_lai: 7, tran: 10 }],
}

function dapUng(body, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) })
}

afterEach(() => vi.restoreAllMocks())

describe('màn tài khoản', () => {
  it('hiện email và tên hiển thị', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(HAN_MUC))
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    // `findBy` để lượt nạp hạn mức settle xong — không thì React cảnh báo `act()` và cảnh báo ồn
    // làm người ta quen bỏ qua đầu ra của bộ test.
    expect(await screen.findByText('a@x.test')).toBeInTheDocument()
    expect(screen.getByText('An')).toBeInTheDocument()
  })

  it('chưa đặt tên thì NÓI RA, không để ô rỗng bí ẩn', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(HAN_MUC))
    render(<ManTaiKhoan nguoiDung={{ ...NGUOI, ten_hien: '' }} onDong={() => {}} />)
    expect(await screen.findByText(/chưa đặt/)).toBeInTheDocument()
    await screen.findByText('7')
  })

  it('hiện hạn mức đã dùng / còn lại và mốc reset', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(HAN_MUC))
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    expect(await screen.findByText('7')).toBeInTheDocument()
    expect(screen.getByText(/\/ 10 trang còn lại/)).toBeInTheDocument()
    expect(screen.getByText(/đã dùng 3/)).toBeInTheDocument()
    expect(screen.getByText(/0h00 giờ Việt Nam/)).toBeInTheDocument()
  })

  it('KHÔNG tự tính con_lai — và NÓI RA khi nó thấp hơn phép trừ', async () => {
    // `con_lai` là NHỎ NHẤT trong các chốt. Tự tính `tran - da_dung` ở đây sẽ cho một con số khác
    // với trang chủ, và người dùng thấy hai số vênh nhau thì không biết tin cái nào.
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => dapUng({ ...HAN_MUC, tran: 10, da_dung: 3, con_lai: 2 }),
    )
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    expect(await screen.findByText('2')).toBeInTheDocument()
    expect(screen.getByText(/địa chỉ mạng/)).toBeInTheDocument()
  })

  it('KHÔNG bịa số liệu không có thật', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(HAN_MUC))
    const { container } = render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    await screen.findByText('7')

    const chu = container.textContent
    for (const bia of ['hạng', 'Hạng', 'thành viên', 'ngày tham gia', 'Tổng số trang', 'liên tiếp']) {
      expect(chu).not.toContain(bia)
    }
  })

  it('nói ĐÚNG chính sách giữ tệp theo con số máy chủ gửi', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(HAN_MUC))
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    expect(await screen.findByText(/30 phút/)).toBeInTheDocument()
    await screen.findByText('7')
  })

  it('máy chủ nói KHÔNG tự xoá thì màn này cũng KHÔNG hứa xoá', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => dapUng({ ...HAN_MUC, giu_ket_qua_phut: null }),
    )
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    expect(await screen.findByText(/không tự xoá/)).toBeInTheDocument()
    expect(screen.queryByText(/Tự xoá/)).not.toBeInTheDocument()
  })

  it('lấy hạn mức lỗi thì NÓI RA, không hiện số 0 giả', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng({ detail: 'sập' }, 500))
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    expect(await screen.findByText('Chưa lấy được hạn mức')).toBeInTheDocument()
    expect(screen.queryByText(/trang còn lại/)).not.toBeInTheDocument()
  })

  it('chỉ hiện dòng Quyền khi thật sự là quản trị', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(HAN_MUC))
    const { unmount } = render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    await screen.findByText('7')
    expect(screen.queryByText('Quyền')).not.toBeInTheDocument()
    unmount()
    render(<ManTaiKhoan nguoiDung={{ ...NGUOI, la_quan_tri: true }} onDong={() => {}} />)
    expect(await screen.findByText('Quản trị')).toBeInTheDocument()
    await screen.findByText('7')
  })
})

/** E56 — tự đổi tên hiển thị và mật khẩu.
 *
 * ## Bài canh nặng nhất
 *
 * `KHONG_gui_duoc_khi_hai_o_mat_khau_lech_nhau` — hệ thống KHÔNG có đường lấy lại mật khẩu (chưa
 * có hạ tầng gửi thư, xem REPORT_E52). Gõ sai mật khẩu mới một lần là mất tài khoản vĩnh viễn.
 * Nên bài này khẳng định `fetch` **không hề được gọi**, chứ không chỉ khẳng định có chữ đỏ hiện
 * ra: một câu cảnh báo cạnh một nút vẫn bấm được là trang trí.
 */
describe('E56 — sửa tài khoản', () => {
  /** Định tuyến theo URL + method để một lượt render có cả `/han-muc` (GET) lẫn `/auth/me` (PATCH). */
  function nhaiFetch({ traVe, loi } = {}) {
    return vi.spyOn(globalThis, 'fetch').mockImplementation((url, tuyChon = {}) => {
      if (String(url).includes('/han-muc')) return dapUng(HAN_MUC)
      if (String(url).includes('/auth/me') && tuyChon.method === 'PATCH') {
        if (loi) return dapUng({ detail: loi }, 400)
        return dapUng(traVe ?? {
          nguoi_dung: { ...NGUOI, ten_hien: 'Tên Mới' },
          da_doi_mat_khau: false, so_phien_khac_da_thu_hoi: 0,
        })
      }
      return dapUng({})
    })
  }

  it('đổi được tên hiển thị và báo lên App để header cập nhật', async () => {
    const f = nhaiFetch()
    const doiNguoiDung = vi.fn()
    const u = userEvent.setup()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} onDoiNguoiDung={doiNguoiDung} />)

    await u.click(await screen.findByRole('button', { name: 'Sửa' }))
    const o = screen.getByLabelText(/Tên hiển thị/)
    await u.clear(o)
    await u.type(o, 'Tên Mới')
    await u.click(screen.getByRole('button', { name: 'Lưu' }))

    const goi = f.mock.calls.find(([, t]) => t?.method === 'PATCH')
    expect(JSON.parse(goi[1].body)).toEqual({ ten_hien: 'Tên Mới' })
    // Không nối lại thì người dùng thấy "đã lưu" mà tên cũ còn nguyên trên header.
    await waitFor(() => expect(doiNguoiDung).toHaveBeenCalledWith(
      expect.objectContaining({ ten_hien: 'Tên Mới' })
    ))
    expect(await screen.findByText(/Đã lưu tên hiển thị/)).toBeInTheDocument()
  })

  it('đổi tên KHÔNG đòi mật khẩu', async () => {
    nhaiFetch()
    const u = userEvent.setup()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    await u.click(await screen.findByRole('button', { name: 'Sửa' }))
    // Đòi mật khẩu cho một thao tác vô hại là dạy người dùng gõ mật khẩu vào bất cứ ô nào.
    expect(screen.queryByLabelText(/Mật khẩu hiện tại/)).not.toBeInTheDocument()
  })

  it('phần đổi mật khẩu đóng sẵn, mở ra mới hiện ĐỦ BA ô', async () => {
    nhaiFetch()
    const u = userEvent.setup()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    expect(screen.queryByLabelText(/Mật khẩu hiện tại/)).not.toBeInTheDocument()

    await u.click(await screen.findByRole('button', { name: 'Đổi mật khẩu' }))
    expect(screen.getByLabelText(/Mật khẩu hiện tại/)).toBeInTheDocument()
    expect(screen.getByLabelText(/^Mật khẩu mới/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Nhập lại mật khẩu mới/)).toBeInTheDocument()
  })

  it('KHONG_gui_duoc_khi_hai_o_mat_khau_lech_nhau', async () => {
    const f = nhaiFetch()
    const u = userEvent.setup()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    await u.click(await screen.findByRole('button', { name: 'Đổi mật khẩu' }))

    await u.type(screen.getByLabelText(/Mật khẩu hiện tại/), 'mat-khau-cu-1')
    await u.type(screen.getByLabelText(/^Mật khẩu mới/), 'mat-khau-moi-1')
    await u.type(screen.getByLabelText(/Nhập lại mật khẩu mới/), 'mat-khau-moi-2')

    const nut = screen.getByRole('button', { name: 'Đổi mật khẩu' })
    expect(nut).toBeDisabled()
    await u.click(nut)
    // Khẳng định vào HÀNH VI: không có lượt PATCH nào. Chữ đỏ cạnh một nút bấm được là trang trí.
    expect(f.mock.calls.filter(([, t]) => t?.method === 'PATCH')).toHaveLength(0)
  })

  it('mật khẩu mới ngắn hơn 8 ký tự thì khoá nút NGAY, không chờ máy chủ', async () => {
    const f = nhaiFetch()
    const u = userEvent.setup()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    await u.click(await screen.findByRole('button', { name: 'Đổi mật khẩu' }))
    await u.type(screen.getByLabelText(/Mật khẩu hiện tại/), 'mat-khau-cu-1')
    await u.type(screen.getByLabelText(/^Mật khẩu mới/), 'abc')
    await u.type(screen.getByLabelText(/Nhập lại mật khẩu mới/), 'abc')

    expect(screen.getByRole('button', { name: 'Đổi mật khẩu' })).toBeDisabled()
    expect(f.mock.calls.filter(([, t]) => t?.method === 'PATCH')).toHaveLength(0)
  })

  it('nói TRƯỚC là các thiết bị khác sẽ bị đăng xuất', async () => {
    nhaiFetch()
    const u = userEvent.setup()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    await u.click(await screen.findByRole('button', { name: 'Đổi mật khẩu' }))
    // Báo sau khi đã đăng xuất điện thoại của người ta thì đã muộn.
    expect(screen.getByText(/thiết bị khác sẽ bị đăng xuất/i)).toBeInTheDocument()
  })

  it('đổi xong thì nói ra ĐÃ đăng xuất bao nhiêu thiết bị', async () => {
    nhaiFetch({ traVe: { nguoi_dung: NGUOI, da_doi_mat_khau: true, so_phien_khac_da_thu_hoi: 2 } })
    const u = userEvent.setup()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    await u.click(await screen.findByRole('button', { name: 'Đổi mật khẩu' }))
    await u.type(screen.getByLabelText(/Mật khẩu hiện tại/), 'mat-khau-cu-1')
    await u.type(screen.getByLabelText(/^Mật khẩu mới/), 'mat-khau-moi-1')
    await u.type(screen.getByLabelText(/Nhập lại mật khẩu mới/), 'mat-khau-moi-1')
    await u.click(screen.getByRole('button', { name: 'Đổi mật khẩu' }))

    // Không có con số này thì người dùng tưởng hệ thống lỗi khi điện thoại đòi đăng nhập lại.
    expect(await screen.findByText(/Đã đổi mật khẩu/)).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('hiện ĐÚNG câu của máy chủ, KHÔNG kèm mã trạng thái', async () => {
    nhaiFetch({ loi: 'Mật khẩu hiện tại không đúng.' })
    const u = userEvent.setup()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    await u.click(await screen.findByRole('button', { name: 'Đổi mật khẩu' }))
    await u.type(screen.getByLabelText(/Mật khẩu hiện tại/), 'sai-het-roi-1')
    await u.type(screen.getByLabelText(/^Mật khẩu mới/), 'mat-khau-moi-1')
    await u.type(screen.getByLabelText(/Nhập lại mật khẩu mới/), 'mat-khau-moi-1')
    await u.click(screen.getByRole('button', { name: 'Đổi mật khẩu' }))

    expect(await screen.findByText('Mật khẩu hiện tại không đúng.')).toBeInTheDocument()
    // Dán "400:" vào ô nhập mật khẩu là bắt người dùng đọc thứ dành cho lập trình viên.
    expect(screen.queryByText(/400:/)).not.toBeInTheDocument()
  })

  it('nói rõ email KHÔNG đổi được ở đây, thay vì im lặng không có ô', async () => {
    nhaiFetch()
    render(<ManTaiKhoan nguoiDung={NGUOI} onDong={() => {}} />)
    expect(await screen.findByText(/Email là tên đăng nhập nên không đổi được/)).toBeInTheDocument()
  })
})
