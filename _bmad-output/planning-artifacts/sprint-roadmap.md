# Sprint Roadmap — Aplifier_Analyze

**Cập nhật lần cuối:** 2026-04-18  
**Người dùng:** Truong pc  
**Mục tiêu:** Triển khai hệ thống Signal Analyzer & Oscilloscope gồm 3 lớp kỹ thuật: Desktop App (Python/PyQt6), Firmware (C/STM32F407), Hardware.

---

## Nguyên tắc triển khai

- Lên **Plan trước**, code sau — cần review kiến trúc toàn hệ thống (software + hardware + firmware) trước khi implement.
- **Giao thức binary Firmware ↔ PC là điểm then chốt** — mọi component khác phụ thuộc vào nó.
- Tham chiếu file `_bmad-output/project-context.md` trước khi bắt đầu bất kỳ bước nào.

---

## Trạng thái hiện tại

| Việc | Trạng thái |
|------|-----------|
| Generate Project Context (`GPC`) | ✅ Hoàn thành — `_bmad-output/project-context.md` |
| Sprint Roadmap | ✅ File này |
| Technical Research (`TR`) | ⏳ Chưa bắt đầu — **BƯỚC TIẾP THEO** |

---

## Phase 0 — Nền tảng (Đã hoàn thành)

| Skill | Code | Output | Trạng thái |
|-------|------|--------|-----------|
| Generate Project Context | `GPC` | `_bmad-output/project-context.md` | ✅ Done |

---

## Phase 1 — Analysis

> **Mục tiêu:** Xác nhận công nghệ, đánh giá khả thi kỹ thuật, hiểu rõ miền bài toán.

| Thứ tự | Skill | Code | Bắt buộc? | Output dự kiến |
|--------|-------|------|-----------|----------------|
| 1 | **Technical Research** | `TR` | ⭐ Bắt buộc | Báo cáo kỹ thuật: chốt ADC mode, USB CDC vs UART, pipeline Python, DAC nội vs AD9833 |
| 2 | Domain Research | `DR` | Tùy chọn | Tổng quan lĩnh vực Signal Analyzer / Bode Plot instruments |

### Câu hỏi cụ thể cần TR trả lời:
- ADC: **Simultaneous** (2 kênh song song) hay **Triple Interleaved** (tốc độ cực cao 1 kênh)?
- Signal generation: **DAC nội STM32** (đơn giản) hay **AD9833 qua SPI** (tần số cao, chính xác hơn)?
- Data pipeline Python: **Queue + Thread** hay **asyncio**? Hiệu năng nào phù hợp với 1 MSPS?
- USB CDC có đủ băng thông cho 2 kênh x 1 MSPS x 16-bit không? (=> ~4 MB/s)
- Có cần **compression** dữ liệu trước khi truyền lên PC không?

---

## Phase 2 — Planning

> **Mục tiêu:** Xác định rõ tính năng, yêu cầu, giao diện người dùng.

| Thứ tự | Skill | Code | Bắt buộc? | Output dự kiến |
|--------|-------|------|-----------|----------------|
| 1 | **Create PRD** | `CP` | ⭐ Bắt buộc | Product Requirements Document đầy đủ |
| 2 | Create UX Design | `CU` | Khuyến nghị | Bản mô tả UI/UX cho desktop app |

---

## Phase 3 — Solutioning (Kiến trúc)

> **Mục tiêu:** Thiết kế kiến trúc toàn hệ thống, chia công việc thành stories.

| Thứ tự | Skill | Code | Bắt buộc? | Output dự kiến |
|--------|-------|------|-----------|----------------|
| 1 | **Create Architecture** | `CA` | ⭐ Bắt buộc | Architecture doc: state machine firmware, binary protocol spec, Python data pipeline |
| 2 | **Create Epics & Stories** | `CE` | ⭐ Bắt buộc | Danh sách Epics + Stories có thể implement tuần tự |
| 3 | Check Implementation Readiness | `IR` | Khuyến nghị | Kiểm tra PRD + Architecture + Epics đồng bộ trước khi code |

### Các khối kiến trúc cần CA giải quyết:
- **Firmware State Machine:** `IDLE → CONFIGURING → ACQUIRING → TRANSMITTING → ERROR`
- **Binary Protocol spec:** Header, Type, Length, Payload encoding, CRC, sync/recovery
- **Python data pipeline:** Serial reader thread → Queue → Timer callback → NumPy buffer → pyqtgraph
- **Hardware integration points:** Chân ADC, chân DAC/SPI DDS, trigger, Vref

---

## Phase 4 — Implementation (Thực thi)

> **Mục tiêu:** Viết code theo đúng stories đã lên kế hoạch, review từng bước.

```
[SP] Sprint Planning
   └── [CS] Create Story → [VS] Validate Story
         └── [DS] Dev Story → [CR] Code Review
               └── Fix nếu có issue → lặp lại [DS]
               └── Nếu Epic xong → [ER] Retrospective (tùy chọn)
```

### Thứ tự Epics gợi ý:
1. **Epic 1 — Desktop Serial Integration:** Thay `generate_signals()` bằng pyserial reader thực
2. **Epic 2 — Binary Protocol Parser:** Python parser + Firmware encoder cho frame format đã định nghĩa
3. **Epic 3 — Firmware Core:** ADC DMA, USB CDC TX, State Machine
4. **Epic 4 — Firmware Signal Gen:** DAC/DDS driver, tần số sweep
5. **Epic 5 — Integration & Calibration:** End-to-end test, phase offset calibration
6. **Epic 6 — Export & Polish:** CSV/Excel export, UI refinement

---

## Hướng dẫn dùng file này trong context mới

Khi mở context mới, nói với AI:

```
Đọc 2 file sau trước khi làm việc:
1. _bmad-output/project-context.md  (quy tắc kỹ thuật)
2. _bmad-output/planning-artifacts/sprint-roadmap.md  (kế hoạch tổng thể)

Bước tiếp theo là chạy [TR] Technical Research cho dự án Aplifier_Analyze.
```
