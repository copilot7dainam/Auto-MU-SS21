"""
Quét memory của client MU để tìm tọa độ nhân vật (thay thế Cheat Engine).
Chỉ dùng ReadProcessMemory - KHONG cai kernel driver.
Yeu cau: pip install pymem

Cach dung:
1. Vao game, dung yen tai vi tri X,Y nao do.
2. Chay script, nhap toa do hien tai cua ban (co the doan gan dung).
   Vi du: dang o ban do Lorencia, X=130, Y=120.
3. Script quet float trong vung module game, in cac dia chi khop.
4. Di chuyen nhan vat (chay den cho khac), quet lai voi toa do moi.
5. Dia chi xuat hien o CA CA 2 lan quet = ung vien cua X (va Y thuong o +4).
"""
import struct
import pymem
import pymem.process

PROCESS_NAME = "main.exe"   # sua neu client khac
CHUNK = 1 << 16             # 64KB moi lan doc


def read_region(pm, start, size):
    """Doc 1 vung nho, tra ve bytes hoac None neu bi bao ve/access deny."""
    try:
        return pm.read_bytes(start, size)
    except Exception:
        return None


def scan_floats_near(pm, base, module_size, targets, tol=1.0):
    """
    Quet float trong [base, base+module_size], tra ve cac dia chi co gia tri
    nam trong [t - tol, t + tol] cho bat ky target nao.
    """
    hits = []
    scanned = 0
    addr = base
    end = base + module_size
    while addr < end:
        buf = read_region(pm, addr, CHUNK)
        if buf:
            for i in range(0, len(buf) - 3, 4):
                val = struct.unpack_from("<f", buf, i)[0]
                if val != val:  # NaN
                    continue
                for t in targets:
                    if abs(val - t) <= tol:
                        hits.append(addr + i)
                        break
        addr += CHUNK
        scanned += CHUNK
        if scanned % (1 << 22) == 0:
            print(f"  da quet {scanned >> 20}MB...")
    return hits


def main():
    pm = pymem.Pymem(PROCESS_NAME)
    mod = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)
    base = mod.lpBaseOfDll
    size = mod.SizeOfImage
    print(f"Module {PROCESS_NAME}: base={hex(base)} size={size/1024/1024:.1f}MB")

    while True:
        line = input("Nhap toa do can tim (vi du: 130 120), hoac 'q' de thoat: ").strip()
        if line.lower() == "q":
            break
        try:
            targets = [float(x) for x in line.split()]
        except ValueError:
            print("Nhap sai. VD: 130 120 1")
            continue
        print(f"Quet theo {targets} ...")
        hits = scan_floats_near(pm, base, size, targets)
        if hits:
            print(f"Tim thay {len(hits)} dia chi:")
            for h in hits[:50]:
                print(f"  {hex(h)}")
        else:
            print("Khong tim thay. Thu giam tol hoac kiem tra toa do.")


if __name__ == "__main__":
    main()
