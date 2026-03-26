#!/usr/bin/env python3
"""
Script to update YouTube bypass parameters in download_service.py
"""

# Read the file
with open('services/download_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace old parameters with new ones
replacements = [
    # Update Chrome version
    ("Chrome/120.0.0.0", "Chrome/121.0.0.0"),
    # Change player_client to only android (more stable)
    ("'player_client': ['android', 'web'],", "'player_client': ['android'],  # Только Android API - более стабилен"),
    # Add translated_subs to skip list
    ("'skip': ['hls', 'dash']", "'skip': ['hls', 'dash', 'translated_subs']"),
]

modified = False
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        modified = True
        print(f"✅ Replaced: {old[:50]}... → {new[:50]}...")
    else:
        print(f"⚠️  Not found: {old[:50]}...")

# Add age_limit parameter if not present
if "'age_limit':" not in content:
    # Find and add age_limit before closing braces
    content = content.replace(
        "'nocheckcertificate': True,\n        }",
        "'nocheckcertificate': True,\n            'age_limit': 99,  # Обход возрастных ограничений\n        }"
    )
    modified = True
    print("✅ Added age_limit parameter")

if modified:
    # Write back
    with open('services/download_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("\n✅ Successfully updated YouTube bypass parameters!")
    print("   Changes:")
    print("   - Updated User-Agent to Chrome 121")
    print("   - Changed player_client to only 'android' (more stable)")
    print("   - Added 'translated_subs' to skip list")
    print("   - Added age_limit parameter")
else:
    print("\n⚠️  No changes were made - parameters might already be up to date")
