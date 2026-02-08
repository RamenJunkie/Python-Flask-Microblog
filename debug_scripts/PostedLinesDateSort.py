#!/usr/bin/env python3
"""
Sort markdown file entries by date in ascending order and remove duplicates.
Each line should start with a timestamp in format [YYYY-MM-DD HH:MM:SS]
Duplicates are identified by URL (the second field after splitting by |)
"""

import sys
from datetime import datetime

def parse_date(line):
    """Extract and parse the date from a line."""
    try:
        # Extract the date string between brackets
        date_str = line.split(']')[0].replace('[', '')
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, IndexError):
        # Return a very old date for lines that can't be parsed
        # This will put them at the beginning
        return datetime.min

def extract_url(line):
    """Extract the URL from a line (second field after splitting by |)."""
    try:
        parts = line.split('|')
        if len(parts) >= 2:
            return parts[1].strip()
    except:
        pass
    return None

def sort_markdown_file(input_file, output_file=None):
    """
    Sort lines in a markdown file by their timestamp and remove duplicates.
    
    Args:
        input_file: Path to input file
        output_file: Path to output file (if None, overwrites input)
    """
    # Read all lines
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Remove duplicates based on URL, keeping the first occurrence
    seen_urls = set()
    unique_lines = []
    duplicates_removed = 0
    
    for line in lines:
        url = extract_url(line)
        if url and url in seen_urls:
            duplicates_removed += 1
            continue
        if url:
            seen_urls.add(url)
        unique_lines.append(line)
    
    # Sort lines by their date
    sorted_lines = sorted(unique_lines, key=parse_date)
    
    # Write to output file
    output_path = output_file if output_file else input_file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(sorted_lines)
    
    print(f"Processed {len(lines)} lines")
    print(f"Removed {duplicates_removed} duplicate(s)")
    print(f"Sorted {len(sorted_lines)} unique lines")
    print(f"Output written to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sort_markdown.py <input_file> [output_file]")
        print("  If output_file is not specified, input file will be overwritten")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    sort_markdown_file(input_file, output_file)