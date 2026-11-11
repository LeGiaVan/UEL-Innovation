# Chatbot Phòng Nhân sự

Hạ tầng chuyển từ `Frontend/chatbot-web`: React 18, Vite 5, React Router, Redux Toolkit, Axios, Markdown và SSE. Frontend kết nối nền tảng FastAPI dùng chung tại `../chatbot-api`.

## Chạy

Trong workspace hiện tại, thư viện dùng liên kết `node_modules` tới TVTS. Chạy `npm run dev`, mở http://localhost:5176.
Khi chuyển sang máy khác, bỏ liên kết `node_modules` rồi chạy `npm ci`.

```sh
npm run dev
npm test
npm run build
```

Dev mặc định dùng API mô phỏng. Production mặc định gọi API thật. Để build bản demo: `VITE_MOCK_API=true npm run build`.

## Cấu trúc (cùng cấp với Frontend/chatbot-web)

```text
src/
  main.jsx                   # Provider + store
  App.jsx                    # BrowserRouter + Routes
  layouts/MainLayout.jsx     # Header, drawer, Outlet, theme
  pages/BotChatPage.jsx       # slug -> selectedMode
  components/                # Header, Sidebar, ChatInterface, MessageList,
                             # MessageInput, DepartmentHub, Markdown, ...
  store/store.js             # chat + mode + qa
  store/slices/              # chatSlice, modeSlice, qaSlice
  api/                       # client.js, mockApi.js (bổ sung)
  config/                    # department.json, featureIdentity, botNav
  constants/                 # chatModes
  context/                   # FeatureThemeContext
  utils/                     # sessionLog, SSE, Markdown, ...
  styles/                    # CSS TVTS
public/
tests/infrastructure.mjs
Dockerfile
nginx.conf
vite.config.js
.env.example
```

`department.json` giữ tên phòng và bốn chủ đề. `featureIdentity.js` ánh xạ chủ đề sang route và `module_1`…`module_4`. Sáu phòng dùng chung backend FastAPI tại `../chatbot-api`; module IDs được hiểu trong phạm vi `X-Department-ID` sau khi backend xác thực membership.

## Luồng dữ liệu

Route → BotChatPage → modeSlice → ChatInterface → sendMessage thunk → API `/chat/stream` → token/done → chatSlice → MessageList. MainLayout tải modes và FAQ qua thunks. Component chỉ giữ trạng thái UI (ô nhập, drawer); hội thoại, trạng thái tải, lỗi và rate limit nằm trong Redux.

Lịch sử theo chủ đề nằm trong Redux trong phiên; sessionLog lưu danh sách ID/preview theo khóa riêng của phòng. `fetchConversation` và `fetchConversationList` giữ endpoint tương thích TVTS. Mock lưu hội thoại trong bộ nhớ, tải lại trang sẽ mất.

## API thật

Sao chép `.env.example` thành `.env.local`, đặt `VITE_MOCK_API=false`, `VITE_API_URL=/api` và `API_PROXY_TARGET` đến backend của phòng, rồi khởi động lại Vite. Các biến `VITE_*` là công khai trong bundle, không đặt secret ở đây.

- `GET /api/chat/modes` → `{"modes":[{"id":"module_1","label":"..."}]}`
- `GET /api/qa` → `[{"id":"1","mode":"module_1","question":"...","answer":"..."}]`
- `POST /api/chat/stream` ← `{"message":"...","conversation_id":null,"mode":"module_1"}`
- SSE: `data: {"type":"token","text":"..."}` rồi dòng trống; kết thúc bằng `data: {"type":"done","response":"...","conversation_id":"...","resolved_mode":"module_1","citations":[]}`.
- SSE lỗi: `{"type":"error","message":"..."}`; giới hạn: `{"type":"rate_limited","retry_after_sec":60,"reason":"..."}`.
- `GET /api/conversations?limit=200` → `{"conversations":[]}`
- `GET /api/conversations/:id` → `{"conversation_id":"...","messages":[{"user_message":"...","assistant_response":"...","timestamp":"..."}]}`

Không tự chuyển về mock khi API thật lỗi. API dùng chung đã được kiểm thử tích hợp với cả sáu frontend bằng tài khoản và database tạm; xem mục Backend dùng chung để cấu hình đăng nhập.

## Phần kế thừa và điều chỉnh

Giữ toàn bộ tập tin nguồn TVTS trong cùng các thư mục, gồm cả module tuyển sinh tham chiếu (quiz, tính điểm, survey, registration). Các module đó không được đưa vào routing của phòng. Header, Sidebar, ChatInterface và feature config được điều chỉnh theo phòng; bổ sung DepartmentHub và lớp API chung. Không gọi mặc định đến máy chủ TVTS.

Nguồn TVTS được cung cấp thiếu một số ảnh `docs/image_*` và có symlink ảnh bị đứt. Bản phòng không dùng các ảnh thiếu trong giao diện đang hoạt động; import ảnh của module tham chiếu chuyển thành URL public. Muốn bật lại module tuyển sinh phải bổ sung ảnh và backend tương ứng.

## Triển khai

`docker build -t chatbot-pns .` từ thư mục này. Docker production mặc định dùng API thật. Nginx kế thừa proxy SSE không buffer và SPA fallback từ TVTS; upstream mặc định `api:30957`, cần đặt service backend tương ứng khi triển khai. Docker chưa được chạy thử trong môi trường này.

Bản FE cũ được lưu tại `../migration-backup/chatbot-PNS` trước khi chuyển đổi.

## Backend dùng chung

Nền tảng FastAPI tại `../chatbot-api`, mặc định cổng 30957. Đặt `VITE_MOCK_API=false` trong `.env.local` và chạy `npm run dev` để hiện đăng nhập. API client tự gửi `X-Department-ID: pns` và Bearer token. Backend kiểm tra membership theo tài khoản, header không tự cấp quyền. Token chỉ giữ trong bộ nhớ; tải lại trang cần đăng nhập lại. Đăng xuất hoặc 401 xóa Redux; lịch sử phía server vẫn được bảo vệ theo chủ sở hữu. Không đặt mật khẩu hoặc token trong biến VITE.
