import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Button from './Button.jsx'
import Dropzone, { coChuoi, locFileHopLe } from './Dropzone.jsx'
import EmptyState from './EmptyState.jsx'
import { Input, Select } from './Field.jsx'
import ProgressStage from './ProgressStage.jsx'
import StatusBadge from './StatusBadge.jsx'

const anh = (ten = 'trang1.png', loai = 'image/png') =>
  new File(['x'], ten, { type: loai })

describe('Nút', () => {
  it('bị khoá thì phải NÓI RÕ vì sao, ngay cạnh nút', () => {
    render(<Button kieu="chinh" lyDoKhoa="Cần chọn ít nhất một ảnh PNG hoặc JPG">Tạo</Button>)
    expect(screen.getByRole('button', { name: 'Tạo' })).toBeDisabled()
    expect(screen.getByText('Cần chọn ít nhất một ảnh PNG hoặc JPG')).toBeInTheDocument()
  })

  it('lý do được nối vào nút qua aria-describedby, không chỉ nằm cạnh cho có', () => {
    render(<Button id="n" lyDoKhoa="Thiếu tên chapter">Tạo</Button>)
    const nut = screen.getByRole('button', { name: 'Tạo' })
    const id = nut.getAttribute('aria-describedby')
    expect(document.getElementById(id)).toHaveTextContent('Thiếu tên chapter')
  })

  it('đang chạy thì không bấm được nữa (chặn bấm hai lần)', async () => {
    const goi = vi.fn()
    render(<Button dangChay onClick={goi}>Đang tải…</Button>)
    await userEvent.click(screen.getByRole('button'))
    expect(goi).not.toHaveBeenCalled()
  })
})

describe('Ô nhập', () => {
  it('nhãn được LIÊN KẾT thật với ô, bấm nhãn là focus vào ô', async () => {
    render(<Input nhan="Tên chapter" batBuoc />)
    const o = screen.getByLabelText(/Tên chapter/)
    await userEvent.click(screen.getByText(/Tên chapter/))
    expect(o).toHaveFocus()
  })

  it('mô tả và lỗi được nối bằng aria-describedby', () => {
    render(<Select nhan="Mục đích" loi="Chưa chọn mục đích"><option>a</option></Select>)
    const o = screen.getByLabelText(/Mục đích/)
    expect(o).toHaveAttribute('aria-invalid', 'true')
    expect(document.getElementById(o.getAttribute('aria-describedby')))
      .toHaveTextContent('Chưa chọn mục đích')
  })
})

describe('Huy hiệu trạng thái', () => {
  it('luôn có CHỮ, không chỉ có màu', () => {
    render(<StatusBadge loai="trang" trangThai="detection_failed" />)
    expect(screen.getByText('Không nhận diện được khung chữ')).toBeInTheDocument()
  })

  it('trạng thái lạ không được hiện như thành công', () => {
    render(<StatusBadge loai="trang" trangThai="perfect" />)
    expect(screen.getByText('Trạng thái chưa được hỗ trợ')).toBeInTheDocument()
  })
})

describe('Vùng thả file', () => {
  it('mở hộp chọn tệp bằng Enter và bằng Space, không chỉ bằng chuột', async () => {
    render(<Dropzone files={[]} onDoi={() => {}} />)
    const vung = screen.getByRole('button', { name: /Chọn ảnh trang truyện/ })
    const bam = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(() => {})
    vung.focus()
    await userEvent.keyboard('{Enter}')
    await userEvent.keyboard(' ')
    expect(bam).toHaveBeenCalledTimes(2)
    bam.mockRestore()
  })

  it('vẫn giữ input file THẬT (ẩn) để trình duyệt và trình đọc màn hình dùng được', () => {
    const { container } = render(<Dropzone files={[]} onDoi={() => {}} />)
    const o = container.querySelector('input[type="file"]')
    expect(o).toBeTruthy()
    expect(o).toHaveAttribute('multiple')
    expect(o.accept).toContain('image/png')
  })

  it('hiện danh sách theo đúng thứ tự trang và bỏ được từng trang', async () => {
    const files = [anh('a.png'), anh('b.png'), anh('c.png')]
    const onDoi = vi.fn()
    render(<Dropzone files={files} onDoi={onDoi} />)

    const muc = screen.getAllByRole('listitem')
    expect(within(muc[0]).getByText('a.png')).toBeInTheDocument()
    expect(within(muc[2]).getByText('c.png')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Bỏ trang 2: b.png/ }))
    expect(onDoi).toHaveBeenCalledWith([files[0], files[2]])
  })

  it('lọc đúng tệp không phải ảnh, không tự bịa giới hạn dung lượng', () => {
    const { nhan, loai } = locFileHopLe([anh('a.png'), anh('t.pdf', 'application/pdf')])
    expect(nhan).toHaveLength(1)
    expect(loai[0].name).toBe('t.pdf')
  })

  it('hiện dung lượng dễ đọc', () => {
    expect(coChuoi(900)).toBe('900 B')
    expect(coChuoi(2048)).toBe('2 KB')
    expect(coChuoi(3 * 1024 * 1024)).toBe('3.0 MB')
  })
})

describe('Dòng thời gian và chỗ trống', () => {
  it('vẽ đủ các bước với tình trạng thật', () => {
    render(<ProgressStage buoc={[
      { ma: 'a', nhan: 'Đã tải lên', tinh_trang: 'xong', mo_ta: '3/3 trang' },
      { ma: 'b', nhan: 'Nhận diện khung chữ', tinh_trang: 'dang_chay', mo_ta: '1/3 trang' },
      { ma: 'c', nhan: 'Đọc chữ gốc', tinh_trang: 'chua', mo_ta: '0/3 trang' },
    ]} />)
    expect(screen.getByText('Đã tải lên')).toBeInTheDocument()
    expect(screen.getByText('1/3 trang')).toBeInTheDocument()
  })

  it('chỗ trống có nút hành động dùng được', async () => {
    const goi = vi.fn()
    render(
      <EmptyState tieuDe="Chưa có chapter nào" moTa="Tạo chapter đầu tiên">
        <Button kieu="chinh" onClick={goi}>Tạo chapter đầu tiên</Button>
      </EmptyState>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Tạo chapter đầu tiên' }))
    expect(goi).toHaveBeenCalled()
  })
})
