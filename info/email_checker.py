import asyncio
from quart import Quart, jsonify
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from login import USERNAME, PASSWORD, URL

app = Quart(__name__)

playwright = None
browser = None
context = None
page = None

# --------------------------------------------------
# ASYNC PLAYWRIGHT HELPER FUNCTIONS
# --------------------------------------------------

# Logs into service now with SSO credentials, set in the login.py file
async def login_sso(page, username, password):
    try:
        await page.wait_for_selector("#i0116", timeout=10_000)
        await page.fill("#i0116", username)
        await page.press("#i0116", "Enter")

        await page.wait_for_selector("#i0118", timeout=10_000)
        await page.fill("#i0118", password)

        await page.wait_for_selector("#idSIButton9", timeout=10_000)
        await page.click("#idSIButton9")

        print("Please complete Duo authentication on your phone...")

        # Wait up to 3 minutes for the final "Yes" button
        await page.wait_for_selector("#idSIButton9", timeout=180_000)
        await page.click("#idSIButton9")

    except PlaywrightTimeout:
        print("Timed out waiting for login elements to load.")
        await page.close()

# Finds the number of incidents in the ServiceNow incident list

async def find_number_of_incidents(page):
    # reloads the page before checking the number of incidents
    await page.reload(wait_until="networkidle")

    try:
        # If your incident list is in an iframe, handle that
        frame = page.frame_locator("iframe[name='gsft_main']")
        row_count_locator = frame.locator('[id^="listv2_"][id$="_total_rows"]').first

        # Wait for the row count element to appear
        await row_count_locator.wait_for(state="attached", timeout=60_000)
        row_count_text = await row_count_locator.text_content()

        return int(row_count_text.strip())
    
    except PlaywrightTimeout:
        print("Timed out waiting for the incident table to load.")
        return None
    
async def refresh_page(page):
    await page.reload(wait_until="networkidle")

# Launches the browser, logs in, and navigates to the target URL
async def launch_and_login():
    """
    Initialize Playwright, open a browser, context, and page,
    then navigate and perform the login sequence.
    """
    global playwright, browser, context, page
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)  # set headless=True if you don’t need to see it
    context = await browser.new_context()
    page = await context.new_page()

    # Go to ServiceNow (or your target URL)
    await page.goto(
        URL
    )

    # Login with your credentials
    username = USERNAME
    password = PASSWORD
    await login_sso(page, username, password)

    print("Logged in successfully.")

# --------------------------------------------------
# QUART LIFECYCLE HOOKS
# --------------------------------------------------

# Launch the browser and login when the app starts
@app.before_serving
async def startup():
    await launch_and_login()

# Close the browser when the app stops
@app.after_serving
async def shutdown():
    if browser:
        await browser.close()
    if playwright:
        await playwright.stop()

# --------------------------------------------------
# QUART ROUTES
# --------------------------------------------------

# Route to get the number of incidents
@app.get("/incidents")
async def get_incidents():
    global page

    if page is None:
        return jsonify({"error": "Browser not initialized"}), 500

    count = await find_number_of_incidents(page)
    return jsonify({"incident_count": count})

# Route to refresh the page
@app.get("/refresh")
async def refresh():
    global page

    if page is None:
        return jsonify({"error": "Browser not initialized"}), 500

    await refresh_page(page)
    return jsonify({"message": "Page refreshed"})

# Runs main
if __name__ == "__main__":
    app.run()