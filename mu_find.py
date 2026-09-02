"""
Tim toa do nhan vat MU theo workflow giong Cheat Engine:
  1) scan <X Y>   -> quet toan bo module lan dau, luu cac dia chi khop
  2) scan <X Y>   -> CHI kiem lai cac dia chi cu (nex scan), loc giam nhanh
  3) watch        -> POLL cac ung vien, in ra dia chi nao THAY DOI khi ban di chuyen
  4) rec <addr>   -> doc 1 dia chi lap lai de quan sat
  5) q            -> thoat

Yeu cau: pip install pymem
"""
import time
import struct
import pymem
import pymem.process

PROCESS_NAME = "main.exe"
IS_64BIT    = False
CHUNK       = 1 << 16        # 64KB
TOL         = 0.5            # do dung sai float (thu 0.5, 0.1 neu qua nhieu)
PTR_SIZE    = 8 if IS_64BIT else 4

hits = set()   # tap dia chi ung vien hien tai
pm   = None
base, size = 0, 0


def rd_ptr(a):
    return pm.read_ulonglong(a) if IS_64BIT else pm.read_uint(a)


def read_float_try(a):
    try:
        return struct.unpack("<f", pm.read_bytes(a, 4))[0]
    except Exception:
        return None


def full_scan(targets):
    """Quet toan bo module, tra ve tap dia chi co float nam trong +-TOL cua bat ky target."""
    found = set()
    addr = base
    end  = base + size
    while addr < end:
        try:
            buf = pm.read_bytes(addr, CHUNK)
        except Exception:
            addr += CHUNK
            continue
        for i in range(0, len(buf) - 3, 4):
            val = struct.unpack_from("<f", buf, i)[0]
            if val != val:
                continue
            for t in targets:
                if abs(val - t) <= TOL:
                    found.add(addr + i)
                    break
        addr += CHUNK
        if (addr - base) % (1 << 22) == 0:
            print(f"  quet { (addr-base)>>20 }MB / {size>>20}MB  hit={len(found)}")
    return found


def narrow_scan(targets):
    """Chi doc lai cac dia chi da co trong 'hits' (next scan). Nhanh va giam nhieu."""
    keep = set()
    for a in hits:
        v = read_float_try(a)
        if v is None:
            continue
        for t in targets:
            if abs(v - t) <= TOL:
                keep.add(a)
                break
    return keep


def watch():
    """Poll cac ung vien nhieu lan, bao cao dia chi thay doi."""
    if not hits:
        print("Chua co ung vien. Hay 'scan' truoc.")
        return
    print(f"WATCH: poll {len(hits)} ung vien. Di chuyen nhan vat qua lai, "
          f"giu yen vai giay giua cac lan. Ctrl+C de dung.\n")
    snap = {}
    try:
        while True:
            cur = {}
            for a in hits:
                v = read_float_try(a)
                if v is not None:
                    cur[a] = v
            # phat hien thay doi
            changed = []
            for a in cur:
                if a in snap and abs(cur[a] - snap[a]) > 0.01:
                    changed.append(a)
            if changed:
                line = "  CHANGED: " + "  ".join(
                    f"{hex(a)}={cur[a]:.2f}" for a in changed[:20])
                print(line, flush=True)
            snap = cur
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\nWATCH dung.")


def rec(addr_hex):
    """Doc 1 dia chi lap lai de quan sat."""
    a = int(addr_hex, 16)
    try:
        while True:
            v = read_float_try(a)
            print(f"{hex(a)} = {v}", end="\r", flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print()


def main():
    global pm, base, size, hits
    pm = pymem.Pymem(PROCESS_NAME)
    mod = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)
    base, size = mod.lpBaseOfDll, mod.SizeOfImage
    print(f"Gan {PROCESS_NAME}: base={hex(base)} size={size/1024/1024:.1f}MB")
    print("Lenh: scan <X Y> | watch | rec <addr> | q")

    while True:
        line = input("> ").strip()
        if line.lower() == "q":
            break
        if line.lower() == "watch":
            watch()
            continue
        if line.lower().startswith("rec "):
            rec(line.split()[1])
            continue
        if line.lower().startswith("scan"):
            parts = line.split()[1:]
            if not parts:
                print("Thieu toa do. VD: scan 53 225")
                continue
            try:
                targets = [float(x) for x in parts]
            except ValueError:
                print("Toa do sai.")
                continue
            if not hits:
                print(f"FULL scan theo {targets} (lan dau)...")
                hits = full_scan(targets)
            else:
                print(f"NEXT scan theo {targets} tren {len(hits)} ung vien...")
                hits = narrow_scan(targets)
            print(f"-> con {len(hits)} ung vien.")
            if len(hits) <= 60:
                print("  ", " ".join(hex(h) for h in sorted(hits)))
        else:
            print("Khong hieu. Dung: scan / watch / rec / q")


if __name__ == "__main__":
    main()
