import re
text = open('/Users/christianengel/Documents/code/roedermark-haushalt/frontend/static/kreisvergleich-map.svg').read()

# Simulate the onMount stripping
text = re.sub(r'^<\?xml[^?]*\?>\s*', '', text, flags=re.IGNORECASE)
text = re.sub(r'<!DOCTYPE[\s\S]*?\]>\s*', '', text, flags=re.IGNORECASE)
text = re.sub(r'<!--[\s\S]*?-->\s*', '', text)
text = re.sub(r'\s+xmlns:[a-z]+="&[^"]+;"', '', text)

# Check: any remaining entity refs?
remaining = re.findall(r'&[a-z_]+;', text)
print('Remaining entities:', set(remaining))

# Check SVG root tag
svg_root = re.search(r'<svg[^>]+>', text)
print('SVG root tag:', svg_root.group()[:400] if svg_root else 'NOT FOUND')
