"""
MU HOOK WSASend (frida) - bat buffer client gui di.

LUU Y QUAN TRONG:
  Luc WSASend duoc goi, MU DA MA hoa xong (CEncryptClient), nen buffer o day
  VAN LA CIPHERTEXT (giong sniff). De doc plaintext can hook ham GOI WSASend
  TRUOC KHI encrypt (thuong la CEncryptClient::Encrypt hoac ham send cua client).
  Script nay in them DIA CHI HAM GOI (caller module+offset) de ban tim duoc
  ham do trong debugger, sau do minh hook plaintext.

YEU CAU:
  pip install frida
  Mo game + dang nhap, roi chay:  python mu_hook_wsasend.py
"""
import frida
import sys

# Dat bang port game world server cua ban (55643 trong lan sniff) de loc bot
# goi cua kenh anti-cheat. De 0 de hien TAT CA.
GAME_PORT = 55643

JS = r"""
const GAME_PORT = __PORT__;
const is64 = Process.pointerSize === 8;

function hexdump(buf, len){
  var s = "";
  for (var i = 0; i < len; i++){
    var b = buf.add(i).readU8();
    s += ("0" + b.toString(16)).slice(-2) + (i % 16 === 15 ? "\n      " : " ");
  }
  return s;
}
function ascii(buf, len){
  var s = "";
  for (var i = 0; i < len; i++){
    var c = buf.add(i).readU8();
    s += (c >= 32 && c < 127) ? String.fromCharCode(c) : ".";
  }
  return s;
}
function callerInfo(ra){
  try {
    var sym = DebugSymbol.fromAddress(ra);
    if (sym && sym.name) return sym.moduleName + "!" + sym.name + " (+" + (ra - sym.address) + ")";
    var mod = Process.findModuleByAddress(ra);
    if (mod) return mod.name + "+" + (ra - mod.base);
    return ra.toString();
  } catch (e) { return ra.toString(); }
}

// WSABUF: len (4 byte) + buf pointer.
//   x86  (32-bit):  buf o offset 4
//   x64  (64-bit):  len(4) + pad(4) + buf(8) => buf o offset 8
var ws2 = Process.getModuleByName("ws2_32.dll");
var WSASend = ws2.findExportByName("WSASend");
console.log("[*] Hooked WSASend @ " + WSASend + "  (" + (is64 ? "x64" : "x86") + ")");

Interceptor.attach(WSASend, {
  onEnter: function (args){
    var lp = args[1];
    var buflen = lp.readU32();
    var buf = lp.add(is64 ? 8 : 4).readPointer();
    var ra = is64 ? this.context.rip : this.context.eip;  // ham goi WSASend
    send({
      kind: "pkt",
      len: buflen,
      caller: callerInfo(ra),
      hex: hexdump(buf, buflen),
      asc: ascii(buf, buflen)
    });
  }
});
"""

JS = JS.replace("__PORT__", str(GAME_PORT))


def on_message(message, data):
    if message["type"] == "send":
        p = message["payload"]
        if p.get("kind") == "pkt":
            print(f"[{p['len']}B] caller={p['caller']}")
            print("  hex:", p["hex"])
            print("  asc:", p["asc"])
            print("-" * 60)
    elif message["type"] == "error":
        print("FRIDA ERROR:", message.get("description"))


def find_pid():
    for proc in frida.get_local_device().enumerate_processes():
        if proc.name.lower() == "main.exe":
            return proc.pid
    return None


def main():
    pid = find_pid()
    if pid is None:
        sys.exit("Khong tim thay main.exe. Mo game + dang nhap truoc.")
    print(f"[*] Attach PID={pid}")
    session = frida.get_local_device().attach(pid)
    script = session.create_script(JS)
    script.on("message", on_message)
    script.load()
    print("[*] Dang hook... (Ctrl+C de dung)\n")
    try:
        sys.stdin.read()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
