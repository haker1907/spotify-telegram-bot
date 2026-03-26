#!/usr/bin/env python3
"""
Script to add YouTube bypass parameters after 'default_search' lines
"""

# Read the file
with open('services/download_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Parameters to add
bypass_lines = [
    "            # Обход блокировки YouTube \"Sign in to confirm you're not a bot\"\n",
    "            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',\n",
    "            'extractor_args': {\n",
    "                'youtube': {\n",
    "                    'player_client': ['android', 'web'],\n",
    "                    'skip': ['hls', 'dash']\n",
    "                }\n",
    "            },\n",
    "            'geo_bypass': True,\n",
    "            'nocheckcertificate': True,\n"
]

# Find and insert after 'default_search': 'ytsearch1',
new_lines = []
modified_count = 0

for i, line in enumerate(lines):
    new_lines.append(line)
    
    # Check if this line contains 'default_search': 'ytsearch1',
    if "'default_search': 'ytsearch1'," in line:
        # Check if bypass params are not already added (check next line)
        if i + 1 < len(lines) and 'user_agent' not in lines[i + 1]:
            # Add bypass parameters
            new_lines.extend(bypass_lines)
            modified_count += 1
            print(f"✅ Added bypass params after line {i + 1}")

# Write back
with open('services/download_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"\n✅ Successfully modified {modified_count} ydl_opts blocks")
print("   Added YouTube bypass parameters to prevent 'Sign in to confirm you're not a bot' error")
