import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

// `import.meta.url` phải lấy Ở ĐÂY, tại điểm vào — không phải trong App.jsx. `index.html` trỏ tới
// chunk của điểm vào, nên chỉ URL này so được. Ở chế độ dev nó là `/src/main.jsx`, đúng thứ
// `index.html` tham chiếu; lấy từ App.jsx sẽ ra `/src/App.jsx` và báo "có bản mới" sai ngay khi
// chạy dev. Dùng để phát hiện tab chạy bundle cũ — xem components/BangBanMoi.jsx.
createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App urlBundle={import.meta.url} />
  </React.StrictMode>,
)
