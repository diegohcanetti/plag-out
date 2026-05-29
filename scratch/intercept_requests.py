import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Intercept network requests and responses
        page.on("request", lambda request: print(f">> Request: {request.method} {request.url}"))
        page.on("response", lambda response: print(f"<< Response: {response.status} {response.url}"))
        
        print("Navigating to AAPRESID insect map page...")
        await page.goto("https://www.aapresid.org.ar/rem-malezas/mapa-insectos/", wait_until="networkidle")
        
        print("\nPage loaded successfully!")
        
        # Wait a bit to ensure all lazy elements/AJAX loaded
        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
