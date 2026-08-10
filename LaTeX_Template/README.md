# LaTeX Registration Form Template

`registration_form.tex` is a fillable, single-page PDF registration form
built with LaTeX + `hyperref` AcroForm fields. It is designed to be:

- **Filled offline** by participants in any standard PDF reader (Adobe
  Acrobat Reader recommended) and emailed back as an attachment -- no web
  server involved.
- **Easy to re-theme per event**: edit the six lines under "EVENT DETAILS"
  at the top of `registration_form.tex`.
- **Easy to parse later**: every field has a fixed, unique, English,
  snake_case internal name (see table below). A local Python script (next
  project step) will read these names back out of the PDF with
  `pypdf`/`PyMuPDF` -- it does not rely on the visible on-page labels at all.

## Files

| File | Purpose |
|---|---|
| `registration_form.tex` | Main, short, editable document. Event details + field list live here. |
| `event-form-style.sty` | All visual styling: gradient background, rounded black frame, white content card, rounded field/checkbox macros, modern sans font. You normally don't need to touch this. |
| `registration_form.pdf` | Compiled sample output. |

## Compiling

```bash
pdflatex registration_form.tex
pdflatex registration_form.tex           # run twice so hyperref settles references
python3 fix_pdf_appearances.py registration_form.pdf
```

Requires a standard TeX Live install with `hyperref`, `tikz`, `tcolorbox`
(skins + breakable libraries), `eso-pic`, `enumitem`, `ragged2e`, and the
`tex-gyre` fonts (`tgheros`) -- all part of a full TeX Live distribution --
plus `pypdf` (already a dependency of `app/`) for the last step.

The last step matters, it's not just cleanup: hyperref sets the PDF's
`/NeedAppearances` flag to true by default on any form it creates, which
tells some (not all) PDF readers to regenerate a field's on-screen
appearance themselves instead of trusting what's already there -- readers
that don't actually do that regeneration (several lightweight ones don't;
this includes the `app/` desktop application's own PDF preview before it
was fixed) can render an otherwise-correctly-filled field as blank.
`fix_pdf_appearances.py` clears that flag right after compiling, before
the template is ever sent out or filled in by anyone. Verified to be a
purely cosmetic-metadata change -- field names/values and the rendered
page image are identical before and after running it.

## Editing the form

- **Event details**: change `\eventName{}`, `\eventTagline{}`,
  `\eventDateText{}`, `\eventLocationText{}`, `\eventDeadlineText{}`,
  `\registrationEmail{}` at the top of `registration_form.tex`.
- **Add/remove/reorder a field**: use the three macros defined in
  `event-form-style.sty`:
  - `\RegField{Visible Label}{internal_field_name}{width}` -- single-line
    text field.
  - `\RegFieldMulti{Visible Label}{internal_field_name}{width}{height}` --
    multi-line text field (e.g. allergies).
  - `\RegCheck{internal_field_name}{label text}` -- checkbox with a label
    paragraph.
  - `\FormPair{...}{...}` -- lay two field calls side by side.
- **Important**: once a form has been sent out for a real event, never
  rename an existing field's internal name -- the Python parser matches on
  that name. If you need a new field for a future event, add a new one
  instead of renaming/reusing an old name.

## Field name schema

These are the exact AcroForm field names embedded in the PDF (the `T` key
that `pypdf`'s `get_fields()` / `PyMuPDF`'s `widget.field_name` will return).
Field type is noted for parsing purposes; checkbox values come back as
`/Yes` (checked) or `/Off` (unchecked).

| Internal field name | Type | Meaning |
|---|---|---|
| `reg_first_name` | text | Participant's first name |
| `reg_last_name` | text | Participant's last name |
| `reg_date_of_birth` | text | Date of birth, format DD/MM/YYYY (free text, not enforced by the PDF) |
| `reg_place_of_birth` | text | Place of birth |
| `reg_address` | text | Residential address (street, city, postal code, single line) |
| `reg_phone` | text | Phone number |
| `reg_email` | text | Email address |
| `reg_allergies` | text (multiline) | Allergies / dietary restrictions, free text |
| `consent_gdpr` | checkbox | Consent to data processing (GDPR) -- intended to be mandatory to participate; the PDF does not technically enforce this, so the parsing script should flag registrations where this is unchecked |
| `consent_marketing` | checkbox | Consent to marketing use of data |
| `consent_promotions` | checkbox | Opt-in to promotional communications |

## Notes for the next step (Python parsing)

- Treat `reg_first_name` + `reg_last_name` (or a combination with
  `reg_date_of_birth`) as the stable identifier for deduplicating
  resubmissions -- prefer the most recent email by date, but don't
  silently discard conflicting older submissions; flag mismatches for
  manual review instead.
- Archive every received PDF as-is; never overwrite or delete originals.
- `reg_date_of_birth` is a plain text field, not a PDF date field, so
  expect free-form input and validate/normalize it in the parser.
