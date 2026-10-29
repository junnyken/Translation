import { useEffect, useState } from 'react'
import { kiemBanMoi } from '../lib/phien-ban-moi.js'
import Alert from './ui/Alert.jsx'
import Button from './ui/Button.jsx'

/** Banner "có bản mới, tải lại đi" cho tab đang chạy bundle cũ.
 *
 * Vì sao cần: `REPORT_E21b.md §11.3` — tab mở sẵn từ trước lúc deploy chạy **frontend cũ trên
 * backend mới**, và đó là tổ hợp vỡ. Đã xảy ra thật: lưu chữ gốc OCR thành công nhưng giao diện
 * báo lỗi `/jobs/null`, người dùng không biết đã lưu hay chưa.
 *
 * ## Hai quyết định có chủ đích
 *
 * **KHÔNG tự tải lại trang.** Tự tải lại sẽ xoá đúng thứ E21b vừa dựng để bảo vệ: chữ người dùng
 * đang gõ dở. Chỉ hiện banner, để họ chọn thời điểm. Bấm "Tải lại ngay" mà còn thay đổi chưa lưu
 * thì `beforeunload` của E21b vẫn chặn — hai cơ chế xếp tầng đúng thứ tự.
 *
 * **Kiểm lại lúc tab được xem lại**, không chỉ theo nhịp. Cảnh phổ biến nhất là tab bị bỏ đó nhiều
 * giờ rồi mở lại — đúng lúc đó mới cần biết. Chờ hết nhịp định kỳ là để họ bấm Lưu trước khi biết.
 */
export default function BangBanMoi({ urlBundle, nhipMs = 5 * 60 * 1000, kiem = kiemBanMoi }) {
  const [daCu, setDaCu] = useState(false)

  useEffect(() => {
    // Không biết mình đang chạy bundle nào (vd trong test đơn vị) ⇒ không kiểm, không báo.
    if (!urlBundle) return undefined
    // Đã biết là cũ thì thôi: dọn nhịp, không hỏi lại nữa.
    if (daCu) return undefined

    let dungRoi = false
    const chay = async () => {
      const cu = await kiem({ urlDangChay: urlBundle })
      if (!dungRoi && cu) setDaCu(true)
    }
    chay()

    const dinhKy = setInterval(chay, nhipMs)
    const khiHienLai = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') chay()
    }
    document.addEventListener('visibilitychange', khiHienLai)

    return () => {
      dungRoi = true
      clearInterval(dinhKy)
      document.removeEventListener('visibilitychange', khiHienLai)
    }
  }, [urlBundle, nhipMs, kiem, daCu])

  if (!daCu) return null

  return (
    <div className="bang-ban-moi">
      <Alert sac="canh" tieuDe="Có bản mới của giao diện">
        Tab này đang chạy bản cũ nên có thể báo lỗi sai dù việc bạn làm <b>đã</b> được lưu.
        Tải lại trang để dùng bản mới. Nếu đang gõ dở, hệ thống sẽ hỏi trước khi rời trang.
        <div className="bang-ban-moi-nut">
          <Button kieu="chinh" icon="quay" onClick={() => window.location.reload()}>
            Tải lại ngay
          </Button>
        </div>
      </Alert>
    </div>
  )
}
