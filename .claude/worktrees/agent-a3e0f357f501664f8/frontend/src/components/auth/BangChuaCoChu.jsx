import { useState } from 'react'
import * as api from '../../api.js'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'

/** Nhãn "chapter này chưa có chủ" + nút nhận về (Auth slice B).
 *
 * Chapter tạo TRƯỚC slice B không thuộc về ai — lúc đó chưa có tài khoản nào để ghi vào. Ba
 * cách xử lý, và vì sao chọn cách này:
 *
 * - Giấu đi ⇒ người dùng mất sạch việc cũ mà không hiểu vì sao. Loại.
 * - Gán bừa cho tài khoản đầu tiên ⇒ đoán mò, và nếu nhiều người dùng chung thì gán sai người.
 * - **Hiện ra kèm nhãn, để người dùng tự nhận.** Không mất gì, không đoán gì.
 *
 * Im lặng coi như của người đang xem cũng là một dạng đoán — nên phải có nhãn, không chỉ có nút.
 */
export default function BangChuaCoChu({ project, onNhanXong }) {
  const [dangNhan, setDangNhan] = useState(false)
  const [loi, setLoi] = useState(null)

  const nhan = () => chay(() => api.nhanChapter(project.id))
  // Khai báo TRƯỚC mọi `return` sớm: `const` không được nâng lên đầu phạm vi, nên dùng nó ở
  // khối return phía trên rồi khai báo phía dưới sẽ ném "Cannot access before initialization"
  // ngay lúc bấm nút — không phải lúc render, nên mắt thường không thấy.
  const nha = () => chay(() => api.nhaChapter(project.id))

  if (!project) return null

  // Đã là của mình ⇒ hiện đường NHẢ. Có `claim` mà không có đường ngược lại là bẫy một chiều:
  // nhận nhầm một cái là chapter khoá cứng vào tài khoản đó, không ai lấy lại được.
  if (project.chu_so_huu_id) {
    return (
      <p className="ghi-chu">
        Chapter này là của bạn.{' '}
        <button
          type="button" className="nut-chu" disabled={dangNhan}
          onClick={() => {
            if (!window.confirm(
              'Nhả chapter này về "chưa có chủ"?\n\n'
              + 'Mọi người đăng nhập sẽ thấy và nhận được nó.'
            )) return
            nha()
          }}
        >
          {dangNhan ? 'Đang nhả…' : 'Nhả về chưa có chủ'}
        </button>
        {loi && <span className="canh-bao"> {loi}</span>}
      </p>
    )
  }

  async function chay(viec) {
    setDangNhan(true); setLoi(null)
    try {
      onNhanXong(await viec())
    } catch (e) {
      setLoi(String(e?.message || e).replace(/^\d+:\s*/, ''))
    } finally {
      setDangNhan(false)
    }
  }

  return (
    <Alert sac="canh" tieuDe="Chapter này chưa có chủ">
      <p>
        Nó được tạo trước khi hệ thống có tài khoản, nên hiện <b>mọi người đăng nhập đều
        mở được</b>. Nhận về thì chỉ mình bạn thấy.
      </p>
      <Button kieu="chinh" onClick={nhan} disabled={dangNhan}>
        {dangNhan ? 'Đang nhận…' : 'Nhận chapter này'}
      </Button>
      {loi && <p className="canh-bao">{loi}</p>}
    </Alert>
  )
}
