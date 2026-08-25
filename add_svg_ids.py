"""
Add municipality IDs to the Kreis Offenbach SVG map.
Based on centroid analysis: the 13 #CCCCCC polygons in the Gemeinden layer
are matched to their municipalities by geographic position.
"""
import re
from xml.etree import ElementTree as ET

# The 13 Kreis Offenbach municipalities and their polygon indices (0-based)
# in the <g id="Gemeinden"> group, identified by centroid analysis:
#
#   idx | px(0-618) | py(0-360) | Municipality
#   265 |      89.6 |     305.9 | Egelsbach       (SW, southernmost)
#   253 |     114.7 |     278.9 | Langen          (W, south)
#   238 |     122.5 |     173.4 | Neu-Isenburg    (W, upper - borders Frankfurt)
#   261 |     180.2 |     252.2 | Dreieich        (center-W, lower-middle)
#   204 |     263.5 |     234.9 | Dietzenbach     (center, lower-middle)
#   203 |     300.3 |     291.0 | Rödermark       (center, very south)
#   179 |     308.4 |     171.2 | Heusenstamm     (center, upper)
#   176 |     343.3 |      77.2 | Mühlheim        (center-right, very north)
#   167 |     372.7 |     131.3 | Obertshausen    (center-right, upper)
#   144 |     391.8 |     227.2 | Rodgau          (center-right, middle)
#   161 |     467.6 |     143.2 | Hainburg        (right, upper)
#   126 |     486.1 |     183.3 | Mainhausen      (right, middle)
#   117 |     569.1 |     233.9 | Seligenstadt    (far right, middle)
#
# White (#FFFFFF) polygons are context/neighboring districts:
#   364 |      80.8 |      39.2 | Frankfurt am Main (NW context)
#   192 |     251.4 |      99.0 | Offenbach am Main Stadt (enclave)
#   332 |      56.5 |     333.3 | Neighboring municipality (SW context)

INDEX_TO_ID = {
    117: 'seligenstadt',
    126: 'mainhausen',
    144: 'rodgau',
    161: 'hainburg',
    167: 'obertshausen',
    176: 'muehlheim',
    179: 'heusenstamm',
    203: 'roedermark',
    204: 'dietzenbach',
    238: 'neu-isenburg',
    253: 'langen',
    261: 'dreieich',
    265: 'egelsbach',
}

SVG_IN  = 'frontend/static/kreisvergleich-map.svg'
SVG_OUT = 'frontend/static/kreisvergleich-map.svg'

content = open(SVG_IN, encoding='utf-8').read()

# Find the Gemeinden group and extract all polygon tags with their positions
gemeinden_match = re.search(r'(<g id="Gemeinden">)(.*?)(</g>)', content, re.DOTALL)
if not gemeinden_match:
    raise ValueError("Gemeinden group not found")

pre  = content[:gemeinden_match.start(2)]
body = gemeinden_match.group(2)
post = content[gemeinden_match.end(2):]

VX, VY, VW, VH = -311.114, 1293.91, 618.0, 360.0

# Split body into polygon tags and other content
# We'll process token by token
poly_pattern = re.compile(r'<polygon([^>]+)>', re.DOTALL)
tokens = poly_pattern.split(body)  # alternates: text, attrs, text, attrs, ...

# Rebuild: tokens[0] is text before first poly, tokens[1] is first poly attrs, etc.
# Collect all polygon attribute strings, indexed
attrs_list = tokens[1::2]  # every second element starting at 1

# For each polygon, compute centroid and assign id if in INDEX_TO_ID
new_attrs_list = []
for i, attr_str in enumerate(attrs_list):
    pts_m = re.search(r'points="([^"]+)"', attr_str)
    fill_m = re.search(r'fill="([^"]+)"', attr_str)
    fill = fill_m.group(1) if fill_m else '#CCCCCC'
    
    if pts_m and fill == '#CCCCCC' and i in INDEX_TO_ID:
        mid = INDEX_TO_ID[i]
        # Add id attribute (replace existing if any, else prepend)
        if 'id=' in attr_str:
            new_attr = re.sub(r'id="[^"]*"', f'id="{mid}"', attr_str)
        else:
            new_attr = f' id="{mid}"' + attr_str
        new_attrs_list.append(new_attr)
        print(f'  idx={i:3d} → id="{mid}"')
    else:
        new_attrs_list.append(attr_str)

# Rebuild body
new_body_parts = [tokens[0]]
for attr, text in zip(new_attrs_list, tokens[2::2]):
    new_body_parts.append('<polygon' + attr + '>')
    new_body_parts.append(text)
# tokens[0], poly0_attrs, text_after_poly0, poly1_attrs, text_after_poly1, ...
# len(tokens) = 1 + 2*n_polys
new_body = ''.join(new_body_parts)

new_content = pre + new_body + post

with open(SVG_OUT, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'\nSaved to {SVG_OUT}')

# Verify
verify_ids = re.findall(r'id="(egelsbach|langen|neu-isenburg|dreieich|dietzenbach|roedermark|heusenstamm|muehlheim|obertshausen|rodgau|hainburg|mainhausen|seligenstadt)"', new_content)
print(f'IDs found in output: {sorted(verify_ids)}')
print(f'Count: {len(verify_ids)} (expected 13)')
