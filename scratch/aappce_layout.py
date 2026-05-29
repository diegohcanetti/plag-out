import pdfplumber

def analyze_layout():
    path = "scratch/aappce_dec_2025.pdf"
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[4] # Page 5
        
        print("=== TEXT ELEMENTS ON PAGE 5 ===")
        # Group characters by y-coordinate (approximate line)
        lines = {}
        for char in page.chars:
            y = round(char["top"], 1)
            found = False
            for existing_y in lines:
                if abs(existing_y - y) < 5:
                    lines[existing_y].append(char)
                    found = True
                    break
            if not found:
                lines[y] = [char]
                
        # Sort lines by y
        for y in sorted(lines.keys()):
            # Sort chars in line by x
            chars = sorted(lines[y], key=lambda c: c["x0"])
            text = "".join([c["text"] for c in chars])
            first_char = chars[0]
            print(f"y={y:.1f} (x0={first_char['x0']:.1f}): {text}")
            
        print("\n=== SMALL COLORED SHAPES (CURVES) ON PAGE 5 ===")
        # Filter curves that are small circles (e.g. width/height < 20) and have colorful fills
        colored_shapes = []
        for idx, c in enumerate(page.curves):
            color = c.get("non_stroking_color")
            if not color:
                continue
            # Filter out white/very light background curves
            if color == (0.9961, 0.9961, 0.9961) or color == (1.0, 1.0, 1.0) or color == (0.9373, 0.9725, 0.9804):
                continue
            width = c["x1"] - c["x0"]
            height = c["y1"] - c["y0"]
            # Small elements that are likely grid cells
            if width < 40 and height < 40:
                colored_shapes.append(c)
                
        print(f"Found {len(colored_shapes)} colored grid cell shapes:")
        for idx, s in enumerate(colored_shapes):
            print(f"  Shape {idx+1}: x0={s['x0']:.1f}, y0={s['y0']:.1f}, x1={s['x1']:.1f}, y1={s['y1']:.1f}, fill={s.get('non_stroking_color')}")

if __name__ == "__main__":
    analyze_layout()
