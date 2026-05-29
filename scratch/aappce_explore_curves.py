import pdfplumber

def explore_curves():
    path = "scratch/aappce_dec_2025.pdf"
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[4] # Page 5
        print("Total curves:", len(page.curves))
        
        # Let's count unique non-stroking colors
        color_counts = {}
        for idx, c in enumerate(page.curves):
            color = c.get("non_stroking_color")
            # convert color tuple to string for keying
            color_str = str(color)
            color_counts[color_str] = color_counts.get(color_str, 0) + 1
            
        print("\nCurve colors and counts:")
        for color, count in color_counts.items():
            print(f"  {color}: {count}")
            
        # Let's look at a few curves with interesting colors (like red, yellow, green)
        # Red is usually close to (1.0, 0.0, 0.0) or (0.9, 0.1, 0.1)
        # Yellow is usually close to (1.0, 1.0, 0.0) or (0.9, 0.9, 0.1)
        # Green is usually close to (0.0, 1.0, 0.0) or (0.1, 0.8, 0.1)
        print("\nSome sample curves:")
        for idx, c in enumerate(page.curves[:10]):
            print(f"  Curve {idx+1}: x0={c['x0']:.1f}, y0={c['y0']:.1f}, x1={c['x1']:.1f}, y1={c['y1']:.1f}, width={c['width']:.1f}, height={c['height']:.1f}, fill={c.get('non_stroking_color')}")

if __name__ == "__main__":
    explore_curves()
