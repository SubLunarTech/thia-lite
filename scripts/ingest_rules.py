#!/usr/bin/env python3
"""
Thia-Lite RAG Ingestion Script
================================
Automates the process of chunking raw text into Thia-Lite's 
structured astrological rules format (JSON).
"""

import json
import os
import sys
import asyncio
import re
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thia_lite.llm.client import get_llm_client

async def extract_rules_from_chunk(text: str, source_name: str) -> List[Dict[str, Any]]:
    """Use the LLM to extract structured rules from a text chunk."""
    client = get_llm_client()
    
    prompt = f"""
Extract discrete astrological rules or aphorisms from the following text fragment.
A rule should be a standalone statement that can be used for chart interpretation.

TEXT FRAGMENT:
---
{text}
---

SOURCE: {source_name}

FORMAT:
Respond ONLY with a JSON list of objects:
[
  {{
    "id": "{source_name.upper()}_XXXX",
    "category": "natal/horary/mundane/general",
    "text": "The extracted rule text...",
    "planets": ["Sun", "Moon", ...],
    "signs": ["Aries", ...],
    "houses": [1, 2, ...],
    "confidence": 0.9,
    "source": "{source_name}"
  }}
]
"""
    
    messages = [
        {"role": "system", "content": "You are an expert at extracting and structuring traditional astrological rules."},
        {"role": "user", "content": prompt}
    ]
    
    try:
        response = await client.chat(messages=messages, temperature=0.1)
        content = response.get("content", "[]")
        
        # Strip potential markdown code blocks
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'\s*```', '', content)
        
        rules = json.loads(content)
        return rules
    except Exception as e:
        print(f"Error extracting rules: {e}")
        return []

async def ingest_file(file_path: str, source_name: str, output_file: str):
    """Ingest a large text file by chunking it and processing each chunk."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    with open(file_path, 'r') as f:
        content = f.read()

    # Simple chunking by paragraph or length
    chunks = [content[i:i+4000] for i in range(0, len(content), 4000)]
    print(f"Processing {len(chunks)} chunks for {source_name}...")

    all_rules = []
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}/{len(chunks)}...")
        rules = await extract_rules_from_chunk(chunk, source_name)
        # Assign unique IDs
        for j, r in enumerate(rules):
            r["id"] = f"{source_name.upper()}_{i}_{j}"
        all_rules.extend(rules)
        # Small delay to avoid rate limits
        await asyncio.sleep(0.5)

    # Save to output file (merge if exists)
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            try:
                existing = json.load(f)
                all_rules.extend(existing)
            except:
                pass

    with open(output_file, 'w') as f:
        json.dump(all_rules, f, indent=2)
    
    print(f"Success! Ingested {len(all_rules)} total rules into {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python ingest_rules.py <input_file> <source_name>")
        sys.exit(1)

    input_file = sys.argv[1]
    source = sys.argv[2]
    output = "thia_lite/rules/public_domain_rules_data.json"
    
    asyncio.run(ingest_file(input_file, source, output))
