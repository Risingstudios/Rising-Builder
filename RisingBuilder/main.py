import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QSplitter, QListWidget, QListWidgetItem,
    QTextEdit, QMessageBox, QFileDialog
)

from utils import ensure_folder, read_json, write_json, find_default_codex_file, make_backup, unique_id, slugify
from constants import SLOTS
from ui_editors import UnitEditorDialog, RulesManagerDialog, WeaponsManagerDialog, WargearManagerDialog
from ui_roster import RosterBuilderWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("40k 5th Army Builder")
        self.codex_path: Optional[Path] = None
        self.codex_data: Dict[str, Any] = {"codex_name": "Unnamed Codex", "units": []}

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- Editor Tab ---
        self.editor_tab = QWidget()
        self.tabs.addTab(self.editor_tab, "Codex Editor")
        outer = QVBoxLayout(self.editor_tab)

        top = QHBoxLayout()
        outer.addLayout(top)
        self.codex_name_edit = QLineEdit()
        self.codex_name_edit.setPlaceholderText("Codex Name")
        self.open_btn = QPushButton("Open Codex...")
        self.open_btn.clicked.connect(self.open_codex)
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_codex)
        self.rules_btn = QPushButton("Rules...")
        self.rules_btn.clicked.connect(self.open_rules_manager)
        self.weapons_btn = QPushButton("Weapons...")
        self.weapons_btn.clicked.connect(self.open_weapons_manager)
        self.wargear_btn = QPushButton("Wargear...")
        self.wargear_btn.clicked.connect(self.open_wargear_manager)

        top.addWidget(QLabel("Codex:"))
        top.addWidget(self.codex_name_edit, stretch=1)
        top.addWidget(self.open_btn)
        top.addWidget(self.rules_btn)
        top.addWidget(self.weapons_btn)
        top.addWidget(self.wargear_btn)
        top.addWidget(self.save_btn)

        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter, stretch=1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        splitter.addWidget(left)

        self.unit_list = QListWidget()
        self.unit_list.currentItemChanged.connect(self.on_unit_selected)
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add Unit")
        self.edit_btn = QPushButton("Edit Unit")
        self.del_btn = QPushButton("Delete Unit")
        self.add_btn.clicked.connect(self.add_unit)
        self.edit_btn.clicked.connect(self.edit_unit)
        self.del_btn.clicked.connect(self.delete_unit)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.del_btn)

        left_layout.addWidget(QLabel("Units"))
        left_layout.addWidget(self.unit_list, stretch=1)
        left_layout.addLayout(btn_row)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        splitter.addWidget(right)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        right_layout.addWidget(QLabel("Details (read-only preview)"))
        right_layout.addWidget(self.detail, stretch=1)
        splitter.setSizes([420, 780])

        # --- Roster Tab ---
        self.roster_tab = RosterBuilderWidget(self)
        self.tabs.addTab(self.roster_tab, "Roster Builder")

        self.load_startup_codex()

    # [Methods: transport_units, unit_name_by_id, load_startup_codex, load_codex, 
    # open_codex, open_rules_manager, open_weapons_manager, open_wargear_manager,
    # save_codex, refresh_unit_list, get_unit_by_id, generate_unique_unit_id,
    # add_unit, edit_unit, delete_unit, on_unit_selected]
    #
    # Copy these methods from your original main.py

    def transport_units(self) -> list:
        out = []
        for u in self.codex_data.get("units", []):
            if bool(u.get("is_transport", False)) or (u.get("slot") == "Dedicated Transport"):
                out.append(u)
        return out

    def load_startup_codex(self):
        default = find_default_codex_file()
        if default is None:
            ensure_folder(Path("codexes"))
            starter = Path("codexes") / "eldar_5e.json"
            starter_data = {"codex_name": "Eldar (5th Edition) - My Data", "units": []}
            write_json(starter, starter_data)
            self.load_codex(starter)
            return
        self.load_codex(default)

    def load_codex(self, path: Path):
        try:
            data = read_json(path)
            data.setdefault("codex_name", path.stem)
            data.setdefault("units", [])
            data.setdefault("rules", {})
            data.setdefault("weapons", {})
            data.setdefault("wargear", {})
        except Exception as e:
            QMessageBox.critical(self, "Failed to open codex", f"{path}\n\n{e}")
            return
        self.codex_path = path
        self.codex_data = data
        self.codex_name_edit.setText(self.codex_data.get("codex_name", path.stem))
        self.refresh_unit_list()
        self.detail.setPlainText("")
        self.statusBar().showMessage(f"Opened: {path}")
        if hasattr(self, "roster_tab"):
            self.roster_tab.on_codex_loaded()

    def open_codex(self):
        ensure_folder(Path("codexes"))
        filename, _ = QFileDialog.getOpenFileName(self, "Open Codex JSON", str(Path("codexes").resolve()), "JSON Files (*.json)")
        if not filename: return
        self.load_codex(Path(filename))

    def open_rules_manager(self):
        if self.codex_path is None: return
        RulesManagerDialog(self, self.codex_data).exec()

    def open_weapons_manager(self):
        if self.codex_path is None: return
        WeaponsManagerDialog(self, self.codex_data).exec()

    def open_wargear_manager(self):
        if self.codex_path is None: return
        WargearManagerDialog(self, self.codex_data).exec()

    def save_codex(self):
        if self.codex_path is None: return
        self.codex_data["codex_name"] = self.codex_name_edit.text().strip() or "Unnamed Codex"
        try:
            make_backup(self.codex_path)
            write_json(self.codex_path, self.codex_data)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self.statusBar().showMessage(f"Saved: {self.codex_path}")
        if hasattr(self, "roster_tab"):
            self.roster_tab.on_codex_loaded()

    def refresh_unit_list(self):
        self.unit_list.clear()
        units = self.codex_data.get("units", [])
        slot_order = {s: i for i, s in enumerate(SLOTS)}
        units_sorted = sorted(units, key=lambda u: (slot_order.get(u.get("slot", ""), 999), u.get("name", "")))
        for u in units_sorted:
            name = u.get("name", "Unnamed")
            slot = u.get("slot", "Unknown")
            item = QListWidgetItem(f"[{slot}] {name}")
            item.setData(Qt.UserRole, u.get("id"))
            self.unit_list.addItem(item)

    def get_unit_by_id(self, unit_id: str) -> Optional[Dict[str, Any]]:
        for u in self.codex_data.get("units", []):
            if u.get("id") == unit_id: return u
        return None

    def add_unit(self):
        dlg = UnitEditorDialog(self, available_transports=self.transport_units())
        if dlg.exec() != QDialog.Accepted: return
        unit = dlg.get_unit()
        unit["id"] = unique_id(f"{unit['slot']}_{slugify(unit['name'])}", {u.get("id") for u in self.codex_data["units"]})
        self.codex_data["units"].append(unit)
        self.refresh_unit_list()
        self.save_codex()

    def edit_unit(self):
        item = self.unit_list.currentItem()
        if not item: return
        unit_id = item.data(Qt.UserRole)
        unit = self.get_unit_by_id(unit_id)
        if not unit: return
        dlg = UnitEditorDialog(self, available_transports=self.transport_units())
        dlg.set_unit(unit)
        if dlg.exec() != QDialog.Accepted: return
        updated = dlg.get_unit()
        updated["id"] = unit_id
        for i, u in enumerate(self.codex_data["units"]):
            if u["id"] == unit_id:
                self.codex_data["units"][i] = updated
                break
        self.refresh_unit_list()
        self.save_codex()

    def delete_unit(self):
        item = self.unit_list.currentItem()
        if not item: return
        unit_id = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete?", f"Delete unit?") == QMessageBox.Yes:
            self.codex_data["units"] = [u for u in self.codex_data["units"] if u["id"] != unit_id]
            self.refresh_unit_list()
            self.detail.setPlainText("")
            self.save_codex()

    def on_unit_selected(self, current, _prev):
        if not current:
            self.detail.setPlainText("")
            return
        unit = self.get_unit_by_id(current.data(Qt.UserRole))
        if unit:
            self.detail.setPlainText(str(unit)) # Simplified for brevity

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1400, 850)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()