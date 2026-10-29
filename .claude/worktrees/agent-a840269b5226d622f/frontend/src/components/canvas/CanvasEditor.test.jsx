/** E76 — màn "Sửa tay kiểu canvas". Chạy trong jsdom nên không có canvas/WebGPU thật:
 *  `getContext('2d')` được thay bằng bản giả ghi lại lệnh vẽ, ảnh được thay bằng `tai-anh` giả.
 */
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../api.js'
import CanvasEditor from './CanvasEditor.jsx'

vi.mock('./tai-anh.js', () => ({
  taiLop: vi.fn(async (url) => (url.includes('clean-image')
    ? null // trang chưa xoá chữ lần nào: 404 ⇒ lớp trống
    : { source: { width: 1000, height: 1400 }, w: 1000, h: 1400 })),
}))

const trang = () => ({
  page: { id: 'p1', project_id: 'c1', he_so_ve: 1, order: 2, status: 'typeset_done' },
  preview_url: '/api/v1/pages/p1/typeset-preview',
  font_families: ['Bangers', 'Roboto'], min_font_size: 8, max_font_size: 40,
  regions: [{
    id: 'r1', reading_order: 1, bbox: { x: 100, y: 200, w: 300, h: 150 },
    raw_text: 'あの暁山です', translated_text: 'Đó là Akiyama.',
    font_family: 'Bangers', font_size: 24, fit_status: 'fit_ok',
    translation_status: 'ok', typeset_edited_by_user: false,
    text_color: '#1a1626', stroke_color: null, stroke_width: null, xep_theo_hinh: false,
  }],
})
const chapter = () => ({
  id: 'c1', name: 'Cuộc gặp trên sân thượng',
  pages: [{ id: 'p0', order: 1, status: 'typeset_done' }, { id: 'p1', order: 2, status: 'typeset_done' }],
})

let ctxGia
beforeEach(() => {
  ctxGia = new Proxy({}, {
    get(t, ten) {
      if (ten in t) return t[ten]
      if (ten === 'getImageData') return (x, y, w, h) => ({ data: new Uint8ClampedArray(w * h * 4) })
      if (ten === 'createImageData') return (w, h) => ({ data: new Uint8ClampedArray(w * h * 4) })
      t[ten] = vi.fn()
      return t[ten]
    },
    set(t, ten, v) { t[ten] = v; return true },
  })
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => ctxGia)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (cb) {
    cb(new Blob(['png'], { type: 'image/png' }))
  })
  // Khung vẽ rộng 800×600 (jsdom đo ra 0).
  const goc = Element.prototype.getBoundingClientRect
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function () {
    return this.classList?.contains('cv-stage')
      ? { left: 0, top: 0, width: 800, height: 600, right: 800, bottom: 600, x: 0, y: 0 }
      : goc.call(this)
  })
  vi.spyOn(api, 'layChiTietTrang').mockImplementation(async () => trang())
  vi.spyOn(api, 'layProject').mockResolvedValue(chapter())
  vi.spyOn(api, 'suaVung').mockResolvedValue({ refit_job_id: 'j1' })
  vi.spyOn(api, 'dichLaiVung').mockResolvedValue({ job_id: 'j3' })
  vi.spyOn(api, 'choJobXong').mockResolvedValue({ status: 'done' })
  vi.spyOn(api, 'xoaVungTo').mockResolvedValue({ page_id: 'p1', status: 'inpainted', job_id: 'j2' })
})
afterEach(() => {
  vi.restoreAllMocks()
  delete navigator.gpu
})

/** Chờ màn sẵn sàng: bộ vẽ đã dựng, ảnh đã nạp, đã có khung chữ. */
async function moMan() {
  render(<CanvasEditor pageId="p1" projectId="" />)
  const khung = await screen.findByLabelText('Khung chữ 1')
  await screen.findByRole('button', { name: 'Về 100%' })
  await waitFor(() => expect(screen.getByRole('button', { name: 'Phóng to' })).toBeEnabled())
  return { khung, stage: screen.getByTestId('cv-stage') }
}

describe('bộ vẽ', () => {
  it('không có navigator.gpu ⇒ lùi về 2D và hiện banner như mockup canvas-loi', async () => {
    expect(navigator.gpu).toBeUndefined()
    await moMan()
    expect(await screen.findByText(
      'Máy này không hỗ trợ WebGPU — đang dùng chế độ thường (chậm hơn khi trang lớn).',
    )).toBeInTheDocument()
    // Và vẽ thật bằng ngữ cảnh 2D: ảnh "Chữ dịch" được vẽ, ảnh gốc (mặc định ẩn) thì không.
    await waitFor(() => expect(ctxGia.drawImage).toHaveBeenCalled())
  })

  it('có navigator.gpu nhưng không có adapter ⇒ cũng lùi về 2D', async () => {
    Object.defineProperty(navigator, 'gpu', {
      configurable: true, value: { requestAdapter: async () => null },
    })
    await moMan()
    expect(await screen.findByText(/Máy này không hỗ trợ WebGPU/)).toBeInTheDocument()
  })

  it('"Dùng chế độ thường" tắt banner', async () => {
    await moMan()
    await userEvent.click(await screen.findByRole('button', { name: 'Dùng chế độ thường' }))
    expect(screen.queryByText(/Máy này không hỗ trợ WebGPU/)).not.toBeInTheDocument()
  })
})

describe('khung chữ', () => {
  it('kéo khung ⇒ suaVung với toạ độ ẢNH GỐC đúng sau khi đổi zoom, rồi chờ job', async () => {
    const { khung, stage } = await moMan()
    await userEvent.click(screen.getByRole('button', { name: 'Về 100%' }))   // zoom 1
    await userEvent.click(screen.getByRole('button', { name: 'Phóng to' }))  // zoom 1,25
    expect(screen.getByRole('button', { name: 'Về 100%' })).toHaveTextContent('125%')

    fireEvent.pointerDown(khung, { clientX: 300, clientY: 300, pointerId: 1, button: 0 })
    fireEvent.pointerMove(stage, { clientX: 350, clientY: 325, pointerId: 1 })   // dời 50, 25 trên màn
    fireEvent.pointerUp(stage, { clientX: 350, clientY: 325, pointerId: 1 })

    // 50/1,25 = 40 và 25/1,25 = 20 pixel ảnh gốc.
    await waitFor(() => expect(api.suaVung).toHaveBeenCalledWith(
      'r1', { bbox: { x: 140, y: 220, w: 300, h: 150 } },
    ))
    await waitFor(() => expect(api.choJobXong).toHaveBeenCalledWith('j1', expect.anything()))
  })

  it('kéo nút góc dưới-phải ⇒ đổi cỡ theo pixel ảnh gốc', async () => {
    const { stage } = await moMan()
    await userEvent.click(screen.getByRole('button', { name: 'Về 100%' }))
    await userEvent.click(screen.getByRole('button', { name: 'Phóng to' }))
    const goc = screen.getByLabelText('Kéo góc dưới-phải để đổi cỡ')
    fireEvent.pointerDown(goc, { clientX: 500, clientY: 500, pointerId: 1, button: 0 })
    fireEvent.pointerMove(stage, { clientX: 525, clientY: 550, pointerId: 1 })
    fireEvent.pointerUp(stage, { clientX: 525, clientY: 550, pointerId: 1 })
    await waitFor(() => expect(api.suaVung).toHaveBeenCalledWith(
      'r1', { bbox: { x: 100, y: 200, w: 320, h: 190 } },
    ))
  })

  it('bấm rồi thả không kéo ⇒ KHÔNG gọi suaVung', async () => {
    const { khung, stage } = await moMan()
    fireEvent.pointerDown(khung, { clientX: 300, clientY: 300, pointerId: 1, button: 0 })
    fireEvent.pointerUp(stage, { clientX: 300, clientY: 300, pointerId: 1 })
    expect(api.suaVung).not.toHaveBeenCalled()
  })

  it('hoàn tác gửi lại khung cũ', async () => {
    const { khung, stage } = await moMan()
    await userEvent.click(screen.getByRole('button', { name: 'Về 100%' }))
    fireEvent.pointerDown(khung, { clientX: 300, clientY: 300, pointerId: 1, button: 0 })
    fireEvent.pointerMove(stage, { clientX: 310, clientY: 330, pointerId: 1 })
    fireEvent.pointerUp(stage, { clientX: 310, clientY: 330, pointerId: 1 })
    await waitFor(() => expect(api.suaVung).toHaveBeenCalledTimes(1))
    const hoanTac = screen.getByRole('button', { name: 'Hoàn tác' })
    await waitFor(() => expect(hoanTac).toBeEnabled())
    await userEvent.click(hoanTac)
    await waitFor(() => expect(api.suaVung).toHaveBeenLastCalledWith(
      'r1', { bbox: { x: 100, y: 200, w: 300, h: 150 } },
    ))
  })

  it('công cụ Thêm chữ bị vô hiệu kèm lý do', async () => {
    await moMan()
    const t = screen.getByRole('button', { name: 'Thêm chữ, phím T' })
    expect(t).toBeDisabled()
    expect(t).toHaveAttribute('title', expect.stringContaining('chưa hỗ trợ'))
  })
})

describe('bảng Thuộc tính', () => {
  it('sửa bản dịch rồi Lưu ⇒ suaVung đúng trường + choJobXong + tải lại chi tiết', async () => {
    await moMan()
    const o = screen.getByLabelText('Bản dịch')
    await userEvent.clear(o)
    await userEvent.type(o, 'Là Akiyama đó.')
    const soLanTai = api.layChiTietTrang.mock.calls.length
    await userEvent.click(screen.getByRole('button', { name: 'Lưu thay đổi' }))
    await waitFor(() => expect(api.suaVung).toHaveBeenCalledWith('r1', { translated_text: 'Là Akiyama đó.' }))
    await waitFor(() => expect(api.choJobXong).toHaveBeenCalledWith('j1', expect.anything()))
    await waitFor(() => expect(api.layChiTietTrang.mock.calls.length).toBeGreaterThan(soLanTai))
  })

  it('"Dịch lại vùng này" gọi dichLaiVung và chờ job_id của nó', async () => {
    await moMan()
    await userEvent.click(screen.getByRole('button', { name: 'Dịch lại vùng này' }))
    await waitFor(() => expect(api.dichLaiVung).toHaveBeenCalledWith('r1'))
    await waitFor(() => expect(api.choJobXong).toHaveBeenCalledWith('j3', expect.anything()))
  })

  it('lỗi từ máy chủ hiện ra đọc được', async () => {
    api.suaVung.mockRejectedValue(Object.assign(new Error('500: x'), { cauNguoiDoc: 'Máy chủ đang bận' }))
    await moMan()
    await userEvent.selectOptions(screen.getByLabelText('Font'), 'Roboto')
    expect(await screen.findByRole('alert')).toHaveTextContent('Máy chủ đang bận')
  })

  it('màu chữ lấy từ vùng; màu viền chưa đo ghi "mặc định"; không có ô sửa màu', async () => {
    await moMan()
    expect(screen.getByText('#1a1626')).toBeInTheDocument()
    expect(screen.getAllByText('mặc định').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/đo từ chữ gốc/).length).toBeGreaterThan(0)
  })

  it.each([
    ['overflow_warning', 'Tràn khung'],
    ['font_missing_glyph', 'Font thiếu chữ'],
    ['fit_ok', 'Vừa khung'],
  ])('fit_status %s ⇒ nhãn "%s"', async (fit, nhan) => {
    api.layChiTietTrang.mockImplementation(async () => {
      const t = trang()
      t.regions[0].fit_status = fit
      return t
    })
    await moMan()
    const bang = screen.getByRole('heading', { name: /Thuộc tính/ })
    expect(within(bang).getByText(nhan)).toBeInTheDocument()
  })
})

describe('cọ xoá chữ', () => {
  async function toVaXoa() {
    const { stage } = await moMan()
    await userEvent.click(screen.getByRole('button', { name: 'Cọ xoá chữ, phím B' }))
    fireEvent.pointerDown(stage, { clientX: 300, clientY: 300, pointerId: 1, button: 0 })
    fireEvent.pointerMove(stage, { clientX: 340, clientY: 320, pointerId: 1 })
    fireEvent.pointerUp(stage, { clientX: 340, clientY: 320, pointerId: 1 })
    const nut = screen.getByRole('button', { name: 'Xoá vùng đã tô' })
    await waitFor(() => expect(nut).toBeEnabled())
    return nut
  }

  it('xoaVungTo nhận Blob PNG, chờ job rồi tải lại ảnh và dọn mặt nạ', async () => {
    const nut = await toVaXoa()
    await userEvent.click(nut)
    await waitFor(() => expect(api.xoaVungTo).toHaveBeenCalledTimes(1))
    const [pageId, blob] = api.xoaVungTo.mock.calls[0]
    expect(pageId).toBe('p1')
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.type).toBe('image/png')
    await waitFor(() => expect(api.choJobXong).toHaveBeenCalledWith('j2', expect.anything()))
    // Xong thì mặt nạ được dọn: nút khoá lại (về công cụ Chọn nên bảng cọ biến mất).
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Xoá vùng đã tô' })).not.toBeInTheDocument())
  })

  it('lỗi 422 hiện đúng detail của máy chủ và GIỮ mặt nạ để sửa', async () => {
    api.xoaVungTo.mockRejectedValue(Object.assign(
      new Error('422: Vùng tô chiếm 60% trang — quá rộng để là vết chữ sót'),
      { cauNguoiDoc: 'Vùng tô chiếm 60% trang — quá rộng để là vết chữ sót' },
    ))
    const nut = await toVaXoa()
    await userEvent.click(nut)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Vùng tô chiếm 60% trang — quá rộng để là vết chữ sót',
    )
    expect(api.choJobXong).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Xoá vùng đã tô' })).toBeEnabled()
  })

  it('"Bỏ mặt nạ" xoá trắng', async () => {
    await toVaXoa()
    await userEvent.click(screen.getByRole('button', { name: 'Bỏ mặt nạ' }))
    expect(screen.getByRole('button', { name: 'Xoá vùng đã tô' })).toBeDisabled()
    expect(api.xoaVungTo).not.toHaveBeenCalled()
  })

  it('hoàn tác mặt nạ theo nét, không gọi máy chủ', async () => {
    await toVaXoa()
    await userEvent.click(screen.getByRole('button', { name: 'Hoàn tác' }))
    expect(screen.getByRole('button', { name: 'Xoá vùng đã tô' })).toBeDisabled()
    expect(api.suaVung).not.toHaveBeenCalled()
  })

  it('phím ] đổi cỡ cọ', async () => {
    await moMan()
    await userEvent.click(screen.getByRole('button', { name: 'Cọ xoá chữ, phím B' }))
    expect(screen.getByLabelText(/Cỡ cọ/)).toHaveValue('24')
    await act(async () => { fireEvent.keyDown(window, { key: ']' }) })
    expect(screen.getByLabelText(/Cỡ cọ/)).toHaveValue('28')
  })
})

describe('lớp', () => {
  it('Ảnh gốc mặc định ẩn; bật được; có ô độ mờ cho từng lớp', async () => {
    await moMan()
    const mat = screen.getByRole('button', { name: 'Hiện lớp Ảnh gốc' })
    await userEvent.click(mat)
    expect(screen.getByRole('button', { name: 'Ẩn lớp Ảnh gốc' })).toBeInTheDocument()
    for (const ten of ['Ảnh gốc', 'Đã xoá chữ', 'Chữ dịch', 'Mặt nạ cọ']) {
      expect(screen.getByLabelText(`Độ mờ ${ten}`)).toBeInTheDocument()
    }
  })
})

describe('trạng thái', () => {
  it('chapter chưa có trang ⇒ màn rỗng như canvas-rong', async () => {
    api.layProject.mockResolvedValue({ id: 'c1', name: 'Rỗng', pages: [] })
    render(<CanvasEditor pageId="" projectId="c1" />)
    expect(await screen.findByText('Chapter này chưa có trang nào')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Thêm trang' })).toHaveAttribute('href', '#project=c1')
    expect(api.layChiTietTrang).not.toHaveBeenCalled()
  })

  it('không tải được trang ⇒ hiện lỗi + Thử lại tải lại thật', async () => {
    api.layChiTietTrang.mockRejectedValueOnce(
      Object.assign(new Error('500: x'), { cauNguoiDoc: 'Tệp ảnh bị hỏng' }),
    )
    render(<CanvasEditor pageId="p1" projectId="" />)
    expect(await screen.findByText(/Không tải được trang/)).toBeInTheDocument()
    expect(screen.getByText('Tệp ảnh bị hỏng')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByLabelText('Khung chữ 1')).toBeInTheDocument()
    expect(api.layChiTietTrang).toHaveBeenCalledTimes(2)
  })

  it('dải trang liệt kê trang của chapter và đánh dấu trang đang mở', async () => {
    await moMan()
    const dai = await screen.findByRole('complementary', { name: 'Dải trang' })
    const dang = within(dai).getByRole('link', { current: 'page' })
    expect(dang).toHaveAttribute('href', '#canvas=p1')
    expect(within(dai).getAllByRole('link')).toHaveLength(2)
  })

  it('lớp "Đã xoá chữ" 404 ⇒ lớp trống, màn không vỡ', async () => {
    await moMan()
    expect(await screen.findByText(/chưa có ảnh/)).toBeInTheDocument()
    expect(screen.getByLabelText('Khung chữ 1')).toBeInTheDocument()
  })
})
