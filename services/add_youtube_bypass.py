#!/usr/bin/env python3
"""
Script to add YouTube bypass parameters to download_service.py
"""

# Read the file
with open('services/download_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the bypass parameters to add
bypass_params = """            # Обход блокировки YouTube "Sign in to confirm you're not a bot"
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'skip': ['hls', 'dash']
                }
            },
            'geo_bypass': True,
            'nocheckcertificate': True,
"""

# Find and replace pattern
# We need to add bypass params before the closing brace of ydl_opts
import re

# Pattern to find ydl_opts dictionaries
pattern = r"(            'default_search': 'ytsearch1',\s*\n)(        })"

# Replacement with bypass parameters
replacement = r"\1" + bypass_params + r"\2"

# Apply replacement
new_content = re.sub(pattern, replacement, content)

# Check if any replacements were made
if new_content != content:
    # Write back
    with open('services/download_service.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Successfully added YouTube bypass parameters")
    print(f"   Modified {content.count(\"'default_search': 'ytsearch1',\")} ydl_opts blocks")
else:
    print("❌ No matching patterns found")
    print("   Trying alternative approach...")
    
    # Alternative: find all occurrences of 'default_search': 'ytsearch1', and add params after
    lines = content.split('\n')
    new_lines = []
    i = 0
    modified_count = 0
    
    while i < len(lines):
        new_lines.append(lines[i])
        
        # Check if this line contains 'default_search': 'ytsearch1',
        if "'default_search': 'ytsearch1'," in lines[i]:
            # Check if bypass params are not already added
            if i + 1 < len(lines) and 'user_agent' not in lines[i + 1]:
                # Add bypass parameters
                new_lines.append(bypass_params.rstrip())
                modified_count += 1
        
        i += 1
    
    if modified_count > 0:
        with open('services/download_service.py', 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print(f"✅ Successfully added YouTube bypass parameters (alternative method)")
        print(f"   Modified {modified_count} ydl_opts blocks")
    else:
        print("❌ Could not find any ydl_opts blocks to modify")
