import streamlit as st
import json
import uuid
from pathlib import Path
from reports import write_roster_pdf  # We reuse your existing PDF engine!

# --- Setup & Configuration ---
st.set_page_config(page_title="Rising Builder", page_icon="⚔️", layout="wide")

BASE_DIR = Path(__file__).parent
CODEX_DIR = BASE_DIR / "codexes"
CODEX_DIR.mkdir(exist_ok=True)

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
        
        # Points
        cost = u.get("base_points", 0) + u.get("points_per_model", 0) * entry.get("size", 1)
        for gid, picks in entry.get("selected", {}).items():
            # Find the option definition
            opt_def = next((o for o in u.get("options", []) if o.get("group_id") == gid), None)
            if not opt_def: continue
            
            for choice in opt_def.get("choices", []):
                # Count how many times this choice is in the picks list
                c_qty = picks.count(choice["id"]) if isinstance(picks, list) else (1 if picks == choice["id"] else 0)
                if c_qty > 0:
                    pts = choice.get("points", 0)
                    if choice.get("points_mode") == "per_model":
                        cost += pts * entry.get("size", 1)
                    else:
                        cost += pts * c_qty
        
        entry["calculated_cost"] = cost
        total_pts += cost
        
        # Slots (only if not a child unit)
        if not entry.get("parent_id") and u.get("slot") in counts:
            counts[u["slot"]] += 1
            
    return total_pts, counts

# --- Sidebar: Codex Selection & PDF Export ---
with st.sidebar:
    st.header("Settings")
    
    # Codex Loader
    available_codexes = list(CODEX_DIR.glob("*.json"))
    codex_names = [p.name for p in available_codexes]
    selected_codex_name = st.selectbox("Select Codex", codex_names)
    
    if selected_codex_name:
        path = CODEX_DIR / selected_codex_name
        # Reload only if changed
        if st.session_state.get("current_codex_path") != str(path):
            st.session_state.codex_data = load_codex(path)
            st.session_state.current_codex_path = str(path)
            st.session_state.roster = [] # Reset roster on change
            st.rerun()

    points_limit = st.number_input("Points Limit", value=1500, step=250)
    
    st.divider()
    
    # PDF Export
    if st.button("Generate PDF Roster"):
        pdf_path = BASE_DIR / "temp_roster.pdf"
        write_roster_pdf(
            st.session_state.roster, 
            st.session_state.codex_data, 
            points_limit, 
            str(pdf_path), 
            get_unit_by_id
        )
        with open(pdf_path, "rb") as f:
            st.download_button("Download PDF", f, file_name="roster.pdf", mime="application/pdf")
    # --- Feedback / Bug Report ---
    st.divider()
    st.subheader("Report an Issue")
    
    with st.form("feedback_form"):
        feedback_type = st.selectbox("Type", ["Bug", "Missing Unit", "Wrong Stat", "Missing Upgrade", "Weapon/Wargear Selection", "Feature Request"])
        feedback_msg = st.text_area("Description", placeholder="E.g. The Fire Warrior Shas'ui has WS 2 but should be WS 3...")
        
        # Optional: Attach current roster state context
        include_context = st.checkbox("Include current roster data (helps debugging)", value=True)
        
        submitted = st.form_submit_button("Submit Feedback")
        
        if submitted and feedback_msg:
            # --- FIX: Calculate points right now for the report ---
            report_pts, _ = calculate_roster()
            # ------------------------------------------------------

            # 1. Get Secrets
            try:
                token = st.secrets["github"]["token"]
                owner = st.secrets["github"]["owner"]
                repo = st.secrets["github"]["repo"]
            except FileNotFoundError:
                st.error("Secrets file not found. Feedback cannot be sent.")
                st.stop()

            # 2. Build the Issue Body
            body_text = f"**Type:** {feedback_type}\n\n**User Report:**\n{feedback_msg}"
            
            if include_context:
                # Add a summary of what they were building
                context_str = "\n\n**Context:**\n"
                if "codex_data" in st.session_state:
                    context_str += f"- Codex: {st.session_state.codex_data.get('codex_name')}\n"
                
                # Use the locally calculated 'report_pts' variable here
                context_str += f"- Points: {report_pts}/{points_limit}\n"
                context_str += f"- Unit Count: {len(st.session_state.roster)}"
                body_text += context_str

            # 3. Send to GitHub API
            api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json"
            }
            payload = {
                "title": f"[{feedback_type}] Feedback from App",
                "body": body_text
            }
            
            import requests 
            response = requests.post(api_url, json=payload, headers=headers)
            
            if response.status_code == 201:
                st.success("Feedback sent! Check your GitHub Issues.")
            else:
                st.error(f"Failed to send. Error: {response.status_code}")
                st.error(response.text)

# --- Main Page ---
if "codex_data" in st.session_state and st.session_state.codex_data:
    data = st.session_state.codex_data
    
    st.title(f"{data.get('codex_name', 'Army')} Builder")
    
    # Summary Bar
    curr_pts, slots = calculate_roster()
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Total Points", f"{curr_pts} / {points_limit}", delta=points_limit-curr_pts)
    col2.metric("HQ", f"{slots['HQ']}/2")
    col3.metric("Troops", f"{slots['Troops']}/6")
    col4.metric("Elites", f"{slots['Elites']}/3")
    col5.metric("Fast", f"{slots['Fast Attack']}/3")
    col6.metric("Heavy", f"{slots['Heavy Support']}/3")
    
    st.divider()

    # --- Add Unit Section ---
    st.subheader("Add Unit")
    add_cols = st.columns([3, 1])
    
    # Filter units for dropdown
    unit_opts = [(u["name"], u["id"]) for u in data.get("units", []) 
                 if u.get("slot") != "Dedicated Transport"] # Don't show DTs in main list
    
    selected_unit_name = add_cols[0].selectbox("Choose Unit", [u[0] for u in unit_opts], label_visibility="collapsed")
    
    if add_cols[1].button("Add to Roster", use_container_width=True):
        uid = next(u[1] for u in unit_opts if u[0] == selected_unit_name)
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

    # --- Roster Display ---
    st.header("Current Roster")
    
    # Sort and Group logic for display (Parent -> Child)
    parents = [e for e in st.session_state.roster if not e.get("parent_id")]
    
    for entry in parents:
        u = get_unit_by_id(entry["unit_id"])
        
        # Card Container
        with st.expander(f"[{u['slot']}] {u['name']} ({entry.get('calculated_cost', 0)} pts)", expanded=True):
            
            # --- Squad Size ---
            min_s = int(u.get("min_size", 1))
            max_s = int(u.get("max_size", 1))
            if min_s != max_s:
                entry["size"] = st.number_input(f"Squad Size ({min_s}-{max_s})", 
                                                min_value=min_s, max_value=max_s, 
                                                value=int(entry.get("size", min_s)), 
                                                key=f"size_{entry['id']}")

            # --- Options Logic ---
            for opt in u.get("options", []):
                gid = opt["group_id"]
                st.caption(f"**{opt.get('group_name', 'Options')}**")
                
                # Get current picks for this group
                current_picks = entry["selected"].get(gid, [])
                
                # Logic: Checkboxes, Radios, or Counters?
                choices = opt.get("choices", [])
                max_sel = opt.get("max_select", 1)
                if opt.get("linked_to_size"): max_sel = entry["size"]
                
                # CASE A: Counters (Mix & Match)
                # If linked to size AND multiple choices (e.g. Crisis Weapons) OR single choice with high max (e.g. Grenades)
                if (opt.get("linked_to_size") and len(choices) > 1) or (len(choices)==1 and max_sel > 1):
                    for c in choices:
                        cid = c["id"]
                        # Count existing
                        qty = current_picks.count(cid)
                        new_qty = st.number_input(f"{c['name']} (+{c['points']} pts)", 
                                                  min_value=0, max_value=max_sel, value=qty, 
                                                  key=f"opt_{entry['id']}_{gid}_{cid}")
                        
                        # Update logic: Remove all old instances of this ID, add new count
                        current_picks = [x for x in current_picks if x != cid]
                        current_picks.extend([cid] * new_qty)
                        entry["selected"][gid] = current_picks

                # CASE B: Radio (Pick 1)
                elif max_sel == 1:
                    opts = ["(None)"] + [f"{c['name']} (+{c['points']})" for c in choices]
                    current_idx = 0
                    if current_picks:
                        # Find index of currently selected ID
                        curr_id = current_picks[0]
                        for i, c in enumerate(choices):
                            if c["id"] == curr_id: current_idx = i + 1; break
                            
                    sel = st.selectbox("", opts, index=current_idx, key=f"opt_{entry['id']}_{gid}")
                    
                    if sel == "(None)": entry["selected"][gid] = []
                    else:
                        # Find ID from name match (simple parsing)
                        idx = opts.index(sel) - 1
                        entry["selected"][gid] = [choices[idx]["id"]]

                # CASE C: Checkboxes (Pick up to N unique)
                else:
                    for c in choices:
                        cid = c["id"]
                        is_checked = cid in current_picks
                        if st.checkbox(f"{c['name']} (+{c['points']})", value=is_checked, key=f"opt_{entry['id']}_{gid}_{cid}"):
                            if cid not in current_picks: 
                                if len(current_picks) < max_sel: entry["selected"].setdefault(gid, []).append(cid)
                        else:
                            if cid in current_picks: entry["selected"][gid].remove(cid)

            # --- Add Attachment Button ---
            valid_transports = u.get("dedicated_transports", [])
            if valid_transports:
                st.divider()
                cols = st.columns([3, 1])
                t_opts = [get_unit_by_id(tid) for tid in valid_transports]
                t_opts = [t for t in t_opts if t] # filter nones
                
                t_names = [t["name"] for t in t_opts]
                sel_t = cols[0].selectbox("Add Attachment", t_names, key=f"trans_sel_{entry['id']}")
                
                if cols[1].button("Add", key=f"add_trans_{entry['id']}"):
                    tid = next(t["id"] for t in t_opts if t["name"] == sel_t)
                    child_entry = {
                        "id": str(uuid.uuid4()),
                        "unit_id": tid,
                        "size": 1,
                        "selected": {},
                        "parent_id": entry["id"]
                    }
                    st.session_state.roster.append(child_entry)
                    st.rerun()

            # --- Remove Button ---
            st.divider()
            if st.button("Remove Unit", key=f"del_{entry['id']}", type="primary"):
                # Remove self AND children
                ids_to_remove = [entry["id"]] + [c["id"] for c in st.session_state.roster if c.get("parent_id") == entry["id"]]
                st.session_state.roster = [e for e in st.session_state.roster if e["id"] not in ids_to_remove]
                st.rerun()

        # --- Display Children (Attachments) ---
        children = [e for e in st.session_state.roster if e.get("parent_id") == entry["id"]]
        for child in children:
            uc = get_unit_by_id(child["unit_id"])
            with st.container():
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{uc['name']}** ({child.get('calculated_cost',0)} pts)")
                # Minimal editor for child
                with st.expander("Edit Attachment"):
                    # (Simplified option logic reuse or copy-paste the option loop here if you want full editing for children)
                    # For brevity in this snippet, I'll just put a delete button, but you can copy the Option loop above here too.
                    if st.button("Remove Attachment", key=f"del_child_{child['id']}"):
                        st.session_state.roster.remove(child)
                        st.rerun()

else:

    st.info("Please select a Codex from the sidebar to begin.")


