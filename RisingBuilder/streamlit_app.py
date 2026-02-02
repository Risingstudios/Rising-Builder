import streamlit as st
import json
import uuid
from pathlib import Path
from PIL import Image
from reports import write_roster_pdf

# --- Setup & Configuration ---
BASE_DIR = Path(__file__).parent
CODEX_DIR = BASE_DIR / "codexes"
CODEX_DIR.mkdir(exist_ok=True)

# Load Icon
icon_path = BASE_DIR / "app_icon.ico"
if icon_path.exists():
    app_icon = Image.open(icon_path)
else:
    app_icon = "🌙"

st.set_page_config(page_title="Rising Builder", page_icon=app_icon, layout="wide")

if "roster" not in st.session_state:
    st.session_state.roster = []

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

def calculate_roster():
    total_pts = 0
    counts = {"HQ": 0, "Troops": 0, "Elites": 0, "Fast Attack": 0, "Heavy Support": 0}
    
    for entry in st.session_state.roster:
        u = get_unit_by_id(entry["unit_id"])
        if not u: continue
        
        # 1. Base Points
        cost = u.get("base_points", 0) + u.get("points_per_model", 0) * entry.get("size", 1)
        
        # 2. Options Calculation
        # We track selections to check for Twin-Linking later
        # Structure: { "weapon_id": { "count": 0, "points": 12 } }
        selection_tracker = {}
        
        for gid, picks in entry.get("selected", {}).items():
            opt_def = next((o for o in u.get("options", []) if o.get("group_id") == gid), None)
            if not opt_def: continue
            
            for choice in opt_def.get("choices", []):
                # Count how many of this specific item were picked
                c_qty = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                
                if c_qty > 0:
                    pts = choice.get("points", 0)
                    
                    # Per-model points (like Grenades) are simple multiplication
                    if choice.get("points_mode") == "per_model":
                        cost += pts * entry.get("size", 1)
                    else:
                        # Flat points (like Weapons) might get discounted
                        cost += pts * c_qty
                        
                        # Track for Twin-Link check
                        cid = choice["id"]
                        if cid not in selection_tracker:
                            selection_tracker[cid] = {"count": 0, "points": pts}
                        selection_tracker[cid]["count"] += c_qty

        # 3. Apply Twin-Link Discount
        # If the JSON says this unit can twin-link, we look for pairs.
        if u.get("enable_twin_link_discount"):
            for cid, data in selection_tracker.items():
                # For every pair (2), we assume it's a Twin-Linked weapon.
                # The cost of TL is usually 1.5x Base. We charged 2x Base.
                # So we refund 0.5x Base for every pair.
                pairs = data["count"] // 2
                if pairs > 0:
                    discount = pairs * (data["points"] * 0.5)
                    cost -= discount

        entry["calculated_cost"] = cost
        total_pts += cost
        
        # Slots (only if not a child unit)
        if not entry.get("parent_id") and u.get("slot") in counts:
            counts[u["slot"]] += 1
            
    return total_pts, counts

def render_unit_options(entry, unit):
    """
    Renders the Size spinner and Option widgets (Counters, Radios, Checkboxes)
    for a specific roster entry. Used by both Parents and Children.
    """
    # 1. Squad Size
    min_s = int(unit.get("min_size", 1))
    max_s = int(unit.get("max_size", 1))
    if min_s != max_s:
        entry["size"] = st.number_input(f"Squad Size ({min_s}-{max_s})", 
                                        min_value=min_s, max_value=max_s, 
                                        value=int(entry.get("size", min_s)), 
                                        key=f"size_{entry['id']}")

    # 2. Options Logic
    if "selected" not in entry: entry["selected"] = {}
    
    for opt in unit.get("options", []):
        gid = opt["group_id"]
        st.caption(f"**{opt.get('group_name', 'Options')}**")
        
        current_picks = entry["selected"].get(gid, [])
        choices = opt.get("choices", [])
        max_sel = opt.get("max_select", 1)
        if opt.get("linked_to_size"): max_sel = entry["size"]
        
        # A) Counter Logic (Multiple items, or single item with max > 1)
        if (opt.get("linked_to_size") and len(choices) > 1) or (len(choices)==1 and max_sel > 1):
            for c in choices:
                cid = c["id"]
                qty = current_picks.count(cid)
                new_qty = st.number_input(f"{c['name']} (+{c['points']} pts)", 
                                          min_value=0, max_value=max_sel, value=qty, 
                                          key=f"opt_{entry['id']}_{gid}_{cid}")
                
                # Update pick list: remove all old instances, add new count
                current_picks = [x for x in current_picks if x != cid]
                current_picks.extend([cid] * new_qty)
                entry["selected"][gid] = current_picks

        # B) Radio Logic (Single Choice, Max 1)
        elif max_sel == 1:
            opts = ["(None)"] + [f"{c['name']} (+{c['points']})" for c in choices]
            current_idx = 0
            if current_picks:
                curr_id = current_picks[0]
                for i, c in enumerate(choices):
                    if c["id"] == curr_id: current_idx = i + 1; break
                    
            sel = st.selectbox("", opts, index=current_idx, key=f"opt_{entry['id']}_{gid}", label_visibility="collapsed")
            
            if sel == "(None)": entry["selected"][gid] = []
            else:
                idx = opts.index(sel) - 1
                entry["selected"][gid] = [choices[idx]["id"]]

        # C) Checkbox Logic (Multiple unique choices)
        else:
            for c in choices:
                cid = c["id"]
                is_checked = cid in current_picks
                if st.checkbox(f"{c['name']} (+{c['points']})", value=is_checked, key=f"opt_{entry['id']}_{gid}_{cid}"):
                    if cid not in current_picks: 
                        if len(current_picks) < max_sel: entry["selected"].setdefault(gid, []).append(cid)
                else:
                    if cid in current_picks: entry["selected"][gid].remove(cid)


# --- Sidebar ---
with st.sidebar:
    col1, col2 = st.columns([1, 4])
    with col1:
        if icon_path.exists(): st.image(app_icon, width=60)
        else: st.write("🌙")
    with col2:
        st.title("Rising Builder")
        
    st.divider()
    st.header("Settings")
    
    # 1. Codex Loader
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
            st.session_state.roster = [] 
            st.rerun()

    points_limit = st.number_input("Points Limit", value=1500, step=250, key="points_limit_input")
    
    st.divider()

    # 2. Save / Load
    st.subheader("Save / Load List")
    save_data = {
        "roster": st.session_state.roster,
        "codex_file": selected_codex_name,
        "points_limit": points_limit
    }
    roster_json = json.dumps(save_data, indent=2)
    st.download_button("💾 Download Roster File", roster_json, "my_army_list.json", "application/json")

    uploaded_file = st.file_uploader("📂 Load Roster File", type=["json"])
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            saved_codex = data.get("codex_file")
            if saved_codex and saved_codex != selected_codex_name:
                st.error(f"⚠️ Codex Mismatch! File is for '{saved_codex}', but you have '{selected_codex_name}'.")
            else:
                st.session_state.roster = data.get("roster", [])
                st.success("List loaded successfully!")
                st.rerun()
        except Exception as e: st.error(f"Error reading file: {e}")

    st.divider()
    
    # 3. PDF Export
    if st.button("📄 Generate PDF Roster"):
        pdf_path = BASE_DIR / "temp_roster.pdf"
        write_roster_pdf(st.session_state.roster, st.session_state.codex_data, points_limit, str(pdf_path), get_unit_by_id)
        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF", f, "roster.pdf", "application/pdf")

    # 4. Feedback
    st.divider()
    st.subheader("Report an Issue")
    with st.form("feedback_form"):
        feedback_type = st.selectbox("Type", ["Bug", "Missing Unit", "Wrong Stat", "Missing Upgrade", "Weapon/Wargear Selection", "Feature Request"])
        feedback_msg = st.text_area("Description", placeholder="E.g. The Fire Warrior Shas'ui has WS 2 but should be WS 3...")
        include_context = st.checkbox("Include roster data", value=True)
        submitted = st.form_submit_button("Submit Feedback")
        
        if submitted and feedback_msg:
            report_pts, _ = calculate_roster()
            try:
                token = st.secrets["github"]["token"]
                owner = st.secrets["github"]["owner"]
                repo = st.secrets["github"]["repo"]
                
                body_text = f"**Type:** {feedback_type}\n\n**User Report:**\n{feedback_msg}"
                if include_context:
                    context_str = "\n\n**Context:**\n"
                    if "codex_data" in st.session_state:
                        context_str += f"- Codex: {st.session_state.codex_data.get('codex_name')}\n"
                    context_str += f"- Points: {report_pts}/{points_limit}\n"
                    context_str += f"- Unit Count: {len(st.session_state.roster)}"
                    body_text += context_str

                import requests 
                api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                payload = {"title": f"[{feedback_type}] Feedback from App", "body": body_text}
                response = requests.post(api_url, json=payload, headers=headers)
                
                if response.status_code == 201: st.success("Feedback sent!")
                else: st.error(f"Error {response.status_code}: {response.text}")
            except Exception as e:
                st.error(f"Error sending feedback: {e}")

# --- Main Page ---
if "codex_data" in st.session_state and st.session_state.codex_data:
    data = st.session_state.codex_data
    st.title(f"{data.get('codex_name', 'Army')} Builder")
    
    # Summary
    curr_pts, slots = calculate_roster()
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Points", f"{curr_pts} / {points_limit}", delta=points_limit-curr_pts)
    col2.metric("HQ", f"{slots['HQ']}/2")
    col3.metric("Troops", f"{slots['Troops']}/6")
    col4.metric("Elites", f"{slots['Elites']}/3")
    col5.metric("Fast", f"{slots['Fast Attack']}/3")
    col6.metric("Heavy", f"{slots['Heavy Support']}/3")
    st.divider()

    # --- Roster Display ---
    st.header(f"Current Roster ({len(st.session_state.roster)} Units)")
    parents = [e for e in st.session_state.roster if not e.get("parent_id")]
    
    if not parents: st.info("Your roster is empty. Add a unit below!")
    else:
        for entry in parents:
            u = get_unit_by_id(entry["unit_id"])
            if not u: continue

            with st.expander(f"[{u['slot']}] {u['name']} ({entry.get('calculated_cost', 0)} pts)", expanded=False):
                # RENDER PARENT OPTIONS
                render_unit_options(entry, u)

                # Add Attachment Logic
                valid_transports = u.get("dedicated_transports", [])
                if valid_transports:
                    st.divider()
                    cols = st.columns([3, 1])
                    t_opts = [t for t in [get_unit_by_id(tid) for tid in valid_transports] if t]
                    t_names = [t["name"] for t in t_opts]
                    
                    sel_t = cols[0].selectbox("Add Attachment", t_names, key=f"trans_sel_{entry['id']}")
                    if cols[1].button("Add", key=f"add_trans_{entry['id']}"):
                        tid = next(t["id"] for t in t_opts if t["name"] == sel_t)
                        child_entry = {
                            "id": str(uuid.uuid4()),
                            "unit_id": tid,
                            "size": int(get_unit_by_id(tid).get("default_size", 1)),
                            "selected": {},
                            "parent_id": entry["id"]
                        }
                        st.session_state.roster.append(child_entry)
                        st.rerun()

                st.divider()
                if st.button("Remove Unit", key=f"del_{entry['id']}", type="primary"):
                    ids_to_remove = [entry["id"]] + [c["id"] for c in st.session_state.roster if c.get("parent_id") == entry["id"]]
                    st.session_state.roster = [e for e in st.session_state.roster if e["id"] not in ids_to_remove]
                    st.rerun()

            # --- Roster Children (Attachments) ---
            children = [e for e in st.session_state.roster if e.get("parent_id") == entry["id"]]
            for child in children:
                uc = get_unit_by_id(child["unit_id"])
                if not uc: continue
                with st.container():
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{uc['name']}** ({child.get('calculated_cost',0)} pts)")
                    with st.expander(f"Edit {uc['name']}", expanded=False):
                        
                        # RENDER CHILD OPTIONS (FIXED!)
                        render_unit_options(child, uc)
                        
                        st.divider()
                        if st.button("Remove Attachment", key=f"del_child_{child['id']}"):
                            st.session_state.roster.remove(child)
                            st.rerun()

    st.divider()

    # --- Add New Unit Section ---
    st.subheader("Add New Unit")
    slots_map = ["HQ", "Troops", "Elites", "Fast Attack", "Heavy Support"]
    tabs = st.tabs(slots_map)

    for i, slot_name in enumerate(slots_map):
        with tabs[i]:
            slot_units = [u for u in data.get("units", []) if u.get("slot") == slot_name]
            if not slot_units: st.caption(f"No units found for {slot_name}")
            else:
                unit_options = [u["name"] for u in slot_units]
                selected_unit = st.selectbox(f"Select {slot_name}", unit_options, key=f"sel_{slot_name}")
                if st.button(f"Add {selected_unit}", key=f"btn_add_{slot_name}"):
                    uid = next(u["id"] for u in slot_units if u["name"] == selected_unit)
                    unit_def = get_unit_by_id(uid)
                    new_entry = {
                        "id": str(uuid.uuid4()),
                        "unit_id": uid,
                        "size": int(unit_def.get("default_size", 1)),
                        "selected": {},
                        "parent_id": None
                    }
                    st.session_state.roster.append(new_entry)
                    st.rerun()

else:
    st.info("⬅️ Please select a Codex from the sidebar to begin.")

