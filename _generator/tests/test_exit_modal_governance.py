"""Regression tests for sitewide exit-intent modal governance."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHATBOT_JS = ROOT / "js" / "chatbot.js"
BASE_TEMPLATE = ROOT / "_generator" / "templates" / "_base.html"


def test_global_fallback_yields_to_page_specific_overlay():
    """The chatbot must not register a second exit prompt on base-template pages."""
    source = CHATBOT_JS.read_text(encoding="utf-8")

    setup_start = source.index("function setupExitIntent()")
    setup_end = source.index("function showExitPopup()", setup_start)
    setup_source = source[setup_start:setup_end]

    assert "document.getElementById('exitOverlay')" in setup_source
    assert "return" in setup_source
    assert setup_source.count("shouldSuppressExitPrompt()") == 1
    ready_source = source.split("function ready()", 1)[1].split("if (document.readyState", 1)[0]
    assert ready_source.index("trackDirtyForms();") < ready_source.index("prefillFromParams();")


def test_exit_controller_has_shared_session_and_conversion_guards():
    """Legacy sessions and active conversion work must suppress every exit prompt."""
    source = CHATBOT_JS.read_text(encoding="utf-8")

    assert "cls-exit-shown" in source
    assert "exitShown" in source
    assert "shouldSuppressExitPrompt" in source
    assert "function isInViewport" in source
    assert "document.activeElement" in source
    assert "dataset.clsExitDirty" in source
    assert "excludedOverlay.contains(dialogs[i])" in source
    assert "aria-modal" in source
    assert "challenges.cloudflare.com" in source
    assert "recaptcha" in source
    assert "window.addEventListener('scroll', stopCompetingPrompt, true)" in source
    assert "location.pathname" in source
    assert "contact" in source
    assert "apply" in source
    assert "thank-you" in source


def test_retained_dialogs_have_accessible_source_contract():
    """Both page-specific and fallback dialogs must meet the accessibility contract."""
    template = BASE_TEMPLATE.read_text(encoding="utf-8")
    source = CHATBOT_JS.read_text(encoding="utf-8")

    assert 'class="exit-popup" role="dialog" aria-modal="true" aria-labelledby="exitTitle"' in template
    assert 'id="exitOverlay" hidden aria-hidden="true" inert' in template
    assert 'id="exitClose" type="button" aria-label="Close this dialog"' in template
    assert 'role="dialog" aria-modal="true" aria-labelledby="cls-exit-title"' in source
    assert 'type="button" class="cls-exit-close" aria-label="Close this dialog"' in source
    assert "activateExitDialog" in source
    assert "previousFocus.focus" in source
    assert "previousFocus === document.body" in source
    assert "document.body.style.overflow" in source
    assert ".inert" in source
    assert "overlay.hidden" in source
    assert "aria-hidden" in source
    assert "event.key === 'Escape'" in source


def test_page_and_fallback_paths_share_session_and_analytics_contract():
    """Both route families must emit one prompt contract without losing legacy sessions."""
    template = BASE_TEMPLATE.read_text(encoding="utf-8")
    source = CHATBOT_JS.read_text(encoding="utf-8")

    assert "window.CLSExitIntent" in source
    assert "window.CLSExitIntent" in template
    assert "sessionStorage.getItem('cls-exit-shown')" in template
    assert "sessionStorage.getItem('exitShown')" in template
    assert "sessionStorage.setItem('cls-exit-shown', '1')" in template
    assert "sessionStorage.setItem('exitShown', '1')" in template
    assert "gtag('event', 'exit_intent_shown'" not in template
    assert "function trackExitPromptShown" in source
    assert "function clearExitPromptState" in source
    assert "function readExitPromptState" in source
    assert "exitPromptShownInMemory" in source
    assert "function installLegacyExitIntentGate" in source
    assert "nativeStorageGet" in source
    assert "window.dataLayer" in source
    assert source.count("trackExitPromptShown();") >= 2
    assert "exit_popup_shown" not in source
    assert "exit_intent_shown" in source
