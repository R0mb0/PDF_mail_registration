from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions

print("--- QPdfDocument methods (page/render-related) ---")
for name in sorted(dir(QPdfDocument)):
    if any(k in name.lower() for k in ("page", "render", "status", "load")):
        print(" ", name)

print()
print("--- QPdfDocument.Status enum values ---")
print(" ", [v for v in dir(QPdfDocument.Status) if not v.startswith("_")])

print()
print("--- QPdfDocumentRenderOptions methods ---")
for name in sorted(dir(QPdfDocumentRenderOptions)):
    if not name.startswith("_"):
        print(" ", name)

print()
print("--- QPdfDocumentRenderOptions.RenderFlag enum values ---")
print(" ", [v for v in dir(QPdfDocumentRenderOptions.RenderFlag) if not v.startswith("_")])
