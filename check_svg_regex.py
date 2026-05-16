import re

text = open('frontend/static/kreisvergleich-map-clean.svg').read()

test_id = 'roedermark'
new_fill = '#fca5a5'

# Check what the polygon looks like
m = re.search(r'<polygon[^>]*id="' + test_id + r'"[^>]*/>', text)
if m:
    print('Original polygon:', m.group()[:200])
else:
    print('Polygon NOT found by standard search')
    # Try alternate order (id might be first or not)
    m2 = re.search(r'id="' + test_id + r'"', text)
    if m2:
        start = text.rfind('<polygon', 0, m2.start())
        end = text.find('/>', m2.start()) + 2
        print('Polygon (found by id):', text[start:end][:200])

# Test the fill replacement
fill_pattern = re.compile(f'( id="{test_id}"[^>]*?) fill="[^"]*"')
match = fill_pattern.search(text)
if match:
    print('\nFill regex matches:', match.group()[:150])
    new_text = fill_pattern.sub(f'$1 fill="{new_fill}"', text, count=1)
    # Find and print the replaced polygon
    m2 = re.search(r'id="' + test_id + r'"[^/]*/>', new_text)
    if m2:
        start = new_text.rfind('<polygon', 0, m2.start())
        end = new_text.find('/>', m2.start()) + 2
        print('After fill replacement:', new_text[start:end][:200])
else:
    print('\nFill regex DID NOT match! Checking attribute order...')
    ctx = text[text.find(f'id="{test_id}"')-5 : text.find(f'id="{test_id}"')+100]
    print('Context around id:', repr(ctx))
