import { useNgonNguUI } from '../../lib/ngon-ngu-ui.jsx'
import Button from '../ui/Button.jsx'

/**
 * AdminChapter — Nhật ký chapter gần đây trên toàn hệ thống.
 */
export default function AdminChapter({ thongKe }) {
  const { laEn } = useNgonNguUI()
  const chapterGanDay = Array.isArray(thongKe?.chapter_gan_day) ? thongKe.chapter_gan_day : []

  return (
    <div className="admin-khung">
      <div className="admin-khung-dau">
        <div>
          <h3>
            📚 {laEn
              ? `Recent Chapters (${chapterGanDay.length})`
              : `Nhật ký 15 Chapter Gần Nhất (${chapterGanDay.length})`}
          </h3>
          <p className="ghi-chu">
            {laEn
              ? 'Monitor who is translating what, which language, and open for support.'
              : 'Theo dõi ai đang dịch truyện gì, ngôn ngữ nào và mở kiểm tra nhanh khi cần hỗ trợ.'}
          </p>
        </div>
      </div>

      {chapterGanDay.length === 0 ? (
        <div className="admin-khung-than" style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>
          {laEn ? 'No chapters created yet.' : 'Chưa có chapter nào được tạo.'}
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="admin-bang">
            <thead>
              <tr>
                <th>{laEn ? 'Chapter Name' : 'Tên Chapter'}</th>
                <th>{laEn ? 'Owner' : 'Chủ sở hữu'}</th>
                <th>{laEn ? 'Language' : 'Ngôn ngữ'}</th>
                <th>{laEn ? 'Mode' : 'Chế độ'}</th>
                <th>{laEn ? 'Pages' : 'Số trang'}</th>
                <th>{laEn ? 'Created' : 'Thời gian tạo'}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {chapterGanDay.map((ch) => (
                <tr key={ch.id}>
                  <td><strong>{ch.name}</strong></td>
                  <td><code>{ch.email_chu}</code></td>
                  <td>
                    <span
                      className="admin-huy-hieu xam"
                      style={{ fontSize: 11 }}
                    >
                      {(ch.source_lang || 'ja').toUpperCase()} → {(ch.target_lang || 'vi').toUpperCase()}
                    </span>
                  </td>
                  <td style={{ fontSize: 12 }}>
                    {ch.che_do_pipeline === 'chi_chu'
                      ? `⚡ ${laEn ? 'Quick (Extension)' : 'Đọc nhanh (Tiện ích)'}`
                      : `🎨 ${laEn ? 'Full (Clean & Typeset)' : 'Đầy đủ (Xoá & Chèn chữ)'}`}
                  </td>
                  <td>
                    <strong>{ch.so_trang}</strong> {laEn ? 'pages' : 'trang'}
                  </td>
                  <td style={{ fontSize: 12, color: '#64748b' }}>
                    {ch.created_at ? new Date(ch.created_at).toLocaleString('vi-VN') : '—'}
                  </td>
                  <td>
                    <Button
                      kieu="phu"
                      onClick={() => { window.location.hash = `project=${ch.id}` }}
                    >
                      🔍 {laEn ? 'Open' : 'Mở xem'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
