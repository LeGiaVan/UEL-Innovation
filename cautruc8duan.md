# Cấu trúc dự án chatbot cho 8 đơn vị UEL

> Trạng thái: cấu trúc đề xuất để trình bày và thống nhất triển khai. Tài liệu này không thay đổi mã nguồn, thư mục hoặc database hiện tại.

## 1. Phạm vi và nguyên tắc tổ chức

Danh sách gồm **8 đơn vị**, chia thành ba nhóm phân công:

| Nhóm | Đơn vị |
|---|---|
| 1 | Phòng Hành chính; Phòng Tuyển sinh & Công tác sinh viên |
| 2 | Phòng Đào tạo; Phòng Quản trị Tài sản; Viện Quốc tế |
| 3 | Phòng Nhân sự; Phòng Khoa học Công nghệ; Phòng Bảo đảm chất lượng |

Mỗi đơn vị có một thư mục riêng, bên trong gồm:

- `chatbot-web`: giao diện React–Vite, Redux Toolkit và Redux Thunk.
- `chatbot-api`: backend FastAPI, xử lý nghiệp vụ và RAG, lưu dữ liệu nghiệp vụ bằng MongoDB theo thiết kế đích.
- `chatbot-data`: tài liệu nguồn theo module và phiên bản phát hành.
- `docker-compose.yml`: cấu hình chạy các thành phần của đơn vị.
- `README.md`: hướng dẫn cấu hình, chạy và bàn giao.

Cách chia ba phần kế thừa mô hình của các dự án trước, đặc biệt TVTS. Cấu trúc chi tiết bên dưới là đề xuất chuẩn hóa cho dự án này, không phải bản sao nguyên trạng của các dự án tham chiếu.

Ba nhóm trên là nhóm phân công; cây thư mục được chia trực tiếp theo từng đơn vị. Mỗi đơn vị có thể phát triển, cấu hình và triển khai độc lập.

## 2. Cây tổng thể

```text
uel-innovation/
│
├── phong-hanh-chinh/
│   ├── chatbot-web/
│   ├── chatbot-api/
│   ├── chatbot-data/
│   ├── docker-compose.yml
│   └── README.md
│
├── phong-tuyen-sinh-cong-tac-sinh-vien/
│   ├── chatbot-web/
│   ├── chatbot-api/
│   ├── chatbot-data/
│   ├── docker-compose.yml
│   └── README.md
│
├── phong-dao-tao/
│   ├── chatbot-web/
│   ├── chatbot-api/
│   ├── chatbot-data/
│   ├── docker-compose.yml
│   └── README.md
│
├── phong-quan-tri-tai-san/
│   ├── chatbot-web/
│   ├── chatbot-api/
│   ├── chatbot-data/
│   ├── docker-compose.yml
│   └── README.md
│
├── vien-quoc-te/
│   ├── chatbot-web/
│   ├── chatbot-api/
│   ├── chatbot-data/
│   ├── docker-compose.yml
│   └── README.md
│
├── phong-nhan-su/
│   ├── chatbot-web/
│   ├── chatbot-api/
│   ├── chatbot-data/
│   ├── docker-compose.yml
│   └── README.md
│
├── phong-khoa-hoc-cong-nghe/
│   ├── chatbot-web/
│   ├── chatbot-api/
│   ├── chatbot-data/
│   ├── docker-compose.yml
│   └── README.md
│
├── phong-bao-dam-chat-luong/
│   ├── chatbot-web/
│   ├── chatbot-api/
│   ├── chatbot-data/
│   ├── docker-compose.yml
│   └── README.md
│
├── docs/                       # Kiến trúc và quy ước chung
└── README.md                   # Danh mục và hướng dẫn toàn dự án
```

## 3. Frontend — chatbot-web

Mỗi đơn vị có một ứng dụng **React–Vite, Redux Toolkit và Redux Thunk**.

```text
chatbot-web/
├── public/
│   ├── images/                  # Logo, ảnh, biểu tượng
│   └── favicon.ico
│
├── src/
│   ├── api/
│   │   ├── client.js            # HTTP client, base URL, interceptor
│   │   ├── authApi.js           # API đăng nhập, đăng xuất
│   │   ├── chatApi.js           # API chat và SSE
│   │   └── conversationApi.js   # API lịch sử hội thoại
│   │
│   ├── components/
│   │   ├── common/              # Button, modal, loading, thông báo
│   │   ├── chat/                # Khung chat, tin nhắn, ô nhập, trích dẫn
│   │   └── navigation/          # Header, sidebar, danh sách module
│   │
│   ├── pages/
│   │   ├── LoginPage.jsx
│   │   ├── ChatPage.jsx
│   │   └── NotFoundPage.jsx
│   │
│   ├── layouts/
│   │   └── MainLayout.jsx
│   │
│   ├── routes/
│   │   ├── AppRoutes.jsx
│   │   └── ProtectedRoute.jsx
│   │
│   ├── store/
│   │   ├── store.js
│   │   └── slices/
│   │       ├── authSlice.js
│   │       ├── chatSlice.js
│   │       ├── moduleSlice.js
│   │       └── conversationSlice.js
│   │
│   ├── config/
│   │   ├── department.js        # Tên đơn vị, nhận diện giao diện
│   │   └── navigation.js        # Điều hướng
│   │
│   ├── hooks/                  # Hook tái sử dụng
│   ├── utils/                  # SSE parser, định dạng nội dung
│   ├── styles/                 # CSS chung, màu sắc
│   ├── App.jsx
│   └── main.jsx
│
├── tests/
├── .env.example
├── package.json
├── package-lock.json
├── vite.config.js
├── index.html
├── Dockerfile
├── nginx.conf
└── README.md
```

Frontend của từng đơn vị chỉ hiển thị các module thuộc đơn vị đó. Danh sách module đang hoạt động lấy từ backend; `config/` giữ thông tin trình bày, không giữ mật khẩu, khóa LLM hoặc quyền truy cập thực tế.

Redux quản lý trạng thái đăng nhập, module được chọn, tin nhắn và lịch sử. Thunk gọi API và cập nhật trạng thái tải, thành công, thất bại. Frontend không kết nối trực tiếp MongoDB, Qdrant hoặc MinIO.

## 4. Backend — chatbot-api

Đề xuất mỗi đơn vị có **một ứng dụng FastAPI**, cung cấp API cho frontend và xử lý RAG. Đây là cấu trúc đích, khác với cấu trúc hiện tại đang chạy BFF và RAG thành hai dịch vụ.

```text
chatbot-api/
├── app/
│   ├── main.py                 # Entrypoint FastAPI
│   ├── factory.py              # Khởi tạo app, lifecycle, đăng ký router
│   │
│   ├── api/
│   │   ├── router.py           # Tổng hợp các router
│   │   ├── dependencies.py     # User, quyền truy cập, services
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── chat.py
│   │       ├── conversations.py
│   │       ├── modules.py
│   │       ├── documents.py
│   │       ├── admin.py
│   │       └── health.py
│   │
│   ├── core/
│   │   ├── config.py           # Đọc và kiểm tra biến môi trường
│   │   ├── security.py         # Mật khẩu, token, phân quyền
│   │   ├── logging.py
│   │   ├── middleware.py
│   │   └── exceptions.py
│   │
│   ├── schemas/                # Hợp đồng request/response
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── conversation.py
│   │   ├── module.py
│   │   └── document.py
│   │
│   ├── models/                 # Model dữ liệu lưu trong MongoDB
│   │   ├── user.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── module.py
│   │   ├── faq.py
│   │   ├── routing_rule.py
│   │   ├── document.py
│   │   └── sync_run.py
│   │
│   ├── db/
│   │   ├── mongodb.py          # Kết nối và quản lý MongoClient
│   │   ├── indexes.py          # Khai báo index
│   │   └── migrations/        # Migration dữ liệu có version
│   │
│   ├── repositories/          # Truy cập MongoDB
│   │   ├── users.py
│   │   ├── conversations.py
│   │   ├── messages.py
│   │   ├── modules.py
│   │   ├── knowledge.py
│   │   └── sync_runs.py
│   │
│   ├── services/              # Xử lý nghiệp vụ
│   │   ├── auth_service.py
│   │   ├── chat_service.py
│   │   ├── conversation_service.py
│   │   ├── module_service.py
│   │   ├── document_service.py
│   │   └── release_service.py
│   │
│   ├── rag/
│   │   ├── pipeline.py        # Điều phối quá trình trả lời
│   │   ├── routing.py         # Xác định module và phạm vi câu hỏi
│   │   ├── policy.py          # Quy tắc được trả lời/chuyển tiếp
│   │   ├── retrieval.py       # Tìm FAQ và nội dung liên quan
│   │   ├── generation.py      # Gọi LLM tạo câu trả lời
│   │   └── citations.py       # Chuẩn hóa nguồn trích dẫn
│   │
│   ├── ingestion/
│   │   ├── loaders/           # Bộ đọc XLSX, PDF, DOCX khi được hỗ trợ
│   │   ├── validation.py      # Kiểm tra schema và dữ liệu
│   │   ├── normalization.py   # Chuẩn hóa nội dung
│   │   ├── chunking.py        # Chia nội dung phục vụ tìm kiếm
│   │   └── pipeline.py        # Điều phối quá trình nạp
│   │
│   ├── integrations/
│   │   ├── llm.py             # Adapter nhà cung cấp LLM
│   │   ├── embeddings.py      # Adapter mô hình embedding
│   │   ├── qdrant.py          # Vector store
│   │   └── minio.py           # Object storage
│   │
│   └── cli.py                 # Tạo user, nạp dữ liệu, rebuild index
│
├── configs/
│   ├── department.yaml        # Mã và thông tin đơn vị
│   ├── modules.yaml           # Cấu hình khởi tạo các module
│   └── prompts/               # Prompt mẫu theo module
│
├── scripts/                   # Import/export, backup, migration
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
├── pyproject.toml
├── .env.example
├── Dockerfile
└── README.md
```

### Trách nhiệm các lớp

| Lớp | Trách nhiệm |
|---|---|
| `api/routes` | Nhận request, kiểm tra đầu vào, trả response |
| `schemas` | Định nghĩa dữ liệu giao tiếp với frontend |
| `services` | Điều phối nghiệp vụ |
| `repositories` | Đọc, ghi MongoDB |
| `models` | Định nghĩa dữ liệu lưu trữ |
| `rag` | Truy hồi và tạo câu trả lời |
| `ingestion` | Đọc, kiểm tra, chuẩn hóa và nạp tài liệu |
| `integrations` | Kết nối LLM, embedding, Qdrant, MinIO |

Cách phân lớp giữ mô hình quen thuộc `main → services`, đồng thời phân tách HTTP, nghiệp vụ và lưu trữ để tránh đưa toàn bộ xử lý vào `main.py`.

`configs/*.yaml` là cấu hình bootstrap/import/export. Khi áp dụng thiết kế MongoDB, cấu hình runtime đã công bố được quản lý trong MongoDB; không duy trì hai nguồn cấu hình độc lập cạnh tranh nhau.

## 5. Dữ liệu — chatbot-data

Mỗi đơn vị quản lý tài liệu theo **module nghiệp vụ và phiên bản phát hành**.

```text
chatbot-data/
├── README.md
│
├── templates/                      # Biểu mẫu chuẩn dùng để nhập dữ liệu
│   ├── module-template.xlsx
│   ├── faq-template.xlsx
│   └── document-template.xlsx
│
├── modules/
│   ├── <ma-module-1>/
│   │   ├── README.md               # Mô tả phạm vi module
│   │   └── releases/
│   │       └── <release-id>/
│   │           ├── source/         # File nguồn của phiên bản này
│   │           │   ├── module.xlsx
│   │           │   ├── faq.xlsx
│   │           │   └── documents.xlsx
│   │           ├── attachments/    # Tài liệu đính kèm, biểu mẫu
│   │           └── manifest.yaml   # Danh sách file, checksum, metadata
│   │
│   └── <ma-module-2>/
│       └── releases/
│           └── <release-id>/
│               ├── source/
│               ├── attachments/
│               └── manifest.yaml
│
├── staging/                        # File mới upload, chưa công bố
└── reports/                        # Báo cáo validation và ingestion
```

Tên file ở trên minh họa vai trò dữ liệu, không phải yêu cầu đổi tên các workbook hiện có. Khi triển khai cần thống nhất tên manifest với parser; hệ thống hiện tại dùng `release-manifest.yaml`.

Ví dụ Phòng Bảo đảm chất lượng:

```text
phong-bao-dam-chat-luong/
└── chatbot-data/
    └── modules/
        └── khao-khi/
            └── releases/
                └── release-001/
                    ├── source/
                    ├── attachments/
                    └── manifest.yaml
```

Tên thư mục minh họa có thể dùng dấu gạch ngang; mã nghiệp vụ backend hiện dùng dạng như `khao_khi`. Cần cấu hình ánh xạ rõ ràng, không tự đổi mã nghiệp vụ theo tên thư mục.

Tên và số lượng module của từng đơn vị được xác định theo nghiệp vụ thực tế; không bắt buộc đơn vị nào cũng có bốn module.

| Nơi lưu | Nội dung |
|---|---|
| `chatbot-data` | File nguồn, bộ tài liệu theo module/release và báo cáo |
| MongoDB | Nội dung đã trích xuất, metadata, cấu hình, tài khoản và hội thoại |
| Qdrant | Vector và payload phục vụ tìm kiếm |
| MinIO | Bản gốc và file đính kèm trong object storage |

Dữ liệu vật lý của MongoDB/Qdrant/MinIO lưu trong volume riêng. Việc copy file vào `chatbot-data` chưa tự tạo chỉ mục; cần chạy ingestion và công bố phiên bản.

## 6. Luồng nạp tài liệu

```text
Quản trị viên upload
        ↓
chatbot-data/staging
        ↓
Kiểm tra cấu trúc và nội dung
        ↓
Lưu bộ tài liệu theo module/release
        ↓
Trích xuất và chuẩn hóa → MongoDB
        ↓
Tạo embedding → Qdrant
        ↓
Kiểm tra kết quả → Công bố phiên bản
```

File không hợp lệ phải được báo lỗi; không công bố dữ liệu chưa đạt kiểm tra. MongoDB và Qdrant được chuẩn bị theo cùng phiên bản trước khi chuyển phiên bản đang phục vụ để tránh đọc lẫn dữ liệu cũ/mới. Bản gốc được lưu vào MinIO theo luồng ingestion.

## 7. Luồng chat

```text
Người dùng → chatbot-web
                    ↓
             FastAPI /api/chat
                    ↓
         Xác thực và xác định module
                    ↓
       Đọc quy tắc, FAQ từ MongoDB
                    ↓
       Truy hồi tài liệu từ Qdrant
                    ↓
          Tạo câu trả lời bằng LLM
                    ↓
       Trả nội dung + nguồn qua SSE
                    ↓
       Lưu hội thoại vào MongoDB
```

Đây là luồng tổng quát. Câu hỏi khớp FAQ hoặc bị giới hạn bởi policy có thể trả kết quả mà không gọi LLM. Endpoint SSE cụ thể cần giữ hợp đồng frontend/backend đã thống nhất, ví dụ `/api/chat/stream`.

## 8. Quy ước triển khai cho 8 đơn vị

- Mỗi đơn vị có `.env`, cấu hình module, database và vector collection riêng.
- Có thể dùng chung một cụm MongoDB/Qdrant/MinIO về mặt hạ tầng; phải phân tách dữ liệu, thông tin kết nối và quyền truy cập theo đơn vị và môi trường.
- Tám frontend dùng cùng quy ước cấu trúc và API; mỗi frontend có nhận diện và module của đơn vị mình.
- Tám backend tuân theo cùng bộ khung để sửa lỗi, kiểm thử và bàn giao nhất quán.
- Khi chạy đồng thời trên máy phát triển, cấp cổng riêng cho từng đơn vị.
- Khi chạy container, các container có thể dùng cùng cổng nội bộ; truy cập qua tên miền hoặc reverse proxy riêng.
- Secret chỉ nằm ở cấu hình backend/môi trường triển khai; không đưa vào biến frontend `VITE_*`.
- Mỗi README của đơn vị cần ghi rõ cách cài dependency, chạy FE/BE, cấu hình database, tạo tài khoản, nạp tài liệu, kiểm thử và backup/restore.

## 9. Phân biệt thiết kế đích với hiện trạng

Tài liệu này mô tả **8 bộ FE/BE/data độc lập** và backend FastAPI dùng MongoDB. Hiện trạng đã xây dựng trước đó là một `chatbot-web` dùng chung, một `chatbot-api` chứa BFF/RAG và một `chatbot-data` ở gốc; RAG chưa được chuyển khỏi PostgreSQL.

Việc tách thành 8 bộ, bổ sung Viện Quốc tế, thống nhất phạm vi Tuyển sinh & Công tác sinh viên, hợp nhất BFF/RAG và chuyển MongoDB cần được triển khai và kiểm thử riêng. Các adapter đọc PDF/DOCX cũng chỉ được coi là hỗ trợ khi đã có triển khai và kiểm thử thực tế.

Tham khảo [thiết kế MongoDB](mongodb-design.md) cho model, index và cơ chế công bố dữ liệu. Thiết kế đó ban đầu giả định backend dùng chung; khi áp dụng cấu trúc 8 đơn vị, cần điều chỉnh cấu hình database/collection và deployment tương ứng.
