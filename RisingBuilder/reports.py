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
    """Draws a clean, grid-based statline table."""
    if not profiles_list: return

    master_keys = ["WS", "BS", "S", "T", "W", "I", "A", "Ld", "Sv", "Front", "Side", "Rear"]
    active_keys = []
    for k in master_keys:
        for _, p in profiles_list:
            if k in p:
                active_keys.append(k)
                break
    if not active_keys: return

    # Table Config
    pdf.set_font("Arial", 'B', 8)
    stat_width = 9
    name_width = 40
    
    # Header
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(name_width, 5, "Model", 1, 0, 'L', True)
    for k in active_keys:
        pdf.cell(stat_width, 5, k, 1, 0, 'C', True)
    pdf.ln()

    # Rows
    pdf.set_font("Arial", '', 9)
    for name, stats in profiles_list:
        display_name = "Standard" if name == "Unit Profile" else name
        pdf.cell(name_width, 5, display_name, 1, 0, 'L')
        for k in active_keys:
            val = str(stats.get(k, "-"))
            pdf.cell(stat_width, 5, val, 1, 0, 'C')
        pdf.ln()

def draw_game_reference_tables(pdf):
    """
    Draws 5th Ed Reference Charts.
    Infantry Tables on top. Vehicle Table forced below.
    """
    pdf.add_page()
    pdf.chapter_title("Game Reference Tables (5th Edition)")
    
    # --- CONFIGURATION ---
    pdf.set_font("Arial", size=7) 
    row_h = 4.5
    x_start = 10
    y_start = pdf.get_y()
    
    # --- 1. SHOOTING (Vertical) ---
    bs_x = x_start
    pdf.set_xy(bs_x, y_start)
    
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(25, 6, "Shooting", 0, 1, 'C')
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(10, row_h, "BS", 1, 0, 'C', True)
    pdf.cell(15, row_h, "To Hit", 1, 1, 'C', True)
    pdf.set_font("Arial", '', 7)
    bs_vals = {1: "6+", 2: "5+", 3: "4+", 4: "3+"}
    for i in range(1, 11):
        pdf.set_x(bs_x)
        val = bs_vals.get(i, "2+")
        pdf.cell(10, row_h, str(i), 1, 0, 'C')
        pdf.cell(15, row_h, val, 1, 1, 'C')

    # --- 2. ASSAULT (Matrix) ---
    ws_x = bs_x + 30 
    pdf.set_xy(ws_x, y_start)
    col_w = 6
    head_w = 18
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(head_w + (10*col_w), 6, "Assault To Hit (D6)", 0, 1, 'C')
    pdf.set_x(ws_x + head_w)
    pdf.set_fill_color(220, 220, 220)
    for i in range(1, 11):
        pdf.cell(col_w, row_h, str(i), 1, 0, 'C', True)
    pdf.ln()
    
    curr_y = pdf.get_y()
    pdf.set_xy(ws_x, curr_y - row_h)
    pdf.set_font("Arial", 'B', 7)
    pdf.cell(head_w, row_h, "Atk\\Def", 1, 0, 'C', True)
    pdf.set_xy(ws_x, curr_y)
    
    pdf.set_font("Arial", '', 7)
    for a_ws in range(1, 11):
        pdf.set_x(ws_x)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(head_w, row_h, f"WS {a_ws}", 1, 0, 'C', True)
        for d_ws in range(1, 11):
            val = "4+"
            if d_ws > (2 * a_ws): val = "5+"
            elif a_ws > d_ws: val = "3+"
            pdf.cell(col_w, row_h, val, 1, 0, 'C')
        pdf.ln()

    # --- 3. WOUNDING (Matrix) ---
    st_x = ws_x + 78 + 5
    pdf.set_xy(st_x, y_start)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(head_w + (10*col_w), 6, "To Wound (D6)", 0, 1, 'C')
    pdf.set_x(st_x + head_w)
    pdf.set_fill_color(220, 220, 220)
    for i in range(1, 11):
        pdf.cell(col_w, row_h, str(i), 1, 0, 'C', True)
    pdf.ln()
    
    curr_y = pdf.get_y()
    pdf.set_xy(st_x, curr_y - row_h)
    pdf.set_font("Arial", 'B', 7)
    pdf.cell(head_w, row_h, "Str\\T", 1, 0, 'C', True)
    pdf.set_xy(st_x, curr_y)
    
    pdf.set_font("Arial", '', 7)
    for s in range(1, 11):
        pdf.set_x(st_x)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(head_w, row_h, f"Str {s}", 1, 0, 'C', True)
        for t in range(1, 11):
            diff = s - t
            if diff >= 2: val = "2+"
            elif diff == 1: val = "3+"
            elif diff == 0: val = "4+"
            elif diff == -1: val = "5+"
            elif diff == -2: val = "6+"
            else: val = "-"
            pdf.cell(col_w, row_h, val, 1, 0, 'C')
        pdf.ln()

    # ==========================================
    # VEHICLE DAMAGE SECTION
    # ==========================================
    
    # We forcefully move down. 
    # Calculate bottom of previous tables: y_start + (11 * 4.5) + header ~ 60mm
    # So we set Y to y_start + 65. 
    # If that is too low on the page (> 250), we add a page.
    
    new_y = y_start + 65
    if new_y > 250:
        pdf.add_page()
        new_y = 20
    
    pdf.set_xy(x_start, new_y)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(0, 8, "Vehicle Damage", 0, 1, 'L', True)
    pdf.ln(2)
    
    veh_start_y = pdf.get_y()
    
    # --- DAMAGE TABLE (Left) ---
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(15, 6, "Roll", 1, 0, 'C', True)
    pdf.cell(35, 6, "Result", 1, 0, 'L', True)
    pdf.cell(80, 6, "Effect", 1, 1, 'L', True)
    
    pdf.set_font("Arial", '', 8)
    damage_rows = [
        ("1", "Crew Shaken", "Vehicle can only move (No Shooting)."),
        ("2", "Crew Stunned", "Vehicle cannot move or shoot."),
        ("3", "Weapon Destroyed", "One weapon destroyed."),
        ("4", "Immobilised", "Cannot move."),
        ("5", "Wrecked", "Destroyed. Becomes Wreck."),
        ("6+", "Explodes!", "Destroyed. Models within D6\" take S3 hit.")
    ]
    
    for roll, res, eff in damage_rows:
        pdf.cell(15, 6, roll, 1, 0, 'C')
        pdf.cell(35, 6, res, 1, 0, 'L')
        pdf.cell(80, 6, eff, 1, 1, 'L')

    # --- MODIFIERS (Right) ---
    pdf.set_xy(x_start + 135, veh_start_y)
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(55, 6, "Penetration Modifiers", 1, 1, 'L', True)
    
    pdf.set_font("Arial", '', 8)
    modifiers = [
        "AP 1 Weapon: +1",
        "AP - Weapon: -1",
        "Open-topped: +1",
        "Glancing Hit: -2",
        "Melta (Close): +D6",
    ]
    
    for mod in modifiers:
        pdf.set_x(x_start + 135)
        pdf.cell(55, 6, mod, 1, 1, 'L')

def write_roster_pdf(roster, codex_data, points_limit, filename, get_unit_callback, include_ref_tables=False):
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
                    if isinstance(picks, list) and choice["id"] in picks: collect_refs([choice["name"]])
                    elif picks == choice["id"]: collect_refs([choice["name"]])

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
            
            # Unit Bar
            pdf.set_font("Arial", 'B', 11)
            pdf.set_fill_color(240, 240, 240)
            name_str = f"{u['name']}"
            if entry.get("size", 1) > 1: name_str += f" (x{entry['size']})"
            pdf.cell(150, 7, name_str, 1, 0, 'L', True)
            pdf.cell(40, 7, f"{entry.get('calculated_cost', 0)} pts", 1, 1, 'C', True)
            pdf.ln(1)

            # Profiles
            profiles_to_print = []
            if "profile" in u: profiles_to_print.append( ("Unit Profile", u["profile"]) )
            if "sub_profiles" in u and "selected" in entry:
                all_picked_ids = []
                for picks in entry["selected"].values():
                    if isinstance(picks, list): all_picked_ids.extend(picks)
                    else: all_picked_ids.append(picks)
                for key, sub_prof in u["sub_profiles"].items():
                    if key in all_picked_ids: profiles_to_print.append( (sub_prof.get("name", key), sub_prof) )
            
            draw_profile_table(pdf, profiles_to_print)
            pdf.ln(2)

            # Options
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

            # Children
            children = [c for c in roster if c.get("parent_id") == entry["id"]]
            for child in children:
                uc = get_unit_callback(child['unit_id'])
                pdf.ln(2)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(10, 5, "  >", 0, 0)
                pdf.cell(0, 5, f"Attached: {uc['name']} ({child.get('calculated_cost', 0)} pts)", ln=True)
                
                c_profs = []
                if "profile" in uc: c_profs.append( ("Profile", uc["profile"]) )
                if "sub_profiles" in uc and "selected" in child:
                    all_picked_c_ids = []
                    for picks in child["selected"].values():
                        if isinstance(picks, list): all_picked_c_ids.extend(picks)
                        else: all_picked_c_ids.append(picks)
                    for key, sub_prof in uc["sub_profiles"].items():
                        if key in all_picked_c_ids: c_profs.append( (sub_prof.get("name", key), sub_prof) )
                
                draw_profile_table(pdf, c_profs)

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
                if key in w_name: w_stats = weapons_db[key]; break
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

    if include_ref_tables:
        draw_game_reference_tables(pdf)

    try: pdf.output(filename)
    except Exception as e: print(f"Error writing PDF: {e}")
