with open('recovered_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    
start_idx = -1
for i, line in enumerate(lines):
    if '"backgroundColor": "transparent"' in line or "'backgroundColor': 'transparent'" in line:
        start_idx = i - 1
        break

end_idx = -1
for i, line in enumerate(lines):
    if 'def LayerDisplayer():' in line:
        end_idx = i - 1
        break

print(f'Found block from {start_idx} to {end_idx} in recovered_engine.py')
recovered_block = lines[start_idx:end_idx]

with open('pages/engine.py', 'r', encoding='utf-8') as f:
    engine_lines = f.readlines()

bad_start = -1
for i, line in enumerate(engine_lines):
    if "solara.Text('# of vulnerability functions:'" in line:
        bad_start = i
        break

bad_end = -1
for i, line in enumerate(engine_lines):
    if 'def LayerDisplayer():' in line:
        bad_end = i - 1
        break

print(f'Found bad block from {bad_start} to {bad_end} in engine.py')

if start_idx != -1 and end_idx != -1 and bad_start != -1 and bad_end != -1:
    new_engine = engine_lines[:bad_start] + recovered_block + engine_lines[bad_end:]
    with open('pages/engine.py', 'w', encoding='utf-8') as f:
        f.writelines(new_engine)
    print('Recovery complete!')
else:
    print('Failed to find indices.')
