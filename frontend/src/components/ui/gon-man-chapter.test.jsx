import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import Tabs from './Tabs.jsx'
import EmptyState from './EmptyState.jsx'
import { ChuRutGon, GiaiThich } from './GiaiThich.jsx'
import QualityPanel from '../chapter/QualityPanel.jsx'

const CAC = [{ ma: 'a', nhan: 'Tab A' }, { ma: 'b', nhan: 'Tab B' }]
function Bo() {
  const [c, setC] = useState('a')
  return <Tabs nhan="x" idGoc="t" cacTab={CAC} chon={c} onDoi={setC} noiDung={{ a: <input aria-label="o-a" />, b: <p>nội dung B</p> }} />
}

describe('gọn màn chapter', () => {
  it('Tabs noiDung: đổi tab KHÔNG gỡ tab kia (giữ trạng thái), chỉ ẩn', async () => {
    render(<Bo />)
    await userEvent.type(screen.getByLabelText('o-a'), 'giữ')
    await userEvent.click(screen.getByRole('tab', { name: 'Tab B' }))
    expect(screen.getByText('nội dung B')).toBeVisible()
    expect(screen.getByLabelText('o-a')).not.toBeVisible()   // còn trong DOM nhưng ẩn
    await userEvent.click(screen.getByRole('tab', { name: 'Tab A' }))
    expect(screen.getByLabelText('o-a')).toHaveValue('giữ')
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1)
  })

  it('ChuRutGon: chỉ một bản chữ trong DOM; "Chi tiết" mở/thu và đổi aria-expanded', async () => {
    render(<ChuRutGon dai>văn bản lỗi rất dài</ChuRutGon>)
    expect(screen.getAllByText('văn bản lỗi rất dài')).toHaveLength(1)
    const nut = screen.getByRole('button', { name: 'Chi tiết' })
    expect(nut).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(nut)
    expect(screen.getByRole('button', { name: 'Thu gọn' })).toHaveAttribute('aria-expanded', 'true')
  })

  it('ChuRutGon ngắn thì không có nút', () => {
    render(<ChuRutGon>ngắn</ChuRutGon>)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('GiaiThich: nguyên văn nằm trong <details> đóng sẵn', () => {
    const { container } = render(<GiaiThich nhan="Cách tính"><p>đoạn dài</p></GiaiThich>)
    const d = container.querySelector('details')
    expect(d.open).toBe(false)
    expect(d).toHaveTextContent('đoạn dài')
  })

  it('EmptyState gon: vẫn có tiêu đề + mô tả, không có khung to', () => {
    const { container } = render(<EmptyState gon tieuDe="Chưa có" moTa="Thêm đi" />)
    expect(screen.getByRole('heading', { name: 'Chưa có' })).toBeInTheDocument()
    expect(container.querySelector('.trong-icon')).toBeNull()
  })

  it('QualityPanel: giữ nguyên chữ giải thích trong "Cách tính", số liệu hiện sẵn', () => {
    const { container } = render(
      <QualityPanel trangDau="p1" tomTat={{ tong_vung: 15, ro_rang: 0, can_ra_soat: 0, chua_danh_gia: 15, da_bo_qua: 0, theo_phan_loai: {} }} />,
    )
    expect(screen.getByText(/chưa đánh giá được/)).toBeVisible()
    expect(container.querySelector('details')).toHaveTextContent('không phải')
    expect(container.querySelector('details').open).toBe(false)
  })
})
