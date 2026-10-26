"""Real local Chromium rendering. No external navigation or contact transmission."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


# The sites forbid eval through their CSP, which wait_for_function polling
# needs; a single awaited evaluation waits for every image instead.
IMAGES_LOADED = "Promise.all([...document.images].map(x=>x.complete?0:new Promise(r=>{x.addEventListener('load',r,{once:true});x.addEventListener('error',r,{once:true});})))"


def inspect_site(folder, *, screenshots=None):
    from playwright.sync_api import sync_playwright
    folder=Path(folder).resolve()
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(folder)))
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    origin=f'http://127.0.0.1:{server.server_port}'
    checks=[]
    errors=[]
    def check(name,passed):checks.append({'code':name,'passed':bool(passed)})
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            context=browser.new_context(device_scale_factor=1)
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
            page=context.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('response',lambda response:errors.append(f'HTTP {response.status}') if response.status>=400 else None)
            for width in [320,375,768,1024,1440]:
                page.set_viewport_size({'width':width,'height':960})
                page.goto(origin+'/index.html',wait_until='networkidle')
                page.evaluate('document.fonts.ready')
                page.evaluate("document.querySelectorAll('img').forEach(x=>x.loading='eager')")
                page.evaluate(IMAGES_LOADED)
                check(f'{width}_no_overflow',page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
                check(f'{width}_images_decoded',page.evaluate('[...document.images].every(x=>x.naturalWidth>0)'))
                check(f'{width}_title_visible',page.locator('h1').is_visible())
                check(f'{width}_brand_readable',page.locator('.le-header .le-brand').evaluate('node=>node.clientHeight<=parseFloat(getComputedStyle(node).lineHeight)*4'))
                check(f'{width}_local_font_loaded',page.evaluate('[...document.fonts].some(f=>f.family.includes("LE Geist")&&f.status==="loaded")'))
                check(f'{width}_no_unconnected_form',page.locator('form').count()==0)
                if screenshots and width in [375,768,1440]:
                    target=Path(screenshots);target.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(target/f'{width}.png'),full_page=True)
                    page.screenshot(path=str(target/f'{width}-hero.png'))
                faq=page.locator('.le-faq details').first
                if faq.count():
                    faq.locator('summary').click()
                    check(f'{width}_faq',faq.evaluate('node=>node.open'))
                if width<=1024:
                    menu=page.locator('.le-mobile-nav')
                    menu.locator('summary').click()
                    check(f'{width}_mobile_menu',menu.evaluate('node=>node.open'))
                    menu.locator('a[href="#contact"]').click()
                else:page.locator('.le-desktop-nav a[href="#contact"]').click()
                check(f'{width}_contact_anchor',page.evaluate("location.hash==='#contact'"))
                check(f'{width}_contact_links',page.locator('.le-contact a[href^="mailto:"],.le-contact a[href^="tel:"]').count()>0)
            # A Windows double-click opens file://: also validate the offline export.
            context.unroute('**/*')
            page.goto((folder/'index.html').as_uri(),wait_until='load')
            page.evaluate('document.fonts.ready')
            page.evaluate("document.querySelectorAll('img').forEach(x=>x.loading='eager')")
            page.evaluate(IMAGES_LOADED)
            check('offline_css',page.locator('body').evaluate("node=>getComputedStyle(node).fontFamily.includes('Arial')"))
            check('offline_images',page.evaluate('[...document.images].every(x=>x.complete&&x.naturalWidth>0)'))
            check('offline_font',page.evaluate('[...document.fonts].some(f=>f.family.includes("LE Geist")&&f.status==="loaded")'))
            check('no_browser_errors',not errors)
            browser.close()
        return {'completed':True,'passed':all(item['passed'] for item in checks),'checks':checks,'errors':errors}
    except Exception as error:
        return {'completed':False,'passed':False,'checks':checks,'errors':errors,'reason':f'{type(error).__name__}: {error}'}
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
