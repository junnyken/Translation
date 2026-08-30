import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { docDanhSachTrang, laOriginDuocPhep } from './cors-allowlist.js'

// API chạy ở container `api` khi trong docker, cổng 8010 khi chạy trên máy.
const target = process.env.VITE_API_TARGET || 'http://localhost:8010'

// E1a — CHẶN MẶC ĐỊNH.
//
// Vite 6.0.7 mặc định `server.cors: true`, tức gắn `Access-Control-Allow-Origin: *` vào MỌI
// phản hồi, kể cả phản hồi proxy `/api` xuống backend. Đo thật 2026-08-30: bất kỳ website nào
// đang mở cũng đọc được `GET /api/v1/projects/{id}` của Translation local.
//
// Giao diện web KHÔNG cần CORS: trang tải từ cổng 5174 gọi `/api/...` cũng ở cổng 5174 — cùng
// nguồn. Nên mặc định tắt hẳn CORS là an toàn mà không hỏng gì.
//
// Muốn mở cho một origin cụ thể (ví dụ tiện ích E1 đọc trạng thái) thì khai tường minh:
//   DEV_SERVER_CORS_ALLOW_ORIGINS=chrome-extension://<id-thật-32-ký-tự>
// Không có ký tự đại diện, không phản chiếu Origin. Xem `docs/SECURITY.md`.
const { origins: CHO_PHEP, bi_loai } = docDanhSachTrang(
  process.env.DEV_SERVER_CORS_ALLOW_ORIGINS,
)

for (const m of bi_loai) {
  console.warn(`[cors] LOẠI mục khai báo không hợp lệ: ${m.gia_tri} — ${m.ly_do}`)
}
console.info(CHO_PHEP.length
  ? `[cors] máy chủ dev cho phép ${CHO_PHEP.length} origin: ${CHO_PHEP.join(', ')}`
  : '[cors] máy chủ dev CHẶN mọi origin chéo nguồn (giao diện web dùng cùng nguồn nên không ảnh hưởng)')

/** `false` = không gắn header CORS nào. Có khai báo thì chỉ trả đúng origin khớp tuyệt đối. */
const cors = CHO_PHEP.length === 0
  ? false
  : {
    origin(origin, cb) {
      cb(null, laOriginDuocPhep(origin, CHO_PHEP))
    },
    credentials: false,
    // Chỉ mở đúng method/header mà giao diện và tiện ích thật sự dùng.
    methods: ['GET', 'POST', 'PATCH', 'OPTIONS'],
    allowedHeaders: ['Content-Type'],
  }

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    cors,
    proxy: { '/api': { target, changeOrigin: true } },
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    cors,
  },
})
