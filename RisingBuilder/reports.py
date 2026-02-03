from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Rising Builder - Army Roster', 0, 1, 'C')
        self.line(10, 20, 200, 20)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def write_roster_pdf(roster, codex_data, points_limit, filename, get_unit_callback):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=10)

    total_pts = 0
    
    # 1. Calculate Totals first for the header
    for entry in roster:
        total_pts += entry.get('calculated_cost', 0)
        # Add children costs
        for child in roster:
            if child.get('parent_id') == entry['id']:
                total_pts += child.get('calculated_cost', 0)
    
    # Header Info
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Codex: {codex_data.get('codex_name', 'Unknown')}", ln=True)
    pdf.cell(0, 10, f"Total Points: {total_pts} / {points_limit}", ln=True)
    pdf.ln(5)

    # 2. Iterate through Units
    # Filter for parents only first
    parents = [e for e in roster if not e.get("parent_id")]
    
    for entry in parents:
        u = get_unit_callback(entry['unit_id'])
        if not u: continue

        # Unit Header
        pdf.set_font("Arial", 'B', 11)
        pdf.set_fill_color(220, 220, 220) # Light Grey
        unit_name = f"[{u['slot']}] {u['name']}"
        cost = f"{entry.get('calculated_cost', 0)} pts"
        
        # Calculate width for name and cost to justify them
        pdf.cell(140, 8, unit_name, 1, 0, 'L', True)
        pdf.cell(50, 8, cost, 1, 1, 'R', True)
        
        # Unit Stats / Options
        pdf.set_font("Arial", size=10)
        
        # Print Selected Options
        if "selected" in entry and entry["selected"]:
            opt_str = []
            for gid, picks in entry["selected"].items():
                # Find the option group definition
                opt_def = next((o for o in u.get("options", []) if o.get("group_id") == gid), None)
                if not opt_def: continue
                
                for choice in opt_def.get("choices", []):
                    # Count how many of this choice
                    c_qty = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                    if c_qty > 0:
                        if c_qty > 1:
                            opt_str.append(f"{c_qty}x {choice['name']}")
                        else:
                            opt_str.append(f"{choice['name']}")
            
            if opt_str:
                pdf.multi_cell(0, 6, "   Wargear: " + ", ".join(opt_str))

        # Check for Children (Attachments)
        children = [c for c in roster if c.get("parent_id") == entry["id"]]
        for child in children:
            uc = get_unit_callback(child['unit_id'])
            if not uc: continue
            
            pdf.ln(1)
            pdf.set_font("Arial", 'I', 10)
            child_name = f"   + {uc['name']} ({child.get('calculated_cost', 0)} pts)"
            pdf.cell(0, 6, child_name, ln=True)
            
            # Child Options
            if "selected" in child and child["selected"]:
                c_opt_str = []
                for gid, picks in child["selected"].items():
                    opt_def = next((o for o in uc.get("options", []) if o.get("group_id") == gid), None)
                    if not opt_def: continue
                    for choice in opt_def.get("choices", []):
                        c_qty = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                        if c_qty > 0:
                            if c_qty > 1:
                                c_opt_str.append(f"{c_qty}x {choice['name']}")
                            else:
                                c_opt_str.append(f"{choice['name']}")
                
                if c_opt_str:
                    pdf.set_font("Arial", size=9)
                    pdf.multi_cell(0, 5, "      " + ", ".join(c_opt_str))

        pdf.ln(3) # Spacer between units

    try:
        pdf.output(filename)
    except Exception as e:
        print(f"Error writing PDF: {e}")
