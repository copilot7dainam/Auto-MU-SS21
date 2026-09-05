"""
MU SNIFF - bat goi tin TCP client (main.exe) gui di / nhan ve.

MU ma hoa payload (CEncryptClient), nen noi dung la ciphertext. Tuy nhien:
  - Byte dau thuong la OPCODE (nhung cung bi XOR trong S21).
  - Kich thuoc goi tin (len) va THOI DIEM gui la chi muc tot nhat de biet
    goi nao tuong ung voi 1 hanh dong (vi du: go lenh /move).

Cach dung:
  1. Mo game, dang nhap vao nhan vat.
  2. Chay:  python mu_sniff.py
  3. Dung yen vai giay (capture nen) -> ghi nho cac goi phat ra.
  4. Go lenh move (vi du /move Lorencia) -> xem goi nao phat ra NGAY LUC do.
     Do chinh la goi lenh move.

Phu thuoc: pip install scapy  +  Npcap (https://npcap.com) cai dat.
Chay PowerShell Admin.
"""
import subprocess
import sys
import time

try:
    from scapy.all import sniff, TCP, Raw, hexdump
except ImportError:
    sys.exit("Chua cai scapy:  pip install scapy  (va cai Npcap)")


def find_main_exe():
    """Tra ve (pid, [(remote_addr, remote_port, local_port), ...]) cua main.exe."""
    # Lay tat ca tien trinh ten main.exe
    ps = subprocess.run(
        ["powershell", "-noprofile", "-c",
         "Get-Process main -ErrorAction SilentlyContinue | Select-Object Id | ConvertTo-Json"],
        capture_output=True, text=True)
    txt = ps.stdout.strip()
    if not txt:
        return None, []
    # Co the la 1 hoac nhieu (object hoac mang)
    import json
    try:
        data = json.loads(txt)
        pids = [data["Id"]] if isinstance(data, dict) else [d["Id"] for d in data]
    except Exception:
        return None, []
    conns = []
    for pid in pids:
        pc = subprocess.run(
            ["powershell", "-noprofile", "-c",
             f"Get-NetTCPConnection -OwningProcess {pid} -State Established "
             "| Select-Object RemoteAddress,RemotePort,LocalPort | ConvertTo-Json"],
            capture_output=True, text=True)
        try:
            d = json.loads(pc.stdout.strip())
            rows = [d] if isinstance(d, dict) else d
            for r in rows:
                conns.append((r["RemoteAddress"], int(r["RemotePort"]), int(r["LocalPort"])))
        except Exception:
            pass
    return pids[0], conns


def main():
    pid, conns = find_main_exe()
    if pid is None or not conns:
        sys.exit("Khong tim thay main.exe dang co ket noi TCP. Mo game + dang nhap truoc.")
    print(f"[*] PID={pid} | cac ket noi:")
    for a, rp, lp in conns:
        print(f"    {a}:{rp}  (local port {lp})")

    # filter BPF: bat tat ca TCP cua cac remote addr/port tren
    bpf_parts = []
    for a, rp, lp in conns:
        bpf_parts.append(f"(host {a} and (port {rp}))")
    bpf = " or ".join(bpf_parts)
    print(f"[*] BPF filter: {bpf}")
    print("[*] Bat dau sniff... (Ctrl+C de dung)\n")

    seen = set()
    def cb(pkt):
        if not (TCP in pkt and Raw in pkt):
            return
        tcp = pkt[TCP]
        # xac dinh huong: local port cua minh la source -> di ra
        out = any(lp == tcp.sport for (_, _, lp) in conns)
        payload = bytes(pkt[Raw].load)
        tag = ">>> CLIENT->SERVER (gui)" if out else "<<< SERVER->CLIENT (nhan)"
        # in thoi gian de biet goi nao phat ra luc go lenh
        t = time.strftime("%H:%M:%S")
        print(f"[{t}] {tag}  len={len(payload)}  sport={tcp.sport} dport={tcp.dport}")
        # chi hexdump goi di ra (lenh cua client)
        if out:
            hexdump(payload)
        print("-" * 60)

    try:
        sniff(filter=bpf, prn=cb, store=0, promisc=False)
    except KeyboardInterrupt:
        print("\n[*] Dung.")


if __name__ == "__main__":
    main()
