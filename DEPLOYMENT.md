# Deployment Information

## Public URL

https://day14-agent-x6yb.onrender.com

## Platform

Render, deploy bằng Blueprint từ nhánh `dev`.

- Blueprint Path: [`06-lab-complete/render.yaml`](06-lab-complete/render.yaml)
- Web service `day14-agent`: build từ [`06-lab-complete/Dockerfile`](06-lab-complete/Dockerfile), health check `/health`
- Redis: Render Key Value `day14-redis` (dashboard ghi runtime Valkey 8, tương thích giao thức Redis), chỉ truy cập từ mạng nội bộ (`ipAllowList: []`)
- Region: Oregon

Service dùng gói free nên tạm ngủ khi không có traffic. Theo thông báo trên dashboard, request đầu sau đó có thể chậm từ 50 giây trở lên; gọi `/health` một lần để đánh thức trước khi test.

## Test Commands

Chạy trên Windows PowerShell. Đặt biến `AGENT_API_KEY` bằng key trên Render (tab Environment) trước khi chạy lệnh cuối; không ghi key vào file.

```powershell
$BASE = "https://day14-agent-x6yb.onrender.com"
$body = '{\"question\":\"Hello\"}'
curl.exe -sS -o NUL -w "/health          %{http_code}\n" "$BASE/health"
curl.exe -sS -o NUL -w "/ready           %{http_code}\n" "$BASE/ready"
curl.exe -sS -o NUL -w "/ask khong key   %{http_code}\n" -X POST "$BASE/ask" -H "Content-Type: application/json" -d $body
curl.exe -sS -o NUL -w "/ask co key      %{http_code}\n" -X POST "$BASE/ask" -H "Content-Type: application/json" -H "X-API-Key: $env:AGENT_API_KEY" -d $body
```

Bản tương đương cho bash:

```bash
BASE=https://day14-agent-x6yb.onrender.com
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

### Kết quả

```text
/health          200
/ready           200
/ask khong key   401
/ask co key      200
```

`/ready` trả 200 cho thấy agent kết nối được Redis trên Render.

## Environment Variables Set

| Biến | Nguồn giá trị |
|---|---|
| `AGENT_API_KEY` | Render tự sinh (`generateValue: true`), không có trong code |
| `REDIS_URL` | Lấy từ `connectionString` của `day14-redis` (`fromService`) |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` |
| `PORT` | Render cấp, không khai báo trong `render.yaml` |

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
