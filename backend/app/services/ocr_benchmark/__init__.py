"""E20a — benchmark OCR trên chữ truyện tranh cách điệu, TÁCH KHỎI đường phục vụ production.

Không có route API nào gọi vào gói này, không đụng DB, không đụng `OCRResult`. Đây là công cụ
đo offline — chạy tay qua `backend/scripts/ocr_benchmark_run.py`, không nối vào Celery.
"""
