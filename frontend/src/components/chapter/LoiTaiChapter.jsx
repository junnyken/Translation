import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Skeleton from '../ui/Skeleton.jsx'

// wording: BA review — màn chapter khi tải lỗi (mockup-v2/chapter, trạng thái "Lỗi tải")
const TIEU_DE_LOI_TAI = 'Không tải được chapter'
const MO_TA_LOI_TAI = 'Chapter có thể thuộc tài khoản khác hoặc mạng đang lỗi. Việc đang chạy ở máy chủ không bị mất.'
const NHAN_THU_LAI = 'Thử lại'
const NHAN_VE_DANH_SACH = 'Về danh sách chapter'
const NHAN_DANG_THU_LAI = 'Đang tải lại chapter…'

/** Khối lỗi khi nạp chapter hỏng: nói lý do thật, cho thử lại tại chỗ hoặc quay về danh sách.
 *  Đang thử lại thì hiện khung chờ thay cho khối lỗi (không để màn đứng im). */
export default function LoiTaiChapter({ loi, dangThuLai = false, onThuLai, onVeDanhSach }) {
  if (dangThuLai) return <Skeleton kieu="khoi" cao={320} nhan={NHAN_DANG_THU_LAI} />
  return (
    <Alert sac="loi" tieuDe={TIEU_DE_LOI_TAI}>
      <p>{MO_TA_LOI_TAI}</p>
      {loi && <p className="ghi-chu">Chi tiết: {loi}</p>}
      <div className="hang-nut">
        <Button kieu="phu" icon="refresh" onClick={onThuLai}>{NHAN_THU_LAI}</Button>
        <Button kieu="ghost" icon="mui-ten-trai" onClick={onVeDanhSach}>{NHAN_VE_DANH_SACH}</Button>
      </div>
    </Alert>
  )
}
