# Auto MU SS21 — Coordinate Monitor for MuOnline Season 21 (EpicMU)

Tool đọc tọa độ nhân vật (X, Y, Z) trực tiếp từ memory của client MuOnline
Season 21 (epicmu.net) và hiển thị real-time cho mọi cửa sổ game đang mở.

## Đặc điểm

- Tự động phát hiện mọi cửa sổ game (`main.exe`) — không cần gõ lệnh.
- Mỗi cửa sổ một dòng: PID, tiêu đề (tên nhân vật), X, Y, Z.
- Cập nhật tiêu đề khi đăng nhập xong (tiêu đề đổi từ "Epic MU Season 21"
  sang tên nhân vật).
- Tự thêm/xoá dòng khi mở/đóng game.
- Offset tọa độ là **tĩnh** (`main.exe` không bật ASLR) nên không cần scan
  lại sau mỗi lần mở game.

## Yêu cầu

- Windows + Python 3.x
- `pip install pymem`
- **Chạy quyền Administrator** (để mở handle đọc memory của process game).
- Tkinter (thường có sẵn trong Python chuẩn).

## Cách dùng

1. Mở game (vài cửa sổ tuỳ ý).
2. Chuột phải PowerShell → **Run as administrator**:
   ```powershell
   cd <thu-muc-chua-file>
   python mu_gui.py
   ```
3. App hiện bảng: mỗi cửa sổ game một dòng, tọa độ cập nhật liên tục.

## Cấu trúc file

| File | Mô tả |
|------|-------|
| `mu_gui.py` | **App chính** — monitor GUI tự động, chạy Admin. |
| `mu_scanner.py` | Quét memory tìm tọa độ (thay thế Cheat Engine, không cài driver). |
| `mu_find.py` | Workflow scan → narrow → watch để xác định địa chỉ tọa độ. |
| `mu_reader.py` | Đọc tọa độ theo địa chỉ/chain đã biết. |
| `mu_ptrscan.py` | Kiểm tra ASLR và tìm pointer chain (không cần CE). |

## Offset tọa độ

```
X = module_base(0x400000) + 0xB40AF60
Y = X + 4
Z = X + 8
```

> Offset này đúng với client epicmu Season 21 tại thời điểm viết. Nếu server
> cập nhật client, chạy `mu_find.py` để tìm lại địa chỉ mới rồi sửa
> `X_OFFSET`/`Y_OFFSET`/`Z_OFFSET` trong `mu_gui.py`.

## Lưu ý

- Đọc memory client game có thể vi phạm điều khoản dịch vụ của server.
  Tự chịu trách nhiệm khi sử dụng.
- Script dùng `ReadProcessMemory` (không cài kernel driver), nhưng anti-cheat
  của một số server vẫn có thể phát hiện và kick/ban.
