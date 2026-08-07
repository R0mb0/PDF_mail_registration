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

## Current status (Phase 0 + 1)

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
- All panel *content* is still placeholder -- folder opening, PDF
  extraction, the data table, the filter engine and the preview are built
  in the following phases.

## Project layout

```
app/
  main.py              entry point
  theme.py             light/dark theme detection + manual override
  i18n.py               language detection + manual override, translation loading
  scaling.py            UI text/size scale (accessibility "zoom", not OS DPI)
  settings.py          persisted user preferences (QSettings)
  main_window.py        QMainWindow: menu bar + dock widget layout
  panels/
    file_browser_panel.py   left panel (folder open/close, file list, colored status strip)
    preview_panel.py        right panel (PDF preview, up to 2 panes)
    formula_bar_panel.py    filter/formula bar + filter chip stack
    table_panel.py          data table + export button
```
