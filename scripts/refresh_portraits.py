import concurrent.futures, io, json, re, unicodedata
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

manifest=json.loads(Path('scripts/portrait-sources.json').read_text())
out=Path('public/retratos')
out.mkdir(parents=True,exist_ok=True)
def normalize(s):
    return ' '.join(re.findall(r'[a-z0-9]+',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()))
def matches(name, text):
    n=normalize(name).split()
    s=set(normalize(text).split())
    return bool(n) and n[0] in s and n[-1] in s and (len(n)<3 or any(w in s for w in n[1:-1] if len(w)>2 and w not in ('del','dos','das')))
def get(url):
    r=requests.get(url,timeout=(5,9),headers={'User-Agent':'Mozilla/5.0 (compatible; CCD-EP public academic website)'})
    r.raise_for_status()
    return r
def photo(url):
    try:
        r=get(url)
        if len(r.content)>15_000_000:return None
        im=ImageOps.exif_transpose(Image.open(io.BytesIO(r.content))).convert('RGB')
        if min(im.size)<220:return None
        return im
    except Exception:return None
def candidates(page,name):
    r=get(page)
    soup=BeautifulSoup(r.text,'html.parser')
    urls=[]
    for tag in soup.find_all('img'):
        label=' '.join(str(tag.get(k,'')) for k in ('alt','title','aria-label','src','data-src'))
        if not matches(name,label):continue
        for k in ('data-src','data-original','src'):
            u=tag.get(k)
            if u and not u.startswith('data:'):urls.append(urljoin(r.url,u))
        for part in (tag.get('srcset') or '').split(','):
            if part.strip():urls.append(urljoin(r.url,part.strip().split()[0]))
    return list(dict.fromkeys(urls))[:8]
def run(p):
    best=None; source=None
    for page in [p.get('rg'),p.get('url')]:
        if not page:continue
        try: urls=candidates(page,p['name'])
        except Exception:continue
        for url in urls:
            im=photo(url)
            if im and (best is None or min(im.size)>min(best.size)):
                best,source=im,page
        if best and min(best.size)>=400:break
    if p.get('direct'):
        im=photo(p['direct'])
        if im and (best is None or min(im.size)>min(best.size)):
            best,source=im,p['direct']
    if best:
        size=best.size
        best.thumbnail((900,900),Image.Resampling.LANCZOS)
        best.save(out/(p['id']+'.webp'),quality=90)
        return {'name':p['name'],'source':source,'original_dimensions':size}
    return {'name':p['name'],'status':'No verified higher-resolution candidate; existing approved image retained'}
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    report=list(pool.map(run,manifest))
print(json.dumps(report,ensure_ascii=False,indent=2))
