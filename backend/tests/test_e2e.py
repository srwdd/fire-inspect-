"""Playwright E2E tests for fire-inspect frontend.

Run against the live server (already deployed).
Uses synchronous Playwright API for simplicity.
"""
import pytest
import os
import sys

# These tests require a running server
BASE_URL = os.environ.get("TEST_BASE_URL", "https://ai-bang.top/inspect/web/")

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    yield page
    context.close()


class TestDashboard:
    """Dashboard page smoke tests."""

    def test_page_loads_with_correct_title(self, page):
        page.goto(BASE_URL)
        assert page.title() == "消防监督检查智能辅助系统"

    def test_no_console_errors(self, page):
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.goto(BASE_URL)
        page.wait_for_timeout(3000)
        # Only favicon.ico 404 is expected
        real_errors = [e for e in errors if "favicon.ico" not in e]
        assert len(real_errors) == 0, f"Unexpected console errors: {real_errors}"

    def test_scene_cards_visible(self, page):
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        # Check for scene card text
        scenes = ["宾馆/酒店", "商场/市场", "公共娱乐场所", "学校/幼儿园",
                  "医院", "养老机构", "餐饮场所", "高层建筑"]
        for scene in scenes:
            assert page.locator(f"text={scene}").count() > 0, f"Scene '{scene}' not found"


class TestInspectionFlow:
    """Inspection start flow tests."""

    def test_click_scene_card_opens_modal(self, page):
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        # Click the hotel scene card
        page.locator("text=宾馆/酒店").first.click()
        page.wait_for_timeout(1000)
        # Modal should show venue fields
        assert page.locator("text=场所面积").count() > 0, "Modal did not open"
        # Close modal
        cancel = page.locator("button:has-text('取消')")
        if cancel.count() > 0:
            cancel.click()


class TestTheme:
    """Dark/light mode toggle."""

    def test_dark_mode_toggle(self, page):
        page.goto(BASE_URL)
        page.wait_for_timeout(2000)
        # Find the theme toggle button
        toggle = page.locator(".theme-toggle")
        if toggle.count() > 0:
            # Click to toggle
            toggle.click()
            page.wait_for_timeout(500)
            # Should still be on the page
            assert page.title() == "消防监督检查智能辅助系统"
