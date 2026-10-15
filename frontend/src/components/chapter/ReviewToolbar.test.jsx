import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ReviewToolbar from './ReviewToolbar.jsx'

// E76 — lối vào màn canvas phải nằm ở THANH ĐẦU màn sửa tay, dạng nút chính. Bản đầu để nó lẫn giữa
// các ô tick, dạng nút phụ: chủ dự án mở màn sửa tay mà không tìm thấy (15-10-2026).
describe('ReviewToolbar — lối vào màn canvas', () => {
  it('có nút chính dẫn đúng tới trang đang xem', () => {
    render(
      <ReviewToolbar
        tenChapter="Chương 1" projectId="pr1" soCanXem={0}
        trang={{ id: 'p9', order: 1, status: 'typeset_done' }}
        danhSachTrang={[{ id: 'p9', order: 1, status: 'typeset_done' }]}
      />,
    )
    const nut = screen.getByRole('link', { name: 'Mở chế độ canvas' })
    expect(nut.getAttribute('href')).toBe('#canvas=p9')
    expect(nut.className).toContain('nut-chinh')
  })
})
