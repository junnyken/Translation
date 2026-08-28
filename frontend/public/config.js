// Bản DỰ PHÒNG cho lúc chạy máy nhà: không đặt gì cả, để `api.js` dùng đường dẫn tương đối và
// đi qua proxy của Vite.
//
// Khi chạy thật, `docker-entrypoint.sh` ghi đè tệp này bằng địa chỉ API thật lúc khởi động.
// Có tệp này thì console không còn báo 404 mỗi lần mở trang — console nhiễu là console không ai đọc.
