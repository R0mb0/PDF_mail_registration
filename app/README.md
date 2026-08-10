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

## Current status (Phase 0 + 1 + 2 + 3 + 4 + 5 + 6 + 7 -- feature-complete)

- Application shell: menu bar (File / Edit / View / Options), dockable and
  resizable panels laid out as specified (file browser top-left, PDF
  preview top-right, formula/filter bar and data table spanning the full
  width at the bottom).
- Light/dark theme: follows the OS by default, can be forced from
  Options > Theme.
- Language: follows the OS locale by default (falls back to Italian),
  can be forced from Options > Language. All 6 languages (Italian, English,
  French, German, Spanish, Portuguese) have full translations authored --
  see `translations/README.md` for the one remaining manual step (compiling
  the `.ts` source files to `.qm`, which needs the `pyside6-lrelease` tool
  that ships with PySide6 but can't be run from this sandbox).
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
  details view modes, plus a live search box. Single click opens the
  preview, double click opens the field editor (see below).
- PDF extraction (`core/pdf_extraction.py`, no Qt dependency, unit-tested
  headlessly): reads every AcroForm field found in every PDF in the folder
  -- the column set is not hardcoded to LaTeX_Template's schema, since the
  app is meant to work from whatever fields it actually finds (this is
  also the foundation Phase 5's outlier/duplicate detection builds on).
  Runs on a background QThread (`core/extraction_worker.py`) while a
  modal, non-closable progress popup (`dialogs/progress_dialog.py`) shows
  real per-file progress; a corrupt/unreadable PDF is reported in a
  warning dialog afterward rather than aborting the whole scan. A checkbox
  shows its real state as text -- "Yes", "Off", or whatever the PDF's own
  on-state is named -- rather than collapsing "unchecked" to a blank
  cell; that used to make an unchecked checkbox indistinguishable from a
  text field nobody filled in (bug found via real test data, fixed).
- Data table: bound to the extraction result via a DataFrame-backed Qt
  model (`core/dataframe_table_model.py`) -- bold column headers,
  automatic 1-based row numbers (not part of the data), and every data
  cell editable on the spot.
- Closing the folder discards the table entirely, matching the spec's
  "torna allo stato iniziale."
- PDF preview: single-clicking a file in the browser opens it in the
  preview, rendered page-by-page via PySide6's own `QPdfDocument.render()`
  into a `QLabel`/`QScrollArea`, plus Previous/Next page navigation (shown
  only for multi-page PDFs) and simple +/- zoom buttons.
  - Bug found and fixed (via real testing, not synthetic data): this used
    to render via `QPdfWidgets.QPdfView` instead, which turned out to be
    a known, independently-documented Qt limitation -- it never draws
    annotations at all, and AcroForm field values are exactly that
    visually, so a PDF's compiled/filled fields never showed up in the
    preview no matter how correctly they were saved (this app's data
    table, which reads the raw value directly, was never affected --
    only what you *saw*). Switching to `QPdfDocument.render()` directly
    with `QPdfDocumentRenderOptions.RenderFlag.Annotations` set is what
    actually fixes it; QPdfView has no equivalent public option. The
    trade-off is QPdfView's continuous multi-page scroll, which doesn't
    apply to a manually rendered single image per page -- acceptable
    here since this project's own form is one page, and multi-page PDFs
    still show every page, just one at a time via the nav buttons.
  - Second, deeper bug found and fixed (also via real testing): even
    after switching to `QPdfDocument.render()`, filled-in fields were
    *still* invisible in the preview, while the data table stayed
    correct throughout -- proving the values themselves were fine and
    the problem was purely in rendering. Two independent causes, both
    confirmed by rendering to an image with every PDF annotation
    stripped out entirely and checking what still appears:
    1. `QPdfDocument.render()`'s own `Annotations` render flag turned
       out not to be enough in practice -- Qt's PDF module doesn't
       reliably draw AcroForm field/widget content even with it set, a
       real limitation of the module itself, not a wrong option.
    2. Independently, `hyperref` (the LaTeX package used to build the
       form) has its own confirmed upstream bug
       (github.com/latex3/hyperref/issues/94, open since 2019): a
       checkbox's "checked" appearance is written into the PDF as an
       empty object with no actual drawing content -- so no renderer
       anywhere could show a checkmark for it, independent of #1.
    - Fixed by rendering the preview from a temporary, flattened copy
      of the PDF instead of the live file (`core/pdf_field_io.py`'s
      `build_flattened_preview_copy()`): every field's current value is
      baked directly into the page's own content, which every renderer
      already draws correctly regardless of annotation support. Before
      flattening, `repair_checkbox_appearances()` replaces any empty
      checkbox appearance with a real, minimal checkmark drawn in the
      template's own accent color -- this same repair also runs inside
      `write_fields()` (self-heals any file this app's own editor
      touches) and inside `LaTeX_Template/fix_pdf_appearances.py` (fixes
      it at the source, for every copy of the template from now on).
      The original file on disk is never touched by any of this -- only
      a throwaway temp copy used purely for display.
  - The secondary pane is off by default and stays that way until
    explicitly turned on from View > "Seconda anteprima PDF" (or the
    pane's own "✕", which just unchecks that same action) -- while it's
    off there is only ever one usable slot, and every click replaces its
    content outright; only once it's on does opening a file fill the
    primary slot first, then the secondary, then FIFO-replace whichever
    slot was filled longest ago. `PreviewPanel.set_secondary_enabled()`
    is the single place this is decided, so the pane's visibility and
    its FIFO eligibility can never drift apart.
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
  relative to the folder's own "typical" field structure -- majority
  filled-vs-blank for free-text fields, majority *exact value* for
  low-cardinality (checkbox-like) fields -- not a hardcoded schema --
  - **red**: unreadable PDF, or field structure deviating from the
    typical one by more than 30% -- excluded from the table entirely.
  - **orange**: a near-duplicate (>30% of its filled, identifying fields
    identical to another document's), or a structural deviation up to
    30% -- included, blanks stay blank.
  - **green**: none of the above.
  - Two real bugs were found and fixed here after testing against an
    actual filled-out batch of PDFs (`Prova_pdfs/`), not just synthetic
    data: (1) any blank field used to force orange unconditionally, even
    when being blank was the norm for the whole folder (e.g. an optional
    consent checkbox nearly everyone leaves unchecked) -- removed, a
    blank/off field is only a signal when it *deviates* from the folder's
    own norm, which the deviation score already captures; (2) once
    checkboxes stopped reporting "unchecked" as blank (see the PDF
    extraction fix above), duplicate detection started treating a shared
    checkbox answer as evidence two documents were the same registration
    -- fixed by excluding low-cardinality fields (at most 2 distinct
    values folder-wide) from duplicate matching entirely; only higher-
    cardinality, actually identifying fields (name, email, ...) count
    toward a duplicate match now.
  - Known characteristic, not a bug: with very few documents (single
    digits) a field sitting near a 50/50 split across the whole folder
    makes the majority baseline unstable, which can tip a document into
    red a bit more eagerly than with a larger, more typical sample --
    verified this behaves as expected at a realistic scale (10+
    documents, one isolated deviating field correctly lands orange, not
    red -- confirmed both on synthetic data and on the real `Prova_pdfs/`
    batch).
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
  - Bug found and fixed (via real testing, not synthetic data): saved
    fields were correctly stored (the data table always showed the right
    values, since it reads `/V` directly) but showed up blank in this
    app's own PDF preview pane after editing. Root cause was in how the
    file was saved, not how it was read: pypdf was told to bake a real,
    immediately-visible appearance for each field (`auto_regenerate=
    False`) and then, on the very next line, told to throw that away and
    ask the *viewer* to regenerate it instead (`set_need_appearances_
    writer(True)`) -- and this app's own PDF preview, like several other
    lightweight PDF renderers (this is a known, documented hyperref/PDF-
    viewer interaction, not unique to this app), doesn't actually
    regenerate appearances itself, so it rendered nothing. Removing that
    second line was the fix -- verified the saved PDF now has
    `/NeedAppearances: False` and a real `/AP` appearance stream on every
    filled field. Separately, `LaTeX_Template`'s own compiled PDF used to
    ship with `/NeedAppearances: true` from the moment pdflatex/hyperref
    generates it, before this app ever touches it -- now also fixed at
    the source by `LaTeX_Template/fix_pdf_appearances.py`, run once right
    after compiling (see that folder's README), so every fresh copy of
    the template is already correct even before this app's editor ever
    saves it.
- Export (`core/data_export.py`, no Qt dependency, unit-tested headlessly
  round-tripping every format through its own reader): "Esporta dati
  come..." opens a native save dialog defaulting to the app's own folder,
  offering CSV / Excel / SQL database (a standalone `.db` file, table
  `data`) / plain tab-separated text; the format is picked from whichever
  extension ends up in the chosen filename, defaulting to CSV if that's
  ambiguous. Exports exactly what the table currently shows -- i.e. after
  whatever filters/manual edits are active, not the raw extraction. A
  re-export to an existing `.db` path replaces it outright rather than
  appending a second copy of the table.
- Edit menu: Cut/Copy/Paste operate on the table's current cell selection
  using tab-separated clipboard text, the same layout Excel/LibreOffice/
  Sheets themselves use, so copying out of/pasting into an external
  spreadsheet just works (`core/clipboard_format.py`, no Qt dependency,
  unit-tested headlessly). Paste writes every cell through the same
  edit_callback as typing directly into a cell, so it participates
  identically in the filter pipeline's undo/redo and in the "File" column's
  read-only protection. Select all/Select none act on the table selection
  directly.
- Cleaned up a leftover inconsistency from Phase 4: `requirements.txt`
  still listed `duckdb` even though the SQL filter mode was switched to
  the standard-library `sqlite3` back then -- removed.
- Full Italian source strings plus hand-authored English/French/German/
  Spanish/Portuguese translations for all 78 translatable UI strings
  (`translations/registration_app_<lang>.ts`) -- see
  `translations/README.md` for why these ship as `.ts` rather than
  already-compiled `.qm` files.
- Resizable panels: every internal border was already a `QSplitter` handle
  since Phase 1 (drag any border between file browser/preview/formula
  bar/table to resize); nothing further was needed here, just confirmed
  still correct.
- "Apri nuova istanza" (a fresh, independent process with no folder
  pre-opened) was already implemented in Phase 1.

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
    data_export.py          CSV/Excel/SQL/plain-text export (Qt-free, unit-tested headlessly)
    clipboard_format.py     tab-separated formatting for Edit menu Cut/Copy/Paste (Qt-free, unit-tested headlessly)
  dialogs/
    progress_dialog.py      modal, non-closable "analyzing..." popup with real progress
    field_editor_dialog.py  in-app PDF field editor opened by double-clicking a file
  panels/
    file_browser_panel.py   left panel (folder open/close, Explorer-style file view, search, colored status strip)
    preview_panel.py        right panel (PDF preview, up to 2 panes)
    formula_bar_panel.py    filter/formula bar + filter chip stack
    flow_layout.py          Qt's standard wrapping "flow" layout, used by the chip stack
    table_panel.py          data table (DataFrameTableModel-backed) + export button + Cut/Copy/Paste/Select
  translations/
    registration_app_{en,fr,de,es,pt}.ts   translation sources (see translations/README.md to compile to .qm)
```
