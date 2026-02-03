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

def draw_profile_table(pdf, profiles_list):
    """
    Draws a clean, grid-based statline table using Arial.
    """
    if not profiles_list: return

    # Master list of keys to look for
    master_keys = ["WS", "BS", "S", "T", "W", "I", "A", "Ld", "Sv", "Front", "Side", "Rear"]
    
    # Identify active keys (columns) for this specific unit
    active_keys = []
    for k in master_keys:
        for _, p in profiles_list:
            if k in p:
                active_keys.append(k)
                break
    
    if not active_keys: return

    # --- Table Settings ---
    pdf.set_font("Arial", 'B', 8)
    stat_width = 9   # Width of each stat column
    name_width = 40  # Width of the name column
    
    # --- 1. Header Row ---
    pdf.set_fill_color(230, 230, 230) # Light Grey background for headers
    
    # 'Model' Header
    pdf.cell(name_width, 5, "Model", 1, 0, 'L', True)
    
    # Stat Headers (WS, BS, etc.)
    for k in active_keys:
        pdf.cell(stat_width, 5, k, 1, 0, 'C', True)
    pdf.ln()

    # --- 2. Data Rows ---
    pdf.set_font("Arial", '', 9)
    
    for name, stats in profiles_list:
        # Clean up generic name
        display_name = "Standard" if name == "Unit Profile" else name
        
        # Name Cell
        pdf.cell(name_width, 5, display_name, 1, 0, 'L')
        
        # Stat Cells
        for k in active_keys:
            val = str(stats.get(k, "-"))
            pdf.cell(stat_width, 5, val, 1, 0, 'C')
        pdf.ln()

def write_roster_pdf(roster, codex_data, points_limit, filename, get_unit_callback):
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- 1. DATA COLLECTION ---
    total_pts = 0
    slot_counts = {"HQ": 0, "Troops": 0, "Elites": 0, "Fast Attack": 0, "Heavy Support": 0}
    active_weapons = set()
    active_rules = set()
    
    def collect_refs(name_list):
        for name in name_list:
            if name in codex_data.get('weapons', {}): active_weapons.add(name)
            elif name in codex_data.get('rules', {}): active_rules.add(name)
            elif name in codex_data.get('wargear', {}): active_rules.add(name)

    for entry in roster:
        u = get_unit_callback(entry['unit_id'])
        if not u: continue
        total_pts += entry.get('calculated_cost', 0)
        
        if not entry.get("parent_id") and u.get("slot") in slot_counts:
            slot_counts[u["slot"]] += 1

        collect_refs(u.get("wargear", []))
        collect_refs(u.get("special_rules", []))
        
        if "selected" in entry:
            for gid, picks in entry["selected"].items():
                opt_def = next((o for o in u.get("options", []) if o.get("group_id") == gid), None)
                if not opt_def: continue
                for choice in opt_def.get("choices", []):
                    # Check if selected (list or single)
                    if isinstance(picks, list) and choice["id"] in picks:
                        collect_refs([choice["name"]])
                    elif picks == choice["id"]:
                        collect_refs([choice["name"]])

    # --- 2. HEADER ---
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"Codex: {codex_data.get('codex_name', 'Unknown Army')}", ln=True)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(50, 8, f"Points: {total_pts} / {points_limit}", border=1, align='C')
    fo_text = f"HQ: {slot_counts['HQ']}/2   Troops: {slot_counts['Troops']}/6   Elites: {slot_counts['Elites']}/3   Fast: {slot_counts['Fast Attack']}/3   Heavy: {slot_counts['Heavy Support']}/3"
    pdf.cell(140, 8, fo_text, border=1, ln=True, align='C')
    pdf.ln(8)

    # --- 3. ROSTER LISTING ---
    slots_order = ["HQ", "Troops", "Elites", "Fast Attack", "Heavy Support", "Dedicated Transport"]
    
    for slot in slots_order:
        slot_units = [e for e in roster if not e.get("parent_id") and get_unit_callback(e['unit_id'])['slot'] == slot]
        if not slot_units: continue
        
        pdf.chapter_title(slot)
        
        for entry in slot_units:
            u = get_unit_callback(entry['unit_id'])
            
            # --- Unit Header Bar ---
            pdf.set_font("Arial", 'B', 11)
            pdf.set_fill_color(240, 240, 240) # Light Grey Unit Bar
            name_str = f"{u['name']}"
            if entry.get("size", 1) > 1: name_str += f" (x{entry['size']})"
            pdf.cell(150, 7, name_str, 1, 0, 'L', True)
            pdf.cell(40, 7, f"{entry.get('calculated_cost', 0)} pts", 1, 1, 'C', True)
            pdf.ln(1)

            # --- PROFILES TABLE (New Look) ---
            profiles_to_print = []
            
            # 1. Main Profile
            if "profile" in u:
                profiles_to_print.append( ("Unit Profile", u["profile"]) )
            
            # 2. Sub Profiles (Check selections)
            if "sub_profiles" in u and "selected" in entry:
                all_picked_ids = []
                for picks in entry["selected"].values():
                    if isinstance(picks, list): all_picked_ids.extend(picks)
                    else: all_picked_ids.append(picks)
                
                for key, sub_prof in u["sub_profiles"].items():
                    if key in all_picked_ids:
                        profiles_to_print.append( (sub_prof.get("name", key), sub_prof) )
            
            # Draw the Table
            draw_profile_table(pdf, profiles_to_print)
            pdf.ln(2)

            # --- WARGEAR / RULES ---
            pdf.set_font("Arial", size=10)
            options_text = []
            if u.get("wargear"): options_text.append("Base: " + ", ".join(u["wargear"]))
            
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
            
            if options_text: pdf.multi_cell(0, 5, "   " + ", ".join(options_text))
            
            if u.get("special_rules"):
                pdf.set_font("Arial", 'I', 9)
                pdf.multi_cell(0, 5, "   Rules: " + ", ".join(u["special_rules"]))

            # --- ATTACHMENTS (Children) ---
            children = [c for c in roster if c.get("parent_id") == entry["id"]]
            for child in children:
                uc = get_unit_callback(child['unit_id'])
                pdf.ln(2)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(10, 5, "  >", 0, 0)
                pdf.cell(0, 5, f"Attached: {uc['name']} ({child.get('calculated_cost', 0)} pts)", ln=True)
                
                # Child Profiles
                c_profs = []
                if "profile" in uc: c_profs.append( ("Profile", uc["profile"]) )
                
                # Check for child sub-profiles (e.g. Drones on Bodyguard)
                if "sub_profiles" in uc and "selected" in child:
                    all_picked_c_ids = []
                    for picks in child["selected"].values():
                        if isinstance(picks, list): all_picked_c_ids.extend(picks)
                        else: all_picked_c_ids.append(picks)
                    for key, sub_prof in uc["sub_profiles"].items():
                        if key in all_picked_c_ids:
                            c_profs.append( (sub_prof.get("name", key), sub_prof) )

                # Indent the table for children slightly if possible, or just draw it
                # We'll just draw it normally below the name
                draw_profile_table(pdf, c_profs)

                # Child Options
                c_opts = []
                if "selected" in child:
                    for gid, picks in child["selected"].items():
                        opt_def = next((o for o in uc.get("options", []) if o.get("group_id") == gid), None)
                        if not opt_def: continue
                        for choice in opt_def.get("choices", []):
                            count = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                            if count > 0: c_opts.append(f"{choice['name']}")
                if c_opts:
                    pdf.set_font("Arial", size=9)
                    pdf.cell(10, 5, "", 0, 0)
                    pdf.multi_cell(0, 5, ", ".join(c_opts))

            pdf.ln(4)

    # --- 4. APPENDIX ---
    pdf.add_page()
    pdf.chapter_title("Reference: Weapons")
    
    # Weapon Table
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(60, 6, "Name", 1, 0, 'L', True)
    pdf.cell(20, 6, "Range", 1, 0, 'C', True)
    pdf.cell(15, 6, "Str", 1, 0, 'C', True)
    pdf.cell(15, 6, "AP", 1, 0, 'C', True)
    pdf.cell(40, 6, "Type", 1, 0, 'C', True)
    pdf.cell(40, 6, "Notes", 1, 1, 'L', True)
    
    pdf.set_font("Arial", '', 9)
    sorted_weps = sorted(list(active_weapons))
    weapons_db = codex_data.get('weapons', {})
    
    for w_name in sorted_weps:
        w_stats = weapons_db.get(w_name)
        if not w_stats:
            for key in weapons_db.keys():
                if key in w_name:
                    w_stats = weapons_db[key]; break
        
        if w_stats:
            pdf.cell(60, 6, w_name, 1, 0, 'L')
            pdf.cell(20, 6, str(w_stats.get('range', '-')), 1, 0, 'C')
            pdf.cell(15, 6, str(w_stats.get('S', '-')), 1, 0, 'C')
            pdf.cell(15, 6, str(w_stats.get('AP', '-')), 1, 0, 'C')
            pdf.cell(40, 6, str(w_stats.get('type', '-')), 1, 0, 'C')
            notes = str(w_stats.get('notes', '-'))
            pdf.cell(40, 6, notes[:25], 1, 1, 'L')

    pdf.ln(10)
    pdf.chapter_title("Reference: Rules & Wargear")
    sorted_rules = sorted(list(active_rules))
    rules_db = codex_data.get('rules', {})
    gear_db = codex_data.get('wargear', {})
    
    for r_name in sorted_rules:
        desc = ""
        if r_name in rules_db: desc = rules_db[r_name].get('summary', '')
        elif r_name in gear_db: desc = gear_db[r_name].get('summary', '')
            
        if desc:
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(0, 5, r_name, 0, 1)
            pdf.set_font("Arial", '', 9)
            pdf.multi_cell(0, 5, desc)
            pdf.ln(2)

    try: pdf.output(filename)
    except Exception as e: print(f"Error writing PDF: {e}")
