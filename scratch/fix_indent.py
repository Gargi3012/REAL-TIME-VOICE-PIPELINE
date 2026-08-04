import sys

with open("app/main.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_endpoint = False

for i, line in enumerate(lines):
    if line.startswith("    try:") and lines[i+1].startswith("        # Wait for the start event"):
        continue  # skip the rogue try:
    
    new_lines.append(line)

with open("app/main.py", "w") as f:
    f.writelines(new_lines)

print("Removed rogue try:")
