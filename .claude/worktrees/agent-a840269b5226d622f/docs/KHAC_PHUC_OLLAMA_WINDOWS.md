# Khắc phục Ollama trên Windows

Chế độ `local_gguf (Qwen3-VL 8B Offline)` chỉ gửi ảnh đến Ollama/LM Studio đang chạy tại `127.0.0.1`; ứng dụng không tự tải model và mặc định vẫn là Gemini.

1. Cài Ollama từ <https://ollama.com/download/windows>, mở Ollama, rồi chạy `windows-app\Cai-Dich-Offline.bat`. Chỉ xác nhận tải khi chấp nhận model `qwen3-vl:8b` khoảng 6.2 GB.
2. Trong app chọn **Kiểm tra Qwen3-VL 8B**. Kiểm tra thực sự gọi model, không chỉ nhìn danh sách model.
3. Nếu log báo runner/CUDA/`0xc0000409`, xem `%LOCALAPPDATA%\Ollama\server.log`, cập nhật Ollama và driver NVIDIA. Có thể chọn **Chạy Ollama bằng CPU (chậm)** rồi kiểm tra lại.
4. Tick CPU chỉ điều khiển Ollama. Nếu app đang kết nối LM Studio, bỏ tick và chọn CPU trong LM Studio, hoặc chuyển sang Ollama; app sẽ báo rõ thay vì hứa sai.
5. Khi đã chạy thử thành công, tự chọn `local_gguf (Qwen3-VL 8B Offline)`. Chọn thư mục ảnh có sẵn nếu muốn tránh tải ảnh nguồn qua mạng.

Nếu chưa xử lý được, quay về Gemini; app không tự đổi engine hay tự gửi ảnh sang máy chủ dịch khi bạn chọn local.
