# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

File: `01-localhost-vs-production/develop/app.py`

| # | Dòng | Anti-pattern | Hậu quả khi chạy production |
|---|---|---|---|
| 1 | 17–18 | Hardcode API key và chuỗi kết nối database (có mật khẩu) | Đẩy code lên repo là lộ secret. Xoá dòng đó vẫn còn trong lịch sử git nên phải đổi key. Muốn đổi key phải sửa code. |
| 2 | 21–22 | `DEBUG`, `MAX_TOKENS` viết cứng, không đọc từ biến môi trường | Mỗi môi trường cần cấu hình khác nhau thì phải sửa code. |
| 3 | 33, 38 | Dùng `print()` thay cho logging, in cả nội dung câu hỏi và câu trả lời | Log không có thời gian, mức độ hay cấu trúc nên khó lọc khi có sự cố. Nội dung người dùng gửi bị lưu vào log. |
| 4 | 34 | Ghi API key ra log | Ai đọc được log cũng lấy được key, kể cả người không có quyền xem code. |
| 5 | cả file (ghi chú ở dòng 42–43) | Không có endpoint health check | Nền tảng không biết app còn hoạt động hay không để restart. Nếu nền tảng được cấu hình gọi `/health`, nó nhận 404 và coi app là lỗi. |
| 6 | 51 | `host="localhost"` | Chỉ nhận kết nối từ chính máy đó. Chạy trong container thì request từ bên ngoài không vào được. |
| 7 | 52 | `port=8000` cố định | Nền tảng cloud cấp cổng qua biến `PORT`; app không nghe đúng cổng thì không nhận được traffic. |
| 8 | 53 | `reload=True` | Chế độ dành cho lúc phát triển: tốn tài nguyên theo dõi file, và app tự khởi động lại khi file thay đổi. |
| 9 | Lab Coach yêu cầu load test đi qua JWT; nhờ AI thiết kế, review spec rồi triển khai cho stack benchmark (chỉ `benchmark-observability/production/`, không đụng `06-lab-complete/app/`) | AI viết spec `docs/superpowers/specs/2026-11-26-benchmark-jwt-design.md` và tự review (8 điểm cần sửa: 401 thay vì 403, cờ `--username`, secret mặc định trong compose, chỗ đặt test…); viết `app/auth.py`, 21 test, sửa `docker-compose.yml`, Locust, `load_test.py`, `run_eval.py`, README, `DEMO.md`; chạy Locust có đăng nhập và lưu `benchmark-results/jwt_check_*.csv`, viết mục 4.4 trong `BENCHMARK_REPORT.md` | Tôi chọn cách A (chỉ JWT ở stack benchmark), một tài khoản demo, giữ số liệu đã nộp kèm ghi chú. Đọc lại spec và diff trước khi commit; tự chạy `python -m pytest tests -q` và gọi thử `/auth/token`, `/ask`. |
| 9 | cả file | Không xử lý tắt ứng dụng trong code (không có lifespan, không dọn tài nguyên) | Không có chỗ để đóng kết nối hay ngừng nhận traffic một cách chủ động khi nền tảng tắt app. |

### Exercise 1.2: Kết quả chạy bản develop

Chạy `python app.py`, gọi bằng `curl.exe` trên Windows PowerShell.

Câu hỏi gửi qua query → **200**:

```text
> curl.exe -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Health check → **404** (không có route này):

```text
> curl.exe -i http://localhost:8000/health
HTTP/1.1 404 Not Found

{"detail":"Not Found"}
```

Gửi JSON body → **422** vì `def ask_agent(question: str)` khiến FastAPI đọc `question` từ query, không đọc body:

```text
> curl.exe -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{\"question\":\"Hello\"}'
HTTP/1.1 422 Unprocessable Entity

{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

Log của server (key trong code là key giả của bài lab):

```text
INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [25212] using WatchFiles
INFO:     Started server process [3336]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-****(đã che khi dán; log thật in nguyên giá trị key)
[DEBUG] Response: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.
INFO:     127.0.0.1:54792 - "POST /ask?question=Hello HTTP/1.1" 200 OK
INFO:     127.0.0.1:54832 - "GET /health HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:50889 - "POST /ask HTTP/1.1" 422 Unprocessable Entity
```

Nhận xét: app chạy được trên máy nhưng chưa sẵn sàng cho production. Log lộ API key, không có health check, bật reloader và chỉ nghe trên `localhost`.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---|---|---|---|
| Config & secrets | Viết cứng trong `app.py` (dòng 17–22) | Gom trong `config.py`, đọc bằng `os.getenv`; thiếu `AGENT_API_KEY` khi `ENVIRONMENT=production` thì dừng ngay lúc khởi động | Cùng một code chạy được ở nhiều môi trường; secret không nằm trong repo; cấu hình thiếu bị phát hiện sớm. |
| Health check | Không có (`/health` trả 404) | `GET /health` (liveness) và `GET /ready` (readiness, 503 khi chưa sẵn sàng) | `/health` giúp nền tảng biết khi nào cần restart; `/ready` cho load balancer biết khi nào được gửi traffic. |
| Logging | `print()`, in cả API key | Module `logging`, có thời gian và level; chỉ ghi độ dài câu hỏi/câu trả lời và IP, không ghi key | Log có cấu trúc dễ lọc và phân tích, không làm lộ secret. |
| Shutdown | Không có logic riêng | `lifespan` đặt `is_ready = False` và ghi log khi tắt; đăng ký handler `SIGTERM`; việc chờ request đang chạy do uvicorn đảm nhận | Khi deploy bản mới hoặc scale down, request đang xử lý không bị cắt ngang. |
| Host / Port | `localhost:8000` cố định | `HOST` (mặc định `0.0.0.0`) và `PORT` từ biến môi trường | Container và nền tảng cloud cần app nghe trên mọi interface và đúng cổng được cấp. |
| Reload | Luôn bật | Chỉ bật khi `DEBUG=true` | Tránh app tự khởi động lại trên production. |
| Input | `question` qua query | JSON body; thiếu `question` trả 422 | Câu hỏi không nằm trong URL (URL thường bị ghi vào access log). |

Điểm bản production vẫn còn hạn chế:

- `config.py` và `app.py` không nạp file `.env`, nên `python app.py` không tự đọc giá trị trong `.env`.
- Format log ở `app.py` dòng 30 bọc `json.dumps(...)` vào chuỗi `"msg":"..."` mà không escape dấu ngoặc kép, nên các dòng log đó không phải JSON hợp lệ.
- `/ready` chỉ kiểm tra cờ `is_ready`, chưa kiểm tra dependency nào.

Ví dụ anti-pattern đã được sửa: `develop/app.py` dòng 17 hardcode API key; bản production đọc từ biến môi trường tại `production/config.py` (trường `openai_api_key`, `os.getenv("OPENAI_API_KEY", "")`).

**Kết quả chạy bản production:**

```text
> curl.exe -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":17.8,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:19:50.163940+00:00"}

> curl.exe -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true}

> curl.exe -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{\"question\":\"Hello\"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","model":"gpt-4o-mini"}
```

Log server từ lúc khởi động đến khi tắt bằng `Ctrl+C`:

```text
{"time":"2026-11-26 14:19:32,399","level":"INFO","msg":"Starting AI Agent on 0.0.0.0:8000"}
INFO:     Started server process [16412]
INFO:     Waiting for application startup.
{"time":"2026-11-26 14:19:32,445","level":"INFO","msg":"{"event": "startup", "app": "AI Agent", "version": "1.0.0", "env": "development", "port": 8000}"}
{"time":"2026-11-26 14:19:32,546","level":"INFO","msg":"Agent is ready to serve requests"}
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     127.0.0.1:50756 - "GET /health HTTP/1.1" 200 OK
INFO:     127.0.0.1:50759 - "GET /ready HTTP/1.1" 200 OK
{"time":"2026-11-26 14:19:50,211","level":"INFO","msg":"{"event": "agent_request", "question_length": 5, "client_ip": "127.0.0.1"}"}
{"time":"2026-11-26 14:19:50,357","level":"INFO","msg":"{"event": "agent_response", "response_length": 66}"}
INFO:     127.0.0.1:50761 - "POST /ask HTTP/1.1" 200 OK
INFO:     Shutting down
INFO:     Waiting for application shutdown.
{"time":"2026-11-26 14:20:19,676","level":"INFO","msg":"Agent shutting down gracefully — finishing in-flight requests..."}
{"time":"2026-11-26 14:20:19,776","level":"INFO","msg":"Shutdown complete"}
INFO:     Application shutdown complete.
INFO:     Finished server process [16412]
```

Quan sát:

- Khi tắt, app chạy đủ phần shutdown của `lifespan` rồi mới kết thúc process. Lần thử này không có request nào đang chạy dở, nên chưa chứng minh được việc chờ request.
- Sau dòng `Finished server process`, terminal Windows in thêm traceback `KeyboardInterrupt`. Traceback xuất hiện sau khi shutdown đã hoàn tất: uvicorn phát lại tín hiệu `Ctrl+C` đã nhận.
- Không thấy dòng log `Received SIGTERM` vì `Ctrl+C` gửi SIGINT, còn handler trong code đăng ký cho SIGTERM.
- Các dòng `startup`, `agent_request`, `agent_response` có `{...}` lồng trong chuỗi `"msg"` mà không escape, nên không phải JSON hợp lệ.

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)

1. **Base image:** `python:3.11` (dòng 8), bản đầy đủ gồm hệ điều hành Debian, Python và nhiều công cụ build.
2. **Working directory:** `/app` (dòng 11). Các lệnh `COPY`, `RUN`, `CMD` phía sau chạy tương đối theo thư mục này.
3. **Vì sao COPY `requirements.txt` trước:** Docker cache theo từng layer. Khi chỉ sửa code, layer `requirements.txt` và `pip install` không đổi nên được dùng lại, build nhanh hơn. Nếu copy code trước, mỗi lần sửa code sẽ phải cài lại toàn bộ thư viện.
4. **CMD và ENTRYPOINT:** `CMD` là lệnh hoặc tham số mặc định, bị thay thế khi truyền lệnh khác sau tên image trong `docker run`. `ENTRYPOINT` là chương trình chính của container; tham số trong `docker run` được nối vào sau nó, muốn thay phải dùng `--entrypoint`. Dùng chung thì `ENTRYPOINT` là chương trình, `CMD` là tham số mặc định. Dockerfile này chỉ dùng `CMD ["python", "app.py"]`.

### Exercise 2.2: Build và chạy bản develop

```text
> docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
> docker run -d --rm --name day14-develop -p 8000:8000 my-agent:develop

> curl.exe -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":5.2,"container":true}

> curl.exe -i -X POST "http://localhost:8000/ask?question=Docker"
HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}

> docker logs day14-develop
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     172.17.0.1:39226 - "GET /health HTTP/1.1" 200 OK
INFO:     172.17.0.1:39240 - "POST /ask?question=Docker HTTP/1.1" 200 OK
```

Trong container, app là process số 1 và nghe trên `0.0.0.0`. Request từ máy host đi vào qua địa chỉ `172.17.0.1` nhờ `-p 8000:8000`.

### Exercise 2.3: Multi-stage build và so sánh kích thước

```text
> docker images my-agent
REPOSITORY   TAG        IMAGE ID       CREATED         SIZE
my-agent     advanced   bfdce468331d   2 seconds ago   240MB
my-agent     develop    8070ab98c436   4 minutes ago   1.67GB
```

- Develop: 1.67 GB (khoảng 1670 MB)
- Production: 240 MB
- Chênh lệch: giảm khoảng 1430 MB, tức khoảng **85,6%** (image production nhỏ hơn khoảng 7 lần)

**Stage 1 (`builder`):** từ `python:3.11-slim`, cài `gcc`, `libpq-dev`, rồi `pip install --user` các thư viện vào `/root/.local`.

**Stage 2 (`runtime`):** bắt đầu lại từ `python:3.11-slim` sạch, tạo user không phải root (`appuser`), chỉ copy thư viện từ builder cùng code, thêm `HEALTHCHECK` và chạy uvicorn với 2 worker.

**Vì sao nhỏ hơn** (đối chiếu bằng `docker history`; kích thước từng layer cộng lại khác cột `SIZE` của `docker images`):

- Phần chênh lệch lớn nhất đến từ **base image**. `python:3.11` có các layer 696 MB, 202 MB, 134 MB và 65 MB cho hệ điều hành và gói phát triển. Bản `slim` có layer hệ điều hành 87,7 MB và không có các gói đó.
- Phần thư viện Python chênh ít: layer `pip install` ở develop là 53,3 MB, layer copy thư viện ở production là 40,8 MB.
- **Multi-stage** giữ `gcc`, `libpq-dev` ở stage builder, không đưa sang image cuối. Nếu cài chúng trong một image `slim` một stage thì image cuối sẽ phải mang theo.

### Exercise 2.4: Docker Compose stack (`02-docker/production/`)

**Sơ đồ:**

```text
Client (máy host)
   │  HTTP :80
   ▼
┌──────────────────────── mạng Docker "internal" ─────────────────────┐
│  nginx (nginx:alpine)                                               │
│     │  proxy_pass http://agent:8000                                 │
│     ▼                                                               │
│  agent (FastAPI, uvicorn 2 worker, :8000, không mở cổng ra host)    │
│     ├── REDIS_URL=redis://redis:6379/0  ──▶  redis (7-alpine, :6379)│
│     └── QDRANT_URL=http://qdrant:6333   ──▶  qdrant (v1.9.0, :6333) │
└─────────────────────────────────────────────────────────────────────┘
```

- **Services:** `nginx`, `agent`, `redis`, `qdrant`.
- **Cổng ra máy host:** chỉ `nginx` (80 và 443 theo compose; `nginx.conf` chỉ nghe cổng 80). `agent`, `redis`, `qdrant` chỉ truy cập được trong mạng `internal`.
- **Giao tiếp:** các service gọi nhau bằng tên service (Docker DNS).
- **Thứ tự khởi động:** `agent` đợi `redis` và `qdrant` healthy; `nginx` đợi `agent` được khởi động.
- Mũi tên tới Redis và Qdrant là kết nối **theo cấu hình**: `main.py` hiện chưa đọc `REDIS_URL` hay `QDRANT_URL` và không kết nối tới hai service này.
- Chú thích trong compose ghi agent có 2 replica, nhưng file không khai báo `replicas`; khi chạy chỉ có 1 container agent.

**Lưu ý khi chạy trên máy này:** cổng 443 bị service VMware Workstation Server chiếm, nên tôi tạm dừng service đó (`Stop-Service VMwareHostd`) trong lúc chạy stack.

**Trạng thái stack** (`docker compose -p k5-day14-docker ps`, do AI chạy để kiểm tra; rút gọn cột):

```text
NAME                       SERVICE   STATUS         PORTS
k5-day14-docker-agent-1    agent     Up (healthy)   8000/tcp
k5-day14-docker-nginx-1    nginx     Up             0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
k5-day14-docker-qdrant-1   qdrant    Up (healthy)   6333-6334/tcp
k5-day14-docker-redis-1    redis     Up (healthy)   6379/tcp
```

**Test qua Nginx** (header `Server: nginx` cho thấy response đi qua proxy):

```text
> curl.exe -i http://localhost/health
HTTP/1.1 200 OK
Server: nginx
{"status":"ok","uptime_seconds":30.5,"version":"2.0.0","timestamp":"2026-11-26T07:35:01.439284"}

> curl.exe -i -X POST http://localhost/ask -H "Content-Type: application/json" --% -d "{\"question\":\"Explain microservices\"}"
HTTP/1.1 200 OK
Server: nginx
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}

> docker compose -p k5-day14-docker logs agent --tail 8   (trích)
agent-1  | {"time":"2026-11-26 07:35:55,128","level":"INFO","msg":"{"event": "request", "q_len": 21}"}
agent-1  | INFO:     172.21.0.5:59642 - "POST /ask HTTP/1.1" 200 OK
```

**Lỗi phát hiện thêm:** lần gọi đầu, PowerShell 5.1 cắt JSON tại dấu cách nên server nhận body hỏng và trả **500**:

```text
HTTP/1.1 500 Internal Server Error
agent-1  | json.decoder.JSONDecodeError: Unterminated string starting at: line 1 column 13 (char 12)
```

`main.py` gọi `await request.json()` mà không bắt lỗi. Body sai là lỗi phía client nên app phải trả 400 hoặc 422. Gửi lại đúng JSON bằng `--%` thì được 200.

## Part 3: Cloud Deployment

### Exercise 3.2: Deploy Render (nền tảng chính)

Tôi deploy chính agent Part 6 bằng Render Blueprint (nhánh `dev`, Blueprint Path `06-lab-complete/render.yaml`). Chi tiết ở [DEPLOYMENT.md](DEPLOYMENT.md).

- URL: https://day14-agent-x6yb.onrender.com
- Screenshot: [screenshots/running.png](screenshots/running.png)

```text
/health          200
/ready           200
/ask khong key   401
/ask co key      200
```

### So sánh `railway.toml` và `render.yaml` (`06-lab-complete/`)

Tôi chỉ deploy lên Render; phần Railway dưới đây là so sánh file cấu hình, chưa chạy thử trên Railway.

| Điểm | `railway.toml` | `render.yaml` | Vì sao khác |
|---|---|---|---|
| Phạm vi | Cách build và chạy **một** service (`[build]`, `[deploy]`) | Mô tả **cả hạ tầng**: web service và Redis (Key Value) | Blueprint của Render là Infrastructure as Code cho nhiều tài nguyên; file config của Railway gắn với từng service. |
| Redis | Không khai báo; tạo trên dashboard hoặc CLI | Khai báo `type: keyvalue`, `ipAllowList: []` | |
| Nối `REDIS_URL` | Đặt biến trên Railway, tham chiếu service Redis | `fromService` lấy `connectionString` ngay trong file | Render nối các tài nguyên trong cùng Blueprint. |
| Biến và secret | Không có trong file; đặt trên nền tảng | `envVars`: giá trị thường ghi thẳng, `AGENT_API_KEY` dùng `generateValue: true` | Cả hai cách đều không đưa secret vào git. |
| Chọn Dockerfile | `builder = "DOCKERFILE"`, `dockerfilePath` | `runtime: docker`, `dockerfilePath`, `dockerContext` | Thư mục con: Render tính đường dẫn từ gốc repo (khi không đặt `rootDir`); với Railway tôi định chạy `railway up` trong `06-lab-complete/`. |
| Health check | `healthcheckPath = "/health"`, có `healthcheckTimeout` | `healthCheckPath: /health` | Khác tên khoá và cú pháp (TOML / YAML). |
| Restart policy | Khai báo `ON_FAILURE`, tối đa 3 lần | Không khai báo trong file | |
| Gói dịch vụ | Không có trong file | `plan: free` | |

Cả hai đều không đặt start command riêng: dùng `CMD` trong Dockerfile, lệnh này đọc biến `PORT`.

So với file mẫu `03-cloud-deployment/render/render.yaml` (`runtime: python`, có `buildCommand` và `startCommand`), bản của tôi build từ Dockerfile nên môi trường trên cloud giống image đã kiểm tra ở máy local.

### Exercise 3.3: Pipeline Cloud Run (đọc cấu hình, không deploy)

`cloudbuild.yaml` chạy 4 bước nối tiếp nhờ `waitFor`: (1) **test** cài dependencies và chạy `pytest tests/`, test lỗi thì pipeline dừng; (2) **build** Docker image, gắn tag theo `$COMMIT_SHA` và `latest`, dùng `latest` làm layer cache; (3) **push** image lên Container Registry; (4) **deploy** image đúng commit lên Cloud Run ở `asia-southeast1`, 1–10 instance, secret lấy từ Secret Manager.
`service.yaml` khai báo service theo kiểu IaC: tài nguyên CPU/RAM, scale 1–10, 80 request đồng thời mỗi instance, timeout 60 giây, `startupProbe` gọi `/ready` và `livenessProbe` gọi `/health`.
Lưu ý khi đọc: ghi chú nói pipeline tự chạy khi push lên `main`, nhưng trigger không nằm trong file này mà phải cấu hình ở Cloud Build; bước deploy trong `cloudbuild.yaml` chỉ gắn secret `OPENAI_API_KEY`, còn `AGENT_API_KEY` chỉ có trong `service.yaml`.

## Part 4: API Security

### Exercise 4.1: API Key authentication (`04-api-gateway/develop/app.py`)

- **Key được kiểm tra ở đâu:** hàm `verify_api_key` (dòng 39–54) đọc header `X-API-Key`. Endpoint `/ask` gắn hàm này qua `Depends(verify_api_key)` (dòng 70). `/` và `/health` không yêu cầu key.
- **Sai key thì sao:** thiếu key trả **401** (dòng 44–48), key sai trả **403** (dòng 49–53). Yêu cầu ở Part 6 khác: cả thiếu và sai key đều phải trả 401.
- **Rotate key:** key đọc từ biến môi trường `AGENT_API_KEY` (dòng 35). Muốn đổi key thì đổi giá trị biến rồi khởi động lại app, không cần sửa code. Code chỉ nhận một key nên key cũ hết hiệu lực ngay; muốn đổi mà không gián đoạn client thì phải cho phép tạm thời cả key cũ và key mới.
- **Điểm chưa an toàn:** nếu không đặt biến, app dùng key mặc định nằm trong code (dòng 35). App còn in key ra console khi khởi động (dòng 91–92).

Test (khởi động với `AGENT_API_KEY=secret-key-123`, key giả của bài lab; `$body = '{\"question\":\"Hello\"}'`):

```text
> curl.exe -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d $body
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

> curl.exe -i -X POST http://localhost:8000/ask -H "X-API-Key: wrong" -H "Content-Type: application/json" -d $body
HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

> curl.exe -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d $body
HTTP/1.1 200 OK
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Log server:

```text
INFO:     127.0.0.1:52828 - "POST /ask HTTP/1.1" 401 Unauthorized
INFO:     127.0.0.1:52830 - "POST /ask HTTP/1.1" 403 Forbidden
INFO:     127.0.0.1:52835 - "POST /ask HTTP/1.1" 200 OK
```

### Exercise 4.2: JWT authentication (`04-api-gateway/production/`)

**Luồng JWT** (`auth.py`):

1. Client gửi username/password tới `POST /auth/token`. `authenticate_user` kiểm tra, `create_token` trả JWT ký bằng HS256, chứa `sub`, `role`, `iat`, `exp` (hết hạn sau 60 phút).
2. Client gửi `Authorization: Bearer <token>`.
3. `verify_token` kiểm tra chữ ký và hạn dùng, lấy `username` và `role` từ token, không cần tra database ở mỗi request.

Theo code: thiếu token → 401, token hết hạn → 401, token sai → 403. Tôi mới test trường hợp thiếu token và token hợp lệ.

Lấy token bằng tài khoản demo `student`, lưu vào biến `$TOKEN` và không in ra:

```text
> $TOKEN = (Invoke-RestMethod -Method Post -Uri http://localhost:8000/auth/token -ContentType 'application/json' -Body '{"username":"student","password":"demo123"}').access_token

> curl.exe -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d $body
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

> curl.exe -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d $body
HTTP/1.1 200 OK
x-content-type-options: nosniff
x-frame-options: DENY
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":9,"budget_remaining_usd":1.6e-05}}
```

Hạn chế: `JWT_SECRET` có giá trị mặc định nằm trong code (`auth.py` dòng 22) và mật khẩu demo viết thẳng trong code (dòng 27–30). Production phải đọc secret từ môi trường và lưu mật khẩu đã băm.

### Exercise 4.3: Rate limiting (`rate_limiter.py`)

- **Thuật toán:** cửa sổ trượt 60 giây. Docstring ghi "Sliding Window Counter", nhưng code lưu timestamp của từng request trong `deque` và xoá timestamp cũ, tức là kiểu sliding window log.
- **Giới hạn:** user 10 request/phút, admin 100 request/phút.
- **Admin:** không bỏ qua giới hạn; `app.py` dòng 141 chọn `rate_limiter_admin` theo `role` trong token (tài khoản `teacher`).
- **Khi scale:** bộ đếm nằm trong RAM của từng process. Với 3 instance, mỗi instance đếm riêng nên một user có thể gọi tới khoảng 30 request/phút, và restart là mất bộ đếm. Cần lưu trạng thái trong Redis.

```text
> 1..12 | ForEach-Object { curl.exe -s -w " -> HTTP %{http_code}\n" -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d $body }
(lần 1–9: HTTP 200, requests_remaining giảm từ 8 xuống 0)
{... "usage":{"requests_remaining":1,"budget_remaining_usd":0.000158}} -> HTTP 200
{... "usage":{"requests_remaining":0,"budget_remaining_usd":0.000173}} -> HTTP 200
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}} -> HTTP 429
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}} -> HTTP 429
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}} -> HTTP 429

> curl.exe -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d $body
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

Trong vòng lặp, 429 bắt đầu từ lần thứ 10 vì trước đó đã có 1 request có token dùng 1 lượt. Tính chung, request thứ 11 trong cửa sổ 60 giây bị chặn.

### Exercise 4.4: Cost guard (`cost_guard.py`)

**Cách hoạt động:**

- Giá tính theo 1.000 token: input 0,00015 USD, output 0,0006 USD.
- Trước khi gọi LLM, `check_budget` kiểm tra: tổng toàn hệ thống đạt 10 USD → **503**; một user đạt 1 USD/ngày → **402**. Dùng từ 80% thì ghi cảnh báo.
- Sau khi gọi, `record_usage` cộng token và chi phí.

Rate limit bảo vệ **tốc độ**, cost guard bảo vệ **tiền**: user gọi chậm trong giới hạn 10 request/phút vẫn có thể tiêu hết ngân sách nếu mỗi request dùng nhiều token.

**Hạn chế tìm thấy khi đọc code:**

1. Số liệu lưu trong RAM: restart là mất, nhiều instance thì mỗi nơi tính riêng.
2. `_global_cost` chỉ được cộng, không có chỗ nào reset theo ngày (`_global_today` được gán ở dòng 50 nhưng không dùng). Khi chạm ngân sách chung, service bị chặn tới khi restart.
3. Ngày tính bằng `time.strftime` (giờ máy chủ), nhưng thông báo lỗi ghi reset lúc "midnight UTC".
4. Kiểm tra trước, ghi chi phí sau: request cuối hoặc các request đồng thời có thể làm vượt ngân sách.
5. `app.py` dòng 160 trả `budget_remaining_usd = usage.total_cost_usd`, là số **đã dùng**. Output ở trên cho thấy giá trị này tăng dần (1.6e-05 → 0.000173).

**Cách làm cho production:** lưu chi phí trong Redis theo key có kỳ tính (ví dụ `budget:{user}:{YYYY-MM-DD}`), cộng bằng `INCRBYFLOAT` và đặt `EXPIRE`. Mọi instance dùng chung số liệu và key mới tự reset theo kỳ.

Tôi chưa test nhánh 402 ở Part 4 (cần tiêu đủ 1 USD).

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks (`05-scaling-reliability/develop/app.py`)

- **`/health` (liveness):** trả lời "process còn sống không". Nền tảng dùng để quyết định restart.
- **`/ready` (readiness):** trả lời "đã nhận request được chưa". Khi đang khởi động hoặc đang tắt thì trả 503 để load balancer ngừng gửi traffic, không cần restart.

```text
> curl.exe -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"degraded","uptime_seconds":5.9,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:42:38.238843+00:00","checks":{"memory":{"status":"degraded","used_percent":96.2}}}

> curl.exe -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true,"in_flight_requests":1}

> curl.exe -i -X POST "http://localhost:8000/ask?question=hello"
HTTP/1.1 200 OK
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

- `status` là `degraded` vì RAM của máy đang dùng 96,2% (code đặt ngưỡng 90%). HTTP vẫn là 200, nên nền tảng chỉ nhìn mã HTTP sẽ không restart. Chỉ số này đo RAM toàn máy, không phải riêng process của app.
- `in_flight_requests` bằng 1 là do middleware đếm cả chính request `/ready`.

### Exercise 5.2: Graceful shutdown

Tắt bằng `Ctrl+C` trên Windows:

```text
INFO:     Shutting down
INFO:     Waiting for application shutdown.
2026-11-26 14:42:54,566 INFO 🔄 Graceful shutdown initiated...
2026-11-26 14:42:54,566 INFO ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [14796]
2026-11-26 14:42:54,566 INFO Received signal 2 — uvicorn will handle graceful shutdown
```

- Trình tự khi tắt: uvicorn ngừng nhận request, chạy phần shutdown của `lifespan` (đặt `_is_ready = False`, chờ `_in_flight_requests` về 0, tối đa 30 giây), rồi process kết thúc. `timeout_graceful_shutdown=30` giới hạn thời gian chờ của uvicorn.
- Handler `handle_sigterm` ghi `signal 2` (SIGINT) ở cuối log, sau khi shutdown xong.
- **Giới hạn của lần thử:** đây là SIGINT, chưa phải SIGTERM, và không có request nào đang chạy lúc tắt, nên chưa chứng minh được request dở dang được hoàn thành.

### Exercise 5.3: Stateless design (`05-scaling-reliability/production/app.py`)

- **Vấn đề khi giữ state trong RAM:** mỗi instance có bộ nhớ riêng. Request sau đi vào instance khác sẽ không thấy lịch sử, và restart là mất.
- **Cách làm:** session và lịch sử lưu trong Redis ở key `session:{session_id}`, TTL 1 giờ, giữ tối đa 20 message (`save_session`, `load_session`, `append_to_history`). Instance nào cũng đọc được.

**Hạn chế tìm thấy:**

1. Nếu không kết nối được Redis lúc khởi động, code (dòng 35–45) chuyển sang lưu trong RAM. Khi đó `USE_REDIS = False` nên `/ready` (dòng 208–215) vẫn trả 200: instance trông khoẻ nhưng không còn stateless. Với nhiều instance, lịch sử sẽ lúc có lúc mất. Nên để `/ready` trả 503. (Nhận xét từ code, chưa chạy thử trường hợp này.)
2. `append_to_history` đọc, sửa rồi ghi lại cả session, không nguyên tử: hai request đồng thời cùng session có thể ghi đè lên nhau. (Nhận xét từ code.)
3. `turn` lớn hơn thực tế 1: dòng 143 đọc history sau khi đã thêm câu hỏi hiện tại, dòng 154 lại cộng thêm 1. Chạy thử: câu đầu tiên của session trả `turn=2`.

### Exercise 5.4: Load balancing

Các lệnh của 5.4 và 5.5 do AI (Claude Code) chạy trên máy tôi theo yêu cầu của tôi.

```text
> docker compose -p k5-day14-scaling up -d --build --scale agent=3 --wait
> docker compose -p k5-day14-scaling ps        (rút gọn cột)
NAME                       SERVICE   STATUS         PORTS
k5-day14-scaling-agent-1   agent     Up (healthy)   8000/tcp
k5-day14-scaling-agent-2   agent     Up (healthy)   8000/tcp
k5-day14-scaling-agent-3   agent     Up (healthy)   8000/tcp
k5-day14-scaling-nginx-1   nginx     Up             0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1   redis     Up (healthy)   6379/tcp
```

Instance ID của từng container (lấy từ `/health`):

```text
k5-day14-scaling-agent-1 -> instance-68260e
k5-day14-scaling-agent-2 -> instance-2a1ed8
k5-day14-scaling-agent-3 -> instance-9f368e
```

Số request `POST /chat` mỗi container nhận khi chạy `test_stateless.py` (5 request): agent-1: **2**, agent-2: **2**, agent-3: **1**. Nginx chia luân phiên giữa 3 instance.

Cổng 8080 lúc đó đang do Nginx của stack Part 7 giữ; chỉ container này được tạm dừng trong lúc chạy Part 5 rồi bật lại.

### Exercise 5.5: Test stateless

```text
> python test_stateless.py        (rút gọn phần câu trả lời)
Session ID: 44d8a4d1-d180-4edd-b139-ef6ba9a7ef5a
Request 1: [instance-68260e]   What is Docker?
Request 2: [instance-2a1ed8]   Why do we need containers?
Request 3: [instance-9f368e]   What is Kubernetes?
Request 4: [instance-68260e]   How does load balancing work?
Request 5: [instance-2a1ed8]   What is Redis used for?
Total requests: 5
Instances used: {'instance-9f368e', 'instance-68260e', 'instance-2a1ed8'}
✅ All requests served despite different instances!
--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

Script không tự tắt instance nào, nên thử thêm: tạo session, dừng container đã phục vụ request đầu (`docker stop k5-day14-scaling-agent-1`), rồi gửi tiếp 4 request cùng session:

```text
before    : turn=2  served_by=instance-68260e  storage=redis
(docker stop k5-day14-scaling-agent-1)
after #1  : turn=3  served_by=instance-2a1ed8  storage=redis
after #2  : turn=4  served_by=instance-9f368e  storage=redis
after #3  : turn=5  served_by=instance-2a1ed8  storage=redis
after #4  : turn=6  served_by=instance-9f368e  storage=redis
history count = 10
```

**Giải thích:** cả 4 request sau khi tắt đều thành công trên 2 instance còn lại. Lịch sử có đủ 10 message (5 câu hỏi, 5 câu trả lời), gồm cả lượt do instance đã tắt xử lý, vì state nằm trong Redis chứ không nằm trong instance. Phép thử này dừng container chủ động khi không có request đang chạy, và không thử trường hợp Redis gặp sự cố. Redis hiện chỉ có 1 instance nên vẫn là điểm lỗi đơn.

## Part 6: Output `check_production_ready.py`

Chạy đầy đủ (có Docker 28.3.3) trong WSL2 Ubuntu, tại `06-lab-complete/`:

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

Một số chi tiết trong output:

```text
✅ Docker: image < 500 MB — 56 MB
✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)
✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429
✅ Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — exit code 0
✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 0.6s
```

Xử lý input sai (AI thử trên Windows, gửi kèm API key hợp lệ): JSON hỏng, thiếu `question`, `question` toàn dấu cách, dài quá 2000 ký tự, sai kiểu → đều trả **422**, response không có traceback. Khi không có Redis, `/ask` trả **503**.

## AI log

| # | Hỏi gì | Nhận gì | Tự sửa và tự kiểm tra thế nào |
|---|---|---|---|
| 1 | Nhờ AI (Claude Code) đọc tài liệu lab và hướng dẫn từng bước trên Windows | Lộ trình CP0–CP8, lệnh PowerShell, giải thích lỗi 404 và 422 | Tự chạy các lệnh Part 1 trên máy, gửi lại output thật |
| 2 | Nhờ AI hoàn thiện báo cáo theo tiến độ | AI soạn phần Part 1 (bảng anti-pattern, bảng so sánh, nhận xét) từ code trong repo và output tôi đã chạy | Đọc lại từng anti-pattern AI liệt kê và mở `01-localhost-vs-production/develop/app.py` để đối chiếu dòng code; so bảng so sánh với output tôi đã tự chạy ở Part 1. |
| 3 | Tiếp tục nhờ AI cho Part 2 | AI soạn câu trả lời Exercise 2.1 và 2.3, sơ đồ và nhận xét Exercise 2.4; chạy `docker history` và `docker compose ps` để kiểm tra; chỉ ra lỗi trích dẫn JSON trên PowerShell (do lệnh AI đưa ban đầu) và cách sửa bằng `--%` | Tự build, chạy container, gọi API và đo `docker images`. Đối chiếu số MB trong bài với output `docker images` của tôi; chạy lại lệnh JSON với `--%` để xác nhận cách sửa lỗi trích dẫn trên PowerShell. |
| 4 | Tiếp tục nhờ AI cho Part 4 | AI soạn câu trả lời Exercise 4.1–4.4 từ code và output tôi đã chạy, chỉ ra các hạn chế của cost guard | Tự chạy các lệnh test 401 / 403 / 200 / 429. So mã trạng thái trong câu trả lời với output của tôi; đọc lại `auth.py`, `rate_limiter.py`, `cost_guard.py` để hiểu các hạn chế AI chỉ ra. |
| 5 | Tiếp tục nhờ AI cho Part 5 | AI soạn câu trả lời từ code và output; AI chạy toàn bộ lệnh của Exercise 5.4 và 5.5 (bật stack, `test_stateless.py`, dừng 1 instance) | Tự chạy các lệnh của 5.1 và 5.2. 5.3–5.5: đọc output AI chạy (`test_stateless.py`, dừng 1 instance) và đối chiếu với code `05-scaling-reliability/production/app.py`; chưa tự chạy lại. |
| 6 | Dùng một phiên AI chạy song song cho Part 7, sau đó nhờ phiên này kiểm tra và làm nốt Part 7 | Phiên song song: thêm metric `agent_question_length_chars`, sửa `KNOWLEDGE_BASE`, sửa `production/Dockerfile`, thêm job CI, soạn nháp `BENCHMARK_REPORT.md` mục 1–3. Phiên sau: đo lại toàn bộ load test và eval, chạy benchmark scale (phát hiện và sửa lỗi sai số instance), chạy 5 thí nghiệm alert, chụp 4 ảnh Part 7, viết `BENCHMARK_REPORT.md`. Mọi lệnh đo Part 7 trong bài nộp do AI chạy trên máy tôi | Đọc lại `BENCHMARK_REPORT.md` và các ảnh; AI chạy script đối chiếu mọi số trong báo cáo với `reports/*.json` và `benchmark-results/*.csv` (không lệch). Tôi tự xem lại dashboard Grafana, trace Jaeger và trang Alerts khi tập demo theo `DEMO.md`. |
| 7 | Nhờ AI viết code Part 6 | AI viết toàn bộ `app/*.py`, `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `railway.toml`, `render.yaml` (tôi đã sửa `.env.example` và bắt đầu `config.py` trước đó); AI chạy script chấm trên Windows (11/12, 42/42 phép kiểm tra chạy được đạt) và thử input sai (trả 422) | Tự chạy script chấm đầy đủ trong WSL: PASS 12/12; hỏi lại AI về transaction trong rate limiter và cách xử lý SIGTERM. Đọc code AI viết theo từng tiêu chí của script chấm. |
| 8 | Nhờ AI hướng dẫn deploy Render và viết Part 3 | AI hướng dẫn tạo Blueprint, cách đưa key vào biến mà không in ra; commit và push Part 6 theo yêu cầu của tôi; soạn `DEPLOYMENT.md`, phần so sánh config và Exercise 3.3 | Tự tạo Blueprint trên Render, tự chạy 4 lệnh kiểm tra (200 / 200 / 401 / 200). Đọc lại `DEPLOYMENT.md` và so URL, mã trạng thái với kết quả trên máy tôi; kiểm tra key không bị in ra trong tài liệu. |
