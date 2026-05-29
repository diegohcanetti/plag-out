import pdfplumber

def map_cells():
    path = "scratch/aappce_dec_2025.pdf"
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[4] # Page 5
        
        # Columns definition (approximate x center)
        cols = [
            {"name": "Acyrthosiphon pisum", "x": 114.0},
            {"name": "Tetranychus urticae", "x": 138.0},
            {"name": "Dalbulus maidis", "x": 159.0},
            {"name": "Dichelops spp.", "x": 187.0},
            {"name": "Complejo cortadoras", "x": 209.0},
            {"name": "Helicoverpa gelotopoeon", "x": 235.0},
            {"name": "Armadillidium vulgare", "x": 260.0},
            {"name": "Milax gagates", "x": 288.0},
            {"name": "Faronta albilinea", "x": 311.0},
            {"name": "Spodoptera frugiperda", "x": 333.0},
            {"name": "Pseudaletia adultera", "x": 360.0},
            {"name": "Diatraea saccharalis", "x": 384.0}
        ]
        
        # Rows definition (y0 from bottom)
        rows = [
            {"node": "1 NOA", "y0": 327.5},
            {"node": "2 SEE SFN", "y0": 303.4},
            {"node": "3 SFC", "y0": 279.4},
            {"node": "4 CBCN", "y0": 255.4},
            {"node": "5 CBE", "y0": 231.4},
            {"node": "6 ER", "y0": 207.3},
            {"node": "7 SFCS", "y0": 183.3},
            {"node": "8 SFS", "y0": 159.2},
            {"node": "9 BAN", "y0": 135.2},
            {"node": "10 BAO", "y0": 111.2},
            {"node": "11 BASO", "y0": 87.1},
            {"node": "12 BASE", "y0": 63.1}
        ]
        
        # Find curves (small circles) and associate them to cells
        cell_curves = {}
        for c in page.curves:
            color = c.get("non_stroking_color")
            if not color or color == (0.9961, 0.9961, 0.9961) or color == (1.0, 1.0, 1.0) or color == (0.9373, 0.9725, 0.9804):
                continue
            width = c["x1"] - c["x0"]
            height = c["y1"] - c["y0"]
            if width < 30 and height < 30:
                cx = (c["x0"] + c["x1"]) / 2.0
                cy0 = c["y0"]
                # Find matching row and col
                matched_row = None
                matched_col = None
                for r in rows:
                    if abs(r["y0"] - cy0) < 5:
                        matched_row = r["node"]
                        break
                for col in cols:
                    if abs(col["x"] - cx) < 10:
                        matched_col = col["name"]
                        break
                if matched_row and matched_col:
                    cell_curves[(matched_row, matched_col)] = color

        print("=== MAPPED CURVE COLORS BY CELL ===")
        for r in rows:
            row_name = r["node"]
            row_cells = []
            for col in cols:
                col_name = col["name"]
                color = cell_curves.get((row_name, col_name))
                if color:
                    row_cells.append(f"{col_name[:10]}: {color}")
            if row_cells:
                print(f"{row_name}: {', '.join(row_cells)}")

if __name__ == "__main__":
    map_cells()
