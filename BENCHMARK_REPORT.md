# Benchmark & Observability Report — Day 14

> Mọi con số lấy từ report JSON / CSV / log / Prometheus / screenshot thật.

**Họ tên:** Bùi Thái Sỹ (2A202604002)
**Ngày chạy:** 26/11/2026
**Môi trường:** Windows 11, Python 3.11.0, Docker Desktop 28.3.3 (12 CPU, khoảng 15,5 GiB cho Docker, RAM máy 31,7 GB), mock LLM. Phần develop chạy trực tiếp trên Windows.
**Ai chạy:** các phép đo trong báo cáo này do AI (Claude Code) chạy trên máy tôi theo yêu cầu của tôi (xem AI log trong `MISSION_ANSWERS.md`).
**Điều kiện đo:** lúc đo phần develop không có container nào đang chạy (CPU 16%, RAM trống 2,6 GB). Lúc đo production chỉ có stack observability (CPU 10% trước khi tạo tải, RAM trống 11,1 GB). Các số đo trước đó, chạy khi máy còn container khác, đã được bỏ.
**Ghi chú về xác thực:** mọi số liệu production trong báo cáo này được đo khi stack benchmark còn xác thực bằng `X-API-Key`. Sau đó stack chuyển sang JWT (Locust đăng nhập ở `POST /auth/token` rồi gửi Bearer); số liệu không đo lại và không thay đổi. Kiểm chứng sau khi chuyển sang JWT nằm ở mục 4.4.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | p95 phía client ở tải thấp (concurrency 1 và 10) là 234,2 và 231,9 ms, nên 500 ms còn khoảng dự phòng hơn gấp đôi. |
| Error rate `/ask` | < 2 % | Mock LLM lỗi ngẫu nhiên khoảng 1% (`MOCK_ERROR_RATE`), nên SLO phải cao hơn mức nền này. |
| Accuracy trên golden dataset | ≥ 85 % | Trùng ngưỡng của job CI. Agent v2 gốc đạt 91,3%, sau khi sửa KB đạt 100%. |

Với mẫu 300 request, tỉ lệ lỗi của các lần chạy dao động từ 0,67% đến 2,00% quanh mức nền 1%, nên một lần chạy riêng lẻ có thể chạm ngưỡng chỉ do ngẫu nhiên.

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

300 request mỗi lần, gọi qua `http://127.0.0.1:8002` (lý do ở mục 2.3). Agent v2 trước khi sửa knowledge base.

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.18 | 201.5 | 234.2 | 1711.0 | 1.00% | PASS |
| 10 | 45.01 | 187.5 | 231.9 | 1698.3 | 1.33% | PASS |
| 50 | 104.45 | 198.2 | 274.7 | 1733.9 | 2.00% | PASS |
| 100 | 48.14 | 606.3 | 4330.8 | 5002.2 | 1.00% | FAIL (p95) |

**Nhận xét:** RPS không tăng tuyến tính.

- Từ 1 lên 10, RPS tăng khoảng 10,8 lần. Từ 10 lên 50 chỉ tăng khoảng 2,3 lần dù concurrency gấp 5. Ở 100, RPS **giảm** còn 48,14 và p95 lên hơn 4,3 giây.
- Latency đo phía server (field `ms` trong log của agent, cùng 4 lần chạy này, bỏ request warm-up) gần như không đổi:

| Concurrency | Server p50 (ms) | Server p95 (ms) | Server p99 (ms) |
|---|---|---|---|
| 1 | 199.6 | 232.3 | 1709.1 |
| 10 | 185.2 | 230.0 | 1694.9 |
| 50 | 179.1 | 227.4 | 1708.5 |
| 100 | 198.0 | 247.3 | 1656.4 |

- Vậy phần latency tăng thêm ở concurrency 100 phát sinh **ngoài đoạn middleware của app đo được**: phía client (`load_test.py` chạy một process) hoặc lúc request chờ trước khi tới app. Tôi chưa tách được hai nguyên nhân này.
- Metric phía server không thấy độ trễ client phải chịu, nên cần đo cả từ phía ngoài.

### 2.2 Tail latency

Cùng `--requests 300 --concurrency 20`, khởi động lại agent cho mỗi mức.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.2 | 228.4 | 234.4 |
| 0.03 (mặc định) | 215.5 | 225.2 | 1642.2 |
| 0.1 | 360.4 | 1707.0 | 1723.7 |

**Nhận xét:**

- Ở mức 3%, p99 tăng khoảng 7 lần (234 → 1642 ms), avg chỉ tăng khoảng 13%, p95 gần như không đổi vì tỉ lệ request chậm nhỏ hơn 5%.
- Ở mức 10%, tỉ lệ request chậm vượt 5% nên p95 nhảy lên 1707 ms và vi phạm SLO. avg mới là 360 ms, nhìn vẫn "ổn", trong khi p50 không đổi (187,7 ms).
- Percentile cao nhạy nhất. Không nên đặt SLO theo average vì average trộn request chậm vào số đông request nhanh, nên không cho biết nhóm người dùng chậm nhất phải chờ bao lâu.

### 2.3 Ghi chú về `localhost` trên Windows

Mở kết nối mới bằng client đồng bộ của `httpx` tới `http://localhost:8002/health` mất 2068–2072 ms (3 lần), còn tới `http://127.0.0.1:8002/health` mất 9–31 ms. Server chỉ nghe trên IPv4 (`0.0.0.0`). Tôi suy đoán Windows thử IPv6 (`::1`) trước nhưng chưa kiểm chứng riêng điều này. Vì vậy mọi số ở mục 2 và 3 đo qua `127.0.0.1`.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.3 | 108.8 | 114.1 |
| Tổng cost (USD) | 0.000406 | 0.000757 | 0.000794 |
| Cost / câu đúng (USD) | 0.00040635 | 0.00003607 | 0.00003453 |
| Quality gate | FAIL | PASS | PASS (`--min-accuracy 1.0`, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Đã sửa gì |
|---|---|---|
| security-02 | `token`, `hết hạn`, `chữ ký` | Thêm tài liệu so sánh API key với JWT vào `KNOWLEDGE_BASE`, kích hoạt bằng từ `jwt`. |
| scaling-03 | `cpu`, `memory`, `custom metrics` | Thêm tài liệu về Kubernetes HPA, kích hoạt bằng `hpa`, `kubernetes`. |

Cả hai câu sai vì không có tài liệu nào khớp, nên mock LLM trả câu chung chung. Phần sửa được chép sang cả `production/utils/mock_llm.py`. Không sửa `golden_dataset.jsonl`.

**Trade-off giữa v1 và v2:**

- Chất lượng: v2 đúng 21/23 câu, v1 đúng 1/23.
- Chi phí: v2 dùng gần gấp đôi token mỗi câu (108,8 so với 57,3), tổng cost cao hơn khoảng 1,9 lần. Tính trên mỗi câu đúng, v2 rẻ hơn khoảng 11 lần. "Cost / câu đúng" tốt hơn "cost / câu" vì nó không thưởng cho agent rẻ nhưng trả lời sai.
- Latency: p50 trong eval là 170,2 ms (v1) và 203,2 ms (v2), chênh lệch do bước retrieval và prompt dài hơn. p95 trong eval không dùng để kết luận vì 23 request là quá ít.

### Quality gate trong CI

Job nằm ở [.github/workflows/eval.yml](.github/workflows/eval.yml). `run_eval.py` thoát với exit code 1 khi accuracy dưới `--min-accuracy` hoặc có regression so với `--baseline`. Step fail thì job fail. Muốn chặn merge thật, cần đặt job `eval` làm required status check trong branch protection.

Kiểm tra trên máy: chạy v1 với `--baseline reports/eval_v2.json` cho 20 câu regression, gate FAIL, **exit code 1**. Eval cuối của v2 cho exit code 0. Job này chưa được chạy trên GitHub Actions. Job trong file không dùng `--baseline`, chỉ chặn theo ngưỡng 85%.

### Exercise 7.1: metrics của agent develop

- **Counter:** `llm_tokens_total`, `http_requests_total`. **Gauge:** `agent_in_flight_requests`, `agent_info`. **Histogram:** `http_request_duration_seconds`.
- **Label `route`:** dùng `route.path` (URL không khớp gán `unmatched`) để số time series có giới hạn. Nếu dùng URL thật, bot quét hàng nghìn URL lạ sẽ tạo hàng nghìn series và làm Prometheus tốn RAM.
- **Metric thêm mới:** Histogram `agent_question_length_chars`. Sau lần eval 23 câu: `_count` 23, `_sum` 1066, bucket `le="50"` 16, `le="100"` 23.

---

## 4. Observability stack (production)

Stack chạy bằng `docker compose -p k5-day14-observability`, 2 agent, tải nền Locust headless 30 user (`-r 5`). `promtool test rules` cho `alert_rules_test.yml`: **SUCCESS**.

### 4.1 Screenshot

- [x] [Dashboard Grafana khi đang có tải](screenshots/grafana-dashboard.png)
- [x] [Trace chậm trong Jaeger](screenshots/jaeger-slow-trace.png)
- [x] [Trace lỗi trong Jaeger, có event `exception`](screenshots/jaeger-error-trace.png)
- [x] [Trang Alerts của Prometheus, 2 alert cùng firing](screenshots/prometheus-alert-firing.png)

### Exercise 7.4: đọc dashboard

Số đo bằng PromQL ở tải nền 30 user:

1. **p95 và avg:** p95 khoảng 292–295 ms, avg khoảng 229–236 ms, p99 khoảng 1,82–1,85 s. avg và p95 khá gần nhau, còn p99 cách rất xa: có một nhóm nhỏ request chậm (mặc định 3%, dưới 5% nên không đẩy p95 lên). Chỉ nhìn avg thì không thấy nhóm này. (p95 trên Grafana được ước lượng từ bucket của histogram nên có thể khác số của Locust.)
2. **Chia tải:** hai instance nhận 9,85 và 9,29 req/s, gần đều nhau.
3. **Input tokens/s lớn hơn output tokens/s** (khoảng 1480–1507 so với 779–791): agent v2 đưa tài liệu tìm được vào prompt nên input dài hơn câu trả lời.
4. **`curl http://localhost:8080/metrics` trả 404** vì `nginx.conf` chặn `location = /metrics`. Metric lộ thông tin nội bộ (route, lưu lượng, phiên bản). Prometheus scrape thẳng từng agent trong mạng Docker, không đi qua Nginx.

### 4.2 Thí nghiệm "phá hệ thống"

Mỗi lần đổi bằng `production/.env` rồi `docker compose up -d --no-deps --scale agent=2 agent` (thí nghiệm D dùng `docker pause`). Thời gian tính từ lúc chạy lệnh đổi đến khi API `/api/v1/alerts` báo `firing` (hỏi mỗi 3 giây). Khôi phục và đợi alert tắt trước thí nghiệm tiếp theo.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 90 s (pending sau 33 s) | Error rate: 0,8% → 18,9% |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | 143 s (pending sau 26 s) | Latency: p95 0,29 → 1,91 s; avg 0,24 → 0,63 s |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | Không đo được (xem dưới) | Cost burn rate (cửa sổ 1 phút): 2,5 → 37,2 USD/giờ (khoảng 15 lần); p95 latency 0,29 → 0,66 s |
| D | `docker pause` 1 instance | `AgentInstanceDown` | 39 s (pending sau 12 s) | Instances up: 2 → 1 |
| E | `AGENT_VERSION=v1` | Không alert nào firing | — (trong 200 s) | Retrieval hit ratio mất dữ liệu; tokens/s input 1573 → 703, output 827 → 382 |
| A+B | Bật cùng lúc để chụp ảnh | Cả hai | `AgentHighErrorRate` 93 s, `AgentHighLatencyP95` 151 s | Ảnh trang Alerts |

- **Thí nghiệm C:** ngay ở tải nền bình thường (30 user, model nhỏ), chi phí đã khoảng 2,5 USD/giờ, vượt ngưỡng 2 USD/giờ của alert, nên `LLMCostBurnRateHigh` đã firing từ trước khi đổi model (lúc bắt đầu C đang `pending`, sau đó `firing`). Vì vậy không tính được "thời gian từ lúc đổi đến firing". Ngưỡng này quá thấp so với mức tải của lab; nên đặt cao hơn mức nền, hoặc cảnh báo theo cost trên mỗi request.
- **Thí nghiệm D:** trong lúc pause, Nginx ghi 863 request `POST /ask`: 822 mã 200, 14 mã 503, **27 mã 504**. Error rate đo bằng metric của agent chỉ 1,5% (mức nền): request bị 504 ở Nginx không được agent xử lý xong nên metric của agent không đếm. Cần giám sát thêm ở load balancer hoặc synthetic check từ bên ngoài.
- **Thí nghiệm E:** trong lúc container được tạo lại, `AgentInstanceDown` có lúc ở trạng thái `pending` nhưng không firing. p95 còn giảm (292 → 199 ms) vì v1 bỏ bước retrieval.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Metric hạ tầng không đo được câu trả lời đúng hay sai: v1 vẫn trả 200, còn nhanh và rẻ hơn. Cần giám sát chất lượng:

- Chạy `run_eval.py` trên golden dataset trong CI trước khi deploy (v1 chỉ đạt 4,35% nên bị chặn), và chạy định kỳ trên bản đang chạy (synthetic eval).
- Chấm mẫu traffic thật (LLM-as-judge hoặc người chấm), theo dõi phản hồi của người dùng.
- Đặt alert cho tín hiệu gián tiếp như retrieval hit ratio, phiên bản đang chạy (`agent_info`), số output token trung bình thay đổi đột ngột.

### 4.3 Debug bằng trace

**Trace chậm:**

- `trace_id`: `4fcceecd1967d4006e48cc0ab2be3ed2`
- Tổng thời gian: 1724,1 ms (span `POST /ask`); log ghi `ms` 1723,3
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1695,1 ms, khoảng 98%); `agent.retrieve_context` 26,5 ms. Chậm ở bước gọi LLM, không phải ở code retrieval.
- Dòng log tương ứng:

```json
{"ts": "2026-11-26T08:56:12.933581+00:00", "level": "INFO", "service": "observable-agent", "instance": "b7f3a5f1e3dc", "event": "llm_call", "trace_id": "4fcceecd1967d4006e48cc0ab2be3ed2", "span_id": "5bc1043702461c79", "request_id": "dbe068609959", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1694.0}
```

**Trace lỗi:**

- `trace_id`: `7851dd53575ce5e58edcea57f41aafa4`, HTTP 503, tổng 108,9 ms
- Span `chat mock-llm-small` (84,7 ms) có `error.type=upstream_unavailable` và event `exception`: `Upstream LLM error: 503 Service Unavailable (mock)`

```json
{"ts": "2026-11-26T08:57:25.614525+00:00", "level": "INFO", "service": "observable-agent", "instance": "b7f3a5f1e3dc", "event": "llm_error", "trace_id": "7851dd53575ce5e58edcea57f41aafa4", "span_id": "9d5ed174faecffd4", "request_id": "6cbd74bbe490", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

**Lưu ý về độ tin cậy của thời lượng span:** khi so 15 request chậm, 12 trace có thời lượng span khớp với `ms` trong log (lệch khoảng 1 ms), 3 trace ngắn hơn log từ 0,76 đến 1,45 giây. Log đo bằng đồng hồ đơn điệu (`perf_counter`), còn span lấy mốc theo giờ hệ thống, nên tôi suy đoán giờ hệ thống trong container (Docker trên WSL2) thỉnh thoảng bị chỉnh lùi. Theo dõi riêng 20 giây không bắt được lần nhảy nào, nên nguyên nhân chưa được xác nhận. Hai trace ở trên đã được đối chiếu khớp với log. Trong production nên so span với log khi thấy số bất thường.

### 4.4 Xác thực JWT cho load test

Theo yêu cầu của Lab Coach, load test phải đăng nhập lấy JWT rồi mới gọi `/ask`. Sau khi đo xong các mục 2–5, stack production chuyển sang JWT. App chính ở `06-lab-complete/app/` (bản trên Render) vẫn dùng `X-API-Key`.

- **Luồng:** `POST /auth/token` với `{"username", "password"}` trả `access_token` ký HS256 (claim `sub`, `iat`, `exp`, hết hạn sau 60 phút). `/ask` yêu cầu `Authorization: Bearer <token>`. Token thiếu, sai chữ ký, hết hạn, thiếu claim hoặc sai thuật toán đều trả `401` kèm `WWW-Authenticate: Bearer`. Stack không còn nhận `X-API-Key`. Code: `production/app/auth.py`.
- **Cấu hình:** `JWT_SECRET` (tối thiểu 32 byte), `AUTH_USERNAME`, `AUTH_PASSWORD` đọc từ biến môi trường khi agent khởi động. Thiếu biến hoặc secret ngắn thì agent không khởi động: chạy container với `JWT_SECRET=short` báo `RuntimeError` và "Application startup failed", thoát với mã 3. Giá trị mặc định trong `docker-compose.yml` chỉ dùng cho lab local; vì nó nằm trong git nên ai có repo cũng ký được token cho stack local. Đây là rủi ro chấp nhận cho lab.
- **Locust:** mỗi user đăng nhập một lần ở `on_start`, thống kê nằm ở dòng riêng `/auth/token`. Đăng nhập lỗi thì user dừng. `/ask` trả 401 thì tính là lỗi và user đăng nhập lại.
- **Test tự động:** 21 test trong `production/tests/test_auth.py` đều pass.

**Kiểm chứng bằng Locust** (`-u 30 -r 5 -t 1m`, 2 agent, file `benchmark-results/jwt_check_stats.csv`):

| Dòng | Requests | Failures | RPS | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|---|
| `/auth/token` | 30 | 0 | 0.51 | 11 | 43 | 51 |
| `/ask` | 1055 | 7 (0.66%) | 17.85 | 190 | 220 | 1700 |

Mỗi user đăng nhập đúng một lần (30 lượt cho 30 user) và không lần nào lỗi. Có 1055 request `/ask` và không có 401. Cả 7 lỗi đều là 503 do mock cố ý bơm lỗi (`jwt_check_failures.csv`). Latency `/ask` cùng mức với trước khi có JWT (p50 190 ms, p95 220 ms), vì kiểm tra chữ ký HS256 tốn rất ít thời gian so với lượt gọi LLM. Lượt đo này chỉ dùng để kiểm chứng JWT; các bảng ở mục 2–5 giữ nguyên số cũ.

Ngoài ra, `run_eval.py --url http://127.0.0.1:8080 --username demo` chạy qua JWT đạt 100% (23/23), quality gate PASS. Lượt chạy này không lưu file (không dùng `--out`).

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

`-u 100 -r 10 -t 2m`, số liệu dòng `/ask` trong `benchmark-results/scale_*_stats.csv`.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 63.01 | 190 | 260 | 1700 | 68 / 7177 (0.95%) |
| 3 | 62.71 | 190 | 230 | 1700 | 63 / 7105 (0.89%) |

**Cách đo cần lưu ý:** lệnh `docker compose run locust` trong tài liệu lab khởi động cả các service phụ thuộc theo `replicas: 2`, ghi đè `--scale`. Lần đo đầu, sự kiện Docker cho thấy một agent bị bật thêm ngay khi bắt đầu lượt "1 instance" và một agent bị xoá khi bắt đầu lượt "3 instance", nên cả hai thực chất chạy với 2 agent; các số đó đã bỏ. Hai lượt trong bảng dùng thêm `--no-deps`. Đã kiểm tra số container trước, trong và sau tải là 1 và 3. Theo Prometheus, lượt 1 instance có khoảng 7.315 request vào một instance (ước lượng từ `increase()`); lượt 3 instance chia 2.420 / 2.404 / 2.436.

**Giải thích kết quả:** Scale lên 3 không tăng RPS (63,0 → 62,7), p50 và p99 không đổi, p95 giảm nhẹ 30 ms (một lần đo mỗi cấu hình, chưa đủ để khẳng định đây không phải dao động).

- **1 agent chưa bị quá tải:** lúc đang tải, một mẫu `docker stats` cho thấy agent dùng 17% CPU (giới hạn 0,5 CPU, tức 50%).
- **Latency chủ yếu là thời gian chờ LLM:** bước gọi mock LLM chiếm phần lớn mỗi request (xem trace ở 4.3). Mock chờ bất đồng bộ nên một instance xử lý được nhiều request cùng lúc. Thêm instance không làm LLM trả lời nhanh hơn.
- **RPS bị giới hạn bởi cách tạo tải:** mỗi user Locust chờ 0,5–2 giây giữa hai request. 100 user, mỗi vòng khoảng 1,25 s chờ cộng khoảng 0,22 s xử lý, cho khoảng 68 req/s, khớp với tổng khoảng 69 req/s đo được.

Muốn thấy lợi ích của scale, cần tạo tải đủ lớn để CPU của 1 instance chạm giới hạn.

---

## 6. Kết luận

- 3 điều học được về benchmark & observability:
  1. Phải nhìn percentile: 3% request chậm gần như không làm avg và p95 thay đổi nhưng làm p99 tăng khoảng 7 lần.
  2. Mỗi nguồn số liệu có điểm mù: latency phía server không thấy độ trễ phía client (mục 2.1), metric của agent không thấy lỗi 504 ở Nginx (thí nghiệm D), metric hạ tầng không thấy chất lượng giảm (thí nghiệm E).
  3. Phải kiểm tra chính phép đo: lệnh benchmark scale chạy sai số instance mà vẫn cho ra bảng số hợp lý, và một số trace có thời lượng lệch với log. Đối chiếu nhiều nguồn mới phát hiện được.
- Nếu đưa agent này lên production thật, sẽ thêm:
  - Metric và alert ở load balancer (tỉ lệ 502/504, latency phía ngoài) và synthetic check từ bên ngoài.
  - Giám sát chất lượng: eval định kỳ, alert khi retrieval hit ratio giảm hoặc phiên bản đổi ngoài lịch deploy.
  - Alert cost theo cost trên mỗi request và theo ngân sách ngày, thay cho ngưỡng cố định 2 USD/giờ.
  - Alert theo tốc độ tiêu error budget, và Alertmanager để gửi cảnh báo.
