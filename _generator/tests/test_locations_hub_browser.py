import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright


WEBSITE_DIR = Path(__file__).resolve().parents[2]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return


@pytest.fixture(scope="module")
def locations_server():
    handler = functools.partial(QuietHandler, directory=str(WEBSITE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/locations.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize(
    "viewport",
    [
        {"width": 1440, "height": 1000},
        {"width": 390, "height": 844},
    ],
)
def test_locations_hub_browser_accessibility_and_responsiveness(locations_server, viewport):
    console_errors = []
    page_errors = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=viewport)

        def route_request(route):
            if route.request.url.startswith("http://127.0.0.1:"):
                route.continue_()
            elif "tracker.metricool.com/resources/be.js" in route.request.url:
                route.fulfill(
                    status=200,
                    content_type="text/javascript",
                    body="window.beTracker={t:function(){}};",
                )
            else:
                route.fulfill(status=204, content_type="text/javascript", body="")

        page.route("**/*", route_request)
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(locations_server, wait_until="domcontentloaded")

        assert page.locator("h1").inner_text() == (
            "Commercial real estate financing, market by market."
        )
        assert page.locator(".locations-market-card").count() == 242
        assert page.locator(".locations-state-link").count() == 51

        nav_bottom, hero_content_top = page.evaluate(
            "[document.querySelector('#nav').getBoundingClientRect().bottom, "
            "document.querySelector('.locations-hero .locations-shell').getBoundingClientRect().top]"
        )
        assert hero_content_top >= nav_bottom + 4

        viewport_width, document_width = page.evaluate(
            "[document.documentElement.clientWidth, document.documentElement.scrollWidth]"
        )
        assert document_width <= viewport_width

        search = page.locator("#market-search")
        state = page.locator("#state-filter")
        search.fill("Los Angeles")
        filtered_count = page.locator(".locations-market-card:visible").count()
        assert 0 < filtered_count < 242
        assert f"Showing {filtered_count} of 242 markets" == page.locator("#market-results").inner_text()

        search.fill("")
        state.select_option("CA")
        california_count = page.locator(".locations-market-card:visible").count()
        assert california_count == page.locator('.locations-market-card[data-state="CA"]').count()
        page.locator("#market-reset").click()
        assert page.locator(".locations-market-card:visible").count() == 242
        assert search.evaluate("element => document.activeElement === element")

        page.keyboard.press("Tab")
        assert state.evaluate("element => document.activeElement === element")
        focus_outline = state.evaluate("element => getComputedStyle(element).outlineStyle")
        assert focus_outline != "none"

        axe_results = Axe().run(page)
        blocking = [
            violation
            for violation in axe_results.response["violations"]
            if violation.get("impact") in {"critical", "serious"}
        ]
        assert not blocking, AxeResultsSummary(blocking)
        assert not page_errors
        assert not console_errors
        browser.close()


def AxeResultsSummary(violations):
    return "\n".join(
        f"{violation['id']} ({violation['impact']}): {len(violation['nodes'])} node(s)"
        for violation in violations
    )
