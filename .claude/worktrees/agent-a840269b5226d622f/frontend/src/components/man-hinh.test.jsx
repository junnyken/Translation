/** ĐỢT 2 redesign — hành vi của các thành phần bố cục mới (tab ARIA, lưới chapter, lọc trang,
 *  nút chỉ-icon). Kiểm HÀNH VI, không kiểm class CSS. */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api.js'
import ChapterProgress from './chapter/ChapterProgress.jsx'
import ChapterRecentList from './chapter/ChapterRecentList.jsx'
import ReviewToolbar from './chapter/ReviewToolbar.jsx'
import Tabs from './ui/Tabs.jsx'

beforeEach(() => vi.restoreAllMocks())

const CAC = [
  { ma: 'a', nhan: 'Dịch nhanh' }, { ma: 'b', nhan: 'Tạo chapter mới' }, { ma: 'c', nhan: 'Thứ ba' },
]
function MauTab() {
  const [chon, setChon] = useState('a')
  return <Tabs nhan="Chọn cách làm" cacTab={CAC} chon={chon} onDoi={setChon}><p>nội dung {chon}</p></Tabs>
}

describe('Tabs (ARIA)', () => {
  it('có tablist/tab/tabpanel liên kết nhau, chỉ tab đang chọn nằm trong thứ tự Tab', () => {
    render(<MauTab />)
    expect(screen.getByRole('tablist', { name: 'Chọn cách làm' })).toBeInTheDocument()
    const tabA = screen.getByRole('tab', { name: 'Dịch nhanh' })
    expect(tabA).toHaveAttribute('aria-selected', 'true')
    expect(tabA).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('tab', { name: 'Tạo chapter mới' })).toHaveAttribute('tabindex', '-1')
    const panel = screen.getByRole('tabpanel')
    expect(panel).toHaveAttribute('aria-labelledby', tabA.id)
    expect(tabA).toHaveAttribute('aria-controls', panel.id)
  })

  it('phím mũi tên, Home, End chuyển tab và đưa focus theo', async () => {
    const u = userEvent.setup()
    render(<MauTab />)
    screen.getByRole('tab', { name: 'Dịch nhanh' }).focus()
    await u.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Tạo chapter mới' })).toHaveFocus()
    expect(screen.getByText('nội dung b')).toBeInTheDocument()
    await u.keyboard('{End}')
    expect(screen.getByRole('tab', { name: 'Thứ ba' })).toHaveAttribute('aria-selected', 'true')
    await u.keyboard('{ArrowRight}')            // vòng về đầu
    expect(screen.getByRole('tab', { name: 'Dịch nhanh' })).toHaveFocus()
    await u.keyboard('{ArrowLeft}')             // vòng về cuối
    expect(screen.getByRole('tab', { name: 'Thứ ba' })).toHaveFocus()
    await u.keyboard('{Home}')
    expect(screen.getByRole('tab', { name: 'Dịch nhanh' })).toHaveAttribute('aria-selected', 'true')
  })
})

const du = (id, ...status) => ({
  id, name: `Tên ${id}`, source_lang: 'ja', intended_use: 'personal',
  pages: status.map((s, i) => ({ id: `${id}-${i}`, order: i + 1, status: s })),
})

describe('ChapterRecentList — lưới thẻ', () => {
  const DS = [{ id: 'aaaaaaaa1', ten: 'Chương Một' }, { id: 'bbbbbbbb2', ten: 'Chương Hai' }, { id: 'cccccccc3', ten: 'Chương Ba' }]
  function gia() {
    vi.spyOn(api, 'layProject').mockImplementation(async (id) => {
      if (id === 'aaaaaaaa1') return du(id, 'ready_for_export', 'ready_for_export')
      if (id === 'bbbbbbbb2') return du(id, 'ready_for_export', 'detection_failed')
      throw new Error('500: hỏng')
    })
  }

  it('rỗng: nói vì sao trống, không có nút chính thứ hai', () => {
    render(<ChapterRecentList danhSach={[]} />)
    expect(screen.getByText('Chưa có chapter nào trên trình duyệt này')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('đang tải thì hiện khung chờ, KHÔNG hiện số 0; xong thì hiện tiến độ thật', async () => {
    gia()
    render(<ChapterRecentList danhSach={DS} />)
    expect(screen.getAllByText('Đang tải tiến độ…').length).toBe(3)
    expect(screen.queryByText(/trang đã căn chữ xong/)).not.toBeInTheDocument()
    expect(await screen.findByText('Đã căn chữ xong')).toBeInTheDocument()
    expect(screen.getByText('Có trang hỏng')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Tiến độ Chương Một' })).toHaveAttribute('aria-valuenow', '100')
  })

  it('thẻ lỗi nói là lỗi (không đoán), vẫn mở được chapter, và có "Thử lại"', async () => {
    gia()
    render(<ChapterRecentList danhSach={DS} />)
    await waitFor(() => expect(screen.getAllByText('Không tải được tiến độ').length).toBeGreaterThan(0))
    expect(screen.getByRole('link', { name: 'Chương Ba' })).toHaveAttribute('href', '#project=cccccccc3')
    expect(screen.getByRole('button', { name: /Thử lại/ })).toBeInTheDocument()
  })

  it('tìm theo tên/mã và chip lọc theo trạng thái; không khớp thì có trạng thái rỗng', async () => {
    gia()
    const u = userEvent.setup()
    render(<ChapterRecentList danhSach={DS} />)
    await screen.findByText('Đã căn chữ xong')
    await u.type(screen.getByRole('searchbox', { name: 'Tìm chapter' }), 'hai')
    expect(screen.getByText('1 / 3 chapter')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Chương Một' })).not.toBeInTheDocument()
    await u.clear(screen.getByRole('searchbox', { name: 'Tìm chapter' }))
    await u.click(screen.getByRole('button', { name: 'Đã xong' }))
    expect(screen.getByText('1 / 3 chapter')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Đã xong' })).toHaveAttribute('aria-pressed', 'true')
    await u.type(screen.getByRole('searchbox', { name: 'Tìm chapter' }), 'zzz')
    expect(screen.getByText('Không có chapter nào khớp')).toBeInTheDocument()
  })
})

describe('ChapterProgress — lưới trang + chip lọc', () => {
  it('lọc "Hỏng" chỉ còn trang hỏng; chip cho biết số trang; có thanh các bước', async () => {
    vi.spyOn(api, 'layViecHongCuaChapter').mockResolvedValue([])
    const u = userEvent.setup()
    const project = du('p', 'ready_for_export', 'detection_failed', 'queued')
    render(<ChapterProgress project={project} onNapLai={vi.fn()} />)
    expect(screen.getByRole('list', { name: 'Các bước xử lý' })).toBeInTheDocument()
    const nhom = screen.getByRole('group', { name: 'Lọc trang' })
    expect(within(nhom).getByRole('button', { name: /Hỏng/ })).toHaveTextContent('1')
    await u.click(within(nhom).getByRole('button', { name: /Hỏng/ }))
    expect(screen.getByText('1 / 3 trang')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Trang 2' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Trang 1' })).not.toBeInTheDocument()
  })

  it('chapter 0 trang: trạng thái rỗng nói rõ, không biến mất', () => {
    vi.spyOn(api, 'layViecHongCuaChapter').mockResolvedValue([])
    render(<ChapterProgress project={du('q')} onNapLai={vi.fn()} />)
    expect(screen.getByText('Chapter chưa có trang nào')).toBeInTheDocument()
  })
})

describe('ReviewToolbar — nút chỉ có icon', () => {
  it('trước/sau có aria-label + title; trang đầu thì "Trang trước" bị khoá', () => {
    render(
      <ReviewToolbar
        tenChapter="C" projectId="pr" soCanXem={2}
        trang={{ id: 'p1', order: 1, status: 'typeset_done' }}
        danhSachTrang={[{ id: 'p1', order: 1, status: 'typeset_done' }, { id: 'p2', order: 2, status: 'typeset_done' }]}
      />,
    )
    const truoc = screen.getByLabelText('Trang trước')
    const sau = screen.getByLabelText('Trang sau')
    expect(truoc).toHaveAttribute('title', 'Trang trước')
    expect(truoc).toHaveAttribute('aria-disabled', 'true')
    expect(sau).toHaveAttribute('href', '#page=p2')
    expect(screen.getByRole('link', { name: /C$/ })).toHaveAttribute('href', '#project=pr')
    expect(screen.getByText('2 vùng cần kiểm tra')).toBeInTheDocument()
  })
})
