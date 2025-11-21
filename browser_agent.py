import re
import asyncio
from playwright.async_api import async_playwright

async def get_quiz_details(url: str) -> tuple[str, str]:
    """
    Async version.
    Loads the quiz page using Playwright async chromium,
    extracts visible instructions + the submit URL.
    """
    print(f"-> Browser: Visiting quiz URL: {url}")
    quiz_instructions = "ERROR: Could not retrieve quiz instructions."
    submit_url = ""

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)
            await page.wait_for_selector("body", state="visible", timeout=30000)

            quiz_instructions = await page.inner_text("body")

            submit_match = re.search(
                r"Post your answer to (https?://[^\s\"]+)",
                quiz_instructions,
                re.IGNORECASE
            )
            if submit_match:
                submit_url = submit_match.group(1).strip()

            await browser.close()

    except Exception as e:
        print(f"Browser Agent Error: {e}")
        quiz_instructions = f"ERROR during browser operation: {e}"

    return quiz_instructions, submit_url


async def download_file(url: str, save_path: str) -> bool:
    """Async version of file downloader."""
    print(f"-> Browser: Downloading file from: {url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Start download listener BEFORE navigation
            async with page.expect_download() as download_info:
                await page.goto(url, timeout=60000)

            download = await download_info.value
            await download.save_as(save_path)

            await browser.close()
            return True

    except Exception as e:
        print(f"Download Error: {e}")
        return False
