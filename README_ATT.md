# Giải mã bản đồ MU Online (`.att`) — Hướng dẫn đầy đủ

Tài liệu này giải thích **cách đọc và giải mã file `EncTerrain*.att`** của client
MU Online Season 21 (tested với epicmu.net), để lấy được lưới 256×256 tile
biết ô nào đi được / tường / nước / vùng an toàn.

Mục tiêu: ai cũng có thể lấy map walkable của server mình đang chơi, không cần
phần mềm đóng (Pentium Tools, World Editor...).

---

## 1. File `.att` là gì?

Mỗi map trong MU là một lưới **256 × 256 tile**. File `EncTerrainN.att` (trong
thư mục `Data/WorldN/` của client) lưu **thuộc tính từng ô** (có đi được không,
có phải nước, vùng an toàn...).

- Client Webzen lưu dạng **đã mã hóa** (`EncTerrain*.att`).
- Server (và OpenMU) lưu dạng **rõ** (`TerrainN.att`).

Thuộc tính mỗi ô là một **bitmask 16-bit** (theo `TWFlags`):

| Bit | Tên        | Ý nghĩa                     | Màu trong PNG |
|-----|------------|----------------------------|---------------|
| 0x0001 | SafeZone   | Vùng an toàn (không PK)    | xanh lá       |
| 0x0002 | Character  | Đang có người (vẫn đi được) | đen           |
| 0x0004 | NoMove     | Tường / vật cản (chặn)     | trắng         |
| 0x0008 | NoGround   | Vực / không có đất (chặn)  | xám           |
| 0x0010 | Water      | Nước (chặn)                | xanh dương    |
| 0x0020..0x8000 | Att1..Att7 | Flag mở rộng khác          | —             |

> **Đi được** = ô không có bit `NoMove` (0x0004), `NoGround` (0x0008), `Water` (0x0010).

Có 2 định dạng:
- **Standard**: 1 byte/ô → 256×256 = 65536 byte + 4 byte header.
- **Extended** (S21 hầu hết): 2 byte/ô (uint16 little-endian) → 131072 byte + 4 byte header.

Header (sau khi giải mã) luôn là 4 byte:
`[version=0][index=MapNumber][width=255][height=255]`.

---

## 2. Cách client mã hóa (S21)

Quy trình giải mã ngược lại của Webzen:

```
EncTerrain.att
  │
  ├─ Nếu 4 byte đầu = "ATT\x01" (0x41 0x54 0x54 0x01)
  │     → Dùng ModulusCryptor (bỏ 4 byte header)
  │     → thuật toán: RC6 (stage 1, key cố định) giải để lấy key2,
  │       rồi ThreeWay (stage 2, key2) giải phần dữ liệu
  │
  └─ Ngược lại
        → Dùng FileCryptor (rolling XOR)

  Sau đó: XOR toàn bộ với BUX mask = [0xFC, 0xCF, 0xAB]
  → ra được dữ liệu rõ (header + grid)
```

### 2.1 FileCryptor (cho map standard, ~20% file)
```
mapKey = 0x5E
for i in 0..len:
    out[i] = ( (src[i] ^ KEY[i & 15]) - mapKey ) & 0xFF
    mapKey = (src[i] + 0x3D) & 0xFF

KEY = [0xD1,0x73,0x52,0xF6,0xD2,0x9A,0xCB,0x27,
       0x3E,0xAF,0x59,0x31,0x37,0xB3,0xE7,0xA2]
```

### 2.2 ModulusCryptor (cho map extended, ~80% file S21)
Khóa cố định stage 1:
```
KEY_1 = "webzen#@!01webzen#@!01webzen#@!0"  (32 byte)
```
- `algo1 = buf[1] & 7`, `algo2 = buf[0] & 7` (trong header ATT\x01).
- Với epicmu S21: **algo1 = 4 (RC6)**, **algo2 = 1 (ThreeWay)** cho mọi map.
- Stage 1: giải 3 block (giữa, cuối, đầu) bằng cipher `algo1` và KEY_1 để
  thu hồi `key2` (byte 2..33).
- Stage 2: giải phần dữ liệu bằng cipher `algo2` và `key2`.

### 2.3 BUX mask (bắt buộc cho cả 2 đường)
```
out[i] = data[i] ^ [0xFC,0xCF,0xAB][i % 3]
```

---

## 3. Cách giải mã bằng repo này

### Cách A — Dùng script Node (khuyên dùng, chạy thẳng source gốc)

Cần **Node.js 22+** (đã test Node 24). Không cần cài thêm package.

```powershell
cd gfxdec_src
# Giai ma 1 file:
node --experimental-transform-types run.ts
# (run.ts dang hardcode World10, sua duong dan ben trong neu muon file khac)

# Hoac giai ma TAT CA file trong ../att_samples/World* va sinh PNG:
node --experimental-transform-types batch.ts
```

`run.ts` / `batch.ts` dùng **nguyên source TypeScript gốc** từ project
[xulek/muonline-bmd-viewer](https://github.com/xulek/muonline-bmd-viewer)
(port thẳng, chỉ thêm `.ts` vào import và 1 file `utils/Logger.ts` rỗng).
Đây là cách tin cậy nhất vì chạy đúng thuật toán tác giả viết.

Cấu trúc:
```
gfxdec_src/
├── run.ts                     # test 1 file (World10)
├── batch.ts                   # giai ma tat ca -> .att.png
├── utils/Logger.ts           # logger rong (de chay TS)
├── terrain/formats/ATTReader.ts   # entry: phat hien loai ma hoa + parse
└── crypto/
    ├── file-cryptor.ts       # FileCryptor + BUX mask
    ├── modulus-cryptor.ts    # ModulusCryptor (RC6/ThreeWay/...)
    └── {tea,threeway,cast5,rc5,rc6,mars,idea,gost}-cipher.ts
```

### Cách B — Dùng `att_dec.js` (JavaScript thuần, không cần flag)

`att_dec.js` là bản dịch JS của pipeline trên (chỉ implement TEA/ThreeWay/RC6,
đủ cho epicmu S21). Dùng làm module:

```js
const { readATT } = require('./att_dec.js');
const fs = require('fs');
const buf = fs.readFileSync('World1/EncTerrain1.att');
const r = readATT(buf);   // {version,index,isExt,grid:[65536 hoac 131072]}
// r.grid[i] = thuoc tinh 16-bit cua tile thu [i%256, i/256]
```

Chạy nhanh 1 file:
```powershell
cd gfxdec_src
node att_dec.js ../att_samples/World1/EncTerrain1.att
```

---

## 4. Sinh ảnh PNG để xem

Sau khi có `grid` (mảng thuộc tính), tô màu theo bảng ở mục 1 rồi ghi PNG
256×256. Xem `mu_att_view.py` (Python/PIL) hoặc `batch.ts` (Node/zlib) để biết
cách vẽ. Kết quả nằm ở `att_samples/WorldN/EncTerrainN.att.png`.

Gallery duyệt tất cả map: **`att_samples/epic_gallery.html`** (mở bằng trình
duyệt, hover chuột lên ảnh xem tọa độ tile `x,y`).

---

## 5. Lấy file `.att` từ client của bạn

1. Mở thư mục cài game, tìm `Data/World/World1/EncTerrain.att`,
   `World2/...`, ... (mỗi `WorldN` 1 file, một số map có nhiều file biến thể).
2. Copy toàn bộ `World*` vào `att_samples/`.
3. Chạy `batch.ts` (hoặc `att_dec.js`) để giải mã.
4. Mở `epic_gallery.html` xem kết quả.

> Lưu ý: file client Webzen mã hóa có thể thay đổi khóa giữa các Season.
> Nếu giải ra toàn số rác → Season của bạn dùng thuật toán khác (thử GFxDec
> từ thread RageZone, hoặc đọc ngược `ZzzLodTerrain` trong main.dll).

---

## 6. Nguồn tham khảo

- [xulek/muonline-bmd-viewer](https://github.com/xulek/muonline-bmd-viewer) —
  source TS gốc (ATTReader, crypto engine) dùng trong repo này.
- [MUnique/OpenMU](https://github.com/MUnique/OpenMU) — file `.att` rõ (S6) để
  đối chiếu cấu trúc.
- [0x4d696e68/season_xx_bmd](https://github.com/0x4d696e68/season_xx_bmd) —
  GFxDec (giải mã chung S20/S21, tham khảo thêm).
- RageZone: thread "GFxDec one click decrypt latest wz client" (hỗ trợ S21).

---

## 7. Tóm tắt cho người vội

```
1. Copy World* tu client vao att_samples/
2. cd gfxdec_src
3. node --experimental-transform-types batch.ts
4. Mo att_samples/epic_gallery.html
```
