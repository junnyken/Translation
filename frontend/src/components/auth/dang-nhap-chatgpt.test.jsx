import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../api.js'
import { datLaiCodex } from '../../lib/dung-codex.js'
import BatchPanel from '../BatchPanel.jsx'
import DangNhapChatGPT from './DangNhapChatGPT.jsx'

/** E73 — đăng nhập ChatGPT (device-code). Hình dạng phản hồi lấy từ hợp đồng backend. */

const healthz = (bat, daDangNhap = false) => ({ ok: true, codex: { bat, da_dang_nhap: daDangNhap } })

beforeEach(() => { datLaiCodex() })
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

function loiHttp(ma, chiTiet) {
  const e = new Error(`${ma}: ${chiTiet}`)
  e.ma = ma; e.cauNguoiDoc = chiTiet
  return e
}

describe('DangNhapChatGPT', () => {
  it('KHÔNG render khi codex.bat = false và không gọi /codex', async () => {
    vi.spyOn(api, 'layHealthz').mockResolvedValue(healthz(false))
    const tt = vi.spyOn(api, 'layTrangThaiCodex')
    const { container } = render(<DangNhapChatGPT />)
    await act(async () => {})
    expect(container).toBeEmptyDOMElement()
    expect(tt).not.toHaveBeenCalled()
  })

  it('đăng nhập: hiện mã, hỏi mỗi 5 giây, rồi chuyển sang đã đăng nhập', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    vi.spyOn(api, 'layHealthz').mockResolvedValue(healthz(true))
    const tt = vi.spyOn(api, 'layTrangThaiCodex')
      .mockResolvedValueOnce({ da_dang_nhap: false, email: null, goi: null, dang_cho_xac_nhan: false })
      .mockResolvedValue({ da_dang_nhap: true, email: 'a@x.test', goi: 'plus', dang_cho_xac_nhan: false })
    vi.spyOn(api, 'batDauDangNhapCodex')
      .mockResolvedValue({ ma: 'ABCD-1234', link: 'https://auth.openai.com/codex/device', het_han_giay: 900 })
    const hoi = vi.spyOn(api, 'hoiDangNhapCodex')
      .mockResolvedValueOnce({ trang_thai: 'cho_xac_nhan' })
      .mockResolvedValueOnce({ trang_thai: 'da_dang_nhap' })

    render(<DangNhapChatGPT />)
    await user.click(await screen.findByRole('button', { name: 'Đăng nhập ChatGPT' }))
    expect(await screen.findByText('ABCD-1234')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /Mở trang OpenAI/ })
    expect(link).toHaveAttribute('href', 'https://auth.openai.com/codex/device')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByText(/Mã hết hạn sau 15:00/)).toBeInTheDocument()

    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(hoi).toHaveBeenCalledTimes(1)
    expect(screen.getByText('ABCD-1234')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(hoi).toHaveBeenCalledTimes(2)

    expect(await screen.findByText('a@x.test', { exact: false })).toBeInTheDocument()
    expect(screen.getByText(/plus/)).toBeInTheDocument()
    expect(screen.queryByText('ABCD-1234')).not.toBeInTheDocument()
    // Đã xong thì không hỏi nữa.
    await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
    expect(hoi).toHaveBeenCalledTimes(2)
    expect(tt).toHaveBeenCalled()
  })

  it('het_han: báo và cho bấm lại, dừng hỏi', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    vi.spyOn(api, 'layHealthz').mockResolvedValue(healthz(true))
    vi.spyOn(api, 'layTrangThaiCodex').mockResolvedValue({ da_dang_nhap: false })
    vi.spyOn(api, 'batDauDangNhapCodex').mockResolvedValue({ ma: 'ZZZ', link: 'https://x.test', het_han_giay: 60 })
    const hoi = vi.spyOn(api, 'hoiDangNhapCodex').mockResolvedValue({ trang_thai: 'het_han' })
    render(<DangNhapChatGPT />)
    await user.click(await screen.findByRole('button', { name: 'Đăng nhập ChatGPT' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(await screen.findByText(/Mã đã hết hạn/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Đăng nhập ChatGPT' })).toBeEnabled()
    await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
    expect(hoi).toHaveBeenCalledTimes(1)
  })

  it('đăng xuất: hỏi xác nhận rồi gọi API', async () => {
    vi.spyOn(api, 'layHealthz').mockResolvedValue(healthz(true, true))
    vi.spyOn(api, 'layTrangThaiCodex')
      .mockResolvedValueOnce({ da_dang_nhap: true, email: 'a@x.test', goi: 'pro' })
      .mockResolvedValue({ da_dang_nhap: false })
    const xuat = vi.spyOn(api, 'dangXuatCodex').mockResolvedValue()
    const conf = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    render(<DangNhapChatGPT />)
    const nut = await screen.findByRole('button', { name: 'Đăng xuất' })
    await userEvent.click(nut)
    expect(xuat).not.toHaveBeenCalled()
    await userEvent.click(nut)
    expect(conf).toHaveBeenCalledTimes(2)
    expect(xuat).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('button', { name: 'Đăng nhập ChatGPT' })).toBeInTheDocument()
  })

  it('lỗi 502 khi hỏi: hiện detail và dừng hỏi', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    vi.spyOn(api, 'layHealthz').mockResolvedValue(healthz(true))
    vi.spyOn(api, 'layTrangThaiCodex').mockResolvedValue({ da_dang_nhap: false })
    vi.spyOn(api, 'batDauDangNhapCodex').mockResolvedValue({ ma: 'ZZZ', link: 'https://x.test', het_han_giay: 60 })
    const hoi = vi.spyOn(api, 'hoiDangNhapCodex').mockRejectedValue(loiHttp(502, 'Không nối được OpenAI'))
    render(<DangNhapChatGPT />)
    await user.click(await screen.findByRole('button', { name: 'Đăng nhập ChatGPT' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(await screen.findByText('Không nối được OpenAI')).toBeInTheDocument()
    await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
    expect(hoi).toHaveBeenCalledTimes(1)
  })

  it('gỡ component thì dừng hỏi', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    vi.spyOn(api, 'layHealthz').mockResolvedValue(healthz(true))
    vi.spyOn(api, 'layTrangThaiCodex').mockResolvedValue({ da_dang_nhap: false })
    vi.spyOn(api, 'batDauDangNhapCodex').mockResolvedValue({ ma: 'ZZZ', link: 'https://x.test', het_han_giay: 60 })
    const hoi = vi.spyOn(api, 'hoiDangNhapCodex').mockResolvedValue({ trang_thai: 'cho_xac_nhan' })
    const { unmount } = render(<DangNhapChatGPT />)
    await user.click(await screen.findByRole('button', { name: 'Đăng nhập ChatGPT' }))
    unmount()
    await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
    expect(hoi).not.toHaveBeenCalled()
  })
})

describe('bộ chọn cách dịch có chatgpt_codex', () => {
  function dung() {
    vi.spyOn(api, 'layCauHinhMe').mockResolvedValue({
      llm_configured: false, llm_project_rpm: 0, batch_max_concurrent_pages: 2, batch_max_retries: 3,
    })
    vi.spyOn(api, 'layDanhSachMe').mockResolvedValue({ runs: [] })
    vi.spyOn(api, 'layMucCuaMe').mockResolvedValue({ items: [] })
  }

  it('ẩn khi bat=false', async () => {
    dung()
    vi.spyOn(api, 'layHealthz').mockResolvedValue(healthz(false))
    render(<BatchPanel projectId="p-1" soTrang={3} />)
    await act(async () => {})
    expect(screen.queryByRole('option', { name: /ChatGPT/ })).not.toBeInTheDocument()
  })

  it('hiện nhưng khoá khi bat=true mà chưa đăng nhập; mở khi đã đăng nhập', async () => {
    dung()
    const h = vi.spyOn(api, 'layHealthz').mockResolvedValue(healthz(true, false))
    const { unmount } = render(<BatchPanel projectId="p-1" soTrang={3} />)
    const opt = await screen.findByRole('option', { name: /ChatGPT \(tài khoản của bạn\)/ })
    expect(opt).toBeDisabled()
    expect(opt).toHaveValue('chatgpt_codex')
    unmount()
    datLaiCodex()
    h.mockResolvedValue(healthz(true, true))
    render(<BatchPanel projectId="p-1" soTrang={3} />)
    expect(await screen.findByRole('option', { name: /ChatGPT/ })).toBeEnabled()
  })
})
