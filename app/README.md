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

## Current status (Phase 0 + 1 + 2 + 3 + 4 + 5 + 6)

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
- PDF preview: single-clicking a file in the browser opens it in the
  preview (primary slot first, then secondary, then FIFO-replaces
  whichever slot was filled longest ago), rendered via PySide6's own
  QtPdf/QtPdfWidgets (QPdfDocument + QPdfView) -- scrolling and continuous
  multi-page layout come from that widget for free, plus simple +/- zoom
  buttons. The secondary pane's "✕" and the View menu's "Seconda
  anteprima PDF" checkbox are kept in sync with each other. Double-click
  (-> field editor) is not wired yet -- Phase 6.
- Excel/SQL filter-mode buttons are mutually exclusive (QButtonGroup) and
  neither is selected by default; the active one gets a solid accent-color
  fill so it's unambiguous which mode is in effect.
- Filter pipeline (`core/filter_pipeline.py`, no Qt dependency, unit-tested
  headlessly with the exact scenario from the spec: filter -> manual edit
  -> second manual edit folding into the same chip -> another filter ->
  undo -> undo -> redo -> new filter clearing the redo stack -> rejected
  bad formula leaving the pipeline untouched -- all assertions pass).
  Excel-subset mode (`core/excel_formula.py`) is a hand-written, sandboxed
  AST evaluator -- no `eval()`/`exec()` anywhere, verified to reject an
  `__import__(...)` escape attempt -- supporting `[Column Name]`
  references, `=`/`<>`/comparisons, `AND`/`OR`/`NOT`/`IF`/`ISBLANK`/`TRIM`/
  `CONCAT`/`LEFT`/`RIGHT`/`LEN`/`UPPER`/`LOWER`. SQL mode
  (`core/sql_filter.py`) runs the query against an in-memory `sqlite3`
  table named `data` -- dropped the `duckdb` dependency from
  requirements.txt in favor of Python's own standard library, one less
  thing that can fail to install.
  - Colored, wrapping filter chips (`panels/flow_layout.py` is Qt's
    standard "Flow Layout" pattern) -- only the last chip's "✕" is
    enabled, matching the integrity rule that only the most recent filter
    can be removed.
  - A manual cell edit only becomes a chip once at least one filter is
    already active; consecutive edits fold into the same chip until the
    next filter finalizes it. Removing that chip reverts exactly those
    cells. The table's "File" column is read-only, since it doubles as
    the stable row identifier those edits are keyed on.
  - Ctrl+Z / Ctrl+Y (Edit menu "Indietro"/"Avanti") are literally the same
    operation as removing/restoring the last chip -- both start disabled
    and re-enable based on the pipeline's own state.
  - Bad formula/SQL syntax shows a warning dialog with the underlying
    error message and leaves the pipeline completely unchanged.
- Document classification (`core/classification.py`, no Qt dependency,
  unit-tested headlessly): every extracted PDF is green/orange/red
  relative to the folder's own "typical" field structure (majority
  filled-vs-blank per field), not a hardcoded schema --
  - **red**: unreadable PDF, or field structure deviating from the
    typical one by more than 30% -- excluded from the table entirely.
  - **orange**: a near-duplicate (>30% of its filled fields identical to
    another document's), or any blank field, or a structural deviation up
    to 30% -- included, blanks stay blank.
  - **green**: none of the above.
  - Known characteristic, not a bug: with very few documents (single
    digits) a field sitting near a 50/50 filled/blank split across the
    whole folder makes the majority baseline unstable, which can tip a
    document into red a bit more eagerly than with a larger, more typical
    sample -- verified this behaves as expected at a realistic scale (10
    documents, one isolated blank field correctly lands orange, not red).
  - The colored strip under the file browser shows one tall button per
    PDF (including red ones), numbered, with the reasons in its tooltip;
    clicking one opens it in preview and selects/highlights it in the
    browser above. Files can be deleted (Delete key or right-click) to
    exclude them from processing entirely -- that re-runs the same full
    extraction+classification, per the "changing folder contents
    invalidates everything downstream" rule.
- In-app field editor (`core/pdf_field_io.py` for the read/write logic,
  no Qt dependency, verified against a real generated PDF -- multi-pass
  edits, checkbox on/off round-trip and a failure path all checked;
  `dialogs/field_editor_dialog.py` for the UI): double-clicking a file in
  the browser -- never the system's default PDF viewer -- opens a modal
  dialog with one proper widget per AcroForm field (text box, checkbox,
  dropdown for choice fields; anything else, e.g. a signature field, is
  shown read-only). Saving writes to a temp file next to the original and
  only replaces it via an atomic `os.replace()` once the write fully
  succeeds, so a failure never corrupts the PDF -- a write error is shown
  in a dialog and the editor stays open with nothing lost. On success,
  saving triggers the same full extraction+classification re-run as
  opening the folder does, per the "changing a PDF invalidates the whole
  downstream table state" rule -- there is no attempt to patch just the
  edited row in place.

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
    dataframe_table_model.py  QAbstractTableModel bound to a pandas DataFrame, edits routed via callback
    filter_pipeline.py      the filter/undo-redo stack itself (Qt-free, unit-tested headlessly)
    classification.py       green/orange/red document classification (Qt-free, unit-tested headlessly)
    excel_formula.py        sandboxed Excel-subset expression evaluator (Qt-free, unit-tested headlessly)
    sql_filter.py           SQL-mode filter via in-memory sqlite3 (Qt-free, unit-tested headlessly)
    pdf_field_io.py         detailed AcroForm read/write for the field editor (Qt-free, unit-tested headlessly)
  dialogs/
    progress_dialog.py      modal, non-closable "analyzing..." popup with real progress
    field_editor_dialog.py  in-app PDF field editor opened by double-clicking a file
  panels/
    file_browser_panel.py   left panel (folder open/close, Explorer-style file view, search, colored status strip)
    preview_panel.py        right panel (PDF preview, up to 2 panes)
    formula_bar_panel.py    filter/formula bar + filter chip stack
    flow_layout.py          Qt's standard wrapping "flow" layout, used by the chip stack
    table_panel.py          data table (DataFrameTableModel-backed) + export button
```
