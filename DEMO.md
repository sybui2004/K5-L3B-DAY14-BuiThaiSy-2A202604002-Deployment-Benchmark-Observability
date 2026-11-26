# Kịch bản demo — Day 14

Tổng khoảng **18–20 phút**. Demo theo thứ tự: agent trên cloud → chất lượng → hiệu năng và dashboard → trace → alert.
Nếu chỉ có 5 phút: làm **Phần 1**, **Phần 3** và **thí nghiệm D** (alert nhanh nhất).

| Phần | Nội dung | Thời gian |
|---|---|---:|
| 0 | Chuẩn bị (làm trước khi demo) | 10' trước |
| 1 | Agent production trên Render | 3' |
| 2 | Eval và quality gate | 3' |
| 3 | Load test và Grafana | 3' |
| 4 | Trace trong Jaeger | 2' |
| 5 | Alert | 8' |
| 6 | Dọn dẹp | sau demo |

Lệnh chạy bằng **PowerShell**, trừ chỗ ghi WSL.
> **Không dùng `--out`** và không chạy Locust headless với tên `scale_1` / `scale_3` khi demo: sẽ ghi đè file số liệu đã nộp.

---

## 0. Chuẩn bị

**0.1. Bật stack** (Docker Desktop phải đang chạy):

```powershell
cd D:\Vin\K5-L3B-DAY14-BuiThaiSy-2A202604002-Deployment-Benchmark-Observability\06-lab-complete\benchmark-observability\production
if (Test-Path .env) { Remove-Item .env }      # bắt đầu từ cấu hình mặc định
docker compose -p k5-day14-observability up -d --build --scale agent=2
docker compose -p k5-day14-observability ps
```

> Thư mục này không dùng `.env` cho việc gì khác ngoài các thí nghiệm bên dưới.

**0.2. Tạo tải nền:** mở http://localhost:8089 → Users `30`, Ramp up `5`, Host `http://nginx` → **Start**.
Nếu đang chạy tải lớn từ trước: **STOP**, rồi Start lại 30 user. **Giữ tải này suốt Phần 3–5.** Không có traffic thì alert về lỗi và latency không có dữ liệu để firing.

**0.3. Mở sẵn các tab:**

| Tab | Địa chỉ |
|---|---|
| Locust | http://localhost:8089 |
| Grafana | http://localhost:3000 → dashboard **Day 14 — AI Agent Overview**, chọn *Last 15 minutes*, refresh *5s* |
| Prometheus | http://localhost:9090/alerts |
| Jaeger | http://localhost:16686 |
| Render | https://day14-agent-x6yb.onrender.com/health |

**0.4. Đánh thức Render:** mở link `/health` ở trên (gói free tạm ngủ; lần đầu có thể chờ 50 giây hoặc hơn).

**0.5. Đặt biến cho Phần 1** trong một terminal riêng. Copy `AGENT_API_KEY` trên Render (service → **Environment**), rồi **gõ tay** dòng đầu (nếu copy dòng lệnh thì clipboard bị ghi đè):

```powershell
$env:AGENT_API_KEY = (Get-Clipboard).Trim()
$env:AGENT_API_KEY.Length        # khoảng 44
```

```powershell
$BASE = "https://day14-agent-x6yb.onrender.com"
$body = '{\"question\":\"Hello\"}'
```

Khi chia sẻ màn hình: không mở phần giá trị biến trên Render, không `echo` key, không dùng trang `/docs` (lệnh curl mẫu hiện key).

---

## 1. Agent production trên Render (3')

> Render dùng API key, JWT chỉ áp dụng cho stack benchmark (Phần 3–5).

**1.1. Bốn lệnh kiểm tra**

```powershell
curl.exe -sS -o NUL -w "/health          %{http_code}\n" "$BASE/health"
curl.exe -sS -o NUL -w "/ready           %{http_code}\n" "$BASE/ready"
curl.exe -sS -o NUL -w "/ask khong key   %{http_code}\n" -X POST "$BASE/ask" -H "Content-Type: application/json" -d $body
curl.exe -sS -o NUL -w "/ask co key      %{http_code}\n" -X POST "$BASE/ask" -H "Content-Type: application/json" -H "X-API-Key: $env:AGENT_API_KEY" -d $body
```

Mong đợi: `200`, `200`, `401`, `200`.

> **Nói:** "`/health` chỉ cho biết process còn sống, không phụ thuộc Redis. `/ready` kiểm tra Redis: Redis lỗi thì trả 503 để ngừng nhận traffic, nhưng không restart app."

**1.2. Rate limit** (đợi 60 giây sau 1.1):

```powershell
1..12 | ForEach-Object { curl.exe -sS -o NUL -w "lan $_ : %{http_code}\n" -X POST "$BASE/ask" -H "Content-Type: application/json" -H "X-API-Key: $env:AGENT_API_KEY" -d $body }
```

Mong đợi: 10 lần đầu `200`, sau đó `429`. *(Chưa thử trên Render: nên tập trước một lần.)*

> **Nói:** "Sliding window 60 giây bằng Redis sorted set. Ghi và đếm nằm trong một transaction nên 2 worker không cùng cho qua. State ở Redis nên restart vẫn còn."

**1.3. Script chấm (tuỳ chọn, chạy trong WSL, mất vài phút).** Nên chạy trước và để sẵn kết quả, không chạy cùng lúc với Phần 5.

```bash
source ~/venv-day14/bin/activate
cd /mnt/d/Vin/K5-L3B-DAY14-BuiThaiSy-2A202604002-Deployment-Benchmark-Observability/06-lab-complete
PYTHONDONTWRITEBYTECODE=1 python check_production_ready.py
```

Mong đợi: `PASS 12/12`. Trong đó có cost guard (402) và graceful shutdown (SIGTERM).

---

## 2. Eval và quality gate (3')

**Terminal A** (agent v1):

```powershell
cd D:\Vin\K5-L3B-DAY14-BuiThaiSy-2A202604002-Deployment-Benchmark-Observability\06-lab-complete\benchmark-observability\develop
& $env:USERPROFILE\venv-day14\Scripts\Activate.ps1
$env:PYTHONUTF8="1"; $env:AGENT_VERSION="v1"; $env:PORT="8001"; python app.py
```

**Terminal B** (agent v2): như trên, đổi thành `$env:AGENT_VERSION="v2"; $env:PORT="8002"`.

**Terminal C:**

```powershell
cd D:\Vin\K5-L3B-DAY14-BuiThaiSy-2A202604002-Deployment-Benchmark-Observability\06-lab-complete\benchmark-observability\develop
& $env:USERPROFILE\venv-day14\Scripts\Activate.ps1
$env:PYTHONUTF8="1"

python eval/run_eval.py --url http://127.0.0.1:8002 --min-accuracy 1.0
"exit code: $LASTEXITCODE"      # mong đợi 0

python eval/run_eval.py --url http://127.0.0.1:8001 --baseline reports/eval_v2.json
"exit code: $LASTEXITCODE"      # mong đợi 1
```

| Bản | Kết quả khi đo cho báo cáo |
|---|---|
| v2 hiện tại | 23/23, quality gate PASS |
| v1 | 1/23, 20 câu regression, FAIL |

Mock LLM có khoảng 1% lỗi ngẫu nhiên nên kết quả có thể lệch nhẹ giữa các lần chạy.

> **Nói:** "Gate trả exit code 1 thì job CI fail. Job nằm ở `.github/workflows/eval.yml`, chưa chạy trên GitHub Actions; muốn chặn merge phải đặt job làm required status check. v2 tốn gần gấp đôi token mỗi câu nhưng rẻ hơn khoảng 11 lần trên mỗi câu đúng."

Dùng `127.0.0.1`, không dùng `localhost`: trên máy này mở kết nối mới tới `localhost` mất khoảng 2 giây. Xong thì `Ctrl+C` ở terminal A và B.

---

## 3. Load test và Grafana (3')

**3.1. Locust** (tab Statistics): chỉ dòng `/ask`: RPS, p50, p95, p99, tỉ lệ lỗi.

> **Nói:** "30 user, mỗi user nghỉ 0,5–2 giây giữa hai request, nên khoảng 20 request/giây. p95 khoảng 220 ms, đạt SLO dưới 500 ms. p99 khoảng 1,7 giây vì mock làm chậm khoảng 3% request."

**3.2. Grafana:** chỉ lần lượt 4 Golden Signals.

| Signal | Panel | Ở tải 30 user (đã đo) |
|---|---|---|
| Traffic | Traffic (req/s) | khoảng 19–20 |
| Errors | Error rate | khoảng 1% |
| Latency | Latency p95 | khoảng 290–300 ms |
| Saturation | Saturation (in-flight) | khoảng 4–6 |

Chỉ thêm panel **Requests/s theo instance** (2 instance gần bằng nhau) và **Tokens/s** (input gấp khoảng 1,9 lần output vì v2 đưa tài liệu vào prompt).

> **Nói khi bị hỏi vì sao p95 khác Locust:** "Grafana đo trong agent, tính trên 1 phút gần nhất và ước lượng từ histogram. Locust đo từ phía client và cộng dồn cả lượt chạy."

**3.3. `/metrics` không public:**

```powershell
curl.exe -i http://localhost:8080/metrics      # 404
```

> **Nói:** "Nginx chặn vì metric lộ thông tin nội bộ. Prometheus scrape thẳng agent trong mạng Docker."

---

## 4. Trace trong Jaeger (2')

**Trace chậm:** Service `observable-agent` → Span Name `POST /ask` → **Min Duration** `1.5s` → **Find Traces** → ở chế độ *Table* bấm cột **Duration** để trace dài nhất lên đầu → mở trace khoảng 1,7 s.
(Không đặt Min Duration thì chỉ sắp xếp trong số kết quả được trả về, mặc định 20, nên có thể không thấy trace chậm.)

> **Nói:** "Span `chat mock-llm-small` chiếm gần hết thời gian, retrieval chỉ vài chục ms. Chậm ở bước gọi LLM."

**Trace lỗi:** xoá Min Duration, ô **Attributes** nhập `error=true` → **Find Traces** → mở một trace → bấm span `chat` → **Details** → **Events** → `exception`.

**Từ log sang trace:**

```powershell
cd D:\Vin\K5-L3B-DAY14-BuiThaiSy-2A202604002-Deployment-Benchmark-Observability\06-lab-complete\benchmark-observability\production
docker compose -p k5-day14-observability logs --since 5m agent | Select-String llm_error | Select-Object -Last 1
```

Copy `trace_id`, dán vào ô **Lookup by Trace ID** của Jaeger.

- Nếu thời lượng span lệch nhiều so với `ms` trong log, chọn trace khác. Đã gặp 3/15 trace bị lệch (xem mục 4.3 của `BENCHMARK_REPORT.md`; nguyên nhân chưa xác nhận).
- Hai `trace_id` ghi trong báo cáo chỉ còn khi container Jaeger chưa bị tắt hoặc tạo lại.

---

## 5. Alert (8')

### Cách hoạt động

```
inactive → pending (điều kiện đúng) → firing (đúng liên tục đủ thời gian "for")
```

| Alert | Điều kiện | `for` | Cách test | Đã đo: tới lúc firing | Tắt sau khi khôi phục |
|---|---|---|---|---:|---:|
| `AgentHighErrorRate` | lỗi 5xx > 5% (cửa sổ 1 phút) | 1m | `MOCK_ERROR_RATE=0.2` | 90 s | 45 s |
| `AgentHighLatencyP95` | p95 > 1 s (cửa sổ 1 phút) | 2m | `MOCK_SLOW_RATE=0.3` | 143 s | 55 s |
| `AgentInstanceDown` | `up == 0` | 30s | `docker pause` | 39 s | 5 s |
| `LLMCostBurnRateHigh` | > 2 USD/giờ (cửa sổ 5 phút) | 2m | tải ≥ 30 user đã đủ | — | — |

Thời gian có thể xê dịch vài chục giây.

Mọi lệnh dưới đây chạy trong `production\`. Giữ Locust **30 user**.

```powershell
cd D:\Vin\K5-L3B-DAY14-BuiThaiSy-2A202604002-Deployment-Benchmark-Observability\06-lab-complete\benchmark-observability\production
```

### Thí nghiệm D — mất 1 instance (làm trước vì nhanh nhất)

```powershell
docker pause k5-day14-observability-agent-1
```

Xem: Prometheus Alerts (`pending` → `firing`, khoảng 40 s), Grafana **Instances up** 2 → 1, tab **Failures** của Locust (có lỗi 504).

Khôi phục (**bắt buộc**):

```powershell
docker unpause k5-day14-observability-agent-1
```

> **Nói:** "Dùng `pause` chứ không `stop`: container bị stop biến mất khỏi DNS nên Prometheus không còn target để báo down. Lỗi 504 sinh ra ở Nginx nên metric của agent không đếm: lúc đo, Nginx có 27 lỗi 504 nhưng error rate của agent vẫn ở mức nền."

### Thí nghiệm A + B — hai alert cùng firing

Làm gộp để tiết kiệm thời gian; cả hai firing sau khoảng 2,5–3 phút.

```powershell
"MOCK_ERROR_RATE=0.2","MOCK_SLOW_RATE=0.3" | Set-Content .env -Encoding ascii
docker compose -p k5-day14-observability up -d --no-deps --scale agent=2 agent
```

Đã đo khi bật cùng lúc: `AgentHighErrorRate` sau **93 s**, `AgentHighLatencyP95` sau **151 s**.

Trong lúc chờ, chỉ Grafana: Error rate tăng lên gần 19–20%; p95 tăng lên khoảng 1,9 s; trung bình tăng ít hơn p95.

> **Nói:** "`for` giúp không báo động vì một spike ngắn. Error rate chờ 1 phút, latency chờ 2 phút."

Khôi phục (**bắt buộc**):

```powershell
Remove-Item .env
docker compose -p k5-day14-observability up -d --no-deps --scale agent=2 agent
```

> Luôn giữ `--no-deps --scale agent=2 agent` để chỉ tạo lại agent, không đụng đến Jaeger (giữ được trace).

Muốn demo từng alert riêng: chỉ ghi một dòng vào `.env`, ví dụ `"MOCK_ERROR_RATE=0.2" | Set-Content .env -Encoding ascii`.

### `LLMCostBurnRateHigh`

Ở tải 30 user, chi phí ước tính khoảng 2,5 USD/giờ nên alert **đã firing sẵn**.

> **Nói:** "Đây là một phát hiện: ngưỡng 2 USD/giờ thấp hơn mức chi bình thường của lab nên alert luôn kêu. Nên đặt ngưỡng cao hơn mức nền, hoặc cảnh báo theo cost trên mỗi request. Khi đổi sang `mock-llm-large`, cost (cửa sổ 1 phút) tăng từ 2,5 lên 37,2 USD/giờ."

Muốn cho thấy nó **chuyển từ inactive sang firing** *(chưa thử, tập trước nếu định demo; mất khoảng 10 phút nên không hợp demo ngắn)*:
1. Locust: **STOP**, Start lại `10` user; đợi khoảng 5–6 phút tới khi alert `inactive`.
2. `"LLM_MODEL=mock-llm-large" | Set-Content .env -Encoding ascii` rồi chạy lệnh `up -d --no-deps ...` ở trên; đợi alert firing.
3. Khôi phục như trên, đưa Locust về 30 user.

### Thí nghiệm E — lỗi chất lượng, không alert nào kêu (tuỳ chọn, 3')

```powershell
"AGENT_VERSION=v1" | Set-Content .env -Encoding ascii
docker compose -p k5-day14-observability up -d --no-deps --scale agent=2 agent
```

Xem: **Retrieval hit ratio** mất dữ liệu, **Tokens/s** giảm khoảng một nửa, bảng **Phiên bản đang chạy** đổi sang v1. Không alert nào firing (lúc tạo lại container, `AgentInstanceDown` có thể `pending` một lúc).

> **Nói:** "v1 vẫn trả 200, còn nhanh và rẻ hơn, nên metric hạ tầng không thấy gì. Chỉ eval ở Phần 2 mới bắt được: v1 đúng 1/23."

Khôi phục như thí nghiệm A + B.

---

## 6. Dọn dẹp

1. Locust: **STOP**.
2. Kiểm tra đã khôi phục:

```powershell
Test-Path .env                                            # False
docker ps --filter status=paused --format "{{.Names}}"    # không in gì
```

3. Tắt stack khi không dùng nữa (mất dữ liệu metric và trace):

```powershell
docker compose -p k5-day14-observability down -v
```

---

## Xử lý sự cố khi demo

| Hiện tượng | Kiểm tra |
|---|---|
| Alert mãi `inactive` | Locust có đang RUNNING không; đã đợi đủ thời gian `for` chưa; chạy `docker compose -p k5-day14-observability exec agent env` và tìm biến `MOCK_` |
| Alert mãi `pending` | Chưa đủ `for`, hoặc giá trị dao động quanh ngưỡng |
| Latency alert không firing khi chỉ tăng user | p95 phía agent phải > 1 s **liên tục 2 phút**; dùng `MOCK_SLOW_RATE=0.3` |
| Grafana "No data" | Chưa có traffic, hoặc chọn sai khoảng thời gian |
| Locust báo lỗi ở dòng `/auth/token` (và không có `/ask`) | `AUTH_USERNAME` / `AUTH_PASSWORD` của Locust khác của agent; cả hai đọc cùng biến trong `.env`, sửa xong chạy lại `docker compose up -d` |
| Locust báo 401 ở dòng `/ask` | Token hết hạn hoặc agent đổi `JWT_SECRET` giữa chừng; user tự đăng nhập lại, nếu vẫn lỗi thì restart Locust |
| Render phản hồi rất chậm | Service vừa ngủ; gọi `/health` và đợi |
| Lệnh có key trả 401 | Biến key sai; làm lại bước 0.5, kiểm tra độ dài |

**PromQL dán vào http://localhost:9090/query khi cần:**

```promql
sum(rate(http_requests_total{route="/ask",status=~"5.."}[1m])) / sum(rate(http_requests_total{route="/ask"}[1m]))
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{job="agent",route="/ask"}[1m])))
sum(up{job="agent"})
sum(rate(llm_cost_usd_total{job="agent"}[5m])) * 3600
```

---

## Câu hỏi có thể bị hỏi

| Câu hỏi | Ý trả lời |
|---|---|
| Vì sao SLO theo p95 chứ không theo trung bình? | Trung bình trộn request chậm vào số đông. Khi 10% request chậm: trung bình 360 ms nhưng p95 1707 ms. |
| p95 đạt mà vẫn có người dùng chờ lâu? | Nhóm chậm dưới 5% nằm sau mốc p95; xem thêm p99. |
| Vì sao scale 1 lên 3 không tăng RPS? | Tải bị giới hạn bởi số user và thời gian nghỉ; 1 agent chưa quá tải; thời gian chủ yếu là chờ LLM. |
| Lệnh scale trong tài liệu có vấn đề gì? | `docker compose run locust` đưa agent về `replicas: 2`; phải thêm `--no-deps`. |
| Vì sao rate limit và cost guard lưu trong Redis? | Nhiều worker và instance dùng chung, restart không mất. |
| Graceful shutdown hoạt động thế nào? | uvicorn nhận SIGTERM, ngừng nhận request mới, chờ request đang chạy rồi mới tắt; không tự ghi đè handler. |
| Hạn chế của cost guard? | Ngân sách dùng chung mọi key; request đồng thời có thể làm vượt một chút; số token là ước lượng. |
