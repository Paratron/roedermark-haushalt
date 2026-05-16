"""
Pre-process the Wikipedia SVG to produce a clean inline-safe version.
Strips XML declaration, DOCTYPE, comments, and entity-referencing attributes.
"""
import re

src = 'frontend/static/kreisvergleich-map.svg'
dst = 'frontend/static/kreisvergleich-map-clean.svg'

text = open(src, encoding='utf-8').read()

# 1. Strip XML declaration
text = re.sub(r'^<\?xml[^?]*\?>\s*', '', text, flags=re.IGNORECASE)

# 2. Strip DOCTYPE block (includes entity definitions)
text = re.sub(r'<!DOCTYPE[\s\S]*?\]>\s*', '', text, flags=re.IGNORECASE)

# 3. Strip all comments
text = re.sub(r'<!--[\s\S]*?-->', '', text)

# 4. Strip any attribute whose entire value is a custom entity reference
#    e.g. xmlns:x="&ns_extend;" xmlns="&ns_sfw;" requiredExtensions="&ns_ai;"
text = re.sub(r'\s+[\w:]+="&[a-z_]+;"', '', text)

# 5. Strip Adobe-specific xmlns attributes that are harmless but noisy
text = re.sub(r'\s+xmlns:[a-z]="[^"]*adobe[^"]*"', '', text)

# 6. Collapse extra whitespace lines
text = re.sub(r'\n{3,}', '\n\n', text)

# Verify no entities remain
remaining = re.findall(r'&[a-z_]+;', text)
if remaining:
    print('WARNING – remaining entities:', set(remaining))
else:
    print('No custom entities remaining. SVG is clean.')

with open(dst, 'w', encoding='utf-8') as f:
    f.write(text.strip())

print(f'Written to {dst} ({len(text)} chars)')

# Quick sanity: count colored municipality polygons
ids_found = re.findall(r'id="(dietzenbach|dreieich|egelsbach|hainburg|heusenstamm|langen|mainhausen|muehlheim|neu-isenburg|obertshausen|rodgau|roedermark|seligenstadt)"', text)
print(f'Municipality polygon IDs found: {len(ids_found)} → {sorted(ids_found)}')
