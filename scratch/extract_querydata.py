import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        print("Launching headless Chromium browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        querydata_responses = []
        
        async def handle_response(response):
            if "querydata" in response.url:
                try:
                    text = await response.text()
                    json_data = json.loads(text)
                    print(f"\n<< Intercepted querydata response! Size: {len(text)} bytes")
                    querydata_responses.append(json_data)
                except Exception as e:
                    print(f"Error reading querydata response: {e}")
                    
        page.on("response", handle_response)
        
        url = "https://app.powerbi.com/view?r=eyJrIjoiZDMxMjRkZmItMDA4Ny00NjIzLWFkNjUtYzU3OGZjNjlkMjc4IiwidCI6IjE5MTBjMTYzLTY0YWUtNGZhMC1iY2QyLTBjMThiNzNkMmZiYSIsImMiOjR9"
        print(f"Navigating to PowerBI URL: {url} ...")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        print("\nPage loaded. Waiting 15 seconds to capture all lazy queries...")
        await asyncio.sleep(15)
        
        print(f"\nCaptured {len(querydata_responses)} querydata responses.")
        for idx, res in enumerate(querydata_responses):
            file_path = f"scratch/querydata_{idx}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2, ensure_ascii=False)
            print(f"Saved response {idx} to {file_path}")
            
            # Print a snippet of keys/structure
            if "results" in res and res["results"]:
                res_snippet = str(res["results"])[:300]
                print(f"  Snippet of results {idx}: {res_snippet}...")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
