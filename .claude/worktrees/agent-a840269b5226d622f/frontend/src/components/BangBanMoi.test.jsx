/** Banner "có bản mới" cho tab chạy bundle cũ (REPORT_E21b §11.3).
 *
 * Cửa sổ vỡ: tab mở sẵn từ trước lúc deploy chạy frontend CŨ trên backend MỚI ⇒ lưu thành công
 * nhưng báo lỗi `/jobs/null`. Deploy frontend trước không đóng được cửa sổ này.
 */
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import BangBanMoi from './BangBanMoi.jsx'

const URL_BUNDLE = '/assets/index-CU999.js'

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('BangBanMoi', () => {
  it('không hiện gì khi vẫn là bản mới nhất', async () => {
    const kiem = vi.fn(async () => false)
    render(<BangBanMoi urlBundle={URL_BUNDLE} kiem={kiem} />)
    await waitFor(() => expect(kiem).toHaveBeenCalled())
    expect(screen.queryByText(/Có bản mới/i)).not.toBeInTheDocument()
  })

  it('hiện banner khi bundle đang chạy đã cũ', async () => {
    const kiem = vi.fn(async () => true)
    render(<BangBanMoi urlBundle={URL_BUNDLE} kiem={kiem} />)
    expect(await screen.findByText(/Có bản mới của giao diện/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Tải lại ngay/i })).toBeInTheDocument()
  })

  /** Người dùng phải hiểu việc mình vừa làm KHÔNG mất — đó là toàn bộ lý do banner tồn tại.
   *  Nếu câu chữ chỉ nói "có bản mới" thì họ vẫn không biết cái lỗi vừa thấy là thật hay giả. */
  it('nói rõ việc đã được lưu, để người dùng không bấm lại', async () => {
    render(<BangBanMoi urlBundle={URL_BUNDLE} kiem={vi.fn(async () => true)} />)
    const bao = await screen.findByRole('status')
    expect(bao).toHaveTextContent(/báo lỗi sai/i)
    expect(bao).toHaveTextContent(/đã.*được lưu/i)
  })

  it('KHÔNG tự tải lại trang — chỉ tải lại khi người dùng bấm', async () => {
    const reload = vi.fn()
    vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, reload })
    render(<BangBanMoi urlBundle={URL_BUNDLE} kiem={vi.fn(async () => true)} />)
    const nut = await screen.findByRole('button', { name: /Tải lại ngay/i })

    expect(reload).not.toHaveBeenCalled() // tự tải lại sẽ xoá chữ đang gõ dở (E21b)
    await userEvent.click(nut)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('không kiểm gì khi không biết bundle đang chạy', async () => {
    const kiem = vi.fn(async () => true)
    render(<BangBanMoi urlBundle={undefined} kiem={kiem} />)
    await new Promise((r) => setTimeout(r, 20))
    expect(kiem).not.toHaveBeenCalled()
    expect(screen.queryByText(/Có bản mới/i)).not.toBeInTheDocument()
  })

  /** Cảnh phổ biến nhất: tab bị bỏ đó nhiều giờ rồi mở lại. Chờ hết nhịp định kỳ mới báo là để
   *  họ kịp bấm Lưu và nhận thông báo lỗi giả trước khi biết. */
  it('kiểm lại ngay khi tab được xem lại', async () => {
    const kiem = vi.fn(async () => false)
    render(<BangBanMoi urlBundle={URL_BUNDLE} kiem={kiem} />)
    await waitFor(() => expect(kiem).toHaveBeenCalledTimes(1))

    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await waitFor(() => expect(kiem).toHaveBeenCalledTimes(2))
  })

  it('bỏ qua visibilitychange khi tab đang bị ẩn', async () => {
    const kiem = vi.fn(async () => false)
    render(<BangBanMoi urlBundle={URL_BUNDLE} kiem={kiem} />)
    await waitFor(() => expect(kiem).toHaveBeenCalledTimes(1))

    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await new Promise((r) => setTimeout(r, 20))
    expect(kiem).toHaveBeenCalledTimes(1)
  })

  it('dừng hỏi lại sau khi đã biết là cũ', async () => {
    vi.useFakeTimers()
    const kiem = vi.fn(async () => true)
    render(<BangBanMoi urlBundle={URL_BUNDLE} nhipMs={1000} kiem={kiem} />)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    const sauLuotDau = kiem.mock.calls.length

    await act(async () => { await vi.advanceTimersByTimeAsync(5000) }) // 5 nhịp nữa
    expect(kiem.mock.calls.length).toBe(sauLuotDau) // nhịp đã bị dọn, không hỏi thêm
  })

  it('dọn nhịp và listener khi unmount', async () => {
    vi.useFakeTimers()
    const kiem = vi.fn(async () => false)
    const { unmount } = render(<BangBanMoi urlBundle={URL_BUNDLE} nhipMs={1000} kiem={kiem} />)
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    const truoc = kiem.mock.calls.length

    unmount()
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(kiem.mock.calls.length).toBe(truoc)
  })
})
