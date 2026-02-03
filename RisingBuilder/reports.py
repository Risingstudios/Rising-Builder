from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Rising Builder - Army Roster', 0, 1, 'C')
        self.set_line_width(0.5)
        self.line(10, 20, 200, 20)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, label):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(200, 220, 255)  # Light Blue
        self.cell(0, 6, label, 0, 1, 'L', True)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, body)
        self.ln()

def write_roster_pdf(roster, codex_data, points_limit, filename, get_unit_callback):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- 1. COLLECT DATA & SUMMARY ---
    total_pts = 0
    slot_counts = {"HQ": 0, "Troops": 0, "Elites": 0, "Fast Attack": 0, "Heavy Support": 0}
    
    # Collections for the Reference Page
    active_weapons = set()
    active_rules = set()
    
    # Helper to collect rules/weapons from text
    def collect_refs(name_list):
        for name in name_list:
            # Check if it's a weapon
            if name in codex_data.get('weapons', {}):
                active_weapons.add(name)
            # Check if it's a rule
            elif name in codex_data.get('rules', {}):
                active_rules.add(name)
            # Check if it's wargear
            elif name in codex_data.get('wargear', {}):
                active_rules.add(name)

    # First pass: Calculate totals and collect references
    for entry in roster:
        u = get_unit_callback(entry['unit_id'])
        if not u: continue
        
        # Points
        total_pts += entry.get('calculated_cost', 0)
        
        # Slots (Parents only)
        if not entry.get("parent_id") and u.get("slot") in slot_counts:
            slot_counts[u["slot"]] += 1

        # Collect References from Base Wargear/Rules
        collect_refs(u.get("wargear", []))
        collect_refs(u.get("special_rules", []))
        
        # Collect References from Selected Options
        if "selected" in entry:
            for gid, picks in entry["selected"].items():
                opt_def = next((o for o in u.get("options", []) if o.get("group_id") == gid), None)
                if not opt_def: continue
                for choice in opt_def.get("choices", []):
                    # If this choice is selected
                    count = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                    if count > 0:
                        collect_refs([choice["name"]]) # Name usually matches lookup key
                        # Also check if choice name implies a weapon (e.g. "Twin-linked Fusion Blaster")
                        # (Simple matching handled above, complex matching omitted for safety)

    # --- 2. HEADER & FORCE ORG ---
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"Codex: {codex_data.get('codex_name', 'Unknown Army')}", ln=True)
    
    # Points Bar
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(50, 8, f"Points: {total_pts} / {points_limit}", border=1, align='C')
    
    # Force Org Bar
    fo_text = f"HQ: {slot_counts['HQ']}/2   Troops: {slot_counts['Troops']}/6   Elites: {slot_counts['Elites']}/3   Fast: {slot_counts['Fast Attack']}/3   Heavy: {slot_counts['Heavy Support']}/3"
    pdf.cell(140, 8, fo_text, border=1, ln=True, align='C')
    pdf.ln(8)

    # --- 3. ROSTER LISTING (Grouped by Slot) ---
    slots_order = ["HQ", "Troops", "Elites", "Fast Attack", "Heavy Support", "Dedicated Transport"]
    
    for slot in slots_order:
        # Get units in this slot
        slot_units = [e for e in roster if not e.get("parent_id") and get_unit_callback(e['unit_id'])['slot'] == slot]
        
        if not slot_units: continue
        
        pdf.chapter_title(slot)
        
        for entry in slot_units:
            u = get_unit_callback(entry['unit_id'])
            
            # Unit Header: Name, Cost, Size
            pdf.set_font("Arial", 'B', 11)
            pdf.set_fill_color(240, 240, 240)
            name_str = f"{u['name']}"
            if entry.get("size", 1) > 1:
                name_str += f" (x{entry['size']})"
            
            pdf.cell(150, 7, name_str, 1, 0, 'L', True)
            pdf.cell(40, 7, f"{entry.get('calculated_cost', 0)} pts", 1, 1, 'C', True)
            
            # --- PROFILE TABLE (The "Unit Card" feature) ---
            if "profile" in u:
                pdf.set_font("Courier", '', 9) # Monospace for alignment
                p = u["profile"]
                
                # Dynamic Profile Header/Values based on keys
                # Standard order: WS BS S T W I A Ld Sv (for Infantry)
                std_keys = ["WS", "BS", "S", "T", "W", "I", "A", "Ld", "Sv", "Front", "Side", "Rear"]
                keys = [k for k in std_keys if k in p]
                
                # Header Row
                header = "  ".join([f"{k:>4}" for k in keys])
                pdf.cell(0, 5, header, ln=True)
                
                # Value Row
                vals = "  ".join([f"{str(p[k]):>4}" for k in keys])
                pdf.set_font("Courier", 'B', 9)
                pdf.cell(0, 5, vals, ln=True)
            
            pdf.ln(1)

            # --- OPTIONS / WARGEAR ---
            pdf.set_font("Arial", size=10)
            options_text = []
            
            # Base Wargear
            if u.get("wargear"):
                options_text.append("Base: " + ", ".join(u["wargear"]))
            
            # Selected Options
            if "selected" in entry:
                for gid, picks in entry["selected"].items():
                    opt_def = next((o for o in u.get("options", []) if o.get("group_id") == gid), None)
                    if not opt_def: continue
                    for choice in opt_def.get("choices", []):
                        count = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                        if count > 0:
                            item_str = choice['name']
                            if count > 1: item_str = f"{count}x {item_str}"
                            options_text.append(item_str)
            
            if options_text:
                pdf.multi_cell(0, 5, "   " + ", ".join(options_text))
            
            # --- RULES LIST ---
            if u.get("special_rules"):
                pdf.set_font("Arial", 'I', 9)
                pdf.multi_cell(0, 5, "   Rules: " + ", ".join(u["special_rules"]))

            # --- ATTACHED UNITS (Children) ---
            children = [c for c in roster if c.get("parent_id") == entry["id"]]
            for child in children:
                uc = get_unit_callback(child['unit_id'])
                pdf.ln(2)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(10, 5, "  >", 0, 0)
                pdf.cell(0, 5, f"Attached: {uc['name']} ({child.get('calculated_cost', 0)} pts)", ln=True)
                
                # Child Options
                c_opts = []
                if "selected" in child:
                    for gid, picks in child["selected"].items():
                        opt_def = next((o for o in uc.get("options", []) if o.get("group_id") == gid), None)
                        if not opt_def: continue
                        for choice in opt_def.get("choices", []):
                            count = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                            if count > 0:
                                c_opts.append(f"{choice['name']}")
                if c_opts:
                    pdf.set_font("Arial", size=9)
                    pdf.cell(10, 5, "", 0, 0)
                    pdf.multi_cell(0, 5, ", ".join(c_opts))

            pdf.ln(4) # Spacer

    # --- 4. APPENDIX: REFERENCE SHEETS ---
    pdf.add_page()
    pdf.chapter_title("Reference: Weapons")
    
    # Weapon Table Header
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(60, 6, "Name", 1, 0, 'L', True)
    pdf.cell(20, 6, "Range", 1, 0, 'C', True)
    pdf.cell(15, 6, "Str", 1, 0, 'C', True)
    pdf.cell(15, 6, "AP", 1, 0, 'C', True)
    pdf.cell(40, 6, "Type", 1, 0, 'C', True)
    pdf.cell(40, 6, "Notes", 1, 1, 'L', True)
    
    pdf.set_font("Arial", '', 9)
    
    # Sort weapons alphabetically
    sorted_weps = sorted(list(active_weapons))
    weapons_db = codex_data.get('weapons', {})
    
    for w_name in sorted_weps:
        # Check partial matches if exact match fails (e.g. "Twin-linked Plasma rifle" -> "Plasma rifle")
        w_stats = weapons_db.get(w_name)
        if not w_stats:
            # Try to find base weapon name in string
            for key in weapons_db.keys():
                if key in w_name:
                    w_stats = weapons_db[key]
                    break
        
        if w_stats:
            pdf.cell(60, 6, w_name, 1, 0, 'L')
            pdf.cell(20, 6, str(w_stats.get('range', '-')), 1, 0, 'C')
            pdf.cell(15, 6, str(w_stats.get('S', '-')), 1, 0, 'C')
            pdf.cell(15, 6, str(w_stats.get('AP', '-')), 1, 0, 'C')
            pdf.cell(40, 6, str(w_stats.get('type', '-')), 1, 0, 'C')
            # Truncate notes if too long for one line
            notes = str(w_stats.get('notes', '-'))
            pdf.cell(40, 6, notes[:25], 1, 1, 'L')

    pdf.ln(10)
    pdf.chapter_title("Reference: Rules & Wargear")
    
    sorted_rules = sorted(list(active_rules))
    rules_db = codex_data.get('rules', {})
    gear_db = codex_data.get('wargear', {})
    
    for r_name in sorted_rules:
        desc = ""
        if r_name in rules_db:
            desc = rules_db[r_name].get('summary', '')
        elif r_name in gear_db:
            desc = gear_db[r_name].get('summary', '')
            
        if desc:
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(0, 5, r_name, 0, 1)
            pdf.set_font("Arial", '', 9)
            pdf.multi_cell(0, 5, desc)
            pdf.ln(2)

    try:
        pdf.output(filename)
    except Exception as e:
        print(f"Error writing PDF: {e}")
