import pdfplumber

def inspect_shapes():
    path = "scratch/aappce_dec_2025.pdf"
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[4] # Page 5
        print("Page 5 drawings/rects/circles count:")
        print(f"  rects: {len(page.rects)}")
        print(f"  images: {len(page.images)}")
        print(f"  lines: {len(page.lines)}")
        print(f"  curves: {len(page.curves)}")
        
        # Let's inspect some rects or shapes on the page
        if page.rects:
            print("\nFirst 5 rects:")
            for idx, r in enumerate(page.rects[:5]):
                print(f"  Rect {idx+1}: x0={r['x0']:.1f}, y0={r['y0']:.1f}, x1={r['x1']:.1f}, y1={r['y1']:.1f}, width={r['width']:.1f}, height={r['height']:.1f}, non_stroking_color={r.get('non_stroking_color')}, stroking_color={r.get('stroking_color')}")
                
        # Let's inspect text characters to see if there are any unicode symbols with colors or fonts
        char_types = set()
        chars_with_font = []
        for char in page.chars:
            fontname = char.get("fontname", "")
            text = char.get("text", "")
            if text in ["●", "■", "▲", "▼", "○", "□"]:
                chars_with_font.append((text, char.get("x0"), char.get("y0"), fontname))
            char_types.add(text)
            
        print(f"\nUnique character symbols: {sorted(list(char_types))[:50]}")
        print(f"Special shape characters: {chars_with_font}")

if __name__ == "__main__":
    inspect_shapes()
