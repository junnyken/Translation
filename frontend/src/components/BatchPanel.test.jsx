/** E23 — ô "trang xong" của mẻ gây hiểu sai khi chạy quy mô thật.
 *
 * Đo thật (lượt 24 trang, 2026-09-10): hàng đợi FIFO nên pipeline chạy gần như theo từng BƯỚC qua
 * tất cả các trang. Ở phút 43, **22/24 trang đã qua bước đọc chữ** mà ô này vẫn hiện `0/24` và
 * thanh tiến độ đứng 0% — nhìn y như máy đã treo.
 *
 * Con số 0 KHÔNG sai (thật sự chưa trang nào qua hết mọi bước), nên cách sửa KHÔNG phải bịa ra một
 * phần trăm khác — mà là nói rõ nó đếm gì, và chỉ sang chỗ có tiến độ theo bước.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api.js'
import BatchPanel from './BatchPanel.jsx'

const me = (ghiDe = {}) => ({
  id: 'me-1',
  project_id: 'p-1',
  status: 'running',
  total_pages: 24,
  completed_pages: 0,
  failed_pages: 0,
  blocked_pages: 0,
  started_at: new Date().toISOString(),
  finished_at: null,
  error_summary: null,
  ...ghiDe,
})

beforeEach(() => {
  vi.restoreAllMocks()
  // Hình dạng lấy từ chính `api.js`, không đoán: batch-config trả cấu hình phẳng,
  // `layDanhSachMe` trả `{ runs }` (KHÔNG phải `{ items }` — mock sai chỗ này làm component
  // đổ ở `runs.length`), `layMucCuaMe` trả `{ items }`.
  vi.spyOn(api, 'layCauHinhMe').mockResolvedValue({
    llm_configured: false, llm_project_rpm: 0,
    batch_max_concurrent_pages: 2, batch_max_retries: 3,
  })
  vi.spyOn(api, 'layMucCuaMe').mockResolvedValue({ items: [] })
})

const dungMe = (m) => {
  vi.spyOn(api, 'layDanhSachMe').mockResolvedValue({ runs: [m] })
  vi.spyOn(api, 'layMe').mockResolvedValue(m)
}

describe('BatchPanel — ô đếm trang xong (E23)', () => {
  it('nói rõ con số đếm trang đã qua HẾT các bước', async () => {
    dungMe(me())
    render(<BatchPanel projectId="p-1" soTrang={24} />)
    expect(await screen.findByText(/trang xong/i)).toHaveTextContent(/hết mọi bước/i)
  })

  it('đang chạy mà chưa trang nào xong thì giải thích vì sao ô đứng ở 0', async () => {
    dungMe(me({ completed_pages: 0, status: 'running' }))
    render(<BatchPanel projectId="p-1" soTrang={24} />)
    const chu = await screen.findByText(/đứng ở 0 gần hết lượt chạy/i)
    expect(chu).toHaveTextContent(/Tiến trình chapter/i)
  })

  it('KHÔNG giải thích nữa khi đã có trang xong — hết gây hiểu sai thì hết cần nói', async () => {
    dungMe(me({ completed_pages: 3 }))
    render(<BatchPanel projectId="p-1" soTrang={24} />)
    await waitFor(() => expect(screen.getByText(/trang xong/i)).toBeInTheDocument())
    expect(screen.queryByText(/đứng ở 0 gần hết lượt chạy/i)).not.toBeInTheDocument()
  })

  it('KHÔNG giải thích khi mẻ đã kết thúc — 0/24 lúc đó là tin thật, không phải hiểu sai', async () => {
    dungMe(me({ completed_pages: 0, status: 'failed', finished_at: new Date().toISOString() }))
    render(<BatchPanel projectId="p-1" soTrang={24} />)
    await waitFor(() => expect(screen.getByText(/trang xong/i)).toBeInTheDocument())
    expect(screen.queryByText(/đứng ở 0 gần hết lượt chạy/i)).not.toBeInTheDocument()
  })

  /** Chapter một trang thì "0/1 rồi 1/1" không gây hiểu sai gì — thêm chú thích chỉ là nhiễu. */
  it('KHÔNG giải thích với chapter một trang', async () => {
    dungMe(me({ total_pages: 1, completed_pages: 0 }))
    render(<BatchPanel projectId="p-1" soTrang={1} />)
    await waitFor(() => expect(screen.getByText(/trang xong/i)).toBeInTheDocument())
    expect(screen.queryByText(/đứng ở 0 gần hết lượt chạy/i)).not.toBeInTheDocument()
  })
})
