from pathlib import Path
import json
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "py_remote_input" / "templates" / "index.html"


class FrontendTests(unittest.TestCase):
    def run_insert_helper(self, current, inserted, start, end):
        script = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const marker = "function insertTextAtSelection";
const start = source.indexOf(marker);
if (start < 0) throw new Error("insertTextAtSelection is missing");
const end = source.indexOf("\n    function ", start + marker.length);
const helper = source.slice(start, end < 0 ? source.length : end);
const current = JSON.parse(process.argv[2]);
const inserted = JSON.parse(process.argv[3]);
const selectionStart = process.argv[4] === "null" ? null : Number(process.argv[4]);
const selectionEnd = process.argv[5] === "null" ? null : Number(process.argv[5]);
const context = { current, inserted, selectionStart, selectionEnd };
vm.runInNewContext(
  helper + "\nthis.result = insertTextAtSelection(current, inserted, selectionStart, selectionEnd);",
  context,
);
process.stdout.write(JSON.stringify(context.result));
"""
        args = [str(TEMPLATE), json.dumps(current), json.dumps(inserted)]
        args.extend("null" if value is None else str(value) for value in (start, end))
        completed = subprocess.run(
            ["node", "-e", script, *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_history_text_is_inserted_at_caret(self):
        self.assertEqual(
            self.run_insert_helper("hello", "X", 2, 2),
            {"text": "heXllo", "selectionStart": 3, "selectionEnd": 3},
        )

    def test_history_text_replaces_selected_range(self):
        self.assertEqual(
            self.run_insert_helper("hello", "X", 1, 4),
            {"text": "hXo", "selectionStart": 2, "selectionEnd": 2},
        )

    def test_history_text_appends_when_selection_is_unavailable(self):
        self.assertEqual(
            self.run_insert_helper("hello", "X", None, None),
            {"text": "helloX", "selectionStart": 6, "selectionEnd": 6},
        )

    def run_send_or_enter(self, current, sending):
        script = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync(process.argv[1], "utf8");
const marker = "function sendOrEnter";
const start = source.indexOf(marker);
if (start < 0) throw new Error("sendOrEnter is missing");
const end = source.indexOf("\n    function ", start + marker.length);
const helper = source.slice(start, end < 0 ? source.length : end);
const calls = [];
const context = { calls, getComposerText: () => process.argv[2], sendText: () => calls.push("send"), syncKey: (key) => calls.push(key), setStatus: () => {} };
vm.runInNewContext(
  "let pendingEnterAfterSend = false; let sending = " + JSON.stringify(process.argv[3] === "true") + ";\n" +
  helper +
  "\nsendOrEnter(); this.result = { calls, pendingEnterAfterSend };",
  context,
);
process.stdout.write(JSON.stringify(context.result));
"""
        completed = subprocess.run(
            ["node", "-e", script, str(TEMPLATE), current, str(sending).lower()],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_fast_second_send_click_queues_enter_after_current_send(self):
        self.assertEqual(
            self.run_send_or_enter("已有内容", True),
            {"calls": [], "pendingEnterAfterSend": True},
        )

    def test_send_button_still_sends_when_not_already_sending(self):
        self.assertEqual(
            self.run_send_or_enter("已有内容", False),
            {"calls": ["send"], "pendingEnterAfterSend": False},
        )

if __name__ == "__main__":
    unittest.main()
