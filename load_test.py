#!/usr/bin/env python3
"""
Load Tester — themes.moonhost.shop / pgisliven.eu
Async HTTP/HTTPS performance testing with full metrics report.
Requirements: pip install aiohttp
"""

import asyncio
import time
import sys
import statistics
import ssl
from datetime import datetime

try:
    import aiohttp
except ImportError:
    print("Missing dependency. Run: pip install aiohttp")
    sys.exit(1)

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

# ──────────────────────────────────────────────
#  SITES
# ──────────────────────────────────────────────
SITES = {
    "1": {
        "name": "themes.moonhost.shop",
        "url":  "https://themes.moonhost.shop",
        "paths": ["/", "/shop", "/products", "/about", "/contact"],
    },
    "2": {
        "name": "pgisliven.eu",
        "url":  "https://pgisliven.eu",
        "paths": ["/", "/about", "/news", "/contact", "/gallery"],
    },
}

HEADERS = {
    "User-Agent": "LoadTester/1.0 (authorized performance test)",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# ──────────────────────────────────────────────
#  BANNER
# ──────────────────────────────────────────────
def banner():
    print(f"""
{C.CYAN}{C.BOLD}
 ██╗      ██████╗  █████╗ ██████╗     ████████╗███████╗███████╗████████╗
 ██║     ██╔═══██╗██╔══██╗██╔══██╗    ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝
 ██║     ██║   ██║███████║██║  ██║       ██║   █████╗  ███████╗   ██║
 ██║     ██║   ██║██╔══██║██║  ██║       ██║   ██╔══╝  ╚════██║   ██║
 ███████╗╚██████╔╝██║  ██║██████╔╝       ██║   ███████╗███████║   ██║
 ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝        ╚═╝   ╚══════╝╚══════╝   ╚═╝
{C.RESET}{C.YELLOW}         Async HTTP Performance Tester — your sites only{C.RESET}
""")

# ──────────────────────────────────────────────
#  SITE SELECTOR
# ──────────────────────────────────────────────
def select_site():
    print(f"{C.BOLD}Select target site:{C.RESET}\n")
    for k, v in SITES.items():
        print(f"  {C.GREEN}{k}{C.RESET}  —  {C.WHITE}{v['name']}{C.RESET}  ({v['url']})")
    print(f"  {C.GREEN}3{C.RESET}  —  Both sites (sequential)")
    print(f"  {C.RED}0{C.RESET}  —  Exit\n")

    choice = input(f"{C.CYAN}Choice{C.RESET} [1/2/3/0]: ").strip()
    if choice == "0":
        sys.exit(0)
    elif choice in SITES:
        return [SITES[choice]]
    elif choice == "3":
        return list(SITES.values())
    else:
        print(f"{C.RED}Invalid choice.{C.RESET}")
        return select_site()

# ──────────────────────────────────────────────
#  SETTINGS
# ──────────────────────────────────────────────
def ask_settings():
    print(f"\n{C.BOLD}Test configuration:{C.RESET}")

    def ask(label, default, cast=int):
        val = input(f"  {C.CYAN}{label}{C.RESET} [{C.YELLOW}{default}{C.RESET}]: ").strip()
        try:
            return cast(val) if val else default
        except ValueError:
            return default

    concurrent = ask("Concurrent connections", 100)
    duration   = ask("Duration (seconds)", 30)
    ramp_up    = ask("Ramp-up seconds (0 = instant)", 5)
    timeout    = ask("Request timeout (seconds)", 10)
    print()
    return concurrent, duration, ramp_up, timeout

# ──────────────────────────────────────────────
#  ASYNC WORKER
# ──────────────────────────────────────────────
results = []
results_lock = asyncio.Lock()
active_workers = 0

async def fetch(session, base_url, paths, timeout_s, stop_event):
    global active_workers
    connector_timeout = aiohttp.ClientTimeout(total=timeout_s)
    path_index = 0
    while not stop_event.is_set():
        path = paths[path_index % len(paths)]
        path_index += 1
        url = base_url.rstrip("/") + path
        t0 = time.monotonic()
        try:
            async with session.get(url, headers=HEADERS, ssl=False, allow_redirects=True) as resp:
                body = await resp.read()
                elapsed = (time.monotonic() - t0) * 1000  # ms
                async with results_lock:
                    results.append({
                        "ok": True,
                        "status": resp.status,
                        "ms": elapsed,
                        "bytes": len(body),
                    })
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - t0) * 1000
            async with results_lock:
                results.append({"ok": False, "status": 0, "ms": elapsed, "bytes": 0, "err": "timeout"})
        except Exception as e:
            elapsed = (time.monotonic() - t0) * 1000
            async with results_lock:
                results.append({"ok": False, "status": 0, "ms": elapsed, "bytes": 0, "err": str(e)[:40]})

# ──────────────────────────────────────────────
#  LIVE PROGRESS
# ──────────────────────────────────────────────
async def progress_reporter(duration, stop_event):
    start = time.monotonic()
    while not stop_event.is_set():
        await asyncio.sleep(1)
        elapsed = time.monotonic() - start
        snap = results[:]
        ok    = sum(1 for r in snap if r["ok"])
        err   = len(snap) - ok
        rps   = len(snap) / elapsed if elapsed > 0 else 0
        bw    = sum(r["bytes"] for r in snap) / elapsed if elapsed > 0 else 0
        avg   = statistics.mean(r["ms"] for r in snap) if snap else 0
        print(
            f"\r  {C.GREEN}OK: {ok:,}{C.RESET} | {C.RED}Err: {err:,}{C.RESET} | "
            f"{C.YELLOW}{rps:.0f} req/s{C.RESET} | "
            f"{C.BLUE}BW: {bw/1024:.1f} KB/s{C.RESET} | "
            f"{C.CYAN}Avg: {avg:.0f}ms{C.RESET} | "
            f"{C.WHITE}{elapsed:.0f}/{duration}s{C.RESET}  ",
            end="", flush=True
        )

# ──────────────────────────────────────────────
#  RAMP-UP
# ──────────────────────────────────────────────
async def run_test(site, concurrent, duration, ramp_up, timeout_s):
    global results
    results = []

    print(f"\n{C.BOLD}{C.CYAN}Testing: {site['name']}{C.RESET}")
    print(f"  Connections: {concurrent} | Duration: {duration}s | Ramp-up: {ramp_up}s\n")

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(
        limit=concurrent + 50,
        limit_per_host=concurrent,
        ssl=ssl_ctx,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )
    timeout = aiohttp.ClientTimeout(total=timeout_s, connect=5)

    stop_event = asyncio.Event()
    tasks = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Ramp up workers gradually
        if ramp_up > 0:
            batch = max(1, concurrent // max(1, ramp_up))
            for i in range(0, concurrent, batch):
                count = min(batch, concurrent - i)
                for _ in range(count):
                    t = asyncio.create_task(fetch(session, site["url"], site["paths"], timeout_s, stop_event))
                    tasks.append(t)
                await asyncio.sleep(1)
        else:
            for _ in range(concurrent):
                t = asyncio.create_task(fetch(session, site["url"], site["paths"], timeout_s, stop_event))
                tasks.append(t)

        # Progress reporter
        prog = asyncio.create_task(progress_reporter(duration, stop_event))

        # Wait for duration
        await asyncio.sleep(duration)
        stop_event.set()

        # Cancel all workers
        for t in tasks:
            t.cancel()
        prog.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    print()
    _print_report(site["name"], duration)

# ──────────────────────────────────────────────
#  REPORT
# ──────────────────────────────────────────────
def _print_report(site_name, duration):
    snap = results[:]
    if not snap:
        print(f"{C.RED}  No results collected.{C.RESET}")
        return

    ok     = [r for r in snap if r["ok"]]
    errors = [r for r in snap if not r["ok"]]
    times  = sorted(r["ms"] for r in ok) if ok else [0]
    total_bytes = sum(r["bytes"] for r in ok)

    def pct(lst, p):
        if not lst: return 0
        idx = int(len(lst) * p / 100)
        return lst[min(idx, len(lst)-1)]

    status_counts = {}
    for r in ok:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    err_counts = {}
    for r in errors:
        e = r.get("err", "unknown")
        err_counts[e] = err_counts.get(e, 0) + 1

    rps = len(snap) / duration if duration > 0 else 0
    bps = total_bytes / duration if duration > 0 else 0

    sep = f"{C.DIM}{'─'*56}{C.RESET}"
    print(f"\n{C.BOLD}{C.WHITE}{'═'*56}")
    print(f"  REPORT — {site_name}")
    print(f"{'═'*56}{C.RESET}")
    print(f"  {C.CYAN}Total requests  {C.RESET}: {len(snap):,}")
    print(f"  {C.GREEN}Successful      {C.RESET}: {len(ok):,}  ({100*len(ok)/len(snap):.1f}%)")
    print(f"  {C.RED}Errors          {C.RESET}: {len(errors):,}  ({100*len(errors)/len(snap):.1f}%)")
    print(sep)
    print(f"  {C.YELLOW}Throughput      {C.RESET}: {rps:.1f} req/s")
    print(f"  {C.YELLOW}Bandwidth       {C.RESET}: {bps/1024:.1f} KB/s  ({total_bytes/1024/1024:.2f} MB total)")
    print(sep)
    print(f"  {C.BLUE}Response times  {C.RESET}(successful requests)")
    print(f"    Min    : {min(times):.1f} ms")
    print(f"    Avg    : {statistics.mean(times):.1f} ms")
    print(f"    Median : {pct(times,50):.1f} ms")
    print(f"    p75    : {pct(times,75):.1f} ms")
    print(f"    p90    : {pct(times,90):.1f} ms")
    print(f"    p95    : {pct(times,95):.1f} ms")
    print(f"    p99    : {pct(times,99):.1f} ms")
    print(f"    Max    : {max(times):.1f} ms")
    if status_counts:
        print(sep)
        print(f"  {C.BLUE}HTTP Status codes{C.RESET}")
        for code, cnt in sorted(status_counts.items()):
            color = C.GREEN if 200 <= code < 300 else C.YELLOW if 300 <= code < 400 else C.RED
            print(f"    {color}{code}{C.RESET}  →  {cnt:,}")
    if err_counts:
        print(sep)
        print(f"  {C.RED}Error breakdown{C.RESET}")
        for e, cnt in sorted(err_counts.items(), key=lambda x: -x[1]):
            print(f"    {e[:40]}  →  {cnt:,}")
    print(f"{C.BOLD}{C.WHITE}{'═'*56}{C.RESET}\n")

# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
async def main():
    banner()
    selected_sites = select_site()
    concurrent, duration, ramp_up, timeout_s = ask_settings()

    print(f"{C.BOLD}Starting test at {datetime.now().strftime('%H:%M:%S')}...{C.RESET}")

    for site in selected_sites:
        await run_test(site, concurrent, duration, ramp_up, timeout_s)
        if len(selected_sites) > 1:
            print(f"{C.DIM}Cooling down 3s before next site...{C.RESET}")
            await asyncio.sleep(3)

    print(f"{C.GREEN}{C.BOLD}All tests complete.{C.RESET}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}Interrupted.{C.RESET}")
