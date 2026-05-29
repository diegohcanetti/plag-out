import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        print("Launching headless Chromium browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # We can intercept requests to see if we see any querydata requests
        page.on("request", lambda req: print(f"-> Req: {req.method} {req.url[:120]}"))
        page.on("response", lambda res: print(f"<- Res: {res.status} {res.url[:120]}"))
        
        url = "https://app.powerbi.com/view?r=eyJrIjoiZDMxMjRkZmItMDA4Ny00NjIzLWFkNjUtYzU3OGZjNjlkMjc4IiwidCI6IjE5MTBjMTYzLTY0YWUtNGZhMC1iY2QyLTBjMThiNzNkMmZiYSIsImMiOjR9"
        print(f"Navigating to PowerBI URL: {url} ...")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        print("\nPage loaded!")
        
        # Let's wait another 10 seconds for the visualizations to fully render
        await asyncio.sleep(10)
        
        # Save a screenshot to see if it rendered properly
        screenshot_path = "scratch/powerbi_screenshot.png"
        await page.screenshot(path=screenshot_path)
        print(f"Saved screenshot to {screenshot_path}")
        
        # Get the page HTML content
        content = await page.content()
        with open("scratch/powerbi_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Saved HTML content to scratch/powerbi_page.html")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
