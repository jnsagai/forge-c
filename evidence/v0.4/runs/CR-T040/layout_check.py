"""CR-T040: no horizontal overflow at 390 and 1440 px (WebDriver over HTTP to geckodriver; no selenium needed)."""
import base64, json, subprocess, sys, time, urllib.request

tok, out = sys.argv[1], sys.argv[2]
gd = subprocess.Popen(["/snap/bin/firefox.geckodriver", "--port", "4455"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
B = "http://127.0.0.1:4455"


def call(method, path, body=None):
    req = urllib.request.Request(B + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["value"]


try:
    for _ in range(50):
        try:
            urllib.request.urlopen(B + "/status", timeout=1); break
        except Exception:
            time.sleep(0.2)
    sid = call("POST", "/session", {"capabilities": {"alwaysMatch": {"moz:firefoxOptions": {"args": ["-headless"]}}}})["sessionId"]
    res = {}
    for w in (390, 1440):
        call("POST", f"/session/{sid}/window/rect", {"width": w, "height": 1000})
        call("POST", f"/session/{sid}/url", {"url": f"http://127.0.0.1:8766/login?next=/control-room&token={tok}"})
        time.sleep(4)
        m = call("POST", f"/session/{sid}/execute/sync", {"script": """
          const d = document.documentElement;
          const wide = [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > d.clientWidth + 1
                         && getComputedStyle(e).position !== 'fixed' && !e.closest('.scroll')).map(e => e.tagName + '.' + e.className).slice(0, 5);
          return {scrollWidth: d.scrollWidth, clientWidth: d.clientWidth, innerWidth: innerWidth,
                  stations: document.querySelectorAll('.station').length, tiles: document.querySelectorAll('.tile').length,
                  andonText: [...document.querySelectorAll('.station .andon')].map(e => e.textContent.trim()), overflowing: wide};""", "args": []})
        if w == 390:  # Firefox windows cannot be narrower than ~490 px: measure inside a same-origin 390 px iframe
            call("POST", f"/session/{sid}/execute/sync", {"script": """
              document.body.innerHTML = '<iframe id="f" src="/control-room" style="width:390px;height:1000px;border:0"></iframe>';""", "args": []})
            time.sleep(5)
            m = call("POST", f"/session/{sid}/execute/sync", {"script": """
              const doc = document.getElementById('f').contentDocument, d = doc.documentElement;
              const wide = [...doc.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > d.clientWidth + 1
                             && !e.closest('.scroll')).map(e => e.tagName + '.' + e.className).slice(0, 5);
              return {scrollWidth: d.scrollWidth, clientWidth: d.clientWidth, innerWidth: doc.defaultView.innerWidth,
                      stations: doc.querySelectorAll('.station').length, tiles: doc.querySelectorAll('.tile').length,
                      andonText: [...doc.querySelectorAll('.station .andon')].map(e => e.textContent.trim()), overflowing: wide,
                      method: 'same-origin iframe 390 px'};""", "args": []})
        m["no_horizontal_scroll"] = m["scrollWidth"] <= m["clientWidth"]
        res[str(w)] = m
        png = call("GET", f"/session/{sid}/screenshot")
        open(f"{out}/layout-{w}.png", "wb").write(base64.b64decode(png))
    call("DELETE", f"/session/{sid}")
    json.dump(res, open(f"{out}/layout-check.json", "w"), indent=1)
    print(json.dumps({w: {k: v[k] for k in ("scrollWidth", "clientWidth", "no_horizontal_scroll", "stations", "overflowing")} for w, v in res.items()}))
finally:
    gd.terminate()
