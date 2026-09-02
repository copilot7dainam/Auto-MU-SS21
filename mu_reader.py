"""
Doc tọa độ nhân vật MU theo pointer chain (dung sau khi da tim duoc dia chi).
Yeu cau: pip install pymem

Cach dung: tu scanner, ban co struct base S va biet X o offset OX, Y o OY.
Neu tim duoc pointer (main.exe + 0xABCD -> *(+0x10) -> *(+0x20) = X),
thi dien CHAR_STRUCT_CHAIN = [0xABCD, 0x10, 0x20]. Neu khong co pointer,
chi co dia chi tuyet doi tuyen tinh, thi CHAR_STRUCT_CHAIN = [] va
dien ABSOLUTE_ADDR = dia chi do (co the thay doi moi lan mo game neu khong co base).
"""
import time
import pymem
import pymem.process

PROCESS_NAME = "main.exe"
IS_64BIT    = False

# Da xac nhan: X=0xb80af60, Y=0xb80af64 (cach nhau 4 byte = 1 float).
# Dia chi TUYET DOI, co the doi moi lan mo game (ASLR) -> quet lai neu doc sai.
# Neu muon co dinh, can tim pointer chain (main.exe+off -> ...), lam bang CE/ptr scan.
CHAR_STRUCT_CHAIN = []          # de trong vi dung dia chi tuyet doi
ABSOLUTE_ADDR = 0xb80af60      # base struct = X; Y nam o +4

OFFSET_X = 0x00   # X
OFFSET_Y = 0x04   # Y (ngay sau X)
OFFSET_Z = 0x08   # Z (neu game co; doc se ra 0 hoac rac neu khong co)

POLL = 0.2


def rd_ptr(pm, a):
    return pm.read_ulonglong(a) if IS_64BIT else pm.read_uint(a)


def resolve(pm, base, chain):
    if not chain:
        return ABSOLUTE_ADDR
    addr = base + chain[0]
    for off in chain[1:]:
        addr = rd_ptr(pm, addr) + off
    return addr


def main():
    pm = pymem.Pymem(PROCESS_NAME)
    mod = pymem.process.module_from_name(pm.process_handle, PROCESS_NAME)
    base = mod.lpBaseOfDll
    print(f"Gan vao {PROCESS_NAME} base={hex(base)}")

    try:
        while True:
            sa = resolve(pm, base, CHAR_STRUCT_CHAIN)
            x = pm.read_float(sa + OFFSET_X)
            y = pm.read_float(sa + OFFSET_Y)
            z = pm.read_float(sa + OFFSET_Z)
            print(f"X={x:9.2f}  Y={y:9.2f}  Z={z:9.2f}  (struct={hex(sa)})",
                  end="\r", flush=True)
            time.sleep(POLL)
    except KeyboardInterrupt:
        print("\nDung.")
    except Exception as e:
        print(f"\nLoi (offset sai hoac game dong / bi kill): {e}")


if __name__ == "__main__":
    main()
