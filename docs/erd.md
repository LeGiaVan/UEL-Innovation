# ERD — Silver Layer (Phase 3)

PostgreSQL là nguồn chân lý đã chuẩn hóa. Mọi bảng nghiệp vụ gắn cả `department_id` và `module_id`. Qdrant (Phase 4) rebuild từ các bảng này.

## Cardinality

```text
departments 1 ── N modules
modules     1 ── N routing_rules
modules     1 ── N faqs
modules     1 ── N documents
documents   1 ── N document_sections
documents   1 ── 0..1 procedures
documents   1 ── N dossier_items
documents   1 ── N procedure_steps
documents   1 ── N attachments
sync_runs   1 ── N source_records
```

## Sơ đồ

```mermaid
erDiagram
    departments ||--o{ modules : has
    departments ||--o{ sync_runs : tracks
    modules ||--o{ routing_rules : has
    modules ||--o{ faqs : has
    modules ||--o{ documents : has
    modules ||--o{ sync_runs : tracks
    documents ||--o{ document_sections : has
    documents ||--o| procedures : has
    documents ||--o{ dossier_items : has
    documents ||--o{ procedure_steps : has
    documents ||--o{ attachments : has
    sync_runs ||--o{ source_records : audits

    departments {
        uuid id PK
        string code UK
        string name
        string audience
        boolean is_active
        boolean contact_verified
    }

    modules {
        uuid id PK
        uuid department_id FK
        string code
        string release_status
        string content_hash
        boolean is_active
    }

    routing_rules {
        uuid id PK
        uuid module_id FK
        string source_key UK
        string scope_type
        boolean is_active
        string content_hash
    }

    faqs {
        uuid id PK
        uuid module_id FK
        string question_code
        string normalized_question
        boolean is_active
        string content_hash
    }

    documents {
        uuid id PK
        uuid module_id FK
        string document_code
        string document_type
        boolean is_active
        string content_hash
    }

    document_sections {
        uuid id PK
        uuid document_id FK
        string section_key
        string section_type
        boolean is_active
    }

    procedures {
        uuid id PK
        uuid document_id FK
        string fee_type
        string answer_policy
    }

    dossier_items {
        uuid id PK
        uuid document_id FK
        int source_order
    }

    procedure_steps {
        uuid id PK
        uuid document_id FK
        int step_number
    }

    attachments {
        uuid id PK
        uuid document_id FK
        string source_url
        string status
    }

    sync_runs {
        uuid id PK
        string status
        string release_id
        int inserted_count
        int updated_count
        int deactivated_count
    }

    source_records {
        uuid id PK
        uuid sync_run_id FK
        string source_key
        string entity_type
        jsonb raw_payload
    }
```

## Business keys

| Entity | Key |
|---|---|
| Department | `code` |
| Module | `department.code + module.code` |
| Routing rule | `module_id + source_key` |
| FAQ | `module_id + question_code` |
| Document | `module_id + document_code` |
| Document section | `document_id + section_key` |
| Procedure | `document_id` |
| Dossier item | `document_id + source_order` |
| Procedure step | `document_id + step_number` |
| Attachment | `document_id + source_url` |

`source_key` routing: `route:{sha256(department_id\|module_code\|scope_type\|normalized_topic)[0:20]}`.

`section_key`: `section:{sha256(document_code\|section_type\|normalized_heading\|source_order)[0:20]}`.

STT không phải business key. Record biến mất khỏi nguồn được `is_active=false` (soft-delete), không xóa cứng.
