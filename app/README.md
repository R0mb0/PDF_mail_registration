# Registration Manager (desktop app)

Local desktop application (PySide6 / Qt) that reads the filled-in PDF
registration forms produced by `LaTeX_Template/`, extracts their AcroForm
field values, lets you clean/filter the resulting table, and exports it to
CSV / Excel / SQL / plain text -- entirely on your own machine, no server
involved.

This app is being built in phases (see the project's task list / roadmap).
Each phase should be pulled and run locally to check the actual look and
feel, since GUI apps can't be visually verified from the coding sandbox.

## Setup

```bash
cd app
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Current status (Phase 0 + 1 + 2)

- Application shell: menu bar (File / Edit / View / Options), dockable and
  resizable panels laid out as specified (file browser top-left, PDF
  preview top-right, formula/filter bar and data table spanning the full
  width at the bottom).
- Light/dark theme: follows the OS by default, can be forced from
  Options > Theme.
- Language: follows the OS locale by default (falls back to Italian),
  can be forced from Options > Language. Currently wired for Italian and
  English; the other 4 languages (French, German, Spanish, Portuguese)
  will get real translation files in the polish phase -- for now they fall
  back to Italian source strings.
- Text/UI scale: 90/100/110/125/150% presets under Options > Dimensione
  testo, independent from OS display scaling -- accessibility feature so
  each user can adjust to their own screen/eyesight. Every panel reads
  fixed pixel sizes through `scaling.px()` instead of hardcoding them, so
  new panels in later phases should follow the same convention. Theme
  applies live; language and scale changes ask for a restart (avoids
  partial re-layout bugs).
- Session persistence: window size/position/maximized state, splitter
  proportions (how much space each panel gets) and View menu visibility are
  saved on close and restored on next launch automatically -- no menu entry,
  no restart needed for these (unlike theme/language/scale).
- Folder open/close: File > Apri cartella (or the button in the left
  panel) picks a folder; the action/button disables itself while a folder
  is open, per spec. Chiudi cartella resets the app to its initial state
  (empty table, empty browser).
- File browser: Explorer-style view of the *.pdf files in the opened
  folder only (non-recursive), with large/medium/small icons, list and
  details view modes, plus a live search box. Single/double click already
  emit signals (`file_single_clicked` / `file_double_clicked`) that Phase 3
  (preview) and Phase 6 (field editor) will connect to -- not wired to
  anything yet in this phase.
- PDF extraction (`core/pdf_extraction.py`, no Qt dependency, unit-tested
  headlessly): reads every AcroForm field found in every PDF in the folder
  -- the column set is not hardcoded to LaTeX_Template's schema, since the
  app is meant to work from whatever fields it actually finds (this is
  also the foundation Phase 5's outlier/duplicate detection builds on).
  Runs on a background QThread (`core/extraction_worker.py`) while a
  modal, non-closable progress popup (`dialogs/progress_dialog.py`) shows
  real per-file progress; a corrupt/unreadable PDF is reported in a
  warning dialog afterward rather than aborting the whole scan.
- Data table: bound to the extraction result via a DataFrame-backed Qt
  model (`core/dataframe_table_model.py`) -- bold column headers,
  automatic 1-based row numbers (not part of the data), and every data
  cell editable on the spot.
- Closing the folder discards the table entirely, matching the spec's
  "torna allo stato iniziale."

## Project layout

```
app/
  main.py              entry point
  theme.py             light/dark theme detection + manual override
  i18n.py               language detection + manual override, translation loading
  scaling.py            UI text/size scale (accessibility "zoom", not OS DPI)
  settings.py          persisted user preferences (QSettings)
  main_window.py        QMainWindow: menu bar + dock widget layout + folder/extraction wiring
  core/
    pdf_extraction.py       Qt-free AcroForm field extraction (unit-testable headlessly)
    extraction_worker.py    QThread wrapper around pdf_extraction, for a non-blocking progress popup
    dataframe_table_model.py  QAbstractTableModel bound to a pandas DataFrame
  dialogs/
    progress_dialog.py      modal, non-closable "analyzing..." popup with real progress
  panels/
    file_browser_panel.py   left panel (folder open/close, Explorer-style file view, search, colored status strip)
    preview_panel.py        right panel (PDF preview, up to 2 panes)
    formula_bar_panel.py    filter/formula bar + filter chip stack
    table_panel.py          data table (DataFrameTableModel-backed) + export button
```
