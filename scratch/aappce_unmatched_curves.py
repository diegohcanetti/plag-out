import pdfplumber

def explore_unmatched():
    path = "scratch/aappce_dec_2025.pdf"
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[4] # Page 5
        for idx, c in enumerate(page.curves):
            color = c.get("non_stroking_color")
            if not color or color == (0.9961, 0.9961, 0.9961) or color == (1.0, 1.0, 1.0) or color == (0.9373, 0.9725, 0.9804):
                continue
            width = c["x1"] - c["x0"]
            height = c["y1"] - c["y0"]
            # Print if it's relatively small (e.g. width/height < 30)
            if width < 30 and height < 30:
                print(f"Index={idx} x0={c['x0']:.2f} y0={c['y0']:.2f} x1={c['x1']:.2f} y1={c['y1']:.2f} w={width:.2f} h={height:.2f} color={color}")

if __name__ == "__main__":
    explore_unmatched()
