#!/usr/bin/env python3
"""伙伴云使用手册浏览器走查驱动：Playwright 持久化会话 + CDP 常驻连接。

用法（每个子命令独立进程执行，浏览器窗口跨命令常驻）：
  python3 browser.py start [--url https://app.huoban.com]   # 启动浏览器（持久化 profile，首次需人工登录）
  python3 browser.py status                                 # 列出当前所有页面
  python3 browser.py goto --url <url>
  python3 browser.py snapshot [--max-chars 4000]            # 页面文本 + 可交互元素编号清单
  python3 browser.py click (--index N | --text T | --selector S)
  python3 browser.py type --text "内容" [--enter]           # 输入到当前焦点元素
  python3 browser.py fill --selector S --value V
  python3 browser.py press --keys "Escape"
  python3 browser.py scroll --dy 600
  python3 browser.py wait (--ms N | --selector S | --text T)
  python3 browser.py shot --path out.png [--selector S] [--highlight S1,,S2] [--full-page]
  python3 browser.py eval --js "document.title"
  python3 browser.py page --index N                         # 切换活动页面（多标签时）
  python3 browser.py stop
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = 9333
PROFILE = Path.home() / ".hb-manual-profile"
STATE = PROFILE / "driver-state.json"
# 窗口默认最大化，自适应当前屏幕（--start-maximized），截图尺寸即最大化后的窗口尺寸。
# 屏幕本身偏小、内容仍被压到屏幕外时，用 HB_WIN=宽x高 强制放大渲染视口（窗口不变，
# 页面按指定尺寸布局并截图），例如 HB_WIN=2560x1440。
# 真实窗口小于这个尺寸才做放大兜底。定得过高会把页面强行撑大再塞进小窗口，
# 屏幕上看着变形、且每条命令都覆盖一次手动调整的窗口，观感来回横跳。
# 1440×800 是「笔记本满屏」的常见下限，达到即不干预（Retina 下截图已有 2880 像素宽）。
MIN_W, MIN_H = 1440, 800
WIDTH = HEIGHT = 0
_win = os.environ.get("HB_WIN", "")
if "x" in _win:
    try:
        WIDTH, HEIGHT = (int(v) for v in _win.lower().split("x", 1))
    except ValueError:
        WIDTH = HEIGHT = 0

# 逐个渲染过的文本节点取文：innerText 在某些弹层（如自动化编辑器）会整块漏掉
TEXT_JS = """
() => {
  const out = [];
  const w = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
  let n, last = '';
  while ((n = w.nextNode())) {
    const t = (n.nodeValue || '').replace(/\\s+/g, ' ').trim();
    if (!t || t === last) continue;
    const p = n.parentElement;
    if (!p || ['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(p.tagName)) continue;
    const cs = getComputedStyle(p);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const r = p.getBoundingClientRect();
    if (r.width < 1 && r.height < 1) continue;
    out.push(t);
    last = t;
  }
  return out.join('\\n');
}
"""

ENUM_JS = """
() => {
  const sel = 'a,button,input,select,textarea,[role=button],[role=tab],[role=menuitem],[role=option],[role=checkbox],[role=radio],[contenteditable=true]';
  const out = [];
  document.querySelectorAll(sel).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) return;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') return;
    let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
    if (text.length > 60) text = text.slice(0, 60) + '…';
    out.push({tag: el.tagName.toLowerCase(), type: el.getAttribute('type') || '', text,
              x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)});
  });
  return out;
}
"""


def cdp_alive() -> bool:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=2)
        return True
    except Exception:
        return False


def cmd_start(args):
    if cdp_alive():
        print("浏览器已在运行，无需重复启动")
        return
    PROFILE.mkdir(parents=True, exist_ok=True)
    lock = PROFILE / "SingletonLock"
    if lock.exists():
        lock.unlink()
    subprocess.Popen(
        [sys.executable, __file__, "_keeper", "--url", args.url],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(40):
        if cdp_alive():
            fit_window_to_screen()
            print(f"浏览器已启动（profile: {PROFILE}）。若尚未登录伙伴云，请让用户在窗口中完成登录。")
            return
        time.sleep(0.5)
    sys.exit("浏览器启动失败：CDP 端口未就绪")


def fit_window_to_screen():
    """把浏览器窗口铺满主屏（纯观感，截图尺寸由 ensure_metrics 决定）。

    走 macOS 的 System Events，需要「辅助功能」权限；没授权就静默跳过，不影响走查。
    授权路径：系统设置 → 隐私与安全性 → 辅助功能 → 勾上运行本脚本的终端 / Claude Code。
    """
    if sys.platform != "darwin":
        return
    script = '''
    tell application "Finder" to set b to bounds of window of desktop
    set scrW to item 3 of b
    set scrH to item 4 of b
    tell application "System Events"
      set procs to (every process whose name contains "Chrome for Testing")
      if (count of procs) = 0 then return "no-proc"
      tell item 1 of procs
        set position of window 1 to {0, 25}
        set size of window 1 to {scrW, scrH - 25}
      end tell
    end tell
    return "ok"
    '''
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
    except Exception:
        pass


def cmd_keeper(args):
    """常驻子进程：托管浏览器生命周期，浏览器关闭后自动退出。"""
    log = open(PROFILE / "keeper.log", "w")
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(PROFILE), headless=False, viewport=None,
                args=[f"--remote-debugging-port={PORT}", "--start-maximized",
                      "--disable-session-crashed-bubble", "--hide-crash-restore-bubble"],
                ignore_default_args=["--enable-automation"])
            print("browser up", file=log, flush=True)
            if args.url:
                ctx.pages[0].goto(args.url, wait_until="domcontentloaded")
            closed = {"flag": False}
            ctx.on("close", lambda _: closed.update(flag=True))
            while not closed["flag"]:
                time.sleep(2)
            print("browser closed, keeper exit", file=log, flush=True)
    except Exception as e:
        print(f"keeper error: {e!r}", file=log, flush=True)
        raise


def read_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {}


def get_page(browser):
    pages = []
    for _ in range(6):
        pages = [pg for ctx in browser.contexts for pg in ctx.pages]
        if pages:
            break
        time.sleep(0.5)
    state = read_state()
    if not pages:
        # 页面被回收：自愈，新开一页并恢复上次 URL（登录态在 profile 里，不受影响）
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        last = state.get("url", "https://app.huoban.com")
        page.goto(last, wait_until="domcontentloaded")
        print(f"（页面已被浏览器回收，自动新开并恢复：{last}）")
        return page, [page]
    idx = state.get("page", 0)
    if not 0 <= idx < len(pages):
        idx = len(pages) - 1
    return pages[idx], pages


def connect():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
    except Exception:
        p.stop()
        sys.exit("连不上浏览器：先执行 start，并确认窗口没有被手动关闭")
    return p, browser


def fill_screen(page):
    """把窗口铺满主屏可用区（走 CDP 的 Browser.setWindowBounds，不需要系统辅助权限）。

    每条命令都会经过这里，但只在窗口明显小于屏幕时动手，避免覆盖用户手动调的窗口。
    """
    try:
        aw, ah = page.evaluate("[screen.availWidth, screen.availHeight]")
        cdp = page.context.new_cdp_session(page)
        wid = cdp.send("Browser.getWindowForTarget")["windowId"]
        b = cdp.send("Browser.getWindowBounds", {"windowId": wid})["bounds"]
        if b.get("width", 0) >= aw - 40 and b.get("height", 0) >= ah - 80:
            return  # 已基本铺满，不动
        if b.get("windowState") != "normal":
            cdp.send("Browser.setWindowBounds",
                     {"windowId": wid, "bounds": {"windowState": "normal"}})
        # 只调尺寸不动 left/top：窗口在哪块屏就铺满哪块屏，不要把它挪去主屏
        # （availWidth/availHeight 是页面所在屏幕的可用区，天然按当前屏取值）
        cdp.send("Browser.setWindowBounds",
                 {"windowId": wid, "bounds": {"width": aw, "height": ah}})
        page.wait_for_timeout(400)
    except Exception:
        pass


def ensure_metrics(page):
    """把渲染视口撑到 WIDTH×HEIGHT。

    物理窗口受屏幕尺寸限制（笔记本屏往往只有 1400 多逻辑像素宽），直接开大窗口会被系统裁掉，
    导致工作台的筛选区、子表页签被压到屏幕外，走查时整块漏内容。这里用 CDP 覆盖渲染尺寸：
    窗口还是那么大，但页面按 WIDTH×HEIGHT 布局，截图也是这个尺寸，一屏能装下的内容更多。
    deviceScaleFactor=2 保证截图在高分屏下依旧清晰。
    """
    fill_screen(page)

    w, h = WIDTH, HEIGHT
    if not (w and h):
        # 自适应：窗口本身够宽（大屏最大化）就按真实尺寸截，不做任何干预；
        # 窗口偏小（小屏，或 Chrome 把可用屏幕识别得很小）才撑到 MIN_W×MIN_H。
        try:
            real = page.evaluate("[innerWidth, innerHeight]")
        except Exception:
            return
        if real[0] >= MIN_W and real[1] >= MIN_H:
            return
        w, h = max(real[0], MIN_W), max(real[1], MIN_H)
    try:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": w, "height": h,
            "deviceScaleFactor": 2, "mobile": False,
        })
    except Exception:
        pass  # 覆盖失败就按真实窗口走，不阻断走查


def run(fn):
    p, browser = connect()
    try:
        page, pages = get_page(browser)
        ensure_metrics(page)
        fn(page, pages)
        state = read_state()
        try:
            state["url"] = page.url
        except Exception:
            pass
        STATE.write_text(json.dumps(state))
    finally:
        p.stop()


def cmd_status(args):
    def fn(page, pages):
        for i, pg in enumerate(pages):
            mark = " ←当前" if pg == page else ""
            print(f"[{i}] {pg.title()[:50]} | {pg.url}{mark}")
    run(fn)


def cmd_page(args):
    state = read_state()
    state["page"] = args.index
    STATE.write_text(json.dumps(state))
    cmd_status(args)


def cmd_goto(args):
    def fn(page, pages):
        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        print(f"已打开：{page.title()} | {page.url}")
    run(fn)


def cmd_snapshot(args):
    def fn(page, pages):
        try:
            page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass
        print(f"URL: {page.url}\n标题: {page.title()}\n")
        text = page.evaluate(TEXT_JS)
        if len(text) > args.max_chars:
            text = text[:args.max_chars] + f"\n…（截断，共 {len(text)} 字符）"
        print("--- 页面文本 ---")
        print(text)
        print("\n--- 可交互元素 ---")
        for i, el in enumerate(page.evaluate(ENUM_JS)):
            label = el["text"] or f'<{el["tag"]} {el["type"]}>'.strip()
            print(f"[{i}] {el['tag']}{'/' + el['type'] if el['type'] else ''}: {label}")
    run(fn)


def cmd_click(args):
    def fn(page, pages):
        if args.at:
            x, y = (int(v) for v in args.at.split(","))
            page.mouse.click(x, y)
            print(f"已点击坐标 ({x}, {y})")
        elif args.index is not None:
            els = page.evaluate(ENUM_JS)
            if args.index >= len(els):
                sys.exit(f"index 超界：当前只有 {len(els)} 个元素，先重新 snapshot")
            el = els[args.index]
            page.mouse.click(el["x"], el["y"])
            print(f"已点击 [{args.index}] {el['text'] or el['tag']}")
        elif args.text:
            page.get_by_text(args.text, exact=False).first.click(timeout=8000)
            print(f"已点击文本「{args.text}」")
        else:
            page.locator(args.selector).first.click(timeout=8000)
            print(f"已点击 {args.selector}")
        page.wait_for_timeout(1200)
        print(f"当前页面：{page.title()} | {page.url}")
    run(fn)


def cmd_type(args):
    def fn(page, pages):
        page.keyboard.type(args.text, delay=30)
        if args.enter:
            page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        print("已输入")
    run(fn)


def cmd_fill(args):
    def fn(page, pages):
        page.locator(args.selector).first.fill(args.value, timeout=8000)
        print(f"已填写 {args.selector}")
    run(fn)


def cmd_press(args):
    def fn(page, pages):
        page.keyboard.press(args.keys)
        page.wait_for_timeout(800)
        print(f"已按键 {args.keys}")
    run(fn)


def cmd_scroll(args):
    def fn(page, pages):
        page.mouse.wheel(0, args.dy)
        page.wait_for_timeout(600)
        print(f"已滚动 {args.dy}")
    run(fn)


def cmd_wait(args):
    def fn(page, pages):
        if args.selector:
            page.locator(args.selector).first.wait_for(timeout=args.timeout)
        elif args.text:
            page.get_by_text(args.text).first.wait_for(timeout=args.timeout)
        else:
            page.wait_for_timeout(args.ms)
        print("等待完成")
    run(fn)


# 用浮层画框，不改元素自身样式：outline 会被祖先的 overflow:hidden 裁掉。
# 多个框时按选择器传入顺序在框左上角标序号角标（传入顺序=步骤顺序）；单框不标。
# 序号的含义写在文档步骤文字里，不写进图内。
HIGHLIGHT_ON = """
(sels) => {
  const box = document.createElement('div');
  box.id = '__hbHl';
  box.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647';
  const rects = [];
  sels.forEach(s => document.querySelectorAll(s).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    rects.push(r);
  }));
  rects.forEach((r, i) => {
    // 柔和描边样式：珊瑚色圆角框 + 白色外圈 + 轻投影
    const m = document.createElement('div');
    m.style.cssText = `position:absolute;left:${r.left - 4}px;top:${r.top - 4}px;` +
      `width:${r.width + 8}px;height:${r.height + 8}px;` +
      'border:3px solid #D97757;border-radius:10px;box-sizing:border-box;' +
      'box-shadow:0 0 0 3px #fff, 2px 3px 6px rgba(31,35,41,.4), inset 0 0 0 2px #fff';
    box.appendChild(m);
    if (rects.length > 1) {
      const b = document.createElement('div');
      b.style.cssText = `position:absolute;left:${Math.max(2, r.left - 15)}px;top:${Math.max(2, r.top - 15)}px;` +
        'width:22px;height:22px;border-radius:50%;background:#D97757;color:#fff;' +
        'box-shadow:0 0 0 2px #fff;display:flex;align-items:center;justify-content:center;' +
        'font:bold 13px -apple-system,sans-serif';
      b.textContent = String(i + 1);
      box.appendChild(b);
    }
  });
  document.body.appendChild(box);
}
"""
HIGHLIGHT_OFF = "() => { const b = document.getElementById('__hbHl'); if (b) b.remove(); }"

# 不可逆遮挡：在元素上盖不透明块，只用于密钥、令牌、密码等不能入图的秘密
MASK_ON = """
(sels) => {
  const box = document.createElement('div');
  box.id = '__hbMask';
  box.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483646';
  sels.forEach(s => document.querySelectorAll(s).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    const m = document.createElement('div');
    m.style.cssText = `position:absolute;left:${r.left}px;top:${r.top}px;` +
      `width:${r.width}px;height:${r.height}px;background:#8A8F98;border-radius:3px;` +
      'display:flex;align-items:center;justify-content:center;color:#fff;' +
      'font:12px -apple-system,sans-serif;letter-spacing:1px';
    m.textContent = '已打码';
    box.appendChild(m);
  }));
  document.body.appendChild(box);
}
"""
MASK_OFF = "() => { const b = document.getElementById('__hbMask'); if (b) b.remove(); }"

# 模糊脱敏：保留字段和数据行的形态，用于姓名、手机号、企业名称、地址等普通敏感文字
BLUR_ON = """
(sels) => {
  const box = document.createElement('div');
  box.id = '__hbBlur';
  box.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483645';
  sels.forEach(s => document.querySelectorAll(s).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    const m = document.createElement('div');
    m.style.cssText = `position:absolute;left:${r.left}px;top:${r.top}px;` +
      `width:${r.width}px;height:${r.height}px;backdrop-filter:blur(10px);` +
      '-webkit-backdrop-filter:blur(10px);background:rgba(255,255,255,.08);';
    box.appendChild(m);
  }));
  document.body.appendChild(box);
}
"""
BLUR_OFF = "() => { const b = document.getElementById('__hbBlur'); if (b) b.remove(); }"


def cmd_shot(args):
    def fn(page, pages):
        try:
            page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass
        if args.prep:
            # 下拉/悬停菜单在两次调用之间会关掉，要在同一次调用里先把界面摆到位再截
            print("prep:", page.evaluate(args.prep))
            page.wait_for_timeout(args.prep_wait)
        if args.prep_hover:
            # 二级菜单要真实悬停才展开；按选择器悬停比写死坐标稳
            page.locator(args.prep_hover).first.hover(timeout=8000)
            page.wait_for_timeout(args.prep_wait)
        if args.prep_mouse:
            # 二级菜单靠真实鼠标悬停才展开，合成事件无效
            for pt in args.prep_mouse.split(";"):
                x, y = (int(v) for v in pt.split(","))
                page.mouse.move(x, y, steps=8)
                page.wait_for_timeout(args.prep_wait)
        if args.prep_after:
            print("prep_after:", page.evaluate(args.prep_after))
            page.wait_for_timeout(400)
        blurs = [s for s in (args.blur or "").split(",,") if s]
        if blurs:
            page.evaluate(BLUR_ON, blurs)
        masks = [s for s in (args.mask or "").split(",,") if s]
        if masks:
            page.evaluate(MASK_ON, masks)
        sels = [s for s in (args.highlight or "").split(",,") if s]
        if sels:
            page.evaluate(HIGHLIGHT_ON, sels)
        if blurs or masks or sels:
            page.wait_for_timeout(200)
        path = Path(args.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if args.selector:
            page.locator(args.selector).first.screenshot(path=str(path), timeout=8000)
        else:
            page.screenshot(path=str(path), full_page=args.full_page)
        if sels:
            page.evaluate(HIGHLIGHT_OFF)
        if masks:
            page.evaluate(MASK_OFF)
        if blurs:
            page.evaluate(BLUR_OFF)
        print(f"已截图：{path}（{path.stat().st_size // 1024} KB）")
    run(fn)


def cmd_eval(args):
    def fn(page, pages):
        print(json.dumps(page.evaluate(args.js), ensure_ascii=False, indent=2, default=str))
    run(fn)


def cmd_stop(args):
    p, browser = connect()
    try:
        for ctx in browser.contexts:
            for pg in ctx.pages:
                pg.close()
        browser.close()
    finally:
        p.stop()
    print("浏览器已关闭")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start"); s.add_argument("--url", default="https://app.huoban.com"); s.set_defaults(fn=cmd_start)
    s = sub.add_parser("_keeper"); s.add_argument("--url", default=""); s.set_defaults(fn=cmd_keeper)
    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("page"); s.add_argument("--index", type=int, required=True); s.set_defaults(fn=cmd_page)
    s = sub.add_parser("goto"); s.add_argument("--url", required=True); s.set_defaults(fn=cmd_goto)
    s = sub.add_parser("snapshot"); s.add_argument("--max-chars", type=int, default=4000); s.set_defaults(fn=cmd_snapshot)
    s = sub.add_parser("click")
    s.add_argument("--index", type=int); s.add_argument("--text"); s.add_argument("--selector")
    s.add_argument("--at", help="按视口坐标点击，形如 320,385；用于菜单项这类非标准可点元素")
    s.set_defaults(fn=cmd_click)
    s = sub.add_parser("type"); s.add_argument("--text", required=True); s.add_argument("--enter", action="store_true"); s.set_defaults(fn=cmd_type)
    s = sub.add_parser("fill"); s.add_argument("--selector", required=True); s.add_argument("--value", required=True); s.set_defaults(fn=cmd_fill)
    s = sub.add_parser("press"); s.add_argument("--keys", required=True); s.set_defaults(fn=cmd_press)
    s = sub.add_parser("scroll"); s.add_argument("--dy", type=int, default=600); s.set_defaults(fn=cmd_scroll)
    s = sub.add_parser("wait")
    s.add_argument("--ms", type=int, default=1000); s.add_argument("--selector"); s.add_argument("--text")
    s.add_argument("--timeout", type=int, default=15000); s.set_defaults(fn=cmd_wait)
    s = sub.add_parser("shot")
    s.add_argument("--path", required=True); s.add_argument("--selector")
    s.add_argument("--highlight", help="要画标注框的 CSS 选择器，多个用 ,, 分隔（多框按传入顺序自动标序号）")
    s.add_argument("--blur", help="要模糊脱敏的 CSS 选择器（姓名、手机号、企业名称、地址等），多个用 ,, 分隔")
    s.add_argument("--mask", help="要不可逆遮挡的 CSS 选择器（密钥、令牌、密码等），多个用 ,, 分隔")
    s.add_argument("--prep", help="截图前在同一次调用里执行的 JS，用来展开下拉/悬停菜单等瞬时界面")
    s.add_argument("--prep-wait", type=int, default=1200, help="prep 执行后等待毫秒数")
    s.add_argument("--prep-hover", help="prep 之后用真实鼠标悬停到该 CSS 选择器，用于展开二级菜单")
    s.add_argument("--prep-mouse", help="prep 之后依次移动真实鼠标到这些视口坐标，形如 320,385;700,500")
    s.add_argument("--prep-after", help="鼠标移动之后再执行的 JS，通常用来给要画标注框的元素打标记")
    s.add_argument("--full-page", action="store_true"); s.set_defaults(fn=cmd_shot)
    s = sub.add_parser("eval"); s.add_argument("--js", required=True); s.set_defaults(fn=cmd_eval)
    s = sub.add_parser("stop"); s.set_defaults(fn=cmd_stop)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
