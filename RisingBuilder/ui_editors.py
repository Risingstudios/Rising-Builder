from typing import Any, Dict, List, Optional, Tuple, Set
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox, 
    QComboBox, QTextEdit, QDialogButtonBox, QMessageBox, 
    QGroupBox, QScrollArea, QWidget, QGridLayout, QLabel, 
    QHBoxLayout, QListWidget, QListWidgetItem, QCheckBox, 
    QStackedWidget, QPushButton, QSplitter
)

from utils import unique_id, slugify, lines_to_list, list_to_lines
from constants import SLOTS, POINTS_MODES, PROFILE_TYPES

class OptionGroupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Option Group")
        self.setSizeGripEnabled(True)
        self.resize(520, 320)
        self._existing_id: Optional[str] = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 50)
        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 50)
        self.max_spin.setValue(1)
        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Optional notes about this group")

        form.addRow("Group name", self.name_edit)
        form.addRow("Min picks", self.min_spin)
        form.addRow("Max picks", self.max_spin)
        form.addRow("Group notes", self.note_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a group name.")
            return
        if self.max_spin.value() < self.min_spin.value():
            QMessageBox.warning(self, "Invalid picks", "Max picks must be >= Min picks.")
            return
        self.accept()

    def set_group(self, group: Dict[str, Any]):
        self._existing_id = group.get("group_id")
        self.name_edit.setText(group.get("group_name", ""))
        self.min_spin.setValue(int(group.get("min_select", 0)))
        self.max_spin.setValue(int(group.get("max_select", 1)))
        self.note_edit.setPlainText(group.get("note", "") or "")

    def get_group(self) -> Dict[str, Any]:
        return {
            "group_id": self._existing_id,
            "group_name": self.name_edit.text().strip(),
            "min_select": int(self.min_spin.value()),
            "max_select": int(self.max_spin.value()),
            "note": self.note_edit.toPlainText().strip(),
            "choices": [],
        }

class OptionChoiceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Option Choice")
        self.setSizeGripEnabled(True)
        self.resize(520, 300)
        self._existing_id: Optional[str] = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.points_spin = QSpinBox()
        self.points_spin.setRange(0, 5000)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(POINTS_MODES)
        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Optional notes")

        form.addRow("Choice name", self.name_edit)
        form.addRow("Points", self.points_spin)
        form.addRow("Points mode", self.mode_combo)
        form.addRow("Choice notes", self.note_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Please enter a choice name.")
            return
        self.accept()

    def set_choice(self, choice: Dict[str, Any]):
        self._existing_id = choice.get("id")
        self.name_edit.setText(choice.get("name", ""))
        self.points_spin.setValue(int(choice.get("points", 0)))
        mode = choice.get("points_mode", "flat")
        self.mode_combo.setCurrentText(mode if mode in POINTS_MODES else "flat")
        self.note_edit.setPlainText(choice.get("note", "") or "")

    def get_choice(self) -> Dict[str, Any]:
        return {
            "id": self._existing_id,
            "name": self.name_edit.text().strip(),
            "points": int(self.points_spin.value()),
            "points_mode": self.mode_combo.currentText(),
            "note": self.note_edit.toPlainText().strip(),
        }

class DedicatedTransportPicker(QDialog):
    def __init__(self, parent=None, transports: Optional[List[Dict[str, Any]]] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Dedicated Transport")
        self.setSizeGripEnabled(True)
        self.resize(520, 420)
        self._transports = transports or []
        self._selected_id: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a transport:"))
        self.list = QListWidget()
        for u in self._transports:
            nm = u.get("name", "Unnamed")
            uid = u.get("id", "")
            item = QListWidgetItem(nm)
            item.setData(Qt.UserRole, uid)
            self.list.addItem(item)
        layout.addWidget(self.list, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self):
        item = self.list.currentItem()
        if not item:
            QMessageBox.information(self, "No selection", "Pick a transport first.")
            return
        self._selected_id = item.data(Qt.UserRole)
        self.accept()

    @property
    def selected_id(self) -> Optional[str]:
        return self._selected_id

class MultiPickDialog(QDialog):
    def __init__(self, parent=None, title: str = "Select items", items: Optional[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 560)
        items = items or []
        layout = QVBoxLayout(self)
        
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter...")
        layout.addWidget(self.filter_edit)
        
        self.listw = QListWidget()
        self.listw.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.listw, stretch=1)
        
        self._all_items = list(items)
        self._populate()
        self.filter_edit.textChanged.connect(self._populate)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self):
        f = self.filter_edit.text().strip().lower()
        self.listw.clear()
        for it in sorted(self._all_items, key=lambda x: x.lower()):
            if f and f not in it.lower(): continue
            self.listw.addItem(it)

    def selected_items(self) -> List[str]:
        return [i.text() for i in self.listw.selectedItems()]

class SimpleItemDialog(QDialog):
    def __init__(self, parent=None, title: str = "Item"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.summary_edit = QTextEdit()
        self.summary_edit.setPlaceholderText("Short description/summary.")
        form.addRow("Name", self.name_edit)
        form.addRow("Summary", self.summary_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Please enter a name.")
            return
        self.accept()

    def set_data(self, name: str, data: Dict[str, Any]):
        self.name_edit.setText(name)
        self.summary_edit.setPlainText((data or {}).get("summary", "") or "")

    def get_data(self) -> Tuple[str, Dict[str, Any]]:
        return self.name_edit.text().strip(), {"summary": self.summary_edit.toPlainText().strip()}

class RuleDialog(SimpleItemDialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Rule")

class WeaponDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Weapon")
        self.resize(560, 420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.range_edit = QLineEdit()
        self.type_edit = QLineEdit()
        self.s_edit = QLineEdit()
        self.ap_edit = QLineEdit()
        self.notes_edit = QTextEdit()
        form.addRow("Weapon name", self.name_edit)
        form.addRow("Range", self.range_edit)
        form.addRow("Type", self.type_edit)
        form.addRow("S", self.s_edit)
        form.addRow("AP", self.ap_edit)
        form.addRow("Notes", self.notes_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Please enter a weapon name.")
            return
        self.accept()

    def set_data(self, name: str, data: Dict[str, Any]):
        self.name_edit.setText(name)
        d = data or {}
        self.range_edit.setText(str(d.get("range", "") or ""))
        self.type_edit.setText(str(d.get("type", "") or ""))
        self.s_edit.setText(str(d.get("S", "") or d.get("s", "") or ""))
        self.ap_edit.setText(str(d.get("AP", "") or d.get("ap", "") or ""))
        self.notes_edit.setPlainText(str(d.get("notes", "") or ""))

    def get_data(self) -> Tuple[str, Dict[str, Any]]:
        return self.name_edit.text().strip(), {
            "range": self.range_edit.text().strip(),
            "type": self.type_edit.text().strip(),
            "S": self.s_edit.text().strip(),
            "AP": self.ap_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }

class RulesManagerDialog(QDialog):
    def __init__(self, parent=None, codex_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Rules Catalog")
        self.resize(900, 560)
        self.codex_data = codex_data if codex_data is not None else {"rules": {}}
        self.codex_data.setdefault("rules", {})
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, stretch=1)
        left = QWidget()
        ll = QVBoxLayout(left)
        splitter.addWidget(left)
        self.listw = QListWidget()
        self.listw.currentItemChanged.connect(self._on_selected)
        ll.addWidget(QLabel("Rules"))
        ll.addWidget(self.listw, stretch=1)
        btns = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.edit_btn = QPushButton("Edit")
        self.del_btn = QPushButton("Delete")
        btns.addWidget(self.add_btn)
        btns.addWidget(self.edit_btn)
        btns.addWidget(self.del_btn)
        ll.addLayout(btns)
        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.del_btn.clicked.connect(self._delete)
        right = QWidget()
        rl = QVBoxLayout(right)
        splitter.addWidget(right)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        rl.addWidget(QLabel("Preview"))
        rl.addWidget(self.preview, stretch=1)
        splitter.setSizes([320, 580])
        root.addWidget(QDialogButtonBox(QDialogButtonBox.Close, accepted=self.accept, rejected=self.reject))
        self.refresh()

    def refresh(self):
        self.listw.clear()
        for name in sorted((self.codex_data.get("rules", {}) or {}).keys(), key=lambda x: x.lower()):
            self.listw.addItem(name)
        self.preview.setPlainText("")

    def _selected_name(self) -> Optional[str]:
        it = self.listw.currentItem()
        return it.text() if it else None

    def _on_selected(self):
        name = self._selected_name()
        if not name: return
        summary = ((self.codex_data.get("rules", {}) or {}).get(name, {}) or {}).get("summary", "")
        self.preview.setPlainText(f"{name}\n\n{summary}")

    def _add(self):
        dlg = RuleDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        name, data = dlg.get_data()
        self.codex_data.setdefault("rules", {})[name] = data
        self.refresh()

    def _edit(self):
        old = self._selected_name()
        if not old: return
        dlg = RuleDialog(self)
        dlg.set_data(old, self.codex_data.get("rules", {}).get(old, {}))
        if dlg.exec() != QDialog.Accepted: return
        name, data = dlg.get_data()
        if name != old: self.codex_data["rules"].pop(old, None)
        self.codex_data["rules"][name] = data
        self.refresh()

    def _delete(self):
        name = self._selected_name()
        if name and QMessageBox.question(self, "Delete?", f"Delete {name}?") == QMessageBox.Yes:
            self.codex_data["rules"].pop(name, None)
            self.refresh()

class WargearManagerDialog(RulesManagerDialog):
    def __init__(self, parent=None, codex_data=None):
        super().__init__(parent, codex_data)
        self.setWindowTitle("Wargear Catalog")
        if "wargear" not in self.codex_data: self.codex_data["wargear"] = {}

    def refresh(self):
        self.listw.clear()
        for name in sorted((self.codex_data.get("wargear", {}) or {}).keys(), key=lambda x: x.lower()):
            self.listw.addItem(name)
        self.preview.setPlainText("")

    def _on_selected(self):
        name = self._selected_name()
        if not name: return
        summary = ((self.codex_data.get("wargear", {}) or {}).get(name, {}) or {}).get("summary", "")
        self.preview.setPlainText(f"{name}\n\n{summary}")

    def _add(self):
        dlg = SimpleItemDialog(self, title="Wargear")
        if dlg.exec() != QDialog.Accepted: return
        name, data = dlg.get_data()
        self.codex_data.setdefault("wargear", {})[name] = data
        self.refresh()

    def _edit(self):
        old = self._selected_name()
        if not old: return
        dlg = SimpleItemDialog(self, title="Wargear")
        dlg.set_data(old, self.codex_data.get("wargear", {}).get(old, {}))
        if dlg.exec() != QDialog.Accepted: return
        name, data = dlg.get_data()
        if name != old: self.codex_data["wargear"].pop(old, None)
        self.codex_data["wargear"][name] = data
        self.refresh()
    
    def _delete(self):
        name = self._selected_name()
        if name and QMessageBox.question(self, "Delete?", f"Delete {name}?") == QMessageBox.Yes:
            self.codex_data["wargear"].pop(name, None)
            self.refresh()

class WeaponsManagerDialog(QDialog):
    def __init__(self, parent=None, codex_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle("Weapons Catalog")
        self.resize(980, 620)
        self.codex_data = codex_data if codex_data is not None else {"weapons": {}}
        self.codex_data.setdefault("weapons", {})
        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, stretch=1)
        left = QWidget()
        ll = QVBoxLayout(left)
        splitter.addWidget(left)
        self.listw = QListWidget()
        self.listw.currentItemChanged.connect(self._on_selected)
        ll.addWidget(QLabel("Weapons"))
        ll.addWidget(self.listw, stretch=1)
        btns = QHBoxLayout()
        self.add_btn = QPushButton("Add")
        self.edit_btn = QPushButton("Edit")
        self.del_btn = QPushButton("Delete")
        btns.addWidget(self.add_btn)
        btns.addWidget(self.edit_btn)
        btns.addWidget(self.del_btn)
        ll.addLayout(btns)
        self.add_btn.clicked.connect(self._add)
        self.edit_btn.clicked.connect(self._edit)
        self.del_btn.clicked.connect(self._delete)
        right = QWidget()
        rl = QVBoxLayout(right)
        splitter.addWidget(right)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        rl.addWidget(QLabel("Preview"))
        rl.addWidget(self.preview, stretch=1)
        splitter.setSizes([340, 640])
        root.addWidget(QDialogButtonBox(QDialogButtonBox.Close, accepted=self.accept, rejected=self.reject))
        self.refresh()

    def refresh(self):
        self.listw.clear()
        for name in sorted((self.codex_data.get("weapons", {}) or {}).keys(), key=lambda x: x.lower()):
            self.listw.addItem(name)
        self.preview.setPlainText("")

    def _selected_name(self):
        it = self.listw.currentItem()
        return it.text() if it else None

    def _on_selected(self):
        name = self._selected_name()
        if not name: return
        d = (self.codex_data.get("weapons", {}) or {}).get(name, {}) or {}
        self.preview.setPlainText(f"{name}\n\nRange: {d.get('range','')}\nType: {d.get('type','')}\nS: {d.get('S','')}\nAP: {d.get('AP','')}\nNotes: {d.get('notes','')}")

    def _add(self):
        dlg = WeaponDialog(self)
        if dlg.exec() != QDialog.Accepted: return
        name, data = dlg.get_data()
        self.codex_data.setdefault("weapons", {})[name] = data
        self.refresh()

    def _edit(self):
        old = self._selected_name()
        if not old: return
        dlg = WeaponDialog(self)
        dlg.set_data(old, self.codex_data.get("weapons", {}).get(old, {}))
        if dlg.exec() != QDialog.Accepted: return
        name, data = dlg.get_data()
        if name != old: self.codex_data["weapons"].pop(old, None)
        self.codex_data["weapons"][name] = data
        self.refresh()

    def _delete(self):
        name = self._selected_name()
        if name and QMessageBox.question(self, "Delete?", f"Delete {name}?") == QMessageBox.Yes:
            self.codex_data["weapons"].pop(name, None)
            self.refresh()

class UnitEditorDialog(QDialog):
    def __init__(self, parent=None, available_transports: Optional[List[Dict[str, Any]]] = None):
        super().__init__(parent)
        self.setWindowTitle("Unit Editor")
        self.setSizeGripEnabled(True)
        self.resize(900, 780)
        self._existing_id: Optional[str] = None
        self._options: List[Dict[str, Any]] = []
        self._available_transports = available_transports or []
        
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, stretch=1)
        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)

        # Basic Info
        form_box = QGroupBox("Basic Info")
        form = QFormLayout(form_box)
        self.name_edit = QLineEdit()
        self.slot_combo = QComboBox()
        self.slot_combo.addItems(SLOTS)
        self.base_points_spin = QSpinBox()
        self.base_points_spin.setRange(0, 5000)
        self.points_per_model_spin = QSpinBox()
        self.points_per_model_spin.setRange(0, 5000)
        self.min_size_spin = QSpinBox()
        self.min_size_spin.setRange(1, 50)
        self.min_size_spin.setValue(1)
        self.max_size_spin = QSpinBox()
        self.max_size_spin.setRange(1, 50)
        self.max_size_spin.setValue(1)
        self.default_size_spin = QSpinBox()
        self.default_size_spin.setRange(1, 50)
        self.default_size_spin.setValue(1)
        self.unit_type_edit = QLineEdit()
        self.is_transport_cb = QCheckBox("Is Transport Unit")
        self.leader_name_edit = QLineEdit()
        self.leader_name_edit.setPlaceholderText("Leave blank if no squad leader")
        self.dedicated_transport_list = QListWidget()
        self.dedicated_transport_list.setSelectionMode(QListWidget.MultiSelection)
        self._populate_transport_list()

        form.addRow("Unit Name", self.name_edit)
        form.addRow("Force Org Slot", self.slot_combo)
        form.addRow("Base Points (fixed)", self.base_points_spin)
        form.addRow("Points per Model", self.points_per_model_spin)
        size_row = QWidget()
        sl = QHBoxLayout(size_row)
        sl.addWidget(QLabel("Min")); sl.addWidget(self.min_size_spin)
        sl.addWidget(QLabel("Max")); sl.addWidget(self.max_size_spin)
        sl.addWidget(QLabel("Default")); sl.addWidget(self.default_size_spin)
        form.addRow("Squad Size", size_row)
        form.addRow("Unit Type", self.unit_type_edit)
        form.addRow("", self.is_transport_cb)
        form.addRow("Dedicated Transport(s)", self.dedicated_transport_list)
        form.addRow("Squad Leader Name", self.leader_name_edit)
        content_layout.addWidget(form_box)

        self.min_size_spin.valueChanged.connect(self._clamp_default_size)
        self.max_size_spin.valueChanged.connect(self._clamp_default_size)
        self.slot_combo.currentTextChanged.connect(self._on_slot_changed)
        self.is_transport_cb.stateChanged.connect(self._update_transport_enabled)

        # Profile
        profile_box = QGroupBox("Profile")
        pl = QVBoxLayout(profile_box)
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Profile Type"))
        self.profile_type_combo = QComboBox()
        self.profile_type_combo.addItems(PROFILE_TYPES)
        type_row.addWidget(self.profile_type_combo)
        pl.addLayout(type_row)
        self.profile_stack = QStackedWidget()
        pl.addWidget(self.profile_stack)

        # Standard Profile
        self.standard_profile_widget = QWidget()
        std_grid = QGridLayout(self.standard_profile_widget)
        std_grid.addWidget(QLabel("Stat"), 0, 0)
        std_grid.addWidget(QLabel("Base"), 0, 1)
        std_grid.addWidget(QLabel("Leader Mod"), 0, 2)
        self.base_stat = {}
        self.leader_mod = {}
        stats = ["WS", "BS", "S", "T", "W", "I", "A", "Ld"]
        for r, stat in enumerate(stats, start=1):
            b = QSpinBox(); b.setRange(0, 20)
            m = QSpinBox(); m.setRange(-10, 10)
            self.base_stat[stat] = b
            self.leader_mod[stat] = m
            std_grid.addWidget(QLabel(stat), r, 0)
            std_grid.addWidget(b, r, 1)
            std_grid.addWidget(m, r, 2)
        self.base_sv = QComboBox()
        self.base_sv.addItems(["2+", "3+", "4+", "5+", "6+", "-", "7+"])
        self.base_sv.setCurrentText("4+")
        self.leader_sv = QComboBox()
        self.leader_sv.addItems(["(same)"] + ["2+", "3+", "4+", "5+", "6+", "-", "7+"])
        self.leader_sv.setCurrentText("(same)")
        std_grid.addWidget(QLabel("Sv"), 9, 0)
        std_grid.addWidget(self.base_sv, 9, 1)
        std_grid.addWidget(self.leader_sv, 9, 2)
        self.profile_stack.addWidget(self.standard_profile_widget)

        # Vehicle Profile
        self.vehicle_profile_widget = QWidget()
        veh_grid = QGridLayout(self.vehicle_profile_widget)
        self.front_av = QSpinBox(); self.front_av.setRange(0, 14)
        self.side_av = QSpinBox(); self.side_av.setRange(0, 14)
        self.rear_av = QSpinBox(); self.rear_av.setRange(0, 14)
        self.vehicle_bs = QSpinBox(); self.vehicle_bs.setRange(0, 10)
        veh_grid.addWidget(QLabel("Front"), 0, 0); veh_grid.addWidget(self.front_av, 0, 1)
        veh_grid.addWidget(QLabel("Side"), 1, 0); veh_grid.addWidget(self.side_av, 1, 1)
        veh_grid.addWidget(QLabel("Rear"), 2, 0); veh_grid.addWidget(self.rear_av, 2, 1)
        veh_grid.addWidget(QLabel("BS"), 3, 0); veh_grid.addWidget(self.vehicle_bs, 3, 1)
        self.profile_stack.addWidget(self.vehicle_profile_widget)

        # Walker Profile
        self.walker_profile_widget = QWidget()
        wk_grid = QGridLayout(self.walker_profile_widget)
        self.walker_ws = QSpinBox(); self.walker_ws.setRange(0, 10)
        self.walker_bs = QSpinBox(); self.walker_bs.setRange(0, 10)
        self.walker_s = QSpinBox(); self.walker_s.setRange(0, 10)
        self.walker_i = QSpinBox(); self.walker_i.setRange(0, 10)
        self.walker_a = QSpinBox(); self.walker_a.setRange(0, 10)
        self.walker_front = QSpinBox(); self.walker_front.setRange(0, 14)
        self.walker_side = QSpinBox(); self.walker_side.setRange(0, 14)
        self.walker_rear = QSpinBox(); self.walker_rear.setRange(0, 14)
        wk_grid.addWidget(QLabel("WS"),0,0); wk_grid.addWidget(self.walker_ws,0,1)
        wk_grid.addWidget(QLabel("BS"),0,2); wk_grid.addWidget(self.walker_bs,0,3)
        wk_grid.addWidget(QLabel("S"),1,0); wk_grid.addWidget(self.walker_s,1,1)
        wk_grid.addWidget(QLabel("I"),1,2); wk_grid.addWidget(self.walker_i,1,3)
        wk_grid.addWidget(QLabel("A"),2,0); wk_grid.addWidget(self.walker_a,2,1)
        wk_grid.addWidget(QLabel("Front"),3,0); wk_grid.addWidget(self.walker_front,3,1)
        wk_grid.addWidget(QLabel("Side"),3,2); wk_grid.addWidget(self.walker_side,3,3)
        wk_grid.addWidget(QLabel("Rear"),4,0); wk_grid.addWidget(self.walker_rear,4,1)
        self.profile_stack.addWidget(self.walker_profile_widget)
        content_layout.addWidget(profile_box)
        self.profile_type_combo.currentTextChanged.connect(self._on_profile_type_changed)
        self.leader_name_edit.textChanged.connect(self._update_leader_enabled)

        # Wargear / Rules
        text_box = QGroupBox("Wargear / Special Rules")
        grid = QGridLayout(text_box)
        grid.addWidget(QLabel("Wargear"), 0, 0)
        self.wargear_list = QListWidget()
        self.wargear_list.setSelectionMode(QListWidget.ExtendedSelection)
        grid.addWidget(self.wargear_list, 1, 0)
        self.pick_wargear_btn = QPushButton("Add from Catalog...")
        self.pick_wargear_btn.clicked.connect(self._pick_wargear)
        self.remove_wargear_btn = QPushButton("Remove")
        self.remove_wargear_btn.clicked.connect(lambda: self._remove_selected(self.wargear_list))
        wb = QHBoxLayout(); wb.addWidget(self.pick_wargear_btn); wb.addWidget(self.remove_wargear_btn)
        grid.addLayout(wb, 2, 0)

        grid.addWidget(QLabel("Special Rules"), 0, 1)
        self.rules_list = QListWidget()
        self.rules_list.setSelectionMode(QListWidget.ExtendedSelection)
        grid.addWidget(self.rules_list, 1, 1)
        self.pick_rules_btn = QPushButton("Add from Catalog...")
        self.pick_rules_btn.clicked.connect(self._pick_rules)
        self.remove_rules_btn = QPushButton("Remove")
        self.remove_rules_btn.clicked.connect(lambda: self._remove_selected(self.rules_list))
        rb = QHBoxLayout(); rb.addWidget(self.pick_rules_btn); rb.addWidget(self.remove_rules_btn)
        grid.addLayout(rb, 2, 1)
        content_layout.addWidget(text_box)

        # Options Builder
        opt_box = QGroupBox("Options Builder")
        ol = QVBoxLayout(opt_box)
        splitter = QSplitter(Qt.Horizontal)
        ol.addWidget(splitter, stretch=1)
        
        group_panel = QWidget()
        gl = QVBoxLayout(group_panel)
        gl.addWidget(QLabel("Option Groups"))
        self.group_list = QListWidget()
        self.group_list.currentItemChanged.connect(self._on_group_selected)
        gl.addWidget(self.group_list)
        gb = QHBoxLayout()
        self.add_group_btn = QPushButton("Add")
        self.edit_group_btn = QPushButton("Edit")
        self.del_group_btn = QPushButton("Delete")
        self.add_group_btn.clicked.connect(self._add_group)
        self.edit_group_btn.clicked.connect(self._edit_group)
        self.del_group_btn.clicked.connect(self._delete_group)
        gb.addWidget(self.add_group_btn); gb.addWidget(self.edit_group_btn); gb.addWidget(self.del_group_btn)
        gl.addLayout(gb)
        splitter.addWidget(group_panel)

        choice_panel = QWidget()
        cl = QVBoxLayout(choice_panel)
        cl.addWidget(QLabel("Choices"))
        self.choice_list = QListWidget()
        cl.addWidget(self.choice_list)
        cb = QHBoxLayout()
        self.add_choice_btn = QPushButton("Add")
        self.edit_choice_btn = QPushButton("Edit")
        self.del_choice_btn = QPushButton("Delete")
        self.add_choice_btn.clicked.connect(self._add_choice)
        self.edit_choice_btn.clicked.connect(self._edit_choice)
        self.del_choice_btn.clicked.connect(self._delete_choice)
        cb.addWidget(self.add_choice_btn); cb.addWidget(self.edit_choice_btn); cb.addWidget(self.del_choice_btn)
        cl.addLayout(cb)
        splitter.addWidget(choice_panel)
        content_layout.addWidget(opt_box)

        # Free text options
        free_box = QGroupBox("Options (free text)")
        fl = QVBoxLayout(free_box)
        self.options_text_edit = QTextEdit()
        fl.addWidget(self.options_text_edit)
        content_layout.addWidget(free_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        
        self._clamp_default_size()
        self._on_slot_changed()
        self._on_profile_type_changed()
        self._update_leader_enabled()

    def _populate_transport_list(self):
        self.dedicated_transport_list.clear()
        for u in self._available_transports:
            item = QListWidgetItem(u.get("name", "Unnamed"))
            item.setData(Qt.UserRole, u.get("id"))
            self.dedicated_transport_list.addItem(item)

    def _on_slot_changed(self):
        is_dedicated = (self.slot_combo.currentText() == "Dedicated Transport")
        if is_dedicated:
            self.is_transport_cb.setChecked(True)
            self.is_transport_cb.setEnabled(False)
        else:
            self.is_transport_cb.setEnabled(True)
        self._update_transport_enabled()

    def _update_transport_enabled(self):
        is_transport = self.is_transport_cb.isChecked()
        self.dedicated_transport_list.setEnabled(not is_transport)
        if is_transport: self.dedicated_transport_list.clearSelection()

    def _clamp_default_size(self):
        mn = self.min_size_spin.value()
        mx = self.max_size_spin.value()
        if mn > mx:
            self.max_size_spin.setValue(mn)
            mx = mn
        self.default_size_spin.setRange(mn, mx)

    def _on_profile_type_changed(self):
        p = self.profile_type_combo.currentText()
        if p == "Standard": self.profile_stack.setCurrentIndex(0)
        elif p == "Vehicle": self.profile_stack.setCurrentIndex(1)
        else: self.profile_stack.setCurrentIndex(2)
        self.leader_name_edit.setEnabled(p == "Standard")
        self._update_leader_enabled()

    def _update_leader_enabled(self):
        enabled = self.leader_name_edit.isEnabled() and bool(self.leader_name_edit.text().strip())
        for m in self.leader_mod.values(): m.setEnabled(enabled)
        self.leader_sv.setEnabled(enabled)

    def _refresh_group_list(self):
        self.group_list.clear()
        for g in self._options:
            item = QListWidgetItem(f"{g.get('group_name')} ({g.get('min_select')}–{g.get('max_select')})")
            item.setData(Qt.UserRole, g.get("group_id"))
            self.group_list.addItem(item)
        self.choice_list.clear()

    def _get_group_by_id(self, gid):
        for g in self._options:
            if g.get("group_id") == gid: return g
        return None

    def _selected_group(self):
        item = self.group_list.currentItem()
        return self._get_group_by_id(item.data(Qt.UserRole)) if item else None

    def _on_group_selected(self):
        self.choice_list.clear()
        g = self._selected_group()
        if not g: return
        for c in g.get("choices", []):
            item = QListWidgetItem(f"{c.get('name')} (+{c.get('points')})")
            item.setData(Qt.UserRole, c.get("id"))
            self.choice_list.addItem(item)
    
    def _add_group(self):
        dlg = OptionGroupDialog(self)
        if dlg.exec() == QDialog.Accepted:
            g = dlg.get_group()
            g["group_id"] = unique_id(slugify(g["group_name"]), {x.get("group_id") for x in self._options})
            self._options.append(g)
            self._refresh_group_list()

    def _edit_group(self):
        g = self._selected_group()
        if not g: return
        dlg = OptionGroupDialog(self)
        dlg.set_group(g)
        if dlg.exec() == QDialog.Accepted:
            new_g = dlg.get_group()
            new_g["group_id"] = g["group_id"]
            new_g["choices"] = g.get("choices", [])
            for i, x in enumerate(self._options):
                if x["group_id"] == g["group_id"]: self._options[i] = new_g
            self._refresh_group_list()

    def _delete_group(self):
        g = self._selected_group()
        if g:
            self._options = [x for x in self._options if x["group_id"] != g["group_id"]]
            self._refresh_group_list()

    def _selected_choice(self):
        g = self._selected_group()
        item = self.choice_list.currentItem()
        if not g or not item: return g, None
        cid = item.data(Qt.UserRole)
        for c in g.get("choices", []):
            if c.get("id") == cid: return g, c
        return g, None

    def _add_choice(self):
        g = self._selected_group()
        if not g: return
        dlg = OptionChoiceDialog(self)
        if dlg.exec() == QDialog.Accepted:
            c = dlg.get_choice()
            c["id"] = unique_id(slugify(c["name"]), {x.get("id") for x in g.get("choices", [])})
            g.setdefault("choices", []).append(c)
            self._on_group_selected()

    def _edit_choice(self):
        g, c = self._selected_choice()
        if not c: return
        dlg = OptionChoiceDialog(self)
        dlg.set_choice(c)
        if dlg.exec() == QDialog.Accepted:
            new_c = dlg.get_choice()
            new_c["id"] = c["id"]
            for i, x in enumerate(g["choices"]):
                if x["id"] == c["id"]: g["choices"][i] = new_c
            self._on_group_selected()
            
    def _delete_choice(self):
        g, c = self._selected_choice()
        if c:
            g["choices"] = [x for x in g["choices"] if x["id"] != c["id"]]
            self._on_group_selected()

    def _on_save(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Enter a unit name.")
            return
        self.accept()

    def set_unit(self, unit):
        self._existing_id = unit.get("id")
        self.name_edit.setText(unit.get("name", ""))
        self.slot_combo.setCurrentText(unit.get("slot", "HQ"))
        self.base_points_spin.setValue(int(unit.get("base_points", 0)))
        self.points_per_model_spin.setValue(int(unit.get("points_per_model", 0)))
        self.min_size_spin.setValue(int(unit.get("min_size", 1)))
        self.max_size_spin.setValue(int(unit.get("max_size", 1)))
        self.default_size_spin.setValue(int(unit.get("default_size", 1)))
        self.unit_type_edit.setText(unit.get("unit_type", ""))
        self.is_transport_cb.setChecked(bool(unit.get("is_transport", False)))
        
        sel_dt = set(unit.get("dedicated_transports", []))
        for i in range(self.dedicated_transport_list.count()):
            it = self.dedicated_transport_list.item(i)
            it.setSelected(it.data(Qt.UserRole) in sel_dt)

        prof = unit.get("profile", {}) or {}
        ptype = unit.get("profile_type", "standard")
        self.profile_type_combo.setCurrentText("Vehicle" if ptype == "vehicle" else "Walker" if ptype == "walker" else "Standard")
        self._on_profile_type_changed()
        
        if ptype == "vehicle":
            self.front_av.setValue(int(prof.get("Front", 0)))
            self.side_av.setValue(int(prof.get("Side", 0)))
            self.rear_av.setValue(int(prof.get("Rear", 0)))
            self.vehicle_bs.setValue(int(prof.get("BS", 0)))
        elif ptype == "walker":
            self.walker_ws.setValue(int(prof.get("WS", 0)))
            self.walker_bs.setValue(int(prof.get("BS", 0)))
            self.walker_s.setValue(int(prof.get("S", 0)))
            self.walker_i.setValue(int(prof.get("I", 0)))
            self.walker_a.setValue(int(prof.get("A", 0)))
            self.walker_front.setValue(int(prof.get("Front", 0)))
            self.walker_side.setValue(int(prof.get("Side", 0)))
            self.walker_rear.setValue(int(prof.get("Rear", 0)))
        else:
            for k, v in self.base_stat.items(): v.setValue(int(prof.get(k, 0)))
            self.base_sv.setCurrentText(prof.get("Sv", "4+"))
            leader = unit.get("leader", {})
            self.leader_name_edit.setText(leader.get("name", ""))
            mods = leader.get("modifiers", {})
            for k, v in self.leader_mod.items(): v.setValue(int(mods.get(k, 0)))
            self.leader_sv.setCurrentText(leader.get("sv_override", "(same)"))
            
        self.wargear_list.clear()
        self.wargear_list.addItems(unit.get("wargear", []))
        self.rules_list.clear()
        self.rules_list.addItems(unit.get("special_rules", []))
        self.options_text_edit.setPlainText(list_to_lines(unit.get("options_text", [])))
        self._options = unit.get("options", [])
        self._refresh_group_list()

    def get_unit(self):
        unit = {
            "id": self._existing_id,
            "name": self.name_edit.text().strip(),
            "slot": self.slot_combo.currentText(),
            "base_points": self.base_points_spin.value(),
            "points_per_model": self.points_per_model_spin.value(),
            "min_size": self.min_size_spin.value(),
            "max_size": self.max_size_spin.value(),
            "default_size": self.default_size_spin.value(),
            "unit_type": self.unit_type_edit.text().strip(),
            "is_transport": self.is_transport_cb.isChecked(),
            "dedicated_transports": [],
            "wargear": [self.wargear_list.item(i).text() for i in range(self.wargear_list.count())],
            "special_rules": [self.rules_list.item(i).text() for i in range(self.rules_list.count())],
            "options_text": lines_to_list(self.options_text_edit.toPlainText()),
            "options": self._options
        }
        if not unit["is_transport"]:
            unit["dedicated_transports"] = [i.data(Qt.UserRole) for i in self.dedicated_transport_list.selectedItems()]
            
        ptype = self.profile_type_combo.currentText()
        if ptype == "Vehicle":
            unit["profile_type"] = "vehicle"
            unit["profile"] = {"Front": self.front_av.value(), "Side": self.side_av.value(), "Rear": self.rear_av.value(), "BS": self.vehicle_bs.value()}
        elif ptype == "Walker":
            unit["profile_type"] = "walker"
            unit["profile"] = {"WS": self.walker_ws.value(), "BS": self.walker_bs.value(), "S": self.walker_s.value(), "I": self.walker_i.value(), "A": self.walker_a.value(), "Front": self.walker_front.value(), "Side": self.walker_side.value(), "Rear": self.walker_rear.value()}
        else:
            unit["profile_type"] = "standard"
            unit["profile"] = {k: v.value() for k, v in self.base_stat.items()}
            unit["profile"]["Sv"] = self.base_sv.currentText()
            if self.leader_name_edit.text().strip():
                unit["leader"] = {
                    "name": self.leader_name_edit.text().strip(),
                    "modifiers": {k: v.value() for k, v in self.leader_mod.items()},
                    "sv_override": "" if self.leader_sv.currentText() == "(same)" else self.leader_sv.currentText()
                }
        return unit

    def _add_unique_to_list(self, listw, items):
        existing = {listw.item(i).text() for i in range(listw.count())}
        for i in items:
            if i not in existing: listw.addItem(i)

    def _remove_selected(self, listw):
        for item in listw.selectedItems():
            listw.takeItem(listw.row(item))

    def _pick_wargear(self):
        items = sorted(list((self.parent().codex_data.get("weapons", {})).keys()) + list((self.parent().codex_data.get("wargear", {})).keys()))
        dlg = MultiPickDialog(self, "Select Wargear", items)
        if dlg.exec() == QDialog.Accepted:
            self._add_unique_to_list(self.wargear_list, dlg.selected_items())

    def _pick_rules(self):
        items = sorted(list((self.parent().codex_data.get("rules", {})).keys()))
        dlg = MultiPickDialog(self, "Select Rules", items)
        if dlg.exec() == QDialog.Accepted:
            self._add_unique_to_list(self.rules_list, dlg.selected_items())

class DedicatedTransportPicker(QDialog):
    def __init__(self, parent=None, transports: Optional[List[Dict[str, Any]]] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Dedicated Transport")
        self.setSizeGripEnabled(True)
        self.resize(300, 100)
        self._transports = transports or []
        self._selected_id: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a transport:"))
        
        self.combo = QComboBox()
        for u in self._transports:
            self.combo.addItem(u.get("name", "Unnamed"), u.get("id"))
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_ok(self):
        if self.combo.count() == 0:
            self.reject()
            return
        self._selected_id = self.combo.currentData()
        self.accept()

    @property
    def selected_id(self) -> Optional[str]:
        return self._selected_id