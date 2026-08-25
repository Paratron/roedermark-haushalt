import re
text = open('/Users/christianengel/Documents/code/roedermark-haushalt/frontend/static/kreisvergleich-map.svg').read()

# Find all attributes containing &...;
attrs = re.findall(r'\S+="[^"]*&[a-z_]+;[^"]*"', text)
print('Attributes with entities:')
for a in attrs:
    print(' ', a)
