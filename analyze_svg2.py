import re

content = open('frontend/static/kreisvergleich-map.svg').read()

VX, VY, VW, VH = -311.114, 1293.91, 618.0, 360.0

gemeinden = re.search(r'<g id="Gemeinden">(.*?)</g>', content, re.DOTALL)
raw_polys = re.findall(r'(<polygon[^>]+>)', gemeinden.group(1))

large = []
for i, tag in enumerate(raw_polys):
    pts_m = re.search(r'points="([^"]+)"', tag)
    fill_m = re.search(r'fill="([^"]+)"', tag)
    style_m = re.search(r'style="([^"]+)"', tag)
    if not pts_m:
        continue
    p = pts_m.group(1)
    fill = fill_m.group(1) if fill_m else 'none'
    style = style_m.group(1) if style_m else ''
    # extract fill from style too
    style_fill = re.search(r'fill:([^;]+)', style)
    if style_fill:
        fill = style_fill.group(1).strip()
    
    nums = re.findall(r'-?\d+\.?\d*', p)
    coords = [float(x) for x in nums]
    if len(coords) < 20:
        continue
    xs = coords[0::2]
    ys = coords[1::2]
    cx = sum(xs)/len(xs)
    cy = sum(ys)/len(ys)
    if not (VX <= cx <= VX+VW and VY <= cy <= VY+VH):
        continue
    px = cx - VX
    py = cy - VY
    large.append((i, px, py, len(xs), fill))

large.sort(key=lambda x: x[1])
print(f'{"idx":>4} | {"px":>7} | {"py":>7} | {"npts":>5} | fill')
for item in large:
    print(f'  {item[0]:3d} | {item[1]:7.1f} | {item[2]:7.1f} | {item[3]:5d} | {item[4]}')
