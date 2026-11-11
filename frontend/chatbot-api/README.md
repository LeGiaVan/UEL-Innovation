# Backend nền tảng cho bảy chatbot UEL

FastAPI dùng chung cho ĐBCL (`dbcl`), QTTS (`qtts`), PĐT (`pdt`), PNS (`pns`), HC (`hc`), CTSV (`ctsv`) và KHCN (`khcn`). Entry point mới là **`app.main:app`**, chạy từ thư mục `chatbot-api` ngoài cùng. Thư mục lồng `chatbot-api/chatbot-api` là bản TVTS tham chiếu có sẵn, không được import hay khởi chạy bởi ứng dụng mới; không dùng `.env`, dữ liệu cache hoặc khóa của bản đó.

## Môi trường đã thiết lập trong workspace

Đã tạo `.env` cho backend và `.env.local` cho bảy frontend, cùng trỏ backend tới cổng **30957**. Nếu đang kích hoạt `Chatbot/venv`, có thể tiếp tục dùng môi trường đó; bộ thư viện trong `requirements.lock` đã được cài, gồm `pwdlib` và `argon2-cffi`.

Từ thư mục `chatbot-api`, chạy:

```sh
./run-dev.sh
```

Script dùng virtualenv đang kích hoạt, hoặc `chatbot-api/.venv` nếu chưa kích hoạt môi trường nào. Script luôn gọi `python -m uvicorn` và chọn cổng 30957, tránh nhầm interpreter/cổng 8000. Nếu terminal còn chạy Uvicorn lỗi trước đó, nhấn Ctrl+C rồi chạy lại. Khởi động lại Vite để nạp `.env.local` mới.

## Tạm bỏ đăng nhập

Workspace hiện bật `CHATBOT_AUTH_DISABLED=true` trong backend `.env` và `VITE_AUTH_DISABLED=true` trong `.env.local` của bảy FE. Khởi động lại backend/Vite để áp dụng. FE vẫn gọi backend thật. Người truy cập dùng chung danh tính khách phát triển, có quyền chat cả bảy phòng; lịch sử khách trong cùng phòng cũng dùng chung. Hội thoại của tài khoản đã đăng nhập vẫn được cách ly, API quản trị vẫn yêu cầu quyền admin.

Để bật lại đăng nhập, đặt cả hai biến về `false` và khởi động lại. Mặc định trong code và `.env.example` vẫn yêu cầu xác thực; backend từ chối bật chế độ khách trong production, FE chỉ bỏ gate khi chạy dev.

## Chạy local

Yêu cầu Python >=3.11; bộ thư viện khóa hiện được kiểm thử với Python 3.14.

```sh
cd chatbot-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.cli create-user --username admin --system-admin \
  --department dbcl --department qtts --department pdt \
  --department pns --department hc --department ctsv --department khcn --role department_admin
uvicorn app.main:app --host 127.0.0.1 --port 30957 --no-proxy-headers --no-access-log
```

Lệnh tạo tài khoản hỏi mật khẩu hai lần, yêu cầu tối thiểu 12 ký tự. Không có tài khoản/mật khẩu mặc định, không có endpoint đăng ký tự do. Có thể tạo user thường bằng CLI hoặc `POST /api/admin/users` sau khi đăng nhập admin. `--department` lặp lại để cấp quyền nhiều phòng.

- Swagger: http://127.0.0.1:30957/docs (tắt khi production).
- Liveness: `/health/live`; readiness ping database đang chọn: `/health/ready`.
- Mặc định dùng MongoDB (`CHATBOT_DATABASE_BACKEND=mongodb`); URI và tên database cấu hình bằng `CHATBOT_MONGODB_URI`, `CHATBOT_MONGODB_DATABASE`. MongoDB lưu user, memberships, sessions, rate limits, audit events và conversations/messages.
- SQLite chỉ dành cho test (`CHATBOT_DATABASE_BACKEND=sqlite`); schema v1 tự khởi tạo trong `data/chatbot.sqlite3`. Các bài test API dùng SQLite tạm và không cần MongoDB.
- Access log ghi method, path (không gồm query string), status, thời gian xử lý và request ID. Không ghi request/response body, credentials hoặc token. Điều chỉnh mức log bằng `CHATBOT_LOG_LEVEL`.
- `python -m app.cli cleanup` xóa sessions và cửa sổ rate limit hết hạn; có thể gọi từ lịch vận hành bên ngoài. Không tự xóa hội thoại.

## Kết nối bảy frontend

Trong từng frontend, tạo `.env.local`:

```dotenv
VITE_MOCK_API=false
VITE_API_URL=/api
API_PROXY_TARGET=http://127.0.0.1:30957
```

Khởi động lại `npm run dev`. Các cổng lần lượt 5173…5179. FE hiện trang đăng nhập, tự gửi `Authorization: Bearer <token>` và `X-Department-ID` theo `src/config/department.json`. Không đặt mật khẩu hoặc token vào biến `VITE_*`.

Token truy cập ngẫu nhiên 256-bit được lưu **chỉ trong bộ nhớ FE**; DB chỉ lưu SHA-256 của token. Tải lại trang cần đăng nhập lại; logout thu hồi token trên server và reset Redux. HTTP 401 đưa về đăng nhập; 403 báo thiếu quyền; HTTP 429/Retry-After khóa ô gửi theo thời gian chờ. Không tự fallback sang mock khi API lỗi. Server không tin mã phòng từ trình duyệt nếu tài khoản không có membership.

## Cấu trúc và trách nhiệm

```text
app/
  main.py                 # app factory, lifespan, middleware, health, error handling
  api/
    router.py             # prefix /api
    dependencies.py       # current user, department scope, RBAC
    routes/
      auth.py             # login/me/logout
      chat.py             # modes/QA/SSE
      conversations.py    # list/detail/delete
      admin.py            # users, memberships, revoke sessions
  core/
    config.py             # Pydantic Settings, CHATBOT_ env prefix
    security.py           # Argon2 password hash, token hashing
    middleware.py         # bounded body, request ID, security headers
  models/identity.py      # internal Principal / DepartmentContext
  schemas/api.py          # validated request/response DTOs and enums
  db/
    database.py           # transaction/connection lifecycle, SQLite WAL
    migrations.sql        # versioned initial schema v1
  repositories/           # parameterized SQL, user and conversation persistence
  services/               # auth, chat, catalog, provider, rate limiting, audit
  data/departments.json   # seven department catalogs copied from frontend
  cli.py                  # bootstrap user, maintenance cleanup
 tests/                   # backend and live FE integration tests
```

Luồng chat: router → auth dependency → membership → rate limit → ChatService → provider → repository transaction → SSE. Mọi query hội thoại có cả `user_id` và `department`; module cũng phải trùng khi tiếp tục hội thoại. ID ngoài phạm vi trả 404 để không xác nhận sự tồn tại.

## Phân quyền

| Quyền | Phạm vi |
|---|---|
| `member` | Modes/QA và hội thoại của chính mình trong phòng được cấp |
| `department_admin` | Quyền member + xem danh sách thành viên của phòng mình |
| `system_admin` | Tạo user, cấp/thu hồi membership, thu hồi sessions |

System admin vẫn cần membership rõ ràng để chat trong một phòng và không được đọc hội thoại của người khác. Department admin không thể tự tạo tài khoản hay cấp thêm quyền. Membership được kiểm tra từ DB mỗi request, nên thu hồi có hiệu lực ngay ở request tiếp theo. Phiên mặc định một giờ; logout/revoke sessions không cần chờ token hết hạn.

## Hợp đồng API

Tất cả `/api/*` ngoài login yêu cầu Bearer token. Chat, QA, hội thoại và danh sách thành viên còn yêu cầu `X-Department-ID`.

| Method | Endpoint | Dữ liệu / kết quả |
|---|---|---|
| POST | `/api/auth/login` | `{username,password}` → `{access_token,token_type,expires_in,user}` |
| GET | `/api/auth/me` | User và memberships hiện tại |
| POST | `/api/auth/logout` | Thu hồi session hiện tại; 204 |
| GET | `/api/departments` | Chỉ các phòng user được cấp |
| GET | `/api/chat/modes` | `{modes:[{id,label,bot_name,description}]}` |
| GET | `/api/qa` | `[{id,mode,question,answer}]` |
| POST | `/api/chat/stream` | `{message,conversation_id:null,mode:"module_1"}` → SSE |
| GET | `/api/conversations?limit=30&offset=0` | `{conversations:[{id,conversation_id,mode,preview,created_at,updated_at}]}` |
| GET | `/api/conversations/{id}` | `{conversation_id,mode,messages:[{user_message,assistant_response,timestamp}]}` |
| DELETE | `/api/conversations/{id}` | Xóa hội thoại thuộc user và phòng hiện tại; 204 |
| POST | `/api/admin/users` | `{username,password,memberships:[{department,role}]}`; chỉ system admin |
| PUT | `/api/admin/users/{id}/memberships/{department}` | `{role:"member"}`; chỉ system admin |
| DELETE | `/api/admin/users/{id}/memberships/{department}` | Thu hồi quyền phòng; chỉ system admin |
| DELETE | `/api/admin/users/{id}/sessions` | Thu hồi mọi session của user; chỉ system admin |
| GET | `/api/departments/members` | Danh sách thành viên; department admin |

Mã mode `module_1`…`module_4` được diễn giải theo phòng, không ánh xạ sang module tuyển sinh TVTS. Schema cấm field lạ như tự truyền `user_id`, `department` trong body chat hoặc `system_admin` khi tạo user. Message 1–4000 ký tự, ID hội thoại UUID, `limit` tối đa 200.

SSE UTF-8, mỗi event kết thúc bằng hai newline:

```text
data: {"type":"token","text":"[Phản hồi mô phỏng] ..."}

data: {"type":"done","response":"...","conversation_id":"uuid","user_message":"...","resolved_mode":"module_1","citations":[],"contact_info":null,"interactive":null,"provider":"stub"}

```

Auth, validation, ownership, rate limit và lỗi provider hiện được xử lý **trước khi gửi HTTP 200**. Sai quyền: 403/404; sai mode hội thoại: 409; validation: 422; vượt hạn mức: 429 kèm `Retry-After`. Mỗi lượt trả lời stub được ghi DB nguyên tử trước khi stream; nếu mất kết nối, lượt đã ghi vẫn xuất hiện trong lịch sử. Chưa có idempotency key: gửi lại request có thể tạo thêm lượt, FE không tự retry POST.

## Bảo mật đã triển khai

- Password Argon2; opaque Bearer sessions được băm trong DB, có expiry và revoke. Không dùng secret nhúng trong FE.
- Truy vấn SQL có tham số; scope người dùng + phòng trong repository; role được kiểm tra server-side.
- Login rate limit theo IP thật tại socket và tên tài khoản; chat theo user + phòng, lưu DB dùng transaction để tránh vượt hạn mức do ghi đồng thời. Mặc định 10 login/phút và 30 chat/phút.
- Chặn body lớn cả khi không có Content-Length; whitelist CORS/Host; no-store, nosniff, request ID; HSTS khi production.
- Validation không phản chiếu password/body nhạy cảm; audit chỉ lưu actor/action/department/target/time, không ghi chat/token/password. Nội dung chat chỉ nằm trong bảng messages phục vụ lịch sử.
- Backend không tự nhận user, role hoặc phòng từ nội dung prompt. Chưa có file upload, fetch URL đầu vào hay thực thi tác vụ nghiệp vụ.

Compose khởi động MongoDB cùng FastAPI và lưu dữ liệu MongoDB bằng Docker volume. Cấu hình MongoDB trong `.env` để backend Python chạy local; khi dùng Docker Compose, API kết nối tới service `mongo`. SQLite còn được giữ cho test tương thích và có thể gỡ sau khi không còn cần.

Đây là nền tảng local/single-host; cấu hình MongoDB mặc định ở Compose không bật xác thực nên chỉ dành cho phát triển local. Production phải dùng MongoDB có xác thực/TLS, credential qua secret manager và backup phù hợp. Nội dung chat chưa mã hóa ở cấp ứng dụng. Chưa có SSO/OIDC, password reset, MFA, chính sách retention tự động hay refresh token. Bảo vệ TLS ở reverse proxy; chỉ tin proxy headers từ proxy đã cấu hình, không bật trust toàn bộ IP. Không công bố service development trực tiếp ra Internet.

## Điểm mở rộng tài liệu/LLM

`services/providers.py` định nghĩa `AnswerProvider`; hiện chỉ `StubAnswerProvider` và mọi câu trả lời ghi rõ mô phỏng. Chưa tạo đơn, gửi email hay thay đổi nghiệp vụ. Khi có dữ liệu: bổ sung ingestion/worker riêng, phân quyền tài liệu theo department, retrieval trong phạm vi phòng và provider LLM sau lớp kiểm tra quyền. Không lấy department hoặc user identity từ đầu ra LLM. Streaming provider thật cần bổ sung trạng thái interrupted/error, timeout, cancellation và idempotency; stub hiện không giả vờ có các khả năng đó.

`app/data/departments.json` là snapshot của cấu hình bảy frontend. Khi đổi danh mục nghiệp vụ cần cập nhật cả FE và catalog backend hoặc chuyển sang quản lý tập trung.

## Kiểm thử

```sh
python -m pytest -q
python -m tests.run_frontend_integration
```

Backend test bao phủ hợp đồng bảy phòng, quyền sở hữu, đổi phòng/mode, giả mạo token, hết hạn/logout, thu hồi membership/session, role escalation, validation, rate limit, CORS/Host, body limit, persistence và concurrent writes.

Live integration tự tạo DB và tài khoản tạm, mở server tại 127.0.0.1:30958, chạy Redux/API client thật của cả bảy FE (login → modes/QA → SSE → history → logout), rồi tự dừng server và xóa DB tạm. Cần Node và node_modules của các frontend. Test này không thay thế kiểm thử UI bằng trình duyệt.

## Docker

```sh
docker compose up --build -d
docker compose exec api python -m app.cli create-user --username admin --system-admin --department hc --role department_admin
```

Compose là cấu hình local, bind API vào loopback và dùng volume lưu MongoDB. Container API chạy user không phải root, không có Linux capabilities. Production phải đặt `CHATBOT_ENVIRONMENT=production`, danh sách origins HTTPS và allowed hosts cụ thể, MongoDB authentication/TLS, TLS reverse proxy và backup. Các nginx.conf frontend hiện proxy tới service `api:30957`; đặt frontend/backend chung Docker network khi triển khai. Docker artifacts chưa được chạy thử tại môi trường hiện tại.

Tham khảo chính thức: [FastAPI bigger applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/), [security dependencies và password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [CORS](https://fastapi.tiangolo.com/tutorial/cors/). Backend này dùng opaque session token để thu hồi tức thời, không triển khai OAuth authorization server hay JWT.

## Test nhanh phản hồi hello

Khi chế độ khách đang bật, gọi API thật bằng:

```sh
curl -N http://127.0.0.1:30957/api/chat/stream \
  -H 'Content-Type: application/json' \
  -H 'X-Department-ID: hc' \
  -d '{"message":"hello","mode":"module_1","conversation_id":null}'
```

API trả SSE `token` và `done`, câu trả lời bắt đầu bằng “Xin chào, đây là chatbot Phòng Hành chính…”. Đổi header thành `dbcl`, `qtts`, `pdt`, `pns`, `ctsv`, `khcn` để kiểm thử phòng tương ứng. Khi bật lại xác thực, thêm header Bearer token. Lời chào cũng nhận `hi`, `xin chào`, chữ hoa và dấu câu cuối câu.
