/** Auth slice B — tài khoản thật, phiên đăng nhập.
 *
 * Slice A là MỘT khoá chung: ai cầm khoá là làm được mọi thứ với chapter của mọi người.
 * Slice B là tài khoản riêng + chapter có chủ. Giao diện phải: chắn trước khi vào app, không
 * nháy màn đăng nhập khi phiên còn tốt, và nói ĐÚNG lý do khi bị chặn.
 */
import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import * as api from '../../api.js'
import ManDangNhap from './ManDangNhap.jsx'
import BangChuaCoChu from './BangChuaCoChu.jsx'
import QuanTriNguoiDung from './QuanTriNguoiDung.jsx'

beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })

function dapUng(du_lieu, ok = true, status = 200) {
  return Promise.resolve({
    ok, status, statusText: '',
    json: () => Promise.resolve(du_lieu),
  })
}

describe('lưu mã phiên', () => {
  it('lưu rồi đọc lại được; chưa lưu thì trả chuỗi rỗng chứ không phải null', () => {
    expect(api.docMaPhien()).toBe('')
    api.luuMaPhien('ma-abc')
    expect(api.docMaPhien()).toBe('ma-abc')
    api.xoaMaPhien()
    expect(api.docMaPhien()).toBe('')
  })

  it('mọi lời gọi API tự mang mã phiên — không phải sửa từng chỗ gọi', async () => {
    api.luuMaPhien('ma-abc')
    const goi = vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng([]))
    await api.layDanhSachChapter()
    expect(goi.mock.calls[0][1].headers.Authorization).toBe('Bearer ma-abc')
  })

  it('chưa đăng nhập thì KHÔNG gửi header Authorization rỗng', async () => {
    const goi = vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng([]))
    await api.layDanhSachChapter()
    expect(goi.mock.calls[0][1].headers.Authorization).toBeUndefined()
  })
})

describe('nhận biết hết phiên', () => {
  it('401 dạng CHUỖI cũng nhận ra — đúng thứ App truyền vào', () => {
    // Cùng cái bẫy đã làm hỏng `laLoiThieuKhoa` ở slice A: App lưu lỗi bằng `setLoi(e.message)`
    // nên biến `loi` là CHUỖI, không phải Error.
    expect(api.laLoiChuaDangNhap('401: Chưa đăng nhập.')).toBe(true)
    expect(api.laLoiChuaDangNhap(new Error('401: Chưa đăng nhập.'))).toBe(true)
  })

  it('lỗi khác KHÔNG bị nhầm thành hết phiên', () => {
    for (const m of ['404: Không tìm thấy', '500: Lỗi máy chủ', '422: Sai dữ liệu']) {
      expect(api.laLoiChuaDangNhap(m)).toBe(false)
    }
    expect(api.laLoiChuaDangNhap(undefined)).toBe(false)
  })
})

describe('màn đăng nhập', () => {
  it('sai mật khẩu thì NÓI RA, không im lặng nuốt lỗi', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).includes('co-tai-khoan-chua')) return dapUng({ da_co: true })
      return dapUng({ detail: 'Email hoặc mật khẩu không đúng.' }, false, 401)
    })
    render(<ManDangNhap onXong={() => {}} />)
    await userEvent.type(await screen.findByLabelText('Email'), 'a@x.test')
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'sai-mat-khau')
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByText(/Email hoặc mật khẩu không đúng/)).toBeInTheDocument()
  })

  it('đăng nhập sai thì KHÔNG lưu mã phiên rác vào máy', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).includes('co-tai-khoan-chua')) return dapUng({ da_co: true })
      return dapUng({ detail: 'Email hoặc mật khẩu không đúng.' }, false, 401)
    })
    render(<ManDangNhap onXong={() => {}} />)
    await userEvent.type(await screen.findByLabelText('Email'), 'a@x.test')
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'sai')
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    await screen.findByText(/không đúng/)
    expect(api.docMaPhien()).toBe('')
  })

  it('đăng nhập được thì lưu mã phiên và báo lên cho App', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).includes('co-tai-khoan-chua')) return dapUng({ da_co: true })
      return dapUng({
        ma_phien: 'ma-that', het_han: '2026-12-01T00:00:00Z',
        nguoi_dung: { id: 'u1', email: 'a@x.test', ten_hien: 'A', la_quan_tri: false },
      })
    })
    const xong = vi.fn()
    render(<ManDangNhap onXong={xong} />)
    await userEvent.type(await screen.findByLabelText('Email'), 'a@x.test')
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'mat-khau-dung')
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    await waitFor(() => expect(xong).toHaveBeenCalledWith(
      expect.objectContaining({ email: 'a@x.test' })
    ))
    expect(api.docMaPhien()).toBe('ma-that')
  })

  it('hệ thống chưa có tài khoản nào thì tự mở sang màn TẠO, không bắt đoán', async () => {
    // Không có đường này thì chính chủ hệ thống cũng bị khoá ra ngoài ngay sau khi bật slice B.
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng({ da_co: false }))
    render(<ManDangNhap onXong={() => {}} />)
    expect(await screen.findByText('Chưa có tài khoản nào')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tạo tài khoản' })).toBeInTheDocument()
    expect(screen.getByLabelText('Khoá chung của hệ thống')).toBeInTheDocument()
  })

  it('đã có tài khoản thì KHÔNG hiện lời mời tạo tài khoản đầu tiên', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng({ da_co: true }))
    render(<ManDangNhap onXong={() => {}} />)
    await screen.findByLabelText('Email')
    expect(screen.queryByText('Chưa có tài khoản nào')).not.toBeInTheDocument()
  })

  it('tạo tài khoản xong thì đăng nhập luôn, không bắt gõ lại', async () => {
    const goi = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).includes('co-tai-khoan-chua')) return dapUng({ da_co: false })
      if (String(url).includes('register')) {
        return dapUng({ id: 'u1', email: 'a@x.test', ten_hien: 'A', la_quan_tri: true })
      }
      return dapUng({
        ma_phien: 'ma-moi', het_han: '2026-12-01T00:00:00Z',
        nguoi_dung: { id: 'u1', email: 'a@x.test', ten_hien: 'A', la_quan_tri: true },
      })
    })
    const xong = vi.fn()
    render(<ManDangNhap onXong={xong} />)
    await screen.findByText('Chưa có tài khoản nào')
    await userEvent.type(screen.getByLabelText('Email'), 'a@x.test')
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'mat-khau-du-dai')
    await userEvent.type(screen.getByLabelText('Khoá chung của hệ thống'), 'khoa-chung')
    await userEvent.click(screen.getByRole('button', { name: 'Tạo tài khoản' }))
    await waitFor(() => expect(xong).toHaveBeenCalled())
    const duong = goi.mock.calls.map((c) => String(c[0]))
    expect(duong.some((d) => d.includes('/auth/register'))).toBe(true)
    expect(duong.some((d) => d.includes('/auth/login'))).toBe(true)
  })

  it('đăng ký gửi khoá chung lên — thiếu nó thì máy chủ từ chối', async () => {
    const goi = vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      if (String(url).includes('co-tai-khoan-chua')) return dapUng({ da_co: false })
      return dapUng({ id: 'u1', email: 'a@x.test', ten_hien: 'A', la_quan_tri: true })
    })
    render(<ManDangNhap onXong={() => {}} />)
    await screen.findByText('Chưa có tài khoản nào')
    await userEvent.type(screen.getByLabelText('Email'), 'a@x.test')
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'mat-khau-du-dai')
    await userEvent.type(screen.getByLabelText('Khoá chung của hệ thống'), 'khoa-chung')
    await userEvent.click(screen.getByRole('button', { name: 'Tạo tài khoản' }))
    await waitFor(() => {
      const dangKy = goi.mock.calls.find((c) => String(c[0]).includes('/auth/register'))
      expect(dangKy[1].headers['X-API-Key']).toBe('khoa-chung')
    })
  })
})

describe('đăng xuất', () => {
  it('gọi máy chủ TRƯỚC rồi mới xoá mã — xoá trước thì phiên vẫn sống trên máy chủ', async () => {
    api.luuMaPhien('ma-abc')
    let maLucGoi = null
    vi.spyOn(globalThis, 'fetch').mockImplementation((url, opts) => {
      maLucGoi = opts?.headers?.Authorization
      return dapUng(null)
    })
    await api.dangXuat()
    expect(maLucGoi).toBe('Bearer ma-abc')
    expect(api.docMaPhien()).toBe('')
  })

  it('máy chủ không phản hồi thì VẪN xoá mã ở máy — không kẹt lại màn đã đăng nhập', async () => {
    api.luuMaPhien('ma-abc')
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.reject(new Error('mạng hỏng')))
    await expect(api.dangXuat()).rejects.toThrow()
    expect(api.docMaPhien()).toBe('')
  })
})

describe('chapter chưa có chủ', () => {
  it('có chủ rồi thì KHÔNG mời nhận nữa, mà cho đường NHẢ', () => {
    // Có `claim` mà không có đường ngược lại là bẫy một chiều: nhận nhầm một cái là chapter
    // khoá cứng vào tài khoản đó. Đã gặp thật trong lượt kiểm chứng B1 trên bản chạy thật.
    render(<BangChuaCoChu project={{ id: 'p1', chu_so_huu_id: 'u1' }} onNhanXong={() => {}} />)
    expect(screen.queryByRole('button', { name: 'Nhận chapter này' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Nhả về chưa có chủ/ })).toBeInTheDocument()
  })

  it('nhả phải HỎI LẠI trước — nó làm chapter hiện ra với mọi người', async () => {
    const hoi = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const goi = vi.spyOn(globalThis, 'fetch')
    render(<BangChuaCoChu project={{ id: 'p1', chu_so_huu_id: 'u1' }} onNhanXong={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Nhả về chưa có chủ/ }))
    expect(hoi).toHaveBeenCalled()
    expect(goi).not.toHaveBeenCalled()
  })

  it('đồng ý thì nhả thật, và báo lên cho App', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => dapUng({ id: 'p1', chu_so_huu_id: null })
    )
    const xong = vi.fn()
    render(<BangChuaCoChu project={{ id: 'p1', chu_so_huu_id: 'u1' }} onNhanXong={xong} />)
    await userEvent.click(screen.getByRole('button', { name: /Nhả về chưa có chủ/ }))
    await waitFor(() => expect(xong).toHaveBeenCalledWith(
      expect.objectContaining({ chu_so_huu_id: null })
    ))
  })

  it('chưa có chủ thì NÓI RA là mọi người đều mở được, không chỉ mời nhận suông', async () => {
    render(<BangChuaCoChu project={{ id: 'p1', chu_so_huu_id: null }} onNhanXong={() => {}} />)
    expect(screen.getByText('Chapter này chưa có chủ')).toBeInTheDocument()
    expect(screen.getByText(/mọi người đăng nhập đều/)).toBeInTheDocument()
  })

  it('nhận xong thì báo lên cho App để nhãn biến mất ngay, không phải tải lại trang', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => dapUng({ id: 'p1', chu_so_huu_id: 'u1', name: 'x' })
    )
    const xong = vi.fn()
    render(<BangChuaCoChu project={{ id: 'p1', chu_so_huu_id: null }} onNhanXong={xong} />)
    await userEvent.click(screen.getByRole('button', { name: 'Nhận chapter này' }))
    await waitFor(() => expect(xong).toHaveBeenCalledWith(
      expect.objectContaining({ chu_so_huu_id: 'u1' })
    ))
  })

  it('nhận hỏng thì HIỆN lý do, không im lặng', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => dapUng({ detail: 'Chapter này đã có chủ rồi.' }, false, 409)
    )
    render(<BangChuaCoChu project={{ id: 'p1', chu_so_huu_id: null }} onNhanXong={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: 'Nhận chapter này' }))
    expect(await screen.findByText('Chapter này đã có chủ rồi.')).toBeInTheDocument()
  })
})


describe('quản trị tài khoản', () => {
  const DS = [
    { id: 'u1', email: 'toi@x.test', ten_hien: 'Tôi', la_quan_tri: true, dang_hoat_dong: true },
    { id: 'u2', email: 'ban@x.test', ten_hien: 'Bạn', la_quan_tri: false, dang_hoat_dong: true },
  ]

  it('KHÔNG hiện nút khoá/xoá cho chính mình', async () => {
    // Máy chủ cũng chặn, nhưng hiện một cái nút chắc chắn báo lỗi là thiết kế tồi.
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(DS))
    render(<QuanTriNguoiDung toi={{ id: 'u1' }} />)
    const hang = (await screen.findByText('toi@x.test')).closest('tr')
    expect(hang.querySelector('button')).toBeNull()
    expect(hang).toHaveTextContent('(bạn)')
  })

  it('xoá phải HỎI LẠI, và nói rõ chapter KHÔNG bị xoá theo', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(DS))
    const hoi = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<QuanTriNguoiDung toi={{ id: 'u1' }} />)
    await screen.findByText('ban@x.test')
    await userEvent.click(screen.getByRole('button', { name: 'Xoá' }))
    expect(hoi.mock.calls[0][0]).toMatch(/KHÔNG bị xoá/)
  })

  it('nói rõ khoá khác xoá ở chỗ nào — hai việc dễ nhầm nhau', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => dapUng(DS))
    render(<QuanTriNguoiDung toi={{ id: 'u1' }} />)
    await screen.findByText('ban@x.test')
    expect(screen.getByText(/giữ nguyên chapter của họ/)).toBeInTheDocument()
    expect(screen.getByText(/chưa có chủ/)).toBeInTheDocument()
  })
})
