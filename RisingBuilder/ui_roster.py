import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QSpinBox, 
    QLabel, QSplitter, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QFileDialog, QGroupBox, QFormLayout, QScrollArea, QTextEdit, 
    QButtonGroup, QRadioButton, QCheckBox, QDialog, QDialogButtonBox
)

from utils import ensure_folder, read_json, write_json, slugify
from constants import SLOTS, FORCE_ORG_LIMITS_5E
from ui_editors import DedicatedTransportPicker
from reports import write_roster_pdf, HAVE_REPORTLAB

class RosterBuilderWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.roster_entries: List[Dict[str, Any]] = []
        self._current_real_index: Optional[int] = None
        self._suppress_option_signals = False

        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        outer.addLayout(top)
        self.codex_combo = QComboBox()
        self.codex_combo.setMinimumWidth(280)
        self.codex_combo.currentIndexChanged.connect(self._on_codex_combo_changed)
        
        self.open_codex_btn = QPushButton("Open Codex…")
        self.open_codex_btn.clicked.connect(self._open_codex)
        self.points_limit = QSpinBox()
        self.points_limit.setRange(100, 100000)
        self.points_limit.setValue(1500)
        self.points_limit.valueChanged.connect(self._refresh_all)

        top.addWidget(QLabel("Codex")); top.addWidget(self.codex_combo)
        top.addWidget(self.open_codex_btn); top.addSpacing(14)
        top.addWidget(QLabel("Points limit")); top.addWidget(self.points_limit)
        top.addStretch(1)

        summary = QHBoxLayout()
        outer.addLayout(summary)
        self.points_label = QLabel("Total: 0 / 1500")
        self.points_label.setStyleSheet("font-weight: bold;")
        summary.addWidget(self.points_label)
        self.force_org_label = QLabel("Force Org: —")
        summary.addSpacing(16)
        summary.addWidget(self.force_org_label)
        summary.addStretch(1)

        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter, stretch=1)

        left = QWidget(); left_layout = QVBoxLayout(left); splitter.addWidget(left)
        filter_row = QHBoxLayout()
        self.slot_filter = QComboBox()
        self.slot_filter.addItem("All slots")
        self.slot_filter.addItems(SLOTS)
        self.slot_filter.currentTextChanged.connect(self._refresh_available_units)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search unit name…")
        self.search_edit.textChanged.connect(self._refresh_available_units)
        filter_row.addWidget(QLabel("Filter")); filter_row.addWidget(self.slot_filter)
        filter_row.addWidget(self.search_edit, stretch=1)
        left_layout.addLayout(filter_row)
        
        self.available_list = QListWidget()
        self.available_list.itemDoubleClicked.connect(lambda _item: self._add_selected_unit())
        left_layout.addWidget(self.available_list, stretch=1)
        
        add_row = QHBoxLayout()
        self.add_unit_btn = QPushButton("Add unit to roster")
        self.add_unit_btn.clicked.connect(self._add_selected_unit)
        add_row.addWidget(self.add_unit_btn)
        left_layout.addLayout(add_row)

        right = QWidget(); right_layout = QVBoxLayout(right); splitter.addWidget(right)
        right_splitter = QSplitter(Qt.Vertical)
        right_layout.addWidget(right_splitter, stretch=1)

        roster_panel = QWidget(); rpl = QVBoxLayout(roster_panel)
        rpl.addWidget(QLabel("Roster"))
        self.roster_list = QListWidget()
        self.roster_list.currentRowChanged.connect(self._on_roster_row_changed)
        rpl.addWidget(self.roster_list, stretch=1)
        roster_btns = QHBoxLayout()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_selected_entry)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_roster)
        self.save_roster_btn = QPushButton("Save...")
        self.save_roster_btn.clicked.connect(self._save_roster)
        self.load_roster_btn = QPushButton("Load...")
        self.load_roster_btn.clicked.connect(self._load_roster)
        self.export_pdf_btn = QPushButton("Export PDF...")
        self.export_pdf_btn.clicked.connect(self._export_roster_pdf)
        roster_btns.addWidget(self.remove_btn); roster_btns.addWidget(self.clear_btn)
        roster_btns.addWidget(self.save_roster_btn); roster_btns.addWidget(self.load_roster_btn)
        roster_btns.addWidget(self.export_pdf_btn); roster_btns.addStretch(1)
        rpl.addLayout(roster_btns)
        right_splitter.addWidget(roster_panel)

        self.entry_box = QGroupBox("Selected unit")
        eb = QVBoxLayout(self.entry_box)
        form = QFormLayout()
        self.sel_name = QLabel("—"); self.sel_slot = QLabel("—")
        self.size_spin = QSpinBox(); self.size_spin.setRange(1, 50)
        self.size_spin.valueChanged.connect(self._on_size_changed)
        form.addRow("Name", self.sel_name)
        form.addRow("Slot", self.sel_slot)
        form.addRow("Squad size", self.size_spin)
        eb.addLayout(form)
        dt_row = QHBoxLayout()
        self.add_dt_for_unit_btn = QPushButton("Add Attached Unit (Transport/Retinue)…")
        self.add_dt_for_unit_btn.clicked.connect(self._add_dt_for_selected_entry)
        dt_row.addWidget(self.add_dt_for_unit_btn); dt_row.addStretch(1)
        eb.addLayout(dt_row)

        opts_splitter = QSplitter(Qt.Vertical)
        sp = QWidget(); sl = QVBoxLayout(sp); sl.addWidget(QLabel("Options (structured)"))
        self.options_scroll = QScrollArea(); self.options_scroll.setWidgetResizable(True)
        sl.addWidget(self.options_scroll, stretch=1)
        self.options_inner = QWidget(); self.options_layout = QVBoxLayout(self.options_inner)
        self.options_scroll.setWidget(self.options_inner)
        fp = QWidget(); fl = QVBoxLayout(fp); fl.addWidget(QLabel("Options (free text / notes)"))
        self.free_text = QTextEdit(); self.free_text.setReadOnly(True); self.free_text.setMinimumHeight(90)
        fl.addWidget(self.free_text, stretch=1)
        opts_splitter.addWidget(sp); opts_splitter.addWidget(fp)
        eb.addWidget(opts_splitter, stretch=1)
        right_splitter.addWidget(self.entry_box)
        splitter.setSizes([520, 820])
        
        self.entry_box.setEnabled(False)
        self.refresh_codex_combo()

    def refresh_codex_combo(self):
        self.codex_combo.blockSignals(True)
        self.codex_combo.clear()
        codex_dir = Path("codexes"); ensure_folder(codex_dir)
        for p in sorted(codex_dir.glob("*.json")): self.codex_combo.addItem(p.name, str(p))
        if self.mw.codex_path:
            for i in range(self.codex_combo.count()):
                if Path(self.codex_combo.itemData(i)).resolve() == self.mw.codex_path.resolve():
                    self.codex_combo.setCurrentIndex(i); break
        self.codex_combo.blockSignals(False)

    def _on_codex_combo_changed(self):
        data = self.codex_combo.currentData()
        if data and (not self.mw.codex_path or Path(data).resolve() != self.mw.codex_path.resolve()):
            self.mw.load_codex(Path(data))

    def _open_codex(self):
        self.mw.open_codex()
        self.refresh_codex_combo()

    def on_codex_loaded(self):
        self.refresh_codex_combo()
        self._refresh_available_units()
        self._clear_roster()

    def _refresh_available_units(self):
        self.available_list.clear()
        slot_filter = self.slot_filter.currentText()
        q = self.search_edit.text().strip().lower()
        
        slot_order = { "HQ": 0, "Troops": 1, "Elites": 2, "Fast Attack": 3, "Heavy Support": 4, "Dedicated Transport": 5 }
        
        units = sorted(
            self.mw.codex_data.get("units", []), 
            key=lambda u: (slot_order.get(u.get("slot", ""), 99), u.get("name", ""))
        )

        for u in units:
            if u.get("slot") == "Dedicated Transport": continue
            if slot_filter != "All slots" and u.get("slot") != slot_filter: continue
            if q and q not in u.get("name", "").lower(): continue
            item = QListWidgetItem(f"[{u.get('slot')}] {u.get('name')}")
            item.setData(Qt.UserRole, u.get("id"))
            self.available_list.addItem(item)

    def _add_selected_unit(self):
        item = self.available_list.currentItem()
        if not item: return
        unit_id = item.data(Qt.UserRole)
        unit = self.mw.get_unit_by_id(unit_id)
        if unit:
            new_id = str(uuid.uuid4())
            new_entry = {
                "id": new_id,
                "unit_id": unit_id, 
                "size": int(unit.get("default_size", 1)), 
                "selected": {}, 
                "parent_id": None
            }
            self.roster_entries.append(new_entry)
            self._refresh_roster_list(select_entry_id=new_id)

    def _add_dt_for_selected_entry(self):
        if self._current_real_index is None: return
        parent_entry = self.roster_entries[self._current_real_index]
        parent_unit = self.mw.get_unit_by_id(parent_entry["unit_id"])
        
        dt_ids = parent_unit.get("dedicated_transports", [])
        transports = [self.mw.get_unit_by_id(uid) for uid in dt_ids if self.mw.get_unit_by_id(uid)]
        
        if not transports:
            QMessageBox.information(self, "Info", "This unit cannot take a Dedicated Transport or Retinue.")
            return

        dlg = DedicatedTransportPicker(self, transports)
        if dlg.exec() == QDialog.Accepted and dlg.selected_id:
             new_id = str(uuid.uuid4())
             new_entry = {
                 "id": new_id,
                 "unit_id": dlg.selected_id, 
                 "size": 1, 
                 "selected": {}, 
                 "parent_id": parent_entry["id"]
             }
             self.roster_entries.append(new_entry)
             self._refresh_roster_list(select_entry_id=new_id)

    def _remove_selected_entry(self):
        if self._current_real_index is None: return
        
        entry_to_remove = self.roster_entries[self._current_real_index]
        remove_id = entry_to_remove["id"]
        
        ids_to_remove = {remove_id}
        for e in self.roster_entries:
            if e.get("parent_id") == remove_id:
                ids_to_remove.add(e["id"])
                
        self.roster_entries = [e for e in self.roster_entries if e["id"] not in ids_to_remove]
        self._current_real_index = None
        self._refresh_roster_list()

    def _clear_roster(self):
        self.roster_entries = []
        self._current_real_index = None
        self._refresh_roster_list()

    def _refresh_roster_list(self, select_entry_id=None):
        self.roster_list.clear()

        children_map = {}
        roots = []
        for e in self.roster_entries:
            pid = e.get("parent_id")
            if pid:
                if pid not in children_map: children_map[pid] = []
                children_map[pid].append(e)
            else:
                roots.append(e)

        slot_order = {"HQ": 0, "Troops": 1, "Elites": 2, "Fast Attack": 3, "Heavy Support": 4}
        def get_sort_key(e):
            u = self.mw.get_unit_by_id(e["unit_id"])
            if not u: return (99, "")
            return (slot_order.get(u.get("slot", ""), 99), u.get("name", ""))
        roots.sort(key=get_sort_key)

        item_to_select = None
        
        def add_entry_visual(entry, indent=False):
            real_idx = self.roster_entries.index(entry)
            u = self.mw.get_unit_by_id(entry["unit_id"])
            if not u:
                item = QListWidgetItem("Unknown Unit")
            else:
                cost = u.get("base_points", 0) + u.get("points_per_model", 0) * entry.get("size", 1)
                for gid, picks in entry.get("selected", {}).items():
                    for opt in u.get("options", []):
                        if opt["group_id"] == gid:
                            for c in opt.get("choices", []):
                                count = 0
                                if isinstance(picks, list): count = picks.count(c["id"])
                                elif picks == c["id"]: count = 1
                                if count > 0:
                                    pts = c.get("points", 0)
                                    mode = c.get("points_mode", "flat")
                                    cost += (pts * entry.get("size", 1)) if mode == "per_model" else (pts * count)
                
                prefix = "    ↳ [DT] " if indent else f"[{u.get('slot','?')}] "
                text = f"{prefix}{u.get('name','?')} (x{entry.get('size',1)}) - {cost} pts"
                item = QListWidgetItem(text)
            
            item.setData(Qt.UserRole, real_idx)
            self.roster_list.addItem(item)
            return item

        for root in roots:
            it = add_entry_visual(root, False)
            if root["id"] == select_entry_id: item_to_select = it
            if root["id"] in children_map:
                for child in children_map[root["id"]]:
                    it_c = add_entry_visual(child, True)
                    if child["id"] == select_entry_id: item_to_select = it_c

        if item_to_select:
            self.roster_list.setCurrentItem(item_to_select)
        elif self.roster_list.count() > 0:
            self.roster_list.setCurrentRow(0)
        else:
            self._on_roster_row_changed(-1)

        self._refresh_all()

    def _on_roster_row_changed(self, visual_row):
        if visual_row < 0:
            self._current_real_index = None
            self.entry_box.setEnabled(False)
            return
            
        item = self.roster_list.item(visual_row)
        real_idx = item.data(Qt.UserRole)
        
        if real_idx is None or real_idx < 0 or real_idx >= len(self.roster_entries):
            self._current_real_index = None
            self.entry_box.setEnabled(False)
            return

        self._current_real_index = real_idx
        self.entry_box.setEnabled(True)
        
        e = self.roster_entries[real_idx]
        unit = self.mw.get_unit_by_id(e["unit_id"])
        
        if unit:
            self.sel_name.setText(unit.get("name"))
            self.sel_slot.setText(unit.get("slot"))
            
            self.size_spin.blockSignals(True)
            self.size_spin.setRange(int(unit.get("min_size", 1)), int(unit.get("max_size", 1)))
            self.size_spin.setValue(int(e.get("size", 1)))
            self.size_spin.setEnabled(unit.get("min_size") != unit.get("max_size"))
            self.size_spin.blockSignals(False)
            
            self.free_text.setPlainText("\n".join(unit.get("options_text", [])))
            self._build_options_ui(unit, e)
            
            has_dt = bool(unit.get("dedicated_transports"))
            is_child = e.get("parent_id") is not None
            self.add_dt_for_unit_btn.setEnabled(has_dt and not is_child)

    def _on_size_changed(self, val):
        if self._current_real_index is not None:
            entry = self.roster_entries[self._current_real_index]
            entry["size"] = val
            unit = self.mw.get_unit_by_id(entry["unit_id"])
            if unit: self._build_options_ui(unit, entry)
            self._refresh_roster_list(select_entry_id=entry["id"])

    def _get_tooltip(self, choice_id, name):
        """Generates a tooltip by searching sub-profiles, weapons, rules, and wargear."""
        lines = []
        data = self.mw.codex_data
        
        clean = re.sub(r'\s*\(.*?\)', '', name).strip()
        
        # Weapons
        weapons = data.get("weapons", {})
        w_key = next((k for k in weapons if k.lower() == clean.lower()), None)
        if w_key:
            w = weapons[w_key]
            lines.append(f"WEAPON PROFILE: {w_key}")
            lines.append(f"Range: {w.get('range','-')} | S: {w.get('S','-')} | AP: {w.get('AP','-')}")
            lines.append(f"Type: {w.get('type','-')}")
            if w.get("notes"): lines.append(f"Notes: {w.get('notes')}")
            
        # Rules
        rules = data.get("rules", {})
        r_key = next((k for k in rules if k.lower() == clean.lower()), None)
        if r_key:
            lines.append(f"RULE: {r_key}")
            lines.append(rules[r_key].get("summary", ""))
            
        # Wargear
        wargear = data.get("wargear", {})
        wg_key = next((k for k in wargear if k.lower() == clean.lower()), None)
        if wg_key:
            lines.append(f"WARGEAR: {wg_key}")
            lines.append(wargear[wg_key].get("summary", ""))
            
        return "\n\n".join(lines) if lines else None

    def _build_options_ui(self, unit, entry):
        self._suppress_option_signals = True
        
        while self.options_layout.count(): 
            child = self.options_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        selected = entry.setdefault("selected", {})
        current_size = entry.get("size", 1)
        
        for i, g in enumerate(unit.get("options", [])):
            try:
                gid = g.get("group_id") or f"group_{i}"
                max_select = g.get("max_select", 1)
                min_select = g.get("min_select", 0)
                if g.get("linked_to_size"): max_select = current_size
                
                limit_text = f"{min_select}–{max_select}"
                if max_select == current_size and current_size > 1: limit_text = f"Up to {current_size}"
                
                current_picks = selected.get(gid, [])
                total_selected = len(current_picks) if isinstance(current_picks, list) else (1 if current_picks else 0)
                
                box = QGroupBox(f"{g.get('group_name', 'Option')} ({limit_text}) [Selected: {total_selected}]")
                vb = QVBoxLayout(box)
                
                def apply_tooltip(widget, choice_id, choice_name):
                    prof_text = ""
                    if "sub_profiles" in unit and choice_id in unit["sub_profiles"]:
                        p = unit["sub_profiles"][choice_id]
                        prof_text = f"PROFILE: {p.get('name', 'Unit')}\nWS{p.get('WS')} BS{p.get('BS')} S{p.get('S')} T{p.get('T')} W{p.get('W')} I{p.get('I')} A{p.get('A')} Ld{p.get('Ld')} Sv{p.get('Sv')}\n\n"
                    
                    gen_text = self._get_tooltip(choice_id, choice_name)
                    final = (prof_text + (gen_text or "")).strip()
                    if final:
                        widget.setToolTip(final)

                if g.get("linked_to_size") and len(g.get("choices", [])) > 1:
                    for c in g.get("choices", []):
                        cid = c.get("id")
                        current_qty = selected.get(gid, []).count(cid)
                        row = QHBoxLayout()
                        lbl = QLabel(c.get("name", "Unknown"))
                        apply_tooltip(lbl, cid, c.get("name", ""))
                        
                        spin = QSpinBox(); spin.setRange(0, max_select); spin.setValue(current_qty)
                        row.addWidget(lbl); row.addWidget(spin); row.addWidget(QLabel(f"+{c.get('points',0)} pts"))
                        vb.addLayout(row)
                        spin.valueChanged.connect(lambda val, x=gid, c=cid: self._opt_mixed_quantity_changed(x, c, val))

                elif len(g.get("choices", [])) == 1 and max_select > 1:
                    choice = g["choices"][0]; cid = choice.get("id")
                    current_count = selected.get(gid, []).count(cid)
                    row = QHBoxLayout()
                    lbl = QLabel(choice.get("name", "Unknown"))
                    apply_tooltip(lbl, cid, choice.get("name", ""))
                    
                    spin = QSpinBox(); spin.setRange(0, max_select); spin.setValue(current_count)
                    row.addWidget(lbl); row.addWidget(spin); row.addWidget(QLabel(f"+{choice.get('points',0)} pts"))
                    vb.addLayout(row)
                    spin.valueChanged.connect(lambda val, x=gid, c=cid: self._opt_quantity_changed(x, c, val))

                elif max_select <= 1:
                    bg = QButtonGroup(box); bg.setExclusive(True)
                    if min_select == 0:
                        rb = QRadioButton("(none)"); bg.addButton(rb); vb.addWidget(rb)
                        if not selected.get(gid): rb.setChecked(True)
                        rb.toggled.connect(lambda c, x=gid: self._opt_changed(x, [], c) if c else None)
                    for c in g.get("choices", []):
                        rb = QRadioButton(f"{c.get('name', 'Unknown')} (+{c.get('points',0)})")
                        apply_tooltip(rb, c.get("id"), c.get("name", ""))
                        
                        bg.addButton(rb); vb.addWidget(rb)
                        if c.get("id") in selected.get(gid, []): rb.setChecked(True)
                        rb.toggled.connect(lambda c, x=gid, y=c.get("id"): self._opt_changed(x, [y], c) if c else None)
                
                else:
                    current_picks = selected.get(gid, [])
                    if len(current_picks) > max_select:
                        current_picks = current_picks[:max_select]; selected[gid] = current_picks
                    for c in g.get("choices", []):
                        cb = QCheckBox(f"{c.get('name', 'Unknown')} (+{c.get('points',0)})")
                        apply_tooltip(cb, c.get("id"), c.get("name", ""))
                        
                        vb.addWidget(cb)
                        if c.get("id") in current_picks: cb.setChecked(True)
                        cb.toggled.connect(lambda c, x=gid, y=c.get("id"), w=cb, m=max_select: self._opt_multi_changed(c, x, y, w, m))
                
                self.options_layout.addWidget(box)
            except Exception as e: print(f"Error building option group: {e}")
        self.options_layout.addStretch(1)
        self._suppress_option_signals = False

    def _opt_quantity_changed(self, gid, cid, count):
        if self._suppress_option_signals or self._current_real_index is None: return
        entry = self.roster_entries[self._current_real_index]
        entry["selected"][gid] = [cid] * count
        self._refresh_roster_list(select_entry_id=entry["id"])

    def _opt_mixed_quantity_changed(self, gid, cid, count):
        if self._suppress_option_signals or self._current_real_index is None: return
        entry = self.roster_entries[self._current_real_index]
        current_picks = entry["selected"].get(gid, [])
        current_picks = [x for x in current_picks if x != cid]
        for _ in range(count): current_picks.append(cid)
        entry["selected"][gid] = current_picks
        self._refresh_roster_list(select_entry_id=entry["id"])

    def _opt_changed(self, gid, picks, checked):
        if not self._suppress_option_signals and checked and self._current_real_index is not None:
            entry = self.roster_entries[self._current_real_index]
            entry["selected"][gid] = picks
            self._refresh_roster_list(select_entry_id=entry["id"])

    def _opt_multi_changed(self, checked, gid, cid, widget, mx):
        if self._suppress_option_signals or self._current_real_index is None: return
        entry = self.roster_entries[self._current_real_index]
        picks = entry["selected"].setdefault(gid, [])
        if checked:
            if len(picks) >= mx:
                self._suppress_option_signals = True; widget.setChecked(False); self._suppress_option_signals = False; return
            if cid not in picks: picks.append(cid)
        else:
            if cid in picks: picks.remove(cid)
        self._refresh_roster_list(select_entry_id=entry["id"])

    def _refresh_all(self):
        total = 0
        counts = {k: 0 for k in FORCE_ORG_LIMITS_5E}
        for entry in self.roster_entries:
            u = self.mw.get_unit_by_id(entry["unit_id"])
            if not u: continue
            
            cost = u.get("base_points", 0) + u.get("points_per_model", 0) * entry.get("size", 1)
            for gid, picks in entry.get("selected", {}).items():
                for opt in u.get("options", []):
                    if opt["group_id"] == gid:
                        for c in opt.get("choices", []):
                            count = 0
                            if isinstance(picks, list): count = picks.count(c["id"])
                            elif picks == c["id"]: count = 1
                            if count > 0:
                                pts = c.get("points", 0)
                                mode = c.get("points_mode", "flat")
                                cost += (pts * entry.get("size", 1)) if mode == "per_model" else (pts * count)
            total += cost
            if entry.get("parent_id") is None and u.get("slot") in counts: counts[u.get("slot")] += 1

        limit = self.points_limit.value()
        self.points_label.setText(f"Total: {total} / {limit}")
        self.points_label.setStyleSheet("color: red; font-weight: bold;" if total > limit else "font-weight: bold;")
        
        valid = True
        errs = []
        for s, (mn, mx) in FORCE_ORG_LIMITS_5E.items():
            if not (mn <= counts[s] <= mx):
                valid = False
                errs.append(f"{s}: {counts[s]}")
        self.force_org_label.setText("Force Org: " + ("OK" if valid else "INVALID (" + ", ".join(errs) + ")"))
        self.force_org_label.setStyleSheet("color: red;" if not valid else "")

    def _save_roster(self):
        ensure_folder(Path("rosters"))
        path, _ = QFileDialog.getSaveFileName(self, "Save Roster", str(Path("rosters")), "JSON Files (*.json)")
        if path:
            data = {
                "roster_entries": self.roster_entries,
                "points_limit": self.points_limit.value(),
                "codex_file": self.mw.codex_path.name if self.mw.codex_path else None
            }
            write_json(Path(path), data)

    def _load_roster(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Roster", str(Path("rosters")), "JSON Files (*.json)")
        if path:
            data = read_json(Path(path))
            self.roster_entries = []
            for e in data.get("roster_entries", []):
                if "id" not in e: e["id"] = str(uuid.uuid4())
                if "parent_id" not in e: e["parent_id"] = None
                self.roster_entries.append(e)
            self.points_limit.setValue(data.get("points_limit", 1500))
            self._refresh_roster_list()

    def _export_roster_pdf(self):
        if not HAVE_REPORTLAB:
            QMessageBox.critical(self, "Error", "ReportLab not installed.")
            return
        ensure_folder(Path("exports"))
        default_name = f"{(self.mw.codex_data or {}).get('codex_name','roster')}_{self.points_limit.value()}pts_{datetime.now().strftime('%Y%m%d')}.pdf"
        default_name = slugify(default_name).replace("_pdf", "") + ".pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", str((Path("exports") / default_name).resolve()), "PDF Files (*.pdf)")
        if path:
            write_roster_pdf(self.roster_entries, self.mw.codex_data, self.points_limit.value(), path, self.mw.get_unit_by_id)
            QMessageBox.information(self, "Success", "PDF Exported.")