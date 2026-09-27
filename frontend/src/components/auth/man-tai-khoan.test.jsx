import { render, screen } from '@testing-library/react'
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
