/** Ảnh bìa/thumbnail (tải qua taiVeBlobUrl), badge tràn khung/cần xem, và nút "Thử lại" khi chapter tải lỗi. */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../../api.js'
import ChapterProgress from './ChapterProgress.jsx'
import ChapterRecentList from './ChapterRecentList.jsx'
import LoiTaiChapter from './LoiTaiChapter.jsx'

let dem
beforeEach(() => {
  vi.restoreAllMocks()
  dem = 0
  globalThis.URL.createObjectURL = vi.fn()
  globalThis.URL.revokeObjectURL = vi.fn()
  vi.spyOn(api, 'taiVeBlobUrl').mockImplementation(async () => `blob:anh-${++dem}`)
  vi.spyOn(api, 'layViecHongCuaChapter').mockResolvedValue([])
})
afterEach(() => vi.unstubAllGlobals())

describe('thẻ chapter — ảnh bìa', () => {
  it('tải thumbnail của trang có order nhỏ nhất, và thu hồi blob khi gỡ', async () => {
    vi.spyOn(api, 'layProject').mockResolvedValue({
      id: 'aaaaaaaa1', name: 'Một', source_lang: 'ja', intended_use: 'personal',
      pages: [{ id: 'p3', order: 3, status: 'typeset_done' }, { id: 'p1', order: 1, status: 'typeset_done' }],
    })
    const { container, unmount } = render(<ChapterRecentList danhSach={[{ id: 'aaaaaaaa1', ten: 'Một' }]} />)
    await waitFor(() => expect(container.querySelector('img')).toHaveAttribute('src', 'blob:anh-1'))
    expect(api.taiVeBlobUrl).toHaveBeenCalledTimes(1)
    expect(api.taiVeBlobUrl).toHaveBeenCalledWith(api.duongDanThumbnail('p1'))
    expect(container.querySelector('img')).toHaveAttribute('alt', '')
    unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:anh-1')
  })

  it('tải thumbnail lỗi (404) thì giữ khối màu, không ảnh vỡ', async () => {
    api.taiVeBlobUrl.mockRejectedValue(new Error('404'))
    vi.spyOn(api, 'layProject').mockResolvedValue({
      id: 'aaaaaaaa1', name: 'Một', source_lang: 'ja', pages: [{ id: 'p1', order: 1, status: 'translated' }],
    })
    const { container } = render(<ChapterRecentList danhSach={[{ id: 'aaaaaaaa1', ten: 'Một' }]} />)
    await waitFor(() => expect(container.querySelector('.bia-chapter')).toBeTruthy())
    expect(container.querySelector('img')).toBeNull()
  })
})

describe('lưới trang — badge và chip', () => {
  const project = {
    id: 'p', name: 'x', source_lang: 'ja', intended_use: 'personal',
    pages: [
      { id: 'a', order: 1, status: 'typeset_done', so_vung_tran_khung: null, so_vung_can_xem: null },
      { id: 'b', order: 2, status: 'typeset_done', so_vung_tran_khung: 2, so_vung_can_xem: 0 },
      { id: 'c', order: 3, status: 'typeset_done', so_vung_tran_khung: 0, so_vung_can_xem: 3 },
    ],
  }
  it('null không badge; 2 ⇒ "Tràn khung · 2"; 0 không badge', async () => {
    render(<ChapterProgress project={project} onNapLai={vi.fn()} />)
    await waitFor(() => expect(api.taiVeBlobUrl).toHaveBeenCalled())
    expect(screen.getAllByText(/Tràn khung · /)).toHaveLength(1)
    expect(screen.getByText('Tràn khung · 2')).toBeInTheDocument()
    expect(screen.getByText('Cần xem lại · 3')).toBeInTheDocument()
    const o1 = screen.getByText('Trang 1').closest('.the-trang')
    expect(within(o1).queryByText(/Tràn khung|Cần xem lại/)).toBeNull()
  })

  it('chip "Tràn khung" chỉ còn trang có N>0 và đếm đúng', async () => {
    const u = userEvent.setup()
    render(<ChapterProgress project={project} onNapLai={vi.fn()} />)
    const chip = screen.getByRole('button', { name: /^Tràn khung/ })
    expect(chip).toHaveTextContent('1')
    await u.click(chip)
    expect(screen.getByText('Trang 2')).toBeInTheDocument()
    expect(screen.queryByText('Trang 1')).toBeNull()
    expect(screen.queryByText('Trang 3')).toBeNull()
  })

  it('có IntersectionObserver: chưa vào khung nhìn thì chưa tải', async () => {
    const quanSat = vi.fn()
    vi.stubGlobal('IntersectionObserver', class { observe = quanSat; disconnect() {} })
    render(<ChapterProgress project={project} onNapLai={vi.fn()} />)
    expect(quanSat).toHaveBeenCalledTimes(3)
    expect(api.taiVeBlobUrl).not.toHaveBeenCalled()
  })
})

describe('chapter tải lỗi — Thử lại', () => {
  it('bấm Thử lại gọi lại layProject và hiện dữ liệu', async () => {
    const u = userEvent.setup()
    const layProject = vi.spyOn(api, 'layProject')
      .mockRejectedValueOnce(new Error('mạng lỗi'))
      .mockResolvedValue({ id: 'p', name: 'Chương Ổn' })
    function Mau() {
      const [loi, setLoi] = useState(null)
      const [project, setProject] = useState(null)
      const [dang, setDang] = useState(false)
      const nap = async () => {
        setDang(true)
        try { setProject(await api.layProject('p')); setLoi(null) } catch (e) { setLoi(e.message) } finally { setDang(false) }
      }
      if (project) return <h1>{project.name}</h1>
      return (
        <>
          <button onClick={nap}>nạp lần đầu</button>
          {(loi || dang) && <LoiTaiChapter loi={loi} dangThuLai={dang} onThuLai={nap} onVeDanhSach={vi.fn()} />}
        </>
      )
    }
    render(<Mau />)
    await u.click(screen.getByText('nạp lần đầu'))
    expect(await screen.findByText(/mạng lỗi/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Về danh sách chapter/ })).toBeInTheDocument()
    await u.click(screen.getByRole('button', { name: /Thử lại/ }))
    expect(await screen.findByText('Chương Ổn')).toBeInTheDocument()
    expect(layProject).toHaveBeenCalledTimes(2)
  })

  it('đang thử lại thì hiện khung chờ', () => {
    render(<LoiTaiChapter loi="x" dangThuLai onThuLai={vi.fn()} onVeDanhSach={vi.fn()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Đang tải lại chapter…')
    expect(screen.queryByRole('button', { name: /Thử lại/ })).toBeNull()
  })
})
