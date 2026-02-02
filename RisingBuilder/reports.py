import re
from datetime import datetime
from typing import Any, Dict, List, Set

# --- 5th Edition Limits ---
FORCE_ORG_LIMITS_5E = {
    "HQ": (1, 2),
    "Troops": (2, 6),
    "Elites": (0, 3),
    "Fast Attack": (0, 3),
    "Heavy Support": (0, 3),
}

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
    from reportlab.lib import colors
    HAVE_REPORTLAB = True
except ImportError:
    HAVE_REPORTLAB = False

def clean_name(text: str) -> str:
    """
    Removes cost/notes from a name to find its dictionary key.
    """
    text = re.sub(r'\s*\(.*?\)', '', text)
    return text.strip()

def write_roster_pdf(roster_entries: List[Dict[str, Any]], codex_data: Dict[str, Any], points_limit: int, path: str, get_unit_callback):
    if not HAVE_REPORTLAB: return

    styles = getSampleStyleSheet()
    header_style = ParagraphStyle('Header', parent=styles['Heading3'], fontSize=12, spaceAfter=4, textColor=colors.black)
    body_style = ParagraphStyle('Body', parent=styles['BodyText'], fontSize=9, leading=11)
    
    story = []
    
    # --- 1. Data Collection ---
    total_pts = 0
    slot_counts = {k: 0 for k in FORCE_ORG_LIMITS_5E}
    glossary_keys: Set[str] = set()
    
    roster_breakdown = []
    for e in roster_entries:
        u = get_unit_callback(e["unit_id"])
        if not u: continue
        
        # Track Slot
        if e.get("parent") is None and u.get("slot") in slot_counts:
            slot_counts[u["slot"]] += 1
            
        # Calculate Cost & Collect Keywords
        cost = u.get("base_points", 0) + u.get("points_per_model", 0) * e.get("size", 1)
        selected_opts_display = []
        selected_ids = set() # Flattened set of selected IDs for easy lookup
        
        # 1. Base Wargear & Rules
        for w in u.get("wargear", []): glossary_keys.add(w)
        for r in u.get("special_rules", []): glossary_keys.add(r)
        
        # 2. Options
        for gid, picks in e.get("selected", {}).items():
            for opt in u.get("options", []):
                if opt["group_id"] == gid:
                    for c in opt.get("choices", []):
                        # Count Logic
                        count = 0
                        if isinstance(picks, list): count = picks.count(c["id"])
                        elif picks == c["id"]: count = 1
                        
                        if count > 0:
                            selected_ids.add(c["id"]) # Track ID for profile lookup
                            
                            # Points
                            pts = c.get("points", 0)
                            mode = c.get("points_mode", "flat")
                            cost += (pts * e.get("size", 1)) if mode == "per_model" else (pts * count)
                            
                            # Display text
                            c_name = c.get("name", "")
                            display_text = f"{c_name} ({pts} pts)"
                            if count > 1: display_text = f"{c_name} x{count} ({pts*count} pts)"
                            selected_opts_display.append(display_text)
                            
                            # Add to Glossary
                            glossary_keys.add(clean_name(c_name))

        total_pts += cost
        roster_breakdown.append({
            "unit": u, "entry": e, "cost": cost, 
            "selected_opts": selected_opts_display,
            "selected_ids": selected_ids
        })

    # --- 2. Build PDF Content ---
    story.append(Paragraph(f"{codex_data.get('codex_name', 'Army')} Roster", styles["Title"]))
    status_color = "red" if total_pts > points_limit else "black"
    story.append(Paragraph(f"Points: <font color='{status_color}'><b>{total_pts}</b></font> / {points_limit}", styles["Heading2"]))
    story.append(Spacer(1, 6))

    # Force Org Table
    fo_rows = [["Slot", "Taken", "Limit"]]
    for slot, (mn, mx) in FORCE_ORG_LIMITS_5E.items():
        val = slot_counts[slot]
        val_str = f"<font color='red'>{val}</font>" if not (mn <= val <= mx) else str(val)
        fo_rows.append([slot, Paragraph(val_str, styles["BodyText"]), f"{mn}-{mx}"])
    
    t = Table(fo_rows, colWidths=[40*mm, 20*mm, 20*mm], hAlign='LEFT')
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Unit Cards
    weapons_catalog = codex_data.get("weapons", {}) or {}
    
    for item in roster_breakdown:
        u = item["unit"]
        e = item["entry"]
        sel_ids = item["selected_ids"]
        
        elements = []
        indent = "&nbsp;&nbsp;&nbsp;&nbsp;↳ " if e.get("parent") is not None else ""
        elements.append(Paragraph(f"{indent}<b>{u['name']}</b> (x{e['size']}) - {item['cost']} pts", header_style))
        
        # --- Profile Table Logic ---
        prof = u.get("profile", {})
        ptype = u.get("profile_type", "standard")
        
        # Define Headers based on Type
        if ptype == "vehicle":
            headers = ["Unit", "BS", "Front", "Side", "Rear"]
            main_row = ["Main", prof.get("BS","-"), prof.get("Front","-"), prof.get("Side","-"), prof.get("Rear","-")]
        elif ptype == "walker":
            headers = ["Unit", "WS", "BS", "S", "I", "A", "Front", "Side", "Rear"]
            main_row = ["Main", prof.get("WS","-"), prof.get("BS","-"), prof.get("S","-"), prof.get("I","-"), prof.get("A","-"), prof.get("Front","-"), prof.get("Side","-"), prof.get("Rear","-")]
        else:
            headers = ["Unit", "WS", "BS", "S", "T", "W", "I", "A", "Ld", "Sv"]
            main_row = ["Main", prof.get("WS","-"), prof.get("BS","-"), prof.get("S","-"), prof.get("T","-"), prof.get("W","-"), prof.get("I","-"), prof.get("A","-"), prof.get("Ld","-"), prof.get("Sv","-")]

        table_data = [headers, main_row]

        # Check for Sub-Profiles (Exarchs, Warlocks, etc.)
        # Structure in JSON: "sub_profiles": { "option_id": { "name": "Exarch", "WS": 5... } }
        sub_profs = u.get("sub_profiles", {})
        for trigger_id, sp_data in sub_profs.items():
            if trigger_id in sel_ids:
                # Build row based on headers
                row_name = sp_data.get("name", "Leader")
                if ptype == "vehicle":
                    row = [row_name, sp_data.get("BS","-"), sp_data.get("Front","-"), sp_data.get("Side","-"), sp_data.get("Rear","-")]
                elif ptype == "walker":
                    row = [row_name, sp_data.get("WS","-"), sp_data.get("BS","-"), sp_data.get("S","-"), sp_data.get("I","-"), sp_data.get("A","-"), sp_data.get("Front","-"), sp_data.get("Side","-"), sp_data.get("Rear","-")]
                else:
                    row = [row_name, sp_data.get("WS","-"), sp_data.get("BS","-"), sp_data.get("S","-"), sp_data.get("T","-"), sp_data.get("W","-"), sp_data.get("I","-"), sp_data.get("A","-"), sp_data.get("Ld","-"), sp_data.get("Sv","-")]
                table_data.append(row)

        t = Table(table_data, colWidths=[20*mm] + [10*mm]*(len(headers)-1), hAlign='LEFT')
        t.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 8)
        ]))
        elements.append(t)
        elements.append(Spacer(1, 4))
        
        # Weapons Table
        candidates = u.get("wargear", []) + [clean_name(opt) for opt in item["selected_opts"]]
        w_rows = [["Weapon", "Range", "Str", "AP", "Type", "Notes"]]
        has_weapons = False
        seen_w = set()
        for c in candidates:
            c_clean = clean_name(c)
            if c_clean in seen_w: continue
            
            # Fuzzy lookup
            data = None
            if c_clean in weapons_catalog: data = weapons_catalog[c_clean]
            else:
                for k, v in weapons_catalog.items():
                    if k.lower() == c_clean.lower(): data = v; break
            
            if data:
                has_weapons = True
                seen_w.add(c_clean)
                w_rows.append([
                    Paragraph(c_clean, body_style),
                    str(data.get("range", "-")), str(data.get("S", "-")), str(data.get("AP", "-")),
                    Paragraph(str(data.get("type", "-")), body_style),
                    Paragraph(str(data.get("notes", "-")), body_style)
                ])
                
        if has_weapons:
            wt = Table(w_rows, colWidths=[35*mm, 15*mm, 10*mm, 10*mm, 25*mm, 60*mm], hAlign='LEFT')
            wt.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.25, colors.grey), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
            elements.append(wt)
            elements.append(Spacer(1, 4))

        # Lists
        if u.get("wargear"): elements.append(Paragraph(f"<b>Wargear:</b> {', '.join(u['wargear'])}", body_style))
        if u.get("special_rules"): elements.append(Paragraph(f"<b>Rules:</b> {', '.join(u['special_rules'])}", body_style))
        if item["selected_opts"]: elements.append(Paragraph(f"<b>Selections:</b> {', '.join(item['selected_opts'])}", body_style))
        
        elements.append(Spacer(1, 10))
        story.append(KeepTogether(elements))

    # --- 3. Glossary ---
    story.append(PageBreak())
    story.append(Paragraph("Army Reference", styles["Heading1"]))
    story.append(Spacer(1, 6))
    
    rules_db = codex_data.get("rules", {})
    wargear_db = codex_data.get("wargear", {})
    
    master_db = {}
    for k, v in rules_db.items(): master_db[k.lower()] = (k, v.get("summary", ""))
    for k, v in wargear_db.items(): master_db[k.lower()] = (k, v.get("summary", ""))
    
    sorted_keys = sorted(list(glossary_keys), key=lambda x: x.lower())
    definitions = []
    
    for k in sorted_keys:
        k_lower = k.lower()
        if k_lower in master_db:
            real_name, summary = master_db[k_lower]
            if summary: definitions.append(f"<b>{real_name}:</b> {summary}")

    if definitions:
        for d in definitions:
            story.append(Paragraph(d, body_style))
            story.append(Spacer(1, 3))
    else:
        story.append(Paragraph("No rules found.", body_style))

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    doc.build(story)