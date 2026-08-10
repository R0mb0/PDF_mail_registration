# Translations

`registration_app_{en,fr,de,es,pt}.ts` are the Qt Linguist *source*
translation files: plain, human-readable XML mapping every Italian UI
string (extracted straight from the actual `self.tr(...)` call sites) to
its English/French/German/Spanish/Portuguese translation, grouped by the
Qt "context" (the class each string belongs to) the same way
`pyside6-lupdate` would group them.

They are not yet compiled to the binary `.qm` files `i18n.py` actually
loads at runtime (`translations/registration_app_<lang>.qm`) -- producing
`.qm` requires the `pyside6-lrelease` tool that ships with PySide6, which
isn't installable in the sandbox this app is being developed in (no PyPI
network access there). Since you already have PySide6 installed locally to
run the app, compiling them takes one command:

```bash
cd app
pyside6-lrelease translations/registration_app_en.ts -qm translations/registration_app_en.qm
pyside6-lrelease translations/registration_app_fr.ts -qm translations/registration_app_fr.qm
pyside6-lrelease translations/registration_app_de.ts -qm translations/registration_app_de.qm
pyside6-lrelease translations/registration_app_es.ts -qm translations/registration_app_es.qm
pyside6-lrelease translations/registration_app_pt.ts -qm translations/registration_app_pt.qm
```

(or open each `.ts` in Qt Linguist and use File > Release). Once the `.qm`
files exist next to the `.ts` files, Options > Lingua in the running app
will pick them up immediately -- no code changes needed, `i18n.py` already
looks for exactly these filenames and silently falls back to the Italian
source strings if a given `.qm` is missing.

There is no `registration_app_it.ts` -- Italian is the source language
itself (every `self.tr("...")` call *is* the Italian string), so it never
needs a translation file.

If you add or change any `self.tr(...)` string in the app later, the
`.ts` files above will not update automatically -- either hand-edit the
relevant `<translation>` entries, or regenerate them properly with
`pyside6-lupdate main.py main_window.py panels/*.py dialogs/*.py -ts translations/registration_app_<lang>.ts`
(which preserves existing translations for strings that haven't changed
and flags new/changed ones for you to fill in).
