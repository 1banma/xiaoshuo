# -*- coding: utf-8 -*-
"""在 GitHub Actions runner 上运行：HEAD 请求收集 B2 file IDs"""
import os, json, time, ssl, urllib.request, urllib.parse, urllib.error

JOB_ID   = int(os.environ.get('JOB_ID', 0))
START    = int(os.environ.get('START_NUM', 1))
TOTAL    = int(os.environ.get('TOTAL_NUM', 12000))
PARALLEL = 60

# 每个 job 负责的号段
chunk    = TOTAL // PARALLEL
start_n  = START + JOB_ID * chunk
end_n    = start_n + chunk

print(f"Job {JOB_ID}: range {start_n} - {end_n-1}  ({chunk} books)")

UA = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=CTX)
)

BASE = 'http://txt.bequgew.cc/txt{n}.html'

def head_one(n):
    url = BASE.format(n=n)
    req = urllib.request.Request(url, headers=UA, method='HEAD')
    resp = OPENER.open(req, timeout=12)
    h = dict(resp.getheaders())
    fid  = h.get('x-bz-file-id', '')
    size = int(h.get('Content-Length', 0))
    name = h.get('x-bz-file-name', '')
    return fid, size, name

results = {}
n429    = 0
backoff = 20   # 起始间隔（秒），200/hour = 18s，留余量

for n in range(start_n, end_n):
    try:
        fid, size, name = head_one(n)
        if fid:
            results[str(n)] = {'fid': fid, 'size': size, 'name': name}
            n429 = 0           # 成功则重置退避
            backoff = 20
        time.sleep(backoff)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            n429 += 1
            # 渐进退避：每次 429 多等 30 秒，最多 180 秒
            backoff = min(20 + n429 * 30, 180)
            print(f"  429 at #{n}, backoff={backoff}s")
            time.sleep(backoff)
        else:
            time.sleep(backoff)
    except Exception as e:
        print(f"  ERR #{n}: {e}")
        time.sleep(backoff)

    # 每 50 本打印进度
    if (n - start_n + 1) % 50 == 0:
        print(f"  [{n-start_n+1}/{chunk}] collected={len(results)}")

elapsed_note = f"Job {JOB_ID}: done. {len(results)}/{chunk} IDs collected"
print(elapsed_note)

with open('ids_output.json', 'w', encoding='utf-8') as f:
    json.dump({
        'job': JOB_ID,
        'start': start_n,
        'end': end_n,
        'total': chunk,
        'collected': len(results),
        'ids': results,
    }, f, ensure_ascii=False)

print(f"Written ids_output.json with {len(results)} entries")
