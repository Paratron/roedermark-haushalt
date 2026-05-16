import re
text = open('/Users/christianengel/Documents/code/roedermark-haushalt/frontend/static/kreisvergleich-map.svg').read()

text = re.sub(r'^<\?xml[^?]*\?>\s*', '', text, flags=re.IGNORECASE)
text = re.sub(r'<!DOCTYPE[\s\S]*?\]>\s*', '', text, flags=re.IGNORECASE)
text = re.sub(r'<!--[\s\S]*?-->\s*', '', text)
text = re.sub(r'\s+[\w:]+="&[a-z_]+;"', '', text)

remaining = re.findall(r'&[a-z_]+;', text)
print('Remaining entities:', set(remaining))
print('All good!' if not remaining else 'STILL BROKEN')
