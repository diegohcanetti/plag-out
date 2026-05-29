import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        print("Launching Chromium...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        url = "https://app.powerbi.com/view?r=eyJrIjoiZDMxMjRkZmItMDA4Ny00NjIzLWFkNjUtYzU3OGZjNjlkMjc4IiwidCI6IjE5MTBjMTYzLTY0YWUtNGZhMC1iY2QyLTBjMThiNzNkMmZiYSIsImMiOjR9"
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(10)
        
        # Let's see if there are any visual containers, buttons, or tab bars
        print("\nSearching for visual elements...")
        
        # PowerBI page names/tabs are often in elements with class 'navigation-wrapper' or 'tab-element'
        tabs = await page.query_selector_all(".tab-element")
        print(f"Found {len(tabs)} tab elements.")
        for idx, tab in enumerate(tabs):
            text = await tab.inner_text()
            print(f"  Tab {idx}: '{text}'")
            
        # Let's search for buttons
        buttons = await page.query_selector_all("button")
        print(f"Found {len(buttons)} buttons.")
        for idx, btn in enumerate(buttons[:15]):
            text = await btn.inner_text()
            print(f"  Button {idx}: '{text}'")
            
        # Let's search for text blocks that might indicate years like "2024", "2025", "2026"
        elements = await page.query_selector_all("span, div, text")
        print(f"Total spans/divs/texts: {len(elements)}")
        
        year_elements = []
        for el in elements:
            try:
                txt = await el.inner_text()
                if txt in ["2024", "2025", "2026"]:
                    year_elements.append((txt, el))
            except Exception:
                continue
                
        print(f"Found {len(year_elements)} elements matching years.")
        for txt, el in year_elements:
            print(f"  Year match: '{txt}'")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
