#!/usr/bin/env python3
"""
app.py
--------
Launcher cho giao diện web local. Chạy:

    python app.py

rồi mở trình duyệt tới http://127.0.0.1:8420

(File này chỉ import và chạy server/app.py — tách riêng để các import nội bộ
như `from config import settings` hoạt động đúng khi chạy từ thư mục gốc.)
"""
import uvicorn

from config import settings
from server.app import app

if __name__ == "__main__":
    settings.validate()
    print("\n  AI Video Content Tool đang chạy tại: http://127.0.0.1:8420\n")
    uvicorn.run(app, host="127.0.0.1", port=8420)
