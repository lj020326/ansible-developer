import os
import re
import sys

def main(dry_run=True):
    root = os.getcwd()  # run the script from inside the show folder
    renamed = 0

    for year_str in sorted(os.listdir(root)):
        if not re.match(r'^\d{4}$', year_str):
            continue  # skip Extras, Private Snafu, etc.
        year_path = os.path.join(root, year_str)
        if not os.path.isdir(year_path):
            continue

        files = []
        for f in os.listdir(year_path):
            if f.lower().endswith('.avi'):
                # Extract sort key from the date prefix (090030DVD, 011841DVD, etc.)
                match = re.match(r'^(\d+)', f)
                sort_key = int(match.group(1)) if match else 999999
                files.append((sort_key, f, os.path.join(year_path, f)))

        if not files:
            continue

        files.sort(key=lambda x: x[0])  # chronological order = TVDB order

        print(f"\n=== Processing Season {year_str} ({len(files)} episodes) ===")
        for i, (sort_key, old_name, old_path) in enumerate(files, 1):
            base, ext = os.path.splitext(old_name)
            # Remove the dateDVD prefix
            clean_title = re.sub(r'^\d+DVD\s*', '', base).strip()
            new_name = f"Looney Tunes - S{year_str}E{i:02d} - {clean_title}{ext}"
            new_path = os.path.join(year_path, new_name)

            if dry_run:
                print(f"   {old_name}  →  {new_name}")
            else:
                if os.path.exists(new_path):
                    print(f"   SKIPPED (already exists): {new_name}")
                else:
                    os.rename(old_path, new_path)
                    print(f"   RENAMED: {new_name}")
                    renamed += 1

    if dry_run:
        print("\n=== DRY RUN COMPLETE ===")
        script_name = os.path.basename(__file__)
        print("Review the list above. If everything looks good, run again with:")
        print(f"   python3 {script_name} --execute")
    else:
        print(f"\n=== DONE! {renamed} files renamed ===")


if __name__ == "__main__":
    dry = "--execute" not in sys.argv
    main(dry)
