# BẢN ĐỀ XUẤT DỰ ÁN (PROJECT PROPOSAL)

**Dự án:** Hệ thống Chatbot Trợ lý Ảo RAG Đa phòng ban (Multi-tenant)
**Đơn vị thụ hưởng:** Trường Đại học Kinh tế - Luật (UEL)
**Người đề xuất:** Lê Gia Văn

---

## 1. Đặt vấn đề và Mục tiêu Dự án

**Thực trạng:** Hiện tại, sinh viên UEL có nhu cầu tra cứu thông tin học vụ, hành chính, công tác sinh viên rất lớn. Dữ liệu và quy định nằm rải rác ở các phòng ban khác nhau. Quá trình tra cứu thủ công hoặc qua các kênh hỗ trợ truyền thống mất nhiều thời gian, nhân sự các phòng ban thường xuyên phải trả lời lặp lại những câu hỏi đã có quy định rõ ràng.

**Mục tiêu Giải pháp:**
Xây dựng một hệ thống Trợ lý ảo (Chatbot) thông minh ứng dụng AI (RAG - Retrieval-Augmented Generation) đáp ứng các tiêu chí:

* **Zero Hallucination (Không ảo giác):** Trả lời chính xác 100% dựa trên quy định hiện hành, không nhầm lẫn đối tượng (ví dụ: không lấy quy định hệ Liên kết quốc tế trả lời cho sinh viên Chính quy).
* **Multi-tenancy (Đa khách thuê):** Một hệ thống duy nhất phục vụ song song cho 7 phòng ban độc lập (Đào tạo, CTSV, Hành chính...), đảm bảo không rò rỉ hoặc truy xuất chéo dữ liệu sai lệch.
* **Vận hành tối giản (Low-code cho QTV):** Quản trị viên phòng ban chỉ cần thao tác trên Google Sheets với 3 biểu mẫu chuẩn hóa. Không yêu cầu kỹ năng lập trình.

## 2. Phạm vi Dữ liệu & Quy trình Quản trị

Hệ thống chuẩn hóa toàn bộ tri thức của các phòng ban thành **03 Biểu mẫu Google Sheets (Bronze Layer)**:

1. **Thông tin Mô-đun:** Khai báo phạm vi xử lý (Chatbot tự trả lời hay định tuyến sang chuyên viên).
2. **FAQ - Câu hỏi thường gặp:** Dữ liệu hỏi đáp tĩnh (Hỏi - Đáp 1:1) phục vụ truy xuất tốc độ cao (Exact Match).
3. **Tài liệu nghiệp vụ:** Cấu trúc phân cấp chứa siêu dữ liệu (Tên chủ đề, Đối tượng áp dụng, Thời hạn) và nội dung quy định chi tiết.

**Nguyên tắc cập nhật (On-demand):** Quản trị viên phòng ban chỉnh sửa Google Sheets (không xóa dòng, chỉ đổi trạng thái thành "Hết hiệu lực" hoặc "Nháp"). Sau đó, hệ thống sẽ tự động đồng bộ (chạy Batch Job) để cập nhật tri thức cho Chatbot.

## 3. Kiến trúc Hệ thống (System Architecture)

Dự án áp dụng mô hình dữ liệu **Medallion Architecture (Bronze - Silver - Gold)** kết hợp kiến trúc định tuyến thông minh từ **LangGraph**.

### 3.1. Data Pipeline (Đồng bộ Dữ liệu)

Sử dụng mô hình **Batch ELT (Extract, Load, Transform)** để xử lý dữ liệu từ Google Sheets:

* **Bronze Layer (MinIO & Sheets):**
* Nguồn gốc dữ liệu thô: 3 file Google Sheets.
* MinIO Object Storage: Lưu trữ các tệp đính kèm (File PDF biểu mẫu, DOCX đơn từ) được đính kèm trong Sheets, cung cấp URL tải trực tiếp cho sinh viên.


* **Silver Layer (PostgreSQL):**
* Đóng vai trò là Single Source of Truth (Nguồn chân lý duy nhất).
* Lưu trữ siêu dữ liệu (Metadata), trạng thái vòng đời tài liệu và các quy tắc định tuyến (Routing Rules) & FAQ.
* Có khả năng lọc dữ liệu theo `department_id` và trạng thái `is_active`.


* **Gold Layer (Qdrant Vector Database):**
* Lưu trữ các Vector nhúng (Embeddings) phục vụ tìm kiếm ngữ nghĩa.
* Tích hợp JSON Payload chứa Metadata (ID phòng ban, đối tượng áp dụng) để hỗ trợ bộ lọc cứng (Pre-filtering) trước khi tìm kiếm vector.



### 3.2. Cốt lõi Công nghệ: Serialization chuẩn STAIR

Để khắc phục nhược điểm "mất ngữ cảnh" khi băm nhỏ tài liệu của RAG truyền thống, dự án áp dụng **STAIR Serialization**.

* Trước khi đưa vào mô hình nhúng (SentenceTransformers), hệ thống sẽ ghép nối Thông tin chung (Tên quy trình, Đối tượng) vào từng dòng chi tiết (Lệ phí, Thời gian xử lý) để tạo thành một đoạn **Markdown hoàn chỉnh ngữ cảnh**.
* *Kết quả:* LLM hiểu được chính xác từng con số lệ phí, từng mốc thời gian thuộc về chủ đề nào và áp dụng cho khóa học nào, loại bỏ hoàn toàn rủi ro suy luận sai.

### 3.3. Tầng Phục vụ (Serving Layer) với LangGraph

Mỗi luồng hội thoại của sinh viên sẽ đi qua một đồ thị tác vụ (Graph) bảo mật và chính xác:

1. **Semantic Router:** Kiểm tra trong PostgreSQL (bảng `routing_rules`) xem câu hỏi có thuộc phạm vi Bot được trả lời không. Nếu không, hướng dẫn sinh viên liên hệ chuyên viên.
2. **FAQ Match:** Ưu tiên quét trong bảng `faqs` (Postgres). Nếu khớp 100% ý định, trả lời ngay để tiết kiệm token và thời gian phản hồi.
3. **Meta Extractor:** LLM trích xuất siêu dữ liệu từ câu hỏi (ví dụ: K23, Ngành MIS, Hệ Chính quy).
4. **Hybrid Retrieval:** Truy vấn Qdrant với lớp lọc Payload cứng (chỉ lấy tài liệu của đúng phòng ban và đúng đối tượng) kết hợp tìm kiếm Vector (Cosine Similarity).
5. **Generation:** LLM tổng hợp các đoạn Markdown chính xác nhất, tạo câu trả lời mạch lạc và đính kèm link tải form từ MinIO (nếu có).

## 4. Chiến lược Mở rộng Đa khách thuê (Multi-tenancy)

Hệ thống được thiết kế theo tư duy **Configuration-Driven (Điều khiển bằng cấu hình)** để mở rộng dễ dàng cho 7+ phòng ban mà không phình to mã nguồn hay tài nguyên máy chủ:

* **Tập trung hóa Cơ sở dữ liệu:** Không tạo 7 database. Dùng chung 1 schema PostgreSQL và 1 collection Qdrant.
* **Phân tách bằng ID:** Dữ liệu được phân vùng logic thông qua trường `department_id`. LangGraph Agent nhận tham số này để điều hướng luồng truy xuất sao cho sinh viên chat với Bot phòng Đào tạo sẽ không bao giờ nhìn thấy dữ liệu của phòng CTSV.
* **Quản lý tập trung (departments.yaml):** Quản trị viên IT chỉ cần khai báo thêm `department_id` và URL Google Sheets mới vào tệp cấu hình. Pipeline sẽ tự động quét và đồng bộ dữ liệu cho phòng ban mới.

## 5. Môi trường Triển khai (Deployment)

Hệ thống được đóng gói (Containerization) và triển khai trên máy chủ **Ubuntu Server** bằng **Docker Compose** với kiến trúc Microservices:

| Service | Chức năng chính | Trạng thái hoạt động |
| --- | --- | --- |
| **PostgreSQL** | Lưu trữ Metadata (Silver Layer), FAQ, Routing Rules. | 24/7 |
| **Qdrant** | Lưu trữ Vector và Payload (Gold Layer). | 24/7 |
| **MinIO** | Object Storage lưu file đính kèm, biểu mẫu (.docx, .pdf). | 24/7 |
| **LangGraph API** | Nhận tin nhắn, chạy luồng xử lý RAG và phản hồi sinh viên. | 24/7 |
| **Data Sync Worker** | Python Script chạy On-demand (gọi lệnh thủ công) để kéo data từ Sheets, bóc tách, chuẩn hóa STAIR Markdown và nạp vào DB. | Theo yêu cầu |

## 6. Lộ trình Thực hiện (Roadmap)

**Giai đoạn 1: Chuẩn bị Cơ sở Hạ tầng & Dữ liệu (Tuần 1 - Tuần 2)**

* Khởi tạo môi trường Ubuntu Server, thiết lập Docker Compose (Postgres, Qdrant, MinIO).
* Thống nhất định dạng 3 biểu mẫu Google Sheets với 1 phòng ban thử nghiệm đầu tiên (PoC - VD: Phòng Hành chính).
* Tạo file cấu hình `departments.yaml`.

**Giai đoạn 2: Xây dựng Data Pipeline cốt lõi (Tuần 3 - Tuần 4)**

* Lập trình module Extract: Đọc dữ liệu từ Google Sheets (Pandas).
* Lập trình module Transform: Validate Pydantic, ghi CSDL Postgres (Silver Layer).
* Lập trình module Serialize & Vectorize: Sinh Markdown theo định dạng STAIR, tạo Embeddings và đẩy payload vào Qdrant.
* Xây dựng kịch bản Soft-delete (cập nhật trạng thái "Hết hiệu lực").

**Giai đoạn 3: Phát triển LangGraph Agent & Tích hợp (Tuần 5 - Tuần 6)**

* Thiết kế các Node của LangGraph: Routing, FAQ Exact Match, Meta Extractor, Hybrid Search.
* Tích hợp Prompt Engineering đảm bảo giọng văn hành chính, chuẩn mực của UEL.
* Thiết lập API (FastAPI) nhận tham số `department_id` cho cơ chế Multi-tenant.

**Giai đoạn 4: Kiểm thử, Mở rộng và Bàn giao (Tuần 7 - Tuần 8)**

* Kiểm thử bảo mật dữ liệu (Data Leakage) giữa các phòng ban.
* Kiểm thử giới hạn chịu tải (Load Testing) và xử lý ảo giác (Hallucination Testing).
* Khai báo cấu hình và đồng bộ dữ liệu cho 6 phòng ban còn lại.
* Viết tài liệu Hướng dẫn nhập liệu trên Google Sheets cho chuyên viên các phòng ban.


flowchart LR
    %% Global Environment (tương đương khung ngoài cùng chứa Docker/Github Actions)
    subgraph Env [Môi trường triển khai: Ubuntu Server / Docker Compose]
        direction LR

        %% Khối Data Source (Bên trái)
        subgraph Sources [Data Sources]
            direction TB
            DS1[fa:fa-table Google Sheets\n(Dữ liệu biểu mẫu)]
            DS2[fa:fa-file-pdf Tài liệu gốc\n(PDF, Word, Form)]
        end

        %% Khối Xử lý & Lưu trữ (Ở giữa)
        subgraph Core [Data Pipeline & Medallion Architecture]
            direction TB

            %% Transformation Engine (Tương đương khối DBT màu đỏ trên cùng)
            subgraph Engine [Python Processing Engine (Pandas, STAIR, Embedding)]
                direction LR
                T1(fa:fa-cogs Extract &\nValidate)
                T2(fa:fa-code Serialize &\nVectorize)
            end

            %% Storage Layer (Tương đương khối MotherDuck chứa 3 xô ở dưới)
            subgraph Storage [Data Infrastructure]
                direction LR
                Bronze[fa:fa-database Bronze Layer\nMinIO\n(Raw JSON/CSV & Files)]
                Silver[fa:fa-database Silver Layer\nPostgreSQL\n(Cleaned Data & Routing)]
                Gold[fa:fa-database Gold Layer\nQdrant\n(Vector & Metadata)]
            end

            %% Luồng bouncing arrows (Bronze -> Engine -> Silver -> Engine -> Gold)
            Bronze -.->|Đọc dữ liệu thô| T1
            T1 -.->|Lưu dữ liệu sạch| Silver
            Silver -.->|Lấy dữ liệu tạo Markdown| T2
            T2 -.->|Upsert Vectors + Payload| Gold
        end

        %% Khối Serving (Bên phải)
        subgraph Serving [Serving Layer]
            direction TB
            App1[fa:fa-project-diagram LangGraph\n(Routing & RAG Agent)]
            App2[fa:fa-comments Client / Sinh viên\n(Zalo, Web Portal)]
        end

        %% Kết nối chính
        DS1 -->|Trích xuất Batch| Bronze
        DS2 -->|Upload trực tiếp| Bronze

        Gold -->|Semantic Search| App1
        Silver -->|SQL Routing & FAQ| App1
        App1 <--> App2
    end

    %% Styling bám sát màu sắc và nét đứt của ảnh mẫu
    classDef bronze fill:#d9822b,stroke:#333,stroke-width:2px,color:#fff;
    classDef silver fill:#c0c0c0,stroke:#333,stroke-width:2px,color:#000;
    classDef gold fill:#d4af37,stroke:#333,stroke-width:2px,color:#000;
    classDef engine fill:#fff,stroke:#ff5722,stroke-width:2px,stroke-dasharray: 5 5;
    classDef source fill:#fff,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5;
    classDef serve fill:#fff,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5;
    classDef envbox fill:#fcfcfc,stroke:#333,stroke-width:2px,stroke-dasharray: 10 5,rx:10,ry:10;
    classDef corebox fill:#fcfcfc,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5,rx:10,ry:10;

    class Bronze bronze;
    class Silver silver;
    class Gold gold;
    class Engine engine;
    class DS1,DS2 source;
    class App1,App2 serve;
    class Env envbox;
    class Core corebox;


flowchart TB
    %% Khối dữ liệu nguồn
    subgraph Bronze [Bronze Layer - Nguồn Dữ Liệu (Google Sheets)]
        direction TB
        S1[1. Thông tin Mô-đun]
        S2[2. FAQ]
        S3[3. Tài liệu nghiệp vụ]
    end

    %% Luồng xử lý dữ liệu (Chạy on-demand)
    subgraph Pipeline [Data Sync Pipeline - Kích hoạt thủ công]
        direction TB
        P1[Extract & Validate bằng Pandas]
        P2[Chuẩn hóa & Ghi CSDL Quan hệ]
        P3[Serialization: Tạo Markdown kiểu STAIR]
        P4[Embedding: Nhúng Text thành Vector]
    end

    %% Cơ sở hạ tầng lưu trữ trên Ubuntu Server
    subgraph Storage [Hạ tầng Lưu trữ - Ubuntu Server / Docker Compose]
        direction TB
        DB[(PostgreSQL - Silver Layer)\nBảng: routing, faq, documents]
        MINIO[(MinIO - Backup)\nLưu file Markdown]
        QDRANT[(Qdrant - Gold Layer)\nLưu Vector + Payload Metadata]
    end

    %% Luồng truy vấn Chatbot
    subgraph LangGraph [LangGraph Chatbot - Luồng Truy Vấn]
        direction TB
        U((Sinh viên đặt câu hỏi))
        N1{1. Routing Check\n(Phạm vi trả lời?)}
        N2{2. FAQ Exact Match\n(Có sẵn câu hỏi?)}
        N3[3. Semantic Search\nLọc Payload + Tìm Vector]
        N4[4. LLM Generation\nTổng hợp câu trả lời]
        Ans((Trả lời người dùng))
    end

    %% Liên kết luồng Data Pipeline
    S1 & S2 & S3 --> P1
    P1 --> P2
    P2 -- "Lưu Routing, FAQ, Metadata (Trạng thái, Đối tượng...)" --> DB
    P2 --> P3
    P3 -- "Lưu trữ file .md" --> MINIO
    P3 --> P4
    P4 -- "Upsert Points (Vector + JSON Payload)" --> QDRANT

    %% Liên kết luồng Chatbot
    U --> N1
    N1 -. "Query SQL (table_routing)" .-> DB
    N1 -- "Ngoài phạm vi (Chuyển kênh)" --> Ans
    N1 -- "Trong phạm vi" --> N2
    
    N2 -. "Query SQL (table_faq)" .-> DB
    N2 -- "Trúng FAQ (Trả lời ngay)" --> Ans
    N2 -- "Không trúng" --> N3
    
    N3 -. "Filter Metadata + Search Vector" .-> QDRANT
    N3 -- "Lấy Markdown Chunks có ngữ cảnh" --> N4
    N4 --> Ans

    %% Styling cơ bản
    classDef storage fill:#f9f,stroke:#333,stroke-width:2px;
    class DB,MINIO,QDRANT storage;
    classDef process fill:#bbf,stroke:#333,stroke-width:2px;
    class P1,P2,P3,P4 process;
    classDef logic fill:#fcf,stroke:#333,stroke-width:2px;
    class N1,N2 logic;