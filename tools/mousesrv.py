import socket, threading, sys, os, time

FIFO = "/tmp/mouse.fifo"
state = {"l": 0, "r": 0, "conn": None}
lock = threading.Lock()

def pkt(dx, dy):
    dx = max(-128, min(127, dx)); dy = max(-128, min(127, dy))
    b1 = 0x40 | (state["l"] << 5) | (state["r"] << 4) | (((dy >> 6) & 3) << 2) | ((dx >> 6) & 3)
    return bytes([b1, dx & 0x3F, dy & 0x3F])

def send(data):
    c = state["conn"]
    if c:
        try: c.sendall(data)
        except Exception as e: print("send err", e, flush=True)

def move(dx, dy, chunk=30, delay=0.04):
    while dx or dy:
        sx = max(-chunk, min(chunk, dx)); sy = max(-chunk, min(chunk, dy))
        send(pkt(sx, sy)); dx -= sx; dy -= sy
        time.sleep(delay)

def handle(cmd):
    p = cmd.split()
    if not p: return
    if p[0] == "m": move(int(p[1]), int(p[2]))
    elif p[0] == "p": move(int(p[1]), int(p[2]), chunk=3, delay=0.045)  # precise: small packets, 1200-baud pacing
    elif p[0] == "c":
        state["l"] = 1; send(pkt(0, 0)); time.sleep(0.15)
        state["l"] = 0; send(pkt(0, 0)); time.sleep(0.1)
    elif p[0] == "r":
        state["r"] = 1; send(pkt(0, 0)); time.sleep(0.15)
        state["r"] = 0; send(pkt(0, 0)); time.sleep(0.1)
    elif p[0] == "ld": state["l"] = 1; send(pkt(0, 0))
    elif p[0] == "lu": state["l"] = 0; send(pkt(0, 0))
    elif p[0] == "rd": state["r"] = 1; send(pkt(0, 0))
    elif p[0] == "ru": state["r"] = 0; send(pkt(0, 0))
    print("did:", cmd, flush=True)

def fifo_loop():
    try: os.unlink(FIFO)
    except FileNotFoundError: pass
    os.mkfifo(FIFO)
    while True:
        with open(FIFO) as f:
            for line in f:
                line = line.strip()
                if line: handle(line)

t = threading.Thread(target=fifo_loop, daemon=True); t.start()

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 13999)); srv.listen(1)
print("listening on 13999", flush=True)
while True:
    conn, addr = srv.accept()
    print("guest connected", addr, flush=True)
    state["conn"] = conn
    time.sleep(0.3)
    conn.sendall(b"M")   # Microsoft serial mouse ID
    print("sent M after connect", flush=True)
    lastm = [0.0]
    try:
        while True:
            d = conn.recv(4096)
            if not d: break
            print("guest sent bytes:", d, flush=True)
            # DOSBox nullmodem reports line-state changes as \xff escapes;
            # a DTR/RTS toggle is the mouse driver probing -> answer with 'M' fast.
            now = time.time()
            if now - lastm[0] > 0.15:
                lastm[0] = now
                time.sleep(0.03)
                try:
                    conn.sendall(b"M")
                    print("replied M to probe", flush=True)
                except Exception as e:
                    print("M send err", e, flush=True)
    except Exception as e:
        print("conn err", e, flush=True)
    state["conn"] = None
