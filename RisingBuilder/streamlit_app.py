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

# Load Icon
icon_path = BASE_DIR / "app_icon.ico"
if icon_path.exists():
    app_icon = Image.open(icon_path)
else:
    app_icon = "🌙"

st.set_page_config(page_title="Rising Builder", page_icon=app_icon, layout="wide")

# Initialize Session State
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

def fetch_github_issues():
    """Fetches the latest open and closed issues from GitHub."""
    try:
        token = st.secrets["github"]["token"]
        owner = st.secrets["github"]["owner"]
        repo = st.secrets["github"]["repo"]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = { "state": "all", "sort": "updated", "direction": "desc", "per_page": 20 }
        headers = { "Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json" }
        
        response = requests.get(api_url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []

# --- CALLBACKS ---
def cb_update_roster_name():
    """Updates the roster name from session state."""
    st.session_state.roster_name = st.session_state.roster_name_input

def cb_update_custom_name(entry, key):
    """Updates custom unit name."""
    entry["custom_name"] = st.session_state[key]

def cb_update_size(entry, key):
    entry["size"] = st.session_state[key]

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
    
    if selected_name == "(None)":
        entry["selected"][gid] = []
    else:
        cid = name_to_id_map.get(selected_name)
        if cid:
            entry["selected"][gid] = [cid]

def cb_update_checkbox(entry, gid, cid, key):
    is_checked = st.session_state[key]
    if "selected" not in entry: entry["selected"] = {}
    current_picks = entry["selected"].get(gid, [])
    
    if is_checked:
        if cid not in current_picks:
            current_picks.append(cid)
    else:
        if cid in current_picks:
            current_picks.remove(cid)
    
    entry["selected"][gid] = current_picks

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

def render_unit_options(entry, unit):
    # --- Custom Name Input ---
    k_name = f"name_{entry['id']}"
    st.text_input("Custom Name (Optional)", 
                  value=entry.get("custom_name", ""), 
                  placeholder=f"e.g. {unit['name']} Squad Alpha",
                  key=k_name,
                  on_change=cb_update_custom_name, args=(entry, k_name))

    # Points display
    st.markdown(f"**Unit Cost:** :green[{entry.get('calculated_cost', 0)} pts]")
    
    # Size
    min_s = int(unit.get("min_size", 1))
    max_s = int(unit.get("max_size", 1))
    if min_s != max_s:
        k = f"size_{entry['id']}"
        st.number_input(f"Squad Size ({min_s}-{max_s})", 
                        min_value=min_s, max_value=max_s, 
                        value=int(entry.get("size", min_s)), 
                        key=k,
                        on_change=cb_update_size, args=(entry, k))

    if "selected" not in entry: entry["selected"] = {}
    
    # Options
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
                st.number_input(f"{c['name']} (+{c['points']} pts)", 
                                min_value=0, max_value=max_sel, value=qty, 
                                key=k,
                                on_change=cb_update_counter, args=(entry, gid, cid, k))
        elif max_sel == 1:
            name_map = {}
            opts_display = ["(None)"]
            for c in choices:
                d_name = f"{c['name']} (+{c['points']})"
                name_map[d_name] = c['id']
                opts_display.append(d_name)
            current_idx = 0
            if current_picks:
                curr_id = current_picks[0]
                for d_name, d_id in name_map.items():
                    if d_id == curr_id and d_name in opts_display:
                        current_idx = opts_display.index(d_name)
                        break
            k = f"opt_{entry['id']}_{gid}"
            st.selectbox("", opts_display, index=current_idx, key=k, label_visibility="collapsed",
                         on_change=cb_update_radio, args=(entry, gid, name_map, k))
        else:
            for c in choices:
                cid = c["id"]
                is_checked = cid in current_picks
                k = f"opt_{entry['id']}_{gid}_{cid}"
                st.checkbox(f"{c['name']} (+{c['points']})", value=is_checked, key=k,
                            on_change=cb_update_checkbox, args=(entry, gid, cid, k))


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
        # Only load if changed AND not suppressed by load_file event
        if st.session_state.get("current_codex_path") != str(path):
            st.session_state.codex_data = load_codex(path)
            st.session_state.current_codex_path = str(path)
            st.session_state.current_codex_name = selected_codex_name
            
            # WIPE ROSTER only if we are NOT loading a file
            if not st.session_state.get("is_loading_file", False):
                st.session_state.roster = [] 
                st.session_state.roster_name = "My Army List" # Reset name on codex swap
            
            st.session_state.is_loading_file = False
            st.rerun()

    # 2. Roster Details
    st.text_input("Roster Name", 
                  value=st.session_state.roster_name, 
                  key="roster_name_input",
                  on_change=cb_update_roster_name,
                  help="This name will appear on the PDF and the saved file.")
                  
    points_limit = st.number_input("Points Limit", value=1500, step=250, key="points_limit_input")
    
    st.divider()

    # 3. Save / Load
    st.subheader("Save / Load List")
    
    # Sanitize filename
    safe_filename = re.sub(r'[^a-zA-Z0-9_\-]', '_', st.session_state.roster_name)
    if not safe_filename: safe_filename = "army_list"
    
    save_data = {
        "roster_name": st.session_state.roster_name,
        "roster": st.session_state.roster,
        "codex_file": selected_codex_name,
        "points_limit": points_limit
    }
    roster_json = json.dumps(save_data, indent=2)
    st.download_button("💾 Download Roster File", roster_json, f"{safe_filename}.json", "application/json")

    uploaded_file = st.file_uploader("📂 Load Roster File", type=["json"])
    
    if uploaded_file is not None:
        if uploaded_file.file_id != st.session_state.get("last_loaded_file_id"):
            try:
                uploaded_file.seek(0)
                data = json.load(uploaded_file)
                saved_codex = data.get("codex_file")
                
                st.session_state.is_loading_file = True
                st.session_state.last_loaded_file_id = uploaded_file.file_id
                
                if saved_codex:
                    st.session_state.current_codex_name = saved_codex
                    st.session_state.current_codex_path = str(CODEX_DIR / saved_codex)
                    st.session_state.codex_data = load_codex(CODEX_DIR / saved_codex)

                st.session_state.roster = data.get("roster", [])
                st.session_state.roster_name = data.get("roster_name", "My Army List")
                st.success("List loaded successfully!")
                st.rerun()
                
            except Exception as e: st.error(f"Error reading file: {e}")

    st.divider()
    
    # 4. PDF Export
    st.write("### Export Options")
    include_tables = st.checkbox("Include Game Reference Tables", value=True)
    
    if st.button("📄 Generate PDF Roster"):
        pdf_path = BASE_DIR / "temp_roster.pdf"
        write_roster_pdf(
            st.session_state.roster, 
            st.session_state.codex_data, 
            points_limit, 
            str(pdf_path), 
            get_unit_by_id,
            include_ref_tables=include_tables,
            roster_name=st.session_state.roster_name # Pass the custom name
        )
        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF", f, "roster.pdf", "application/pdf")

    # 5. Project Status
    st.divider()
    st.subheader("Project Tracker")
    with st.expander("🛠️ Development Status"):
        issues = fetch_github_issues()
        if not issues:
            st.caption("No recent data found.")
        else:
            for i in issues:
                icon = "✅" if i["state"] == "closed" else "🔴"
                st.markdown(f"{icon} [{i['title']}]({i['html_url']})")

    # 6. Feedback
    st.divider()
    st.subheader("Report an Issue")
    
    with st.form("feedback_form"):
        feedback_type = st.selectbox("Type", ["Bug", "Missing Unit", "Wrong Stat", "Missing Upgrade", "Weapon/Wargear Selection", "Feature Request"])
        feedback_title = st.text_input("Short Summary")
        feedback_name = st.text_input("Your Name (Optional)")
        feedback_msg = st.text_area("Detailed Description")
        include_context = st.checkbox("Include roster data", value=True)
        submitted = st.form_submit_button("Submit Feedback")
        
        if submitted:
            if not feedback_title or not feedback_msg:
                st.error("Please provide both a Summary and a Description.")
            else:
                report_pts, _ = calculate_roster()
                try:
                    if "github" not in st.secrets:
                        st.error("GitHub secrets missing.")
                    else:
                        token = st.secrets["github"]["token"]
                        owner = st.secrets["github"]["owner"]
                        repo = st.secrets["github"]["repo"]
                        
                        final_title = f"[{feedback_type}] {feedback_title}"
                        if feedback_name: final_title += f" (by {feedback_name})"

                        body_text = f"**Reporter:** {feedback_name or 'Anonymous'}\n\n{feedback_msg}"
                        
                        if include_context:
                            context_str = "\n\n**Context:**\n"
                            if "codex_data" in st.session_state:
                                context_str += f"- Codex: {st.session_state.codex_data.get('codex_name')}\n"
                            context_str += f"- Points: {report_pts}/{points_limit}\n"
                            context_str += f"- Unit Count: {len(st.session_state.roster)}"
                            body_text += context_str

                        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
                        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                        payload = {"title": final_title, "body": body_text}
                        
                        response = requests.post(api_url, json=payload, headers=headers)
                        
                        if response.status_code == 201: st.success("Feedback sent!")
                        else: st.error(f"Error {response.status_code}: {response.text}")
                except Exception as e: st.error(f"Error sending feedback: {e}")

# --- Main Page ---
if "codex_data" in st.session_state and st.session_state.codex_data:
    data = st.session_state.codex_data
    
    # Custom Title in App (Uses the new variable)
    st.title(f"{st.session_state.roster_name}")
    st.caption(f"Using Codex: {data.get('codex_name', 'Army')}")
    
    curr_pts, slots = calculate_roster()
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Points", f"{curr_pts} / {points_limit}", delta=points_limit-curr_pts)
    col2.metric("HQ", f"{slots['HQ']}/2")
    col3.metric("Troops", f"{slots['Troops']}/6")
    col4.metric("Elites", f"{slots['Elites']}/3")
    col5.metric("Fast", f"{slots['Fast Attack']}/3")
    col6.metric("Heavy", f"{slots['Heavy Support']}/3")
    st.divider()

    st.header(f"Current Roster ({len(st.session_state.roster)} Units)")
    parents = [e for e in st.session_state.roster if not e.get("parent_id")]
    
    if not parents: st.info("Your roster is empty. Add a unit below!")
    else:
        for entry in parents:
            u = get_unit_by_id(entry["unit_id"])
            if not u: continue

            # Display Name: Use Custom Name if available
            display_title = f"[{u['slot']}] {u['name']}"
            if entry.get("custom_name"):
                display_title = f"[{u['slot']}] {entry['custom_name']} ({u['name']})"

            with st.expander(display_title, expanded=False):
                render_unit_options(entry, u)

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

            children = [e for e in st.session_state.roster if e.get("parent_id") == entry["id"]]
            for child in children:
                uc = get_unit_by_id(child["unit_id"])
                if not uc: continue
                with st.container():
                    # Custom Child Name Logic
                    child_title = uc['name']
                    if child.get("custom_name"):
                        child_title = f"{child['custom_name']} ({uc['name']})"
                        
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{child_title}**")
                    with st.expander(f"Edit {child_title}", expanded=False):
                        render_unit_options(child, uc)
                        st.divider()
                        if st.button("Remove Attachment", key=f"del_child_{child['id']}"):
                            st.session_state.roster.remove(child)
                            st.rerun()

    st.divider()

    st.subheader("Add New Unit")
    slots_map = ["HQ", "Troops", "Elites", "Fast Attack", "Heavy Support"]
    
    selected_slot = st.radio("Force Organisation Slot", slots_map, horizontal=True, label_visibility="collapsed", key="add_unit_slot_selection")
    
    slot_units = [u for u in data.get("units", []) if u.get("slot") == selected_slot]
    
    if not slot_units:
        st.caption(f"No units found for {selected_slot}")
    else:
        unit_options = [u["name"] for u in slot_units]
        selected_unit_name = st.selectbox(f"Select {selected_slot} Unit", unit_options, key=f"sel_unit_{selected_slot}")
        
        if st.button(f"Add {selected_unit_name}", key=f"btn_add_{selected_slot}"):
            uid = next(u["id"] for u in slot_units if u["name"] == selected_unit_name)
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
