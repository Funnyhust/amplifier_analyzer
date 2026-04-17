# Hướng dẫn chuẩn bị tài liệu kỹ thuật cho AI Agent

> **Lý do:** AI agent không đọc được file PDF trực tiếp. Cần convert sang text trước.  
> Thư mục `docs/` này là nơi AI đọc để hiểu phần cứng và SDK của dự án.

---

## Danh sách tài liệu CẦN chuẩn bị (theo độ ưu tiên)

| Tài liệu | Nguồn | Chương cần lấy | File output |
|----------|-------|----------------|-------------|
| **RM0090** — STM32F407 Reference Manual | [st.com](https://www.st.com/resource/en/reference_manual/rm0090.pdf) | Chương ADC (ch.13), DMA (ch.10), USB (ch.35), DAC (ch.12), Timer (ch.18) | `rm0090_adc_dma_usb.txt` |
| **AN2834** — ADC Accuracy in STM32 | [st.com](https://www.st.com/resource/en/application_note/an2834.pdf) | Toàn bộ (~30 trang) | `an2834_adc_accuracy.txt` |
| **AN4666** — ADC Multimode in STM32F4 | [st.com](https://www.st.com/resource/en/application_note/an4666.pdf) | Toàn bộ | `an4666_adc_multimode.txt` |
| **DS8626** — STM32F407 Datasheet | [st.com](https://www.st.com/resource/en/datasheet/stm32f407vg.pdf) | Electrical characteristics, ADC specs (ch.5) | `stm32f407_electrical_specs.txt` |
| **AD9833 Datasheet** | [analog.com](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9833.pdf) | Toàn bộ (~24 trang) | `ad9833_datasheet.txt` |
| **AD8307 Datasheet** | [analog.com](https://www.analog.com/media/en/technical-documentation/data-sheets/ad8307.pdf) | Toàn bộ (~20 trang) | `ad8307_datasheet.txt` |

---

## Cách convert PDF sang text

### Cách 1: Dùng PowerShell + pdftotext (Khuyến nghị)

**Bước 1: Cài pdftotext (chỉ làm 1 lần)**
```powershell
# Cài Chocolatey (nếu chưa có), sau đó:
choco install poppler

# Hoặc tải thủ công từ: https://github.com/oschwartz10612/poppler-windows/releases
# Giải nén và thêm vào PATH
```

**Bước 2: Convert từng tài liệu**
```powershell
# Convert toàn bộ file:
pdftotext "D:\Downloads\rm0090.pdf" "D:\Duong\App_desktop\Aplifier_Analyze\docs\rm0090_adc_dma_usb.txt"

# Chỉ lấy một số trang (tiết kiệm hơn, ví dụ trang 300-420 chứa chương ADC):
pdftotext -f 300 -l 420 "D:\Downloads\rm0090.pdf" "D:\Duong\App_desktop\Aplifier_Analyze\docs\rm0090_adc_dma_usb.txt"
```

**Số trang tham khảo trong RM0090 (rev 19):**
| Chương | Nội dung | Trang (xấp xỉ) |
|--------|----------|----------------|
| Ch.10 | DMA controller | ~300–340 |
| Ch.12 | DAC | ~370–395 |
| Ch.13 | ADC | ~395–460 |
| Ch.35 | USB on-the-go FS/HS | ~1220–1310 |

---

### Cách 2: Copy-Paste thủ công (Nhanh, không cần cài thêm gì)

1. Mở PDF bằng Adobe Reader / Chrome / Edge
2. `Ctrl+A` để chọn tất cả (hoặc chọn từng đoạn liên quan)
3. `Ctrl+C` → mở Notepad → `Ctrl+V`
4. Lưu vào `docs/` với tên file mô tả rõ ràng

> ⚠️ Cách này có thể bị lỗi layout với bảng số và hình vẽ.

---

### Cách 3: Đọc từ HTML online (Tự động, AI làm được)

Một số tài liệu ST có phiên bản HTML xem được online. Khi chạy Technical Research, chỉ cần nói:

```
"Hãy đọc trực tiếp chương ADC từ RM0090 trên st.com và 
datasheet AD9833 từ analog.com"
```

AI sẽ dùng tool `read_url_content` để fetch và đọc tự động.

---

## Cấu trúc thư mục docs/ mục tiêu

```
docs/
├── README-prepare-docs.md          ← File này
├── stm32/
│   ├── rm0090_adc_dma_usb.txt      ← RM0090 chương ADC + DMA + USB
│   ├── an2834_adc_accuracy.txt     ← Application Note ADC accuracy
│   ├── an4666_adc_multimode.txt    ← Application Note ADC multimode
│   └── stm32f407_electrical_specs.txt
├── analog_ic/
│   ├── ad9833_datasheet.txt        ← DDS chip
│   └── ad8307_datasheet.txt        ← Log amplifier
└── notes/
    └── hardware_decisions.md       ← Ghi chú quyết định phần cứng (viết tay)
```

---

## Hướng dẫn cho AI khi đọc tài liệu

Khi bắt đầu bất kỳ task liên quan đến phần cứng, hãy nói với AI:

```
Trước khi trả lời, hãy đọc các file sau trong thư mục docs/:
- docs/stm32/rm0090_adc_dma_usb.txt
- docs/stm32/an4666_adc_multimode.txt
- docs/analog_ic/ad9833_datasheet.txt

Sau đó mới đưa ra khuyến nghị về [vấn đề bạn cần hỏi].
```

---

## Lưu ý quan trọng

- ✅ File `.txt` convert từ PDF là đủ tốt cho AI đọc code register, bảng thông số.
- ⚠️ Hình vẽ (sơ đồ khối, timing diagram) sẽ BỊ MẤT khi convert sang text — phần này bạn vẫn cần tự đọc bằng mắt.
- ✅ Bảng số (register bits, electrical specs) thường convert tốt.
- ⚠️ RM0090 rất dài (~1700 trang), **không nên convert toàn bộ** — chỉ lấy chương cần thiết.

---

*Cập nhật lần cuối: 2026-04-18*
