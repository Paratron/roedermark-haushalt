import re

content = open('frontend/static/kreisvergleich-map.svg').read()

# viewBox: -311.114 1293.91 618 360
VX, VY, VW, VH = -311.114, 1293.91, 618.0, 360.0

gemeinden = re.search(r'<g id="Gemeinden">(.*?)</g>', content, re.DOTALL)
polys = re.findall(r'points="([^"]+)"', gemeinden.group(1))

large = []
for i, p in enumerate(polys):
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
    # Convert to pixel coordinates (viewBox px == CSS px here since 618x360)
    px = cx - VX
    py = cy - VY
    large.append((i, cx, cy, px, py, len(xs)))

large.sort(key=lambda x: x[3])  # sort by pixel x (west to east)
print(f'Large polygons in view: {len(large)}')
print(f'{"idx":>4} | {"px(0-618)":>10} | {"py(0-360)":>10} | {"npts":>5}')
for item in large:
    print(f'  {item[0]:3d} | {item[3]:10.1f} | {item[4]:10.1f} | {item[5]:5d}')
