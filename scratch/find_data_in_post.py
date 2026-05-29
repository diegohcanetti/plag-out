with open("scratch/post_response.html", "r", encoding="utf-8") as f:
    html = f.read()

print("HTML Length:", len(html))

# Let's see if there are other JS scripts or data inline.
# Search for JSON or department structures or any dynamic script
import re
print("\nSearching for script blocks in HTML...")
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"Found {len(scripts)} script blocks.")
for idx, s in enumerate(scripts):
    s_clean = s.strip()
    if s_clean:
        print(f"\n--- Script Block {idx} (len {len(s_clean)}) ---")
        print(s_clean[:500] + ("..." if len(s_clean) > 500 else ""))

# Let's search if the word "Córdoba" or "Santa Fe" or "Rosario" is inside the response
print("\nChecking for common geographical/data words:")
for word in ["Córdoba", "Santa Fe", "Rosario", "chicharrita", "maidis", "abundancia", "presencia"]:
    print(f"- '{word}' count: {html.lower().count(word.lower())}")
