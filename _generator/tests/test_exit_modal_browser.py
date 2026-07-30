"""Real-browser regression tests for exit-intent modal governance.

Run with:
    uv run --with pytest --with playwright pytest \
        _generator/tests/test_exit_modal_browser.py -q -p no:cacheprovider
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

playwright = pytest.importorskip("playwright.sync_api")


ROOT = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


@pytest.fixture(scope="module")
def local_site():
    handler = partial(QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as manager:
        instance = manager.chromium.launch(channel="chrome", headless=True)
        try:
            yield instance
        finally:
            instance.close()


def open_page(browser, local_site, path, viewport=None, init_script=None):
    context = browser.new_context(viewport=viewport or {"width": 1280, "height": 800})
    page = context.new_page()
    if init_script:
        page.add_init_script(init_script)
    page.goto(f"{local_site}/{path}", wait_until="domcontentloaded")
    page.wait_for_function("window.CLSExitIntent !== undefined")
    return context, page


def dispatch_exit(page, include_page_event=False):
    page.evaluate(
        """includePageEvent => {
            if (includePageEvent) {
                document.dispatchEvent(new MouseEvent('mouseout', {
                    clientY: 0, relatedTarget: null, bubbles: true
                }));
            }
            document.dispatchEvent(new MouseEvent('mouseleave', {
                clientY: 0, relatedTarget: null, bubbles: true
            }));
        }""",
        include_page_event,
    )


def test_overlap_page_shows_one_accessible_dialog_and_one_event(browser, local_site):
    context, page = open_page(browser, local_site, "rates.html")
    try:
        page.evaluate(
            """() => {
                document.querySelectorAll(
                    'iframe[src*="challenges.cloudflare.com"], .cf-turnstile, .g-recaptcha'
                ).forEach(element => { element.style.display = 'none'; });
                sessionStorage.clear();
                window.__clsExitIntentTracked = false;
                window.__exitTestEvents = [];
                window.gtag = function () {
                    window.__exitTestEvents.push(Array.from(arguments));
                };
            }"""
        )
        dispatch_exit(page, include_page_event=True)
        page.wait_for_function("document.getElementById('exitOverlay').classList.contains('visible')")
        page.wait_for_function(
            "document.querySelector('#exitOverlay .exit-popup').contains(document.activeElement)"
        )

        result = page.evaluate(
            """() => {
                const overlay = document.getElementById('exitOverlay');
                const dialog = overlay.querySelector('.exit-popup');
                return {
                    fallback: Boolean(document.getElementById('cls-exit-overlay')),
                    role: dialog.getAttribute('role'),
                    ariaModal: dialog.getAttribute('aria-modal'),
                    activeInside: dialog.contains(document.activeElement),
                    bodyOverflow: document.body.style.overflow,
                    keys: [
                        sessionStorage.getItem('cls-exit-shown'),
                        sessionStorage.getItem('exitShown')
                    ],
                    eventCount: window.__exitTestEvents.filter(
                        event => event[0] === 'event' && event[1] === 'exit_intent_shown'
                    ).length
                };
            }"""
        )
        assert result == {
            "fallback": False,
            "role": "dialog",
            "ariaModal": "true",
            "activeInside": True,
            "bodyOverflow": "hidden",
            "keys": ["1", "1"],
            "eventCount": 1,
        }
    finally:
        context.close()


def test_page_specific_dialog_toggles_dormant_accessibility_state(browser, local_site):
    context, page = open_page(browser, local_site, "rates.html")
    try:
        assert page.evaluate(
            """() => {
                const overlay = document.getElementById('exitOverlay');
                return overlay.hidden && overlay.inert && overlay.getAttribute('aria-hidden') === 'true';
            }"""
        ) is True

        page.evaluate("sessionStorage.clear()")
        dispatch_exit(page, include_page_event=True)
        page.wait_for_function("document.getElementById('exitOverlay').hidden === false")
        assert page.evaluate(
            """() => {
                const overlay = document.getElementById('exitOverlay');
                return !overlay.inert && overlay.getAttribute('aria-hidden') === 'false';
            }"""
        ) is True

        page.keyboard.press("Escape")
        page.wait_for_function("document.getElementById('exitOverlay').hidden === true")
        assert page.evaluate(
            """() => {
                const overlay = document.getElementById('exitOverlay');
                return overlay.inert && overlay.getAttribute('aria-hidden') === 'true';
            }"""
        ) is True
    finally:
        context.close()


def test_fallback_is_accessible_and_escape_restores_state(browser, local_site):
    context, page = open_page(browser, local_site, "about.html")
    try:
        page.evaluate(
            """() => {
                sessionStorage.clear();
                window.__exitTestEvents = [];
                window.gtag = function () {
                    window.__exitTestEvents.push(Array.from(arguments));
                };
            }"""
        )
        dispatch_exit(page)
        page.wait_for_selector("#cls-exit-overlay")

        result = page.evaluate(
            """() => {
                const overlay = document.getElementById('cls-exit-overlay');
                const dialog = overlay.querySelector('.cls-exit-card');
                return {
                    role: dialog.getAttribute('role'),
                    ariaModal: dialog.getAttribute('aria-modal'),
                    activeInside: dialog.contains(document.activeElement),
                    eventCount: window.__exitTestEvents.filter(
                        event => event[0] === 'event' && event[1] === 'exit_intent_shown'
                    ).length
                };
            }"""
        )
        assert result == {
            "role": "dialog",
            "ariaModal": "true",
            "activeInside": True,
            "eventCount": 1,
        }

        page.locator("#cls-exit-overlay .cls-exit-close").focus()
        page.keyboard.press("Shift+Tab")
        assert page.evaluate(
            """() => {
                const items = document.querySelectorAll(
                    '#cls-exit-overlay a[href], #cls-exit-overlay button:not([disabled])'
                );
                return document.activeElement === items[items.length - 1];
            }"""
        ) is True
        page.keyboard.press("Tab")
        assert page.evaluate(
            "document.activeElement === document.querySelector('#cls-exit-overlay .cls-exit-close')"
        ) is True

        page.keyboard.press("Escape")
        page.wait_for_function("!document.getElementById('cls-exit-overlay')")
        assert page.evaluate(
            """() => ({
                overflow: document.body.style.overflow,
                activeTag: document.activeElement.tagName
            })"""
        ) == {"overflow": "", "activeTag": "BODY"}
    finally:
        context.close()


def test_fallback_backdrop_closes_dialog(browser, local_site):
    context, page = open_page(browser, local_site, "about.html")
    try:
        page.evaluate("sessionStorage.clear()")
        dispatch_exit(page)
        page.wait_for_selector("#cls-exit-overlay")
        page.evaluate(
            "document.getElementById('cls-exit-overlay').dispatchEvent(new MouseEvent('click', {bubbles: true}))"
        )
        page.wait_for_function("!document.getElementById('cls-exit-overlay')")
        assert page.evaluate("document.body.style.overflow") == ""
    finally:
        context.close()


def test_overlap_captcha_suppresses_without_consuming_session(browser, local_site):
    context, page = open_page(browser, local_site, "rates.html")
    try:
        page.evaluate(
            """() => {
                sessionStorage.clear();
                const captcha = document.createElement('div');
                captcha.className = 'cf-turnstile';
                captcha.id = 'modal-test-captcha';
                captcha.style.cssText = 'position:fixed;top:20px;left:20px;width:300px;height:80px;z-index:99999';
                document.body.appendChild(captcha);
            }"""
        )
        dispatch_exit(page, include_page_event=True)
        page.wait_for_timeout(100)
        assert page.evaluate(
            "document.getElementById('exitOverlay').classList.contains('visible')"
        ) is False
        assert page.locator("#cls-exit-overlay").count() == 0
        assert page.evaluate(
            """() => [
                sessionStorage.getItem('cls-exit-shown'),
                sessionStorage.length
            ]"""
        ) == [None, 0]
    finally:
        context.close()


def test_offscreen_captcha_does_not_block_fallback(browser, local_site):
    context, page = open_page(browser, local_site, "refinance.html")
    try:
        page.evaluate("sessionStorage.clear()")
        dispatch_exit(page)
        page.wait_for_selector("#cls-exit-overlay", timeout=1000)
        assert page.evaluate(
            """() => Array.from(document.querySelectorAll('.cf-turnstile')).some(element => {
                const rect = element.getBoundingClientRect();
                return rect.top > window.innerHeight;
            })"""
        ) is True
    finally:
        context.close()


@pytest.mark.parametrize("guard", ["captcha", "dirty-form"])
def test_actual_legacy_mobile_trigger_is_suppressed_before_side_effects(
    browser, local_site, guard
):
    context, page = open_page(
        browser,
        local_site,
        "financing/permanent-loans.html",
        viewport={"width": 600, "height": 800},
    )
    try:
        page.evaluate(
            """guard => {
                sessionStorage.clear();
                window.__clsExitPromptShown = false;
                window.__clsExitIntentTracked = false;
                window.dataLayer = [];
                window.gtag = function () { window.dataLayer.push(Array.from(arguments)); };
                window.__ordinaryScrolls = 0;
                window.addEventListener('scroll', () => window.__ordinaryScrolls++);
                window.__legacyVisibleTransitions = 0;
                const overlay = document.getElementById('exitOverlay');
                const originalAdd = DOMTokenList.prototype.add;
                DOMTokenList.prototype.add = function (...tokens) {
                    if (this === overlay.classList && tokens.includes('visible')) {
                        window.__legacyVisibleTransitions++;
                    }
                    return originalAdd.apply(this, tokens);
                };
                if (guard === 'captcha') {
                    const captcha = document.createElement('div');
                    captcha.className = 'cf-turnstile';
                    captcha.style.cssText = 'position:fixed;top:20px;left:20px;width:300px;height:80px;z-index:99999';
                    document.body.appendChild(captcha);
                } else {
                    const form = document.createElement('form');
                    const input = document.createElement('input');
                    form.appendChild(input);
                    document.body.appendChild(form);
                    input.value = 'edited';
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                }
                window.__testScrollY = 1000;
                Object.defineProperty(window, 'scrollY', {
                    configurable: true,
                    get() { return window.__testScrollY; }
                });
                window.dispatchEvent(new Event('scroll'));
                for (let index = 0; index < 17; index++) {
                    window.__testScrollY -= 20;
                    window.dispatchEvent(new Event('scroll'));
                }
            }""",
            guard,
        )
        page.wait_for_timeout(150)
        assert page.evaluate("window.__legacyVisibleTransitions") == 0
        assert page.evaluate(
            """() => [
                sessionStorage.getItem('cls-exit-shown'),
                sessionStorage.length,
                window.dataLayer.filter(entry => entry[0] === 'event' && entry[1] === 'exit_intent_shown').length,
                window.__ordinaryScrolls
            ]"""
        ) == [None, 0, 0, 18]
    finally:
        context.close()


def test_shared_controller_owns_eligible_actual_legacy_mobile_trigger(browser, local_site):
    context, page = open_page(
        browser,
        local_site,
        "financing/permanent-loans.html",
        viewport={"width": 600, "height": 800},
    )
    try:
        page.evaluate(
            """() => {
                sessionStorage.clear();
                window.__clsExitPromptShown = false;
                window.__clsExitIntentTracked = false;
                window.dataLayer = [];
                window.gtag = function () { window.dataLayer.push(Array.from(arguments)); };
                window.__ordinaryScrolls = 0;
                window.addEventListener('scroll', () => window.__ordinaryScrolls++);
                window.__testScrollY = 1000;
                Object.defineProperty(window, 'scrollY', {
                    configurable: true,
                    get() { return window.__testScrollY; }
                });
                window.dispatchEvent(new Event('scroll'));
                for (let index = 0; index < 17; index++) {
                    window.__testScrollY -= 20;
                    window.dispatchEvent(new Event('scroll'));
                }
            }"""
        )
        page.wait_for_function("document.getElementById('exitOverlay').hidden === false")
        assert page.locator("#cls-exit-overlay").count() == 0
        assert page.evaluate(
            """() => [
                sessionStorage.getItem('cls-exit-shown'),
                sessionStorage.length,
                window.dataLayer.filter(entry => entry[0] === 'event' && entry[1] === 'exit_intent_shown').length,
                window.__ordinaryScrolls
            ]"""
        ) == ["1", 2, 1, 18]
    finally:
        context.close()


def test_legacy_session_does_not_block_unrelated_mobile_scroll_listeners(browser, local_site):
    context, page = open_page(
        browser,
        local_site,
        "financing/permanent-loans.html",
        viewport={"width": 600, "height": 800},
    )
    try:
        received = page.evaluate(
            """() => {
                sessionStorage.clear();
                sessionStorage.setItem('exitShown', '1');
                window.__ordinaryScrolls = 0;
                window.addEventListener('scroll', () => window.__ordinaryScrolls++);
                window.__testScrollY = 1000;
                Object.defineProperty(window, 'scrollY', {
                    configurable: true,
                    get() { return window.__testScrollY; }
                });
                window.dispatchEvent(new Event('scroll'));
                for (let index = 0; index < 17; index++) {
                    window.__testScrollY -= 20;
                    window.dispatchEvent(new Event('scroll'));
                }
                return window.__ordinaryScrolls;
            }"""
        )
        assert received == 18
        assert page.evaluate("document.getElementById('exitOverlay').hidden") is True
    finally:
        context.close()


def test_storage_restrictions_do_not_disable_page_specific_controller(browser, local_site):
    context, page = open_page(
        browser,
        local_site,
        "rates.html",
        init_script="""
            Object.defineProperty(window, 'sessionStorage', {
                configurable: true,
                get() { throw new DOMException('Storage disabled', 'SecurityError'); }
            });
        """,
    )
    try:
        dispatch_exit(page, include_page_event=True)
        page.wait_for_function("document.getElementById('exitOverlay').hidden === false", timeout=1000)
        assert page.evaluate(
            "document.getElementById('exitOverlay').classList.contains('visible')"
        ) is True
    finally:
        context.close()


def test_storage_restrictions_preserve_mobile_page_specific_trigger(browser, local_site):
    context, page = open_page(
        browser,
        local_site,
        "rates.html",
        viewport={"width": 600, "height": 800},
        init_script="""
            Object.defineProperty(window, 'sessionStorage', {
                configurable: true,
                get() { throw new DOMException('Storage disabled', 'SecurityError'); }
            });
        """,
    )
    try:
        page.evaluate(
            """() => {
                window.__testScrollY = 1000;
                Object.defineProperty(window, 'scrollY', {
                    configurable: true,
                    get() { return window.__testScrollY; }
                });
                window.dispatchEvent(new Event('scroll'));
                for (let index = 0; index < 17; index++) {
                    window.__testScrollY -= 20;
                    window.dispatchEvent(new Event('scroll'));
                }
            }"""
        )
        page.wait_for_function("document.getElementById('exitOverlay').hidden === false", timeout=1000)
        assert page.evaluate(
            "document.getElementById('exitOverlay').classList.contains('visible')"
        ) is True
    finally:
        context.close()


def test_url_prefill_marks_form_dirty_before_exit_governance(browser, local_site):
    context, page = open_page(
        browser,
        local_site,
        "refinance.html?name=Alice&email=alice%40example.com",
    )
    try:
        assert page.evaluate(
            "document.getElementById('refiLeadForm').dataset.clsExitDirty"
        ) == "true"
        page.evaluate("sessionStorage.clear()")
        dispatch_exit(page)
        page.wait_for_timeout(75)
        assert page.locator("#cls-exit-overlay").count() == 0
        assert page.evaluate(
            """() => [
                sessionStorage.getItem('cls-exit-shown'),
                sessionStorage.getItem('exitShown')
            ]"""
        ) == [None, None]
    finally:
        context.close()


def test_focused_and_dirty_forms_suppress_without_consuming_session(browser, local_site):
    context, page = open_page(browser, local_site, "about.html")
    try:
        page.evaluate(
            """() => {
                sessionStorage.clear();
                const form = document.createElement('form');
                form.id = 'modal-test-form';
                const input = document.createElement('input');
                form.appendChild(input);
                document.body.appendChild(form);
                input.focus();
            }"""
        )
        dispatch_exit(page)
        page.wait_for_timeout(75)
        assert page.locator("#cls-exit-overlay").count() == 0

        page.evaluate(
            """() => {
                const input = document.querySelector('#modal-test-form input');
                input.blur();
                input.value = 'edited';
                input.dispatchEvent(new Event('input', {bubbles: true}));
            }"""
        )
        dispatch_exit(page)
        page.wait_for_timeout(75)
        assert page.locator("#cls-exit-overlay").count() == 0
        assert page.evaluate(
            """() => [
                sessionStorage.getItem('cls-exit-shown'),
                sessionStorage.getItem('exitShown')
            ]"""
        ) == [None, None]
    finally:
        context.close()


@pytest.mark.parametrize("path", ["contact.html", "apply.html", "thank-you.html"])
def test_conversion_routes_never_show_exit_prompt(browser, local_site, path):
    context, page = open_page(browser, local_site, path)
    try:
        page.evaluate("sessionStorage.clear()")
        dispatch_exit(page, include_page_event=True)
        page.wait_for_timeout(75)
        assert page.locator("#cls-exit-overlay").count() == 0
        assert page.evaluate(
            """() => Boolean(
                document.getElementById('exitOverlay') &&
                document.getElementById('exitOverlay').classList.contains('visible')
            )"""
        ) is False
    finally:
        context.close()
