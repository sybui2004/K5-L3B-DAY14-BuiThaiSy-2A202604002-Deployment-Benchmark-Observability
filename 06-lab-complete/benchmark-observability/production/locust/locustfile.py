"""
Locust load test — mô phỏng NGƯỜI DÙNG THẬT gọi agent.

Khác load_test.py (develop): Locust có web UI, ramp-up số user dần dần,
vẽ biểu đồ realtime, xuất CSV — là công cụ benchmark chuẩn trong industry.

Chạy qua docker compose (đã cấu hình sẵn):
  Web UI   : http://localhost:8089  → nhập số user, spawn rate → Start
  Headless : docker compose run --rm locust -f /mnt/locust/locustfile.py \
               --headless -u 30 -r 5 -t 2m --csv /mnt/results/run1

Mỗi user: đăng nhập (POST /auth/token) một lần lúc bắt đầu để lấy JWT,
sau đó hỏi agent (phần lớn thời gian), thỉnh thoảng gọi /health,
nghỉ 0.5–2 giây giữa các lần (giống người thật đọc câu trả lời).

Thống kê login nằm ở dòng riêng "/auth/token". Login lỗi → user đó dừng.
/ask trả 401 → request vẫn tính là lỗi, user đăng nhập lại cho lần sau.
"""
import os
import random

from locust import HttpUser, between, task
from locust.exception import StopUser

USERNAME = os.getenv("AUTH_USERNAME", "")
PASSWORD = os.getenv("AUTH_PASSWORD", "")

QUESTIONS = [
    "Docker container là gì?",
    "Multi-stage build trong Dockerfile có lợi ích gì?",
    "Readiness probe fail thì chuyện gì xảy ra?",
    "Graceful shutdown xử lý SIGTERM như thế nào?",
    "Vì sao SLO latency nên dùng p95 thay vì trung bình?",
    "Prometheus thu thập metrics theo cơ chế push hay pull?",
    "Trong distributed tracing, span là gì?",
    "Chi phí gọi LLM được tính dựa trên những gì?",
    "Kubernetes HPA scale dựa trên những chỉ số nào?",
]


class AgentUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        if not self.login():
            raise StopUser()

    def login(self) -> bool:
        """Lấy JWT và lưu vào self.headers. Trả False nếu không lấy được."""
        self.headers = {}
        with self.client.post("/auth/token", json={"username": USERNAME, "password": PASSWORD},
                              name="/auth/token", catch_response=True) as resp:
            token = resp.json().get("access_token") if resp.status_code == 200 else None
            if not token:
                resp.failure(f"Login thất bại: HTTP {resp.status_code}")
                return False
            self.headers = {"Authorization": f"Bearer {token}"}
            return True

    @task(10)
    def ask(self):
        question = random.choice(QUESTIONS)
        # name="/ask" → gom mọi câu hỏi vào 1 dòng thống kê
        with self.client.post("/ask", json={"question": question}, headers=self.headers,
                              name="/ask", catch_response=True) as resp:
            if resp.status_code == 200 and not resp.json().get("answer"):
                resp.failure("Response 200 nhưng answer rỗng")
            elif resp.status_code == 401:
                resp.failure("401 — token hết hạn/không hợp lệ, đăng nhập lại")
        if resp.status_code == 401:
            self.login()

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")
