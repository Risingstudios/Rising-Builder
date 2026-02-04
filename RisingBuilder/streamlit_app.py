import streamlit as st
import json
import uuid
import requests
import re
from pathlib import Path
from PIL import Image
from reports import write_roster_pdf

# --- Setup & Configuration ---
BASE_DIR = Path(__file__).parent
CODEX_DIR = BASE_DIR / "codexes"
CODEX_DIR.mkdir(exist_ok=True)

icon_path = BASE_DIR / "app_icon.ico"
if icon_path.exists():
    app_icon = Image.open(icon_path)
else:
    app_icon = "🌙"

st.set_page_config(page_title="Rising Builder", page_icon=app_icon, layout="wide")

if "roster" not in st.session_state:
    st.session_state.roster = []
if "roster_name" not in st.session_state:
    st.session_state.roster_name = "My Army List"

# --- Helper Functions ---
def load_codex(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading codex: {e}")
        return None

def get_unit_by_id(unit_id):
    if not st.session_state.get("codex_data"): return None
    for u in st.session_state.codex_data.get("units", []):
        if u["id"] == unit_id:
            return u
    return None

def get_tooltip(item_name, codex_data):
    if not codex_data or not item_name: return None
    query = item_name.lower()
    matches = []
    
    # 1. Search Weapons
    weps = codex_data.get("weapons", {})
    for name, stats in weps.items():
        n = name.lower()
        if n in query:
            matches.append(f"⚔️ [{name}] Rng: {stats.get('range', '-')}, S: {stats.get('S', '-')}, AP: {stats.get('AP', '-')}, Type: {stats.get('type', '-')}. {stats.get('notes', '')}")

    # 2. Search Wargear
    gear = codex_data.get("wargear", {})
    for name, data in gear.items():
        n = name.lower()
        if n in query:
            matches.append(f"⚙️ [{name}] {data.get('summary', '')}")
            
    # 3. Search Rules
    rules = codex_data.get("rules", {})
    for name, data in rules.items():
        n = name.lower()
        if n in query:
            matches.append(f"📜 [{name}] {data.get('summary', '')}")
    
    if not matches: return None
    return "\n\n".join(matches)

def fetch_github_issues():
    try:
        token = st.secrets["github"]["token"]
        owner = st.secrets["github"]["owner"]
        repo = st.secrets["github"]["repo"]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = { "state": "all", "sort": "updated", "direction": "desc", "per_page": 20 }
        headers = { "Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json" }
        response = requests.get(api_url, headers=headers, params=params)
        if response.status_code == 200: return response.json()
        return []
    except Exception: return []

# --- CORE LOGIC ---
def calculate_roster():
    total_pts = 0
    counts = {"HQ": 0, "Troops": 0, "Elites": 0, "Fast Attack": 0, "Heavy Support": 0}
    
    for entry in st.session_state.roster:
        u = get_unit_by_id(entry["unit_id"])
        if not u: continue
        
        cost = u.get("base_points", 0) + u.get("points_per_model", 0) * entry.get("size", 1)
        selection_tracker = {}
        
        for gid, picks in entry.get("selected", {}).items():
            opt_def = next((o for o in u.get("options", []) if o.get("group_id") == gid), None)
            if not opt_def: continue
            
            for choice in opt_def.get("choices", []):
                c_qty = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                if c_qty > 0:
                    pts = choice.get("points", 0)
                    if choice.get("points_mode") == "per_model":
                        cost += pts * entry.get("size", 1)
                    else:
                        cost += pts * c_qty
                        cid = choice["id"]
                        if cid not in selection_tracker:
                            selection_tracker[cid] = {"count": 0, "points": pts}
                        selection_tracker[cid]["count"] += c_qty

        if u.get("enable_twin_link_discount"):
            for cid, data in selection_tracker.items():
                pairs = data["count"] // 2
                if pairs > 0:
                    discount = pairs * (data["points"] * 0.5)
                    cost -= discount

        entry["calculated_cost"] = cost
        total_pts += cost
        
        if not entry.get("parent_id") and u.get("slot") in counts:
            counts[u["slot"]] += 1
            
    return total_pts, counts

def validate_roster(limit, curr_pts, slots):
    issues = []
    if curr_pts > limit: issues.append(f"❌ **Points:** {curr_pts}/{limit} (Over by {curr_pts - limit})")
    limits = {"HQ": 2, "Troops": 6, "Elites": 3, "Fast Attack": 3, "Heavy Support": 3}
    for s, max_limit in limits.items():
        if slots[s] > max_limit: issues.append(f"❌ **{s}:** {slots[s]}/{max_limit}")
    if slots["HQ"] < 1: issues.append("⚠️ **HQ:** Need at least 1.")
    if slots["Troops"] < 2: issues.append("⚠️ **Troops:** Need at least 2.")
    
    unique_counter = {}
    for entry in st.session_state.roster:
        u = get_unit_by_id(entry["unit_id"])
        if not u: continue
        min_s = u.get("min_size", 1)
        max_s = u.get("max_size", 1)
        if entry["size"] < min_s: issues.append(f"⚠️ **{u['name']}:** Size {entry['size']} too small (Min {min_s}).")
        if entry["size"] > max_s: issues.append(f"⚠️ **{u['name']}:** Size {entry['size']} too large (Max {max_s}).")
        if u.get("unique", False):
            if u["name"] in unique_counter: issues.append(f"❌ **Unique:** You cannot take '{u['name']}' more than once.")
            unique_counter[u["name"]] = True
    return issues

def generate_text_summary(roster, codex_name, limit):
    curr_pts, _ = calculate_roster()
    txt = [f"{codex_name} - {st.session_state.roster_name}", f"Total: {curr_pts}/{limit} pts", "-"*30]
    
    def print_entry(entry, depth=0):
        u = get_unit_by_id(entry["unit_id"])
        indent = "  " * depth
        prefix = "• " if depth == 0 else "> "
        name_str = f"{u['name']}"
        if entry.get("custom_name"): name_str = f"{entry['custom_name']} ({u['name']})"
        if entry.get("size", 1) > 1: name_str += f" x{entry['size']}"
        
        lines = [f"{indent}{prefix}{name_str} [{entry.get('calculated_cost', 0)} pts]"]
        
        opts = []
        if "selected" in entry:
            for gid, picks in entry["selected"].items():
                opt_def = next((o for o in u.get("options", []) if o.get("group_id") == gid), None)
                if not opt_def: continue
                for choice in opt_def.get("choices", []):
                    count = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                    if count > 0:
                        s = choice['name']
                        if count > 1: s = f"{count}x {s}"
                        opts.append(s)
        if opts: lines.append(f"{indent}  + {', '.join(opts)}")
        return lines

    slots_order = ["HQ", "Troops", "Elites", "Fast Attack", "Heavy Support", "Dedicated Transport"]
    for slot in slots_order:
        slot_units = [e for e in roster if not e.get("parent_id") and get_unit_by_id(e['unit_id'])['slot'] == slot]
        if not slot_units: continue
        txt.append(f"\n[{slot}]")
        
        def recursive_text(units, depth):
            for entry in units:
                txt.extend(print_entry(entry, depth))
                children = [c for c in roster if c.get("parent_id") == entry["id"]]
                recursive_text(children, depth + 1)
        
        recursive_text(slot_units, 0)

    return "\n".join(txt)

# --- CALLBACKS ---
def cb_update_roster_name(): st.session_state.roster_name = st.session_state.roster_name_input
def cb_update_custom_name(entry, key): entry["custom_name"] = st.session_state[key]
def cb_update_size(entry, key): entry["size"] = st.session_state[key]
def cb_update_counter(entry, gid, cid, key):
    qty = st.session_state[key]
    current_picks = entry.get("selected", {}).get(gid, [])
    current_picks = [x for x in current_picks if x != cid]
    current_picks.extend([cid] * qty)
    if "selected" not in entry: entry["selected"] = {}
    entry["selected"][gid] = current_picks
def cb_update_radio(entry, gid, name_to_id_map, key):
    selected_name = st.session_state[key]
    if "selected" not in entry: entry["selected"] = {}
    if selected_name == "(None)": entry["selected"][gid] = []
    else:
        cid = name_to_id_map.get(selected_name)
        if cid: entry["selected"][gid] = [cid]
def cb_update_checkbox(entry, gid, cid, key):
    is_checked = st.session_state[key]
    if "selected" not in entry: entry["selected"] = {}
    current_picks = entry["selected"].get(gid, [])
    if is_checked:
        if cid not in current_picks: current_picks.append(cid)
    else:
        if cid in current_picks: current_picks.remove(cid)
    entry["selected"][gid] = current_picks

def render_unit_options(entry, unit, codex_data):
    k_name = f"name_{entry['id']}"
    st.text_input("Custom Name (Optional)", value=entry.get("custom_name", ""), 
                  placeholder=f"e.g. {unit['name']} Squad Alpha", key=k_name,
                  on_change=cb_update_custom_name, args=(entry, k_name))

    col_pts, col_tip = st.columns([1, 1])
    col_pts.markdown(f"**Unit Cost:** :green[{entry.get('calculated_cost', 0)} pts]")
    col_tip.caption("ℹ️ Hover over the **?** icons for rules.")
    
    min_s = int(unit.get("min_size", 1))
    max_s = int(unit.get("max_size", 1))
    if min_s != max_s:
        k = f"size_{entry['id']}"
        st.number_input(f"Squad Size ({min_s}-{max_s})", min_value=min_s, max_value=max_s, 
                        value=int(entry.get("size", min_s)), key=k,
                        on_change=cb_update_size, args=(entry, k))

    if "selected" not in entry: entry["selected"] = {}
    
    for opt in unit.get("options", []):
        gid = opt["group_id"]
        st.caption(f"**{opt.get('group_name', 'Options')}**")
        current_picks = entry["selected"].get(gid, [])
        choices = opt.get("choices", [])
        max_sel = opt.get("max_select", 1)
        if opt.get("linked_to_size"): max_sel = entry["size"]
        
        if (opt.get("linked_to_size") and len(choices) > 1) or (len(choices)==1 and max_sel > 1):
            for c in choices:
                cid = c["id"]
                qty = current_picks.count(cid)
                k = f"opt_{entry['id']}_{gid}_{cid}"
                tooltip = get_tooltip(c["name"], codex_data)
                st.number_input(f"{c['name']} (+{c['points']} pts)", min_value=0, max_value=max_sel, value=qty, 
                                key=k, help=tooltip, on_change=cb_update_counter, args=(entry, gid, cid, k))
        elif max_sel == 1:
            name_map = {}
            opts_display = ["(None)"]
            for c in choices:
                d_name = f"{c['name']} (+{c['points']})"
                name_map[d_name] = c['id']
                opts_display.append(d_name)
            current_idx = 0
            current_selected_name = "(None)"
            if current_picks:
                curr_id = current_picks[0]
                for d_name, d_id in name_map.items():
                    if d_id == curr_id and d_name in opts_display:
                        current_idx = opts_display.index(d_name)
                        current_selected_name = d_name
                        break
            
            dropdown_tooltip = "Select an option to see rules."
            if current_selected_name != "(None)":
                clean_name = re.sub(r' \(\+\d+.*\)', '', current_selected_name)
                desc = get_tooltip(clean_name, codex_data)
                if desc: dropdown_tooltip = desc

            k = f"opt_{entry['id']}_{gid}"
            selected = st.selectbox("", opts_display, index=current_idx, key=k, help=dropdown_tooltip,
                         on_change=cb_update_radio, args=(entry, gid, name_map, k))
            if selected != "(None)":
                clean_name = re.sub(r' \(\+\d+.*\)', '', selected)
                desc = get_tooltip(clean_name, codex_data)
                if desc: st.caption(f"↳ {desc}")
        else:
            for c in choices:
                cid = c["id"]
                is_checked = cid in current_picks
                k = f"opt_{entry['id']}_{gid}_{cid}"
                tooltip = get_tooltip(c["name"], codex_data)
                st.checkbox(f"{c['name']} (+{c['points']})", value=is_checked, key=k, help=tooltip,
                            on_change=cb_update_checkbox, args=(entry, gid, cid, k))

# --- SIDEBAR ---
with st.sidebar:
    col1, col2 = st.columns([1, 4])
    with col1:
        if icon_path.exists(): st.image(app_icon, width=60)
        else: st.write("🌙")
    with col2: st.title("Rising Builder")
    st.divider()
    
    st.header("Settings")
    available_codexes = list(CODEX_DIR.glob("*.json"))
    codex_names = [p.name for p in available_codexes]
    index = 0
    if "current_codex_name" in st.session_state and st.session_state.current_codex_name in codex_names:
        index = codex_names.index(st.session_state.current_codex_name)
    selected_codex_name = st.selectbox("Select Codex", codex_names, index=index)
    
    if selected_codex_name:
        path = CODEX_DIR / selected_codex_name
        if st.session_state.get("current_codex_path") != str(path):
            st.session_state.codex_data = load_codex(path)
            st.session_state.current_codex_path = str(path)
            st.session_state.current_codex_name = selected_codex_name
            if not st.session_state.get("is_loading_file", False):
                st.session_state.roster = [] 
                st.session_state.roster_name = "My Army List"
            st.session_state.is_loading_file = False
            st.rerun()

    st.text_input("Roster Name", value=st.session_state.roster_name, key="roster_name_input", on_change=cb_update_roster_name)
    points_limit = st.number_input("Points Limit", value=1500, step=250, key="points_limit_input")
    
    st.divider()
    st.subheader("Save / Load")
    safe_filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', st.session_state.roster_name)
    if not safe_filename: safe_filename = "army_list"
    save_data = {"roster_name": st.session_state.roster_name, "roster": st.session_state.roster, "codex_file": selected_codex_name, "points_limit": points_limit}
    st.download_button("💾 Download Roster", json.dumps(save_data, indent=2), f"{safe_filename}.json", "application/json")

    uploaded_file = st.file_uploader("📂 Load Roster", type=["json"])
    if uploaded_file is not None:
        if uploaded_file.file_id != st.session_state.get("last_loaded_file_id"):
            try:
                uploaded_file.seek(0)
                data = json.load(uploaded_file)
                saved_codex = data.get("codex_file")
                st.session_state.is_loading_file = True
                st.session_state.last_loaded_file_id = uploaded_file.file_id
                target_path = CODEX_DIR / saved_codex if saved_codex else None
                if target_path and target_path.exists():
                    st.session_state.current_codex_name = saved_codex
                    st.session_state.current_codex_path = str(target_path)
                    st.session_state.codex_data = load_codex(target_path)
                    st.success(f"Loaded '{saved_codex}'.")
                else: st.warning(f"⚠️ Original Codex '{saved_codex}' missing. Using current Codex.")
                st.session_state.roster = data.get("roster", [])
                st.session_state.roster_name = data.get("roster_name", "My Army List")
                st.rerun()
            except Exception as e: st.error(f"Error reading file: {e}")

    if st.button("⚠️ Reset App", type="primary"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    st.divider()
    st.write("### Export")
    include_tables = st.checkbox("Include Ref Tables", value=True)
    if st.button("📄 Generate PDF"):
        pdf_path = BASE_DIR / "temp_roster.pdf"
        write_roster_pdf(st.session_state.roster, st.session_state.codex_data, points_limit, str(pdf_path), get_unit_by_id, include_ref_tables=include_tables, roster_name=st.session_state.roster_name)
        with open(pdf_path, "rb") as f: st.download_button("Download PDF", f, f"{safe_filename}.pdf", "application/pdf")

    # --- TEXT EXPORT ---
    with st.expander("📋 Text Export (Copy/Paste)"):
        st.caption("Perfect for Reddit/Discord")
        if "codex_data" in st.session_state:
            txt_out = generate_text_summary(st.session_state.roster, st.session_state.codex_data.get("codex_name", "Army"), points_limit)
            st.code(txt_out, language="text")

    # --- CODEX AUDITOR ---
    st.divider()
    with st.expander("🛡️ Codex Auditor"):
        if st.button("Run Audit"):
            if "codex_data" in st.session_state:
                data = st.session_state.codex_data
                issues = []
                all_defs = set(data.get("weapons", {}).keys()) | set(data.get("wargear", {}).keys()) | set(data.get("rules", {}).keys())
                for unit in data.get("units", []):
                    u_name = unit.get("name", "Unknown")
                    for item in unit.get("wargear", []):
                        if item not in all_defs: issues.append(f"⚠️ Unit **{u_name}** has base wargear **'{item}'** which is undefined.")
                    for rule in unit.get("special_rules", []):
                        if rule not in all_defs: issues.append(f"⚠️ Unit **{u_name}** has rule **'{rule}'** which is undefined.")
                    for opt in unit.get("options", []):
                        for ch in opt.get("choices", []):
                            c_name = ch.get("name", "")
                            parts = re.split(r' & | and |, | / ', c_name)
                            for p in parts:
                                p = p.strip()
                                if p and "Upgrade" not in p and "Twin-linked" not in p and p not in all_defs:
                                     issues.append(f"⚠️ Option **'{c_name}'**: Part **'{p}'** is undefined.")
                if not issues: st.success("✅ Codex looks healthy!")
                else:
                    st.error(f"Found {len(issues)} potential issues:")
                    for i in issues: st.write(i)

    st.divider()
    st.subheader("Project Tracker")
    with st.expander("Previous Report Status"):
        issues = fetch_github_issues()
        if issues:
            for i in issues: st.markdown(f"{'✅' if i['state']=='closed' else '🔴'} [{i['title']}]({i['html_url']})")
        else: st.caption("No recent data.")

    with st.form("feedback_form"):
        feedback_type = st.selectbox("Type", ["Bug", "Missing Unit", "Feature Request"])
        feedback_title = st.text_input("Summary")
        feedback_msg = st.text_area("Description")
        if st.form_submit_button("Report"):
            if not feedback_title: st.error("Summary required.")
            else:
                try:
                    token, owner, repo = st.secrets["github"]["token"], st.secrets["github"]["owner"], st.secrets["github"]["repo"]
                    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
                    requests.post(api_url, json={"title": f"[{feedback_type}] {feedback_title}", "body": feedback_msg}, headers={"Authorization": f"token {token}"})
                    st.success("Sent!")
                except Exception as e: st.error(f"Error: {e}")

# --- MAIN PAGE ---
def recursive_render_unit(entry, depth=0):
    u = get_unit_by_id(entry["unit_id"])
    if not u: return
    
    # Indentation visual for children
    if depth > 0:
        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;" * depth + f"↳ **{u['name']}**")
    
    display_title = f"[{u['slot']}] {u['name']}"
    if entry.get("custom_name"): display_title = f"[{u['slot']}] {entry['custom_name']} ({u['name']})"
    if depth > 0: display_title = f"Edit {u['name']}"

    with st.expander(display_title, expanded=False):
        render_unit_options(entry, u, data)
        
        # ATTACHMENT LOGIC (Recursive!)
        valid_transports = u.get("dedicated_transports", [])
        if valid_transports:
            st.divider()
            cols = st.columns([3, 1])
            t_opts = [t for t in [get_unit_by_id(tid) for tid in valid_transports] if t]
            t_names = [t["name"] for t in t_opts]
            sel_t = cols[0].selectbox(f"Add Attachment to {u['name']}", t_names, key=f"trans_sel_{entry['id']}")
            if cols[1].button("Add", key=f"add_trans_{entry['id']}"):
                tid = next(t["id"] for t in t_opts if t["name"] == sel_t)
                child_entry = {"id": str(uuid.uuid4()), "unit_id": tid, "size": int(get_unit_by_id(tid).get("default_size", 1)), "selected": {}, "parent_id": entry["id"]}
                st.session_state.roster.append(child_entry)
                st.rerun()
        st.divider()
        
        # Remove Logic
        if st.button(f"Remove {u['name']}", key=f"del_{entry['id']}", type="primary" if depth==0 else "secondary"):
            # Recursive delete
            ids_to_remove = [entry["id"]]
            def find_kids(eid):
                kids = [c for c in st.session_state.roster if c.get("parent_id") == eid]
                for k in kids:
                    ids_to_remove.append(k["id"])
                    find_kids(k["id"])
            find_kids(entry["id"])
            st.session_state.roster = [e for e in st.session_state.roster if e["id"] not in ids_to_remove]
            st.rerun()

    # Render Children of this unit
    children = [e for e in st.session_state.roster if e.get("parent_id") == entry["id"]]
    for child in children:
        recursive_render_unit(child, depth + 1)

if "codex_data" in st.session_state and st.session_state.codex_data:
    data = st.session_state.codex_data
    st.title(f"{st.session_state.roster_name}")
    st.caption(f"Using: {data.get('codex_name', 'Army')}")
    
    # --- VALIDATOR & METRICS ---
    curr_pts, slots = calculate_roster()
    issues = validate_roster(points_limit, curr_pts, slots)
    
    if issues: st.error("  \n".join(issues))
    else: st.success("✅ Roster is Valid!")

    # 1. SLOT COUNTERS
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Points", f"{curr_pts} / {points_limit}", delta=points_limit-curr_pts)
    col2.metric("HQ", f"{slots['HQ']}/2")
    col3.metric("Troops", f"{slots['Troops']}/6")
    col4.metric("Elites", f"{slots['Elites']}/3")
    col5.metric("Fast", f"{slots['Fast Attack']}/3")
    col6.metric("Heavy", f"{slots['Heavy Support']}/3")

    # 2. POINTS BREAKDOWN
    if curr_pts > 0:
        breakdown = {}
        for entry in st.session_state.roster:
            u = get_unit_by_id(entry["unit_id"])
            if not u: continue
            slot = u["slot"]
            if entry.get("parent_id"):
                parent = next((p for p in st.session_state.roster if p["id"] == entry["parent_id"]), None)
                if parent:
                    pu = get_unit_by_id(parent["unit_id"])
                    if pu: slot = pu["slot"]
            breakdown[slot] = breakdown.get(slot, 0) + entry.get("calculated_cost", 0)
        
        st.caption("Investment Breakdown")
        cols = st.columns(len(breakdown))
        for i, (slot, pts) in enumerate(breakdown.items()):
            pct = int((pts / curr_pts) * 100)
            cols[i].write(f"**{slot}**: {pct}%")
            cols[i].progress(pct / 100)
    
    st.divider()

    st.header(f"Current Roster ({len(st.session_state.roster)} Units)")
    parents = [e for e in st.session_state.roster if not e.get("parent_id")]
    
    if not parents: st.info("Your roster is empty. Add a unit below!")
    else:
        for entry in parents:
            recursive_render_unit(entry, depth=0)

    st.divider()
    st.subheader("Add New Unit")
    slots_map = ["HQ", "Troops", "Elites", "Fast Attack", "Heavy Support"]
    selected_slot = st.radio("Force Organisation Slot", slots_map, horizontal=True, label_visibility="collapsed", key="add_unit_slot_selection")
    
    slot_units = [u for u in data.get("units", []) if u.get("slot") == selected_slot]
    slot_units.sort(key=lambda x: x["name"])
    
    if not slot_units: st.caption(f"No units found for {selected_slot}")
    else:
        unit_options = [u["name"] for u in slot_units]
        selected_unit_name = st.selectbox(f"Select {selected_slot} Unit", unit_options, key=f"sel_unit_{selected_slot}")
        if st.button(f"Add {selected_unit_name}", key=f"btn_add_{selected_slot}"):
            uid = next(u["id"] for u in slot_units if u["name"] == selected_unit_name)
            unit_def = get_unit_by_id(uid)
            new_entry = {"id": str(uuid.uuid4()), "unit_id": uid, "size": int(unit_def.get("default_size", 1)), "selected": {}, "parent_id": None}
            st.session_state.roster.append(new_entry)
            st.rerun()
else: st.info("⬅️ Please select a Codex from the sidebar to begin.")

