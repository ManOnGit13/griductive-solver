"""Tk integration checks. Requires a desktop session with Tk available."""

from pathlib import Path
import sys
import tempfile
import time
import gc
import tkinter as tk
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gui import GriductiveApp, PUZZLES


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.app = GriductiveApp(self.root)
        self.wait_idle()

    def tearDown(self):
        self.app.close()
        self.app = None
        self.root = None
        # Dispose Tk cycles on the main thread before the next test starts workers.
        gc.collect()

    def wait_idle(self):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            self.root.update()
            if not self.app.busy and not self.app.auto_running:
                self.assertFalse(self.errors)
                return
            time.sleep(0.01)
        self.fail("GUI task did not finish within 10 seconds")

    def test_manual_verdict_hint_and_clue_selection(self):
        app = self.app
        self.assertEqual(len(app.cards), 9)
        app.select_cell("A1")
        app.submit("CRIMINAL")
        self.wait_idle()
        self.assertIn("CONTRADICTED", app.message.get())
        self.assertEqual(len(app.state.known), 1)
        app.show_hint()
        self.wait_idle()
        self.assertEqual(app.selected, "A1")
        self.assertEqual(len(app.state.known), 1)
        app.submit("INNOCENT")
        self.wait_idle()
        self.assertIn("ACCEPTED", app.message.get())
        app.clue_tree.selection_set("0")
        app.select_clue()
        self.assertEqual(app.highlights, {"A1", "C1", "C2"})

    def test_auto_solve_trace_and_restart(self):
        app = self.app
        app.next_step()
        self.wait_idle()
        self.assertEqual(len(app.trace), 1)
        self.assertIn("UNSAT", app.trace_detail.get("1.0", "end"))
        app.start_auto()
        self.wait_idle()
        self.assertTrue(app.state.solved)
        self.assertEqual(len(app.trace), 8)
        app.restart()
        self.assertEqual(len(app.state.known), 1)
        self.assertEqual(app.trace, [])

    def test_board_sizes_and_failed_load_preserves_current_game(self):
        app = self.app
        app.load(PUZZLES / "puzzle_5x5_stress.json")
        self.wait_idle()
        self.assertEqual(len(app.cards), 25)
        app.load(PUZZLES / "sample_3x3.json")
        self.wait_idle()
        self.assertEqual(len(app.cards), 9)
        self.assertEqual(app.board.grid_columnconfigure(5)["weight"], 0)
        initial = app.engine.public_state()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "broken.json"
            path.write_text('{"size":3,"characters":[]}', encoding="utf-8")
            app.load(path)
            self.wait_idle()
        self.assertIn("Lỗi:", app.message.get())
        self.assertEqual(app.engine.public_state(), initial)

    def test_mark_dialog_and_optional_inspector(self):
        app = self.app
        initial = app.engine.public_state()
        self.assertFalse(app.analysis_visible)

        app.mark_mode.set(True)
        app._card_clicked("A1")
        self.assertIn("A1", app.marked)
        self.assertIsNone(app.verdict_dialog)
        self.assertEqual(app.engine.public_state(), initial)
        app._card_clicked("A1")
        self.assertNotIn("A1", app.marked)
        app.mark_mode.set(False)
        app._card_clicked("A1")
        self.assertIsNotNone(app.verdict_dialog)
        self.assertEqual(app.engine.public_state(), initial)
        app._dismiss_dialog()
        self.assertIsNone(app.verdict_dialog)
        app._card_clicked("B2")
        self.assertTrue(app.analysis_visible)
        self.assertEqual(app.highlights, {"A1", "C1", "C2"})
        app.toggle_analysis(False)
        self.assertFalse(app.analysis_visible)

    def test_size_selection_new_game_and_transient_feedback(self):
        app = self.app
        for size in (4, 5, 3):
            app.size_name.set(f"{size} × {size}")
            app.size_picker.event_generate("<<ComboboxSelected>>")
            self.wait_idle()
            self.assertEqual(app.state.size, size)
            self.assertEqual(len(app.cards), size * size)
        current_path = app.current_path
        app.new_game()
        self.wait_idle()
        self.assertNotEqual(app.current_path, current_path)
        self.assertEqual(app.state.size, 3)
        app.select_cell("A1")
        app._notify("NOT_PROVABLE • Chưa đủ dữ kiện.", error=True)
        self.root.update_idletasks()
        self.assertEqual(app.toast.winfo_manager(), "place")
        self.root.after_cancel(app.toast_job)
        app._hide_toast()
        self.assertEqual(app.toast.winfo_manager(), "")
        self.assertFalse(hasattr(app, "detail_label"))
        self.assertFalse(hasattr(app, "message_label"))

    def test_statistics_on_demand_follow_selected_step_and_restart(self):
        app = self.app
        self.assertIsNone(app.statistics_dialog)

        self.assertEqual(app.event_text.frame.winfo_manager(), "")
        app.next_step()
        self.wait_idle()
        detail = app.trace_detail.get("1.0", "end")
        self.assertIn("UNSAT", detail)
        self.assertNotIn("sat_calls", detail)
        self.assertNotIn("runtime_ms", detail)
        app.show_statistics()
        dialog = app.statistics_dialog
        app.show_statistics()
        self.assertIs(app.statistics_dialog, dialog)
        self.assertIn("Bước 1", app.statistics_context.get())
        rows = [app.statistics_table.item(i, "values")
                for i in app.statistics_table.get_children()]
        calls = next(row for row in rows if row[0] == "Lần gọi SAT")
        self.assertEqual(int(calls[1]), app.run_totals["sat_calls"])
        self.assertEqual(int(calls[2]), app.trace[0]["solver_stats"]["sat_calls"])
        app.toggle_log()
        self.assertEqual(app.event_text.frame.winfo_manager(), "pack")
        app.toggle_log()
        self.assertEqual(app.event_text.frame.winfo_manager(), "")
        app.restart()
        self.assertIn("Chưa chọn bước", app.statistics_context.get())
        rows = [app.statistics_table.item(i, "values")
                for i in app.statistics_table.get_children()]
        calls = next(row for row in rows if row[0] == "Lần gọi SAT")
        self.assertEqual(calls[1:], ("0", "—"))
        app._close_statistics()
        self.assertIsNone(app.statistics_dialog)

    def test_card_fonts_survive_collection_and_clue_does_not_overlap_status(self):
        app = self.app
        gc.collect()
        self.root.update_idletasks()
        card = app.cards["B2"]
        font_name = card.itemcget(card.clue_item, "font")
        self.assertIn(font_name, self.root.tk.call("font", "names"))
        self.assertEqual(card.clue_font.actual("family"), app.fonts.family)
        clue_box = card.bbox(card.clue_item)
        status_box = card.bbox(card.status_item)
        self.assertLess(clue_box[3], status_box[1])
        self.assertGreaterEqual(clue_box[0], 0)
        self.assertLessEqual(clue_box[2], int(card.cget("width")))
        self.assertGreaterEqual(app.fonts.small.actual("size"), 9)


if __name__ == "__main__":
    unittest.main()
