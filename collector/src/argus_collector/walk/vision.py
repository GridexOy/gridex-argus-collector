"""The vision model on a screenshot, only where the DOM cannot help (owner 05.10.2026).

1. A page with one bot-check sign only (the DOM rule needs two): the model
   says whether the screenshot is a "verify you are human" interstitial; if
   so it is waited out for 20 s like any bot check, then Huomio. The model
   never solves or clicks a check: passing it stays the owner's job.
2. A page without DOM text (an image or canvas page): the model chooses the
   next step from the screenshot and the numbered elements, instead of the
   navigation model reading text that is not there. No contact field is
   taken from a screenshot: a field needs a quote in the page text.
"""

from __future__ import annotations

from dataclasses import replace

from argus_collector.browser import contract as browser
from argus_collector.discovery import contract as discovery
from argus_collector.models import contract as models
from argus_collector.walk import prompts
from argus_collector.walk.service import Action
from argus_collector.walk.state import WalkState

PURPOSE = "walk.vision"
MIN_DOM_TEXT = 40  # canonical characters below which a page counts as having no text
BOT_SYSTEM = (
    "You look at a screenshot of a web page. Answer with one JSON object "
    '{"bot_check": true} only when the page is an interstitial that verifies the visitor '
    "is human (\"Just a moment\", \"Checking your browser\", a CAPTCHA, \"I am not a "
    'robot"), else {"bot_check": false}. Do not describe the page.'
)
SCREENSHOT_NOTE = (
    "\n\nThe page has almost no text in its DOM: the attached screenshot shows what a "
    "visitor sees. Choose from the numbered elements only."
)


def is_bot_check(state: WalkState, wb: browser.WalkBrowser, page: browser.PageState) -> bool:
    """The vision model's answer for a page with one bot-check sign only."""
    if state.vision_client is None or not page.challenge_hint or page.challenge:
        return False
    user = f"URL: {page.url}\nTitle: {page.title}\nJSON:"
    try:
        reply = state.vision_client.chat_json(BOT_SYSTEM, user, PURPOSE,
                                              images=(wb.screenshot(),))
    except (models.ModelError, browser.ActionError):
        return False
    return reply.get("bot_check") is True


def action_without_text(
    state: WalkState, wb: browser.WalkBrowser, page: browser.PageState, text: str,
    prompt: tuple[str, str], candidates: list[discovery.Candidate],
) -> Action | None:
    """The next step from the screenshot of a page without DOM text; None otherwise."""
    if state.vision_client is None or len(text.strip()) >= MIN_DOM_TEXT:
        return None
    system, user = prompt
    try:
        shot = wb.screenshot()
    except browser.ActionError:
        return None
    client = state.vision_client
    try:
        reply = client.chat_json(system, user + SCREENSHOT_NOTE, PURPOSE, images=(shot,))
    except models.ModelError:
        state.vision_client = None  # not pulled or down: the navigation model reads on
        return None
    return replace(prompts.parse_action(reply, candidates), source=f"model:{client.config.name}")
