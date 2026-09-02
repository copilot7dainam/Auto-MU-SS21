"""
Tim pointer chain toi toa do nhan vat MA BUT KHONG DUNG CE.
- Kiem tra ASLR cua main.exe qua PE header (DllCharacteristics).
- Neu khong ASLR -> dia chi la STATIC, offset co dinh = target - base, khong can chain.
- Neu ASLR -> chay pointer scan (numpy) tim chuoi base -> deref + offset -> ... -> target.

Yeu cau: pip install pymem numpy
Chay: python mu_ptrscan.py
"""
import struct
import numpy as np
import pymem
import pymem.process

PROCESS_NAME = "main.exe"
CHUNK        = 1 << 16
TARGET       = 0xb80af60   # X tim duoc
OFF_MIN, OFF_MAX, OFF_STEP = 0, 0x1000, 4   # cac offset moi cap deref
MAX_DEPTH    = 3
MAX_PER_LVL  = 500         # gioi han ung vien moi cap de tranh no


def read_module(pm, mod):
    """Doc toan bo module vao mot bytes buffer (nhieu lan 64KB)."""
    base, size = mod.lpBaseOfDll, mod.SizeOfImage
    out = bytearray()
    addr = base
    end = base + size
    while addr < end:
        try:
            out += pm.read_bytes(addr, CHUNK)
        except Exception:
            out += b"\x00" * CHUNK
        addr += CHUNK
        if (addr - base) % (1 << 22) == 0:
            print(f"  doc {(addr-base)>>20}MB / {size>>20}MB")
    return bytes(out), base, size


def pe_is_aslr(buf):
    """Tra ve True neu exe co DYNAMIC_BASE (ASLR). False = dia chi tinh."""
    if buf[:2] != b"MZ":
        return None
    e_lfanew = struct.unpack_from("<I", buf, 0x3C)[0]
    # Optional header DllCharacteristics tai nt+24+0x40
    dll_char = struct.unpack_from("<H", buf, e_lfanew + 24 + 0x40)[0]
    return bool(dll_char & 0x40)


def main():
    pm = pymem.Pymem(PROCESS_NAME)
    mod = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)
    base, size = mod.lpBaseOfDll, mod.SizeOfImage
    print(f"Module {PROCESS_NAME}: base={hex(base)} size={size/1024/1024:.1f}MB")

    print("Doc toan bo module de pointer-scan...")
    buf, base, size = read_module(pm, mod)

    aslr = pe_is_aslr(buf)
    print(f"ASLR (DYNAMIC_BASE): {aslr}")
    rel = TARGET - base
    print(f"Static offset tu module base: 0x{rel:X}  (base + 0x{rel:X} = {hex(TARGET)})")
    if aslr is False:
        print("=> main.exe KHONG ASLR: dia chi co dinh, dung base+0x%X la xong, "
              "khong can pointer chain." % rel)
        return

    print("ASLR bat / khong ro -> chay pointer scan tim chain...")
    arr = np.frombuffer(buf, dtype="<u4")   # view uint32 little-endian
    B, SZ = base, size

    def preimages(target):
        """Tap dia chi A trong module sao cho u32(A) [+ offset] == target."""
        t = target & 0xFFFFFFFF
        res = set()
        for o in range(OFF_MIN, OFF_MAX, OFF_STEP):
            to = (t - o) & 0xFFFFFFFF
            for i in np.where(arr == to)[0][:MAX_PER_LVL]:
                A = B + int(i) * 4
                res.add((A, o))
                if len(res) >= MAX_PER_LVL:
                    return res
        return res

    # BFS ngược: tầng 1 = A sao cho u32(A)+o = T. Tầng k+1 = preimages của các A tầng trước.
    # chain luu (root_abs, [offsets tu root den target])
    frontier = {TARGET: [(TARGET, [])]}   # target -> list (root, offs) giai tao target
    for depth in range(1, MAX_DEPTH + 1):
        new_frontier = {}
        for tgt, chains in frontier.items():
            for A, o in preimages(tgt):
                for root, offs in chains:
                    new_chain = (root, [o] + offs)
                    new_frontier.setdefault(A, []).append(new_chain)
        # tai tung nay, A la "target moi" (can tim preimage cua A o tang sau)
        frontier = {A: ch for A, ch in new_frontier.items()}
        if not frontier:
            break
        print(f"Tim thay {sum(len(v) for v in frontier.values())} chain ung vien tai do sau {depth}")

    # In cac chain tim duoc (root la dia chi tinh, offs la cac offset can cong sau moi deref)
    found = []
    for A, chains in frontier.items():
        for root, offs in chains:
            found.append((root, offs))
    if not found:
        print("Khong tim thay chain (co the toa do la static truc tiep, hoac nam tren heap).")
        return
    print(f"\n{len(found)} pointer chain tim duoc (root = module + offset):")
    for root, offs in sorted(found, key=lambda x: len(x[1]))[:30]:
        roff = root - B
        # chain: base+roff -> *()+offs[0] -> *()+offs[1] ...
        parts = [f"main.exe + 0x{roff:X}"]
        for o in offs:
            parts.append(f"*() + 0x{o:X}")
        print("  " + " -> ".join(parts) + f"  == 0x{TARGET:X}")


if __name__ == "__main__":
    main()
