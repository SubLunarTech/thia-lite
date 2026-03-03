import json
import os
from pathlib import Path

def convert_rules(source_path, target_path, source_name):
    print(f"Converting rules from {source_path}...")
    with open(source_path, 'r') as f:
        source_data = json.load(f)
    
    source_rules = source_data.get('rules', [])
    converted_rules = []
    
    for i, rule in enumerate(source_rules):
        # Merge condition and outcome into text
        condition = rule.get('condition', '')
        outcome = rule.get('outcome', '')
        text = f"If {condition}, then {outcome}"
        
        # Determine confidence (default to 0.7 if not provided)
        confidence = rule.get('confidence', 0.7)
        
        converted_rule = {
            "id": f"{source_name[:4].upper()}_{i+1000}",
            "category": rule.get('branch', 'general'),
            "text": text,
            "planets": rule.get('planets', []),
            "signs": rule.get('signs', []),
            "houses": rule.get('houses', []),
            "confidence": confidence,
            "source": source_name
        }
        converted_rules.append(converted_rule)
    
    with open(target_path, 'w') as f:
        json.dump(converted_rules, f, indent=2)
    
    print(f"✅ Successfully converted {len(converted_rules)} rules to {target_path}")

if __name__ == "__main__":
    source = "/home/opc/mlearn/extracted_rules/picatrix_ghayat_al_hakim_english_mt_cleaned_v8.json"
    target = "/home/opc/thia-lite/thia_lite/rules/picatrix_rules_data.json"
    convert_rules(source, target, "Picatrix (Ghayat al-Hakim)")
