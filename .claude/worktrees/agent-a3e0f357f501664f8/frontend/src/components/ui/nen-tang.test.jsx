/** ĐỢT 1 redesign — nền tảng dùng chung: Dialog, nút đổi theme, Skeleton, Icon. */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Dialog from './Dialog.jsx'
import DoiTheme from './DoiTheme.jsx'
import Icon, { TEN_ICON } from './Icon.jsx'
import Skeleton from './Skeleton.jsx'

afterEach(() => {
  document.documentElement.removeAttribute('data-theme')
  window.localStorage.clear()
  vi.restoreAllMocks()
})

function Mau() {
  const [mo, setMo] = useState(false)
  return (
    <>
      <button onClick={() => setMo(true)}>Mở hộp</button>
      {mo && (
        <Dialog tieuDe="Hộp thử" onDong={() => setMo(false)}>
          <input aria-label="o-1" />
          <button>Giữa</button>
          <button>Cuối</button>
        </Dialog>
      )}
    </>
  )
}

describe('Dialog dùng chung', () => {
  it('có tên, focus vào hộp, Esc đóng và TRẢ focus về nút đã mở', async () => {
    const u = userEvent.setup()
    render(<Mau />)
    const nut = screen.getByRole('button', { name: 'Mở hộp' })
    await u.click(nut)
    const hop = screen.getByRole('dialog', { name: 'Hộp thử' })
    expect(hop).toHaveFocus()
    await u.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(nut).toHaveFocus()
  })

  it('Tab ở phần tử cuối quay về đầu, Shift+Tab ở đầu nhảy xuống cuối — focus không rời hộp', async () => {
    const u = userEvent.setup()
    render(<Mau />)
    await u.click(screen.getByRole('button', { name: 'Mở hộp' }))
    const dau = screen.getByLabelText('o-1')
    const cuoi = screen.getByRole('button', { name: 'Cuối' })
    cuoi.focus()
    await u.tab()
    expect(dau).toHaveFocus()
    await u.tab({ shift: true })
    expect(cuoi).toHaveFocus()
  })
})

describe('Nút đổi theme', () => {
  it('mặc định THEO MÁY: không đặt data-theme', () => {
    render(<DoiTheme />)
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
    expect(screen.getByRole('button', { name: 'Giao diện theo máy' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('chọn Tối ⇒ data-theme=dark và nhớ vào localStorage; chọn lại Theo máy ⇒ gỡ', async () => {
    const u = userEvent.setup()
    render(<DoiTheme />)
    await u.click(screen.getByRole('button', { name: 'Giao diện tối' }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(window.localStorage.getItem('translation.theme')).toBe('dark')
    await u.click(screen.getByRole('button', { name: 'Giao diện theo máy' }))
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
    expect(window.localStorage.getItem('translation.theme')).toBeNull()
  })

  it('đọc lại lựa chọn đã lưu khi mở', () => {
    window.localStorage.setItem('translation.theme', 'light')
    render(<DoiTheme />)
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('localStorage ném lỗi (bị chặn) thì KHÔNG sập, vẫn đổi được trong phiên', async () => {
    const u = userEvent.setup()
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('chặn') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('chặn') })
    render(<DoiTheme />)
    await u.click(screen.getByRole('button', { name: 'Giao diện tối' }))
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})

describe('Skeleton', () => {
  it('có chữ cho trình đọc màn hình, phần hình là aria-hidden', () => {
    render(<Skeleton nhan="Đang tải thử…" />)
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải thử…')
    expect(document.querySelectorAll('.skeleton-dong[aria-hidden="true"]').length).toBe(3)
  })
})

describe('Icon', () => {
  it('tên không có ⇒ không vẽ gì; mọi tên có sẵn đều ra <svg aria-hidden>', () => {
    const { container, rerender } = render(<Icon ten="khong-co" />)
    expect(container.querySelector('svg')).toBeNull()
    for (const ten of TEN_ICON) {
      rerender(<Icon ten={ten} co={20} />)
      const svg = container.querySelector('svg')
      expect(svg, ten).not.toBeNull()
      expect(svg.getAttribute('aria-hidden')).toBe('true')
      expect(svg.getAttribute('stroke-width')).toBe('2')
    }
  })

  it('có đủ icon canvas và theme mà màn mới cần', () => {
    for (const ten of ['hand', 'pointer', 'type', 'brush', 'eraser', 'pipette', 'eye', 'eye-off', 'sun', 'moon', 'monitor']) {
      expect(TEN_ICON).toContain(ten)
    }
  })
})
