#!/usr/bin/env python3
"""
Create a tailored CV for a specific school application.

Usage:
    python create_tailored_cv.py <school_folder_path>
    python create_tailored_cv.py <school_folder_path> --name "ShortName"

Examples:
    python create_tailored_cv.py ../02_Project/Job/02_Applications/10_UK/10.23_StAndrews_FinancialManagement_20260305
    python create_tailored_cv.py ../02_Project/Job/02_Applications/10_UK/10.24_NewSchool_Finance_20260401 --name NewSchool

What it does:
    1. Copies cv.tex → CV_Academic_PeiChu_{ShortName}.tex into the school folder
    2. Copies citations.bib into the school folder
    3. Adds %TAILOR markers for easy customization
    4. Prints instructions for what to customize
"""

import argparse
import os
import re
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
MASTER_CV = SCRIPT_DIR / "cv.tex"
MASTER_BIB = SCRIPT_DIR / "citations.bib"


def extract_school_name(folder_path: str) -> str:
    """Extract short school name from folder naming convention.
    e.g., '10.23_StAndrews_FinancialManagement_20260305' -> 'StAndrews'
    """
    folder_name = Path(folder_path).name
    # Match pattern: XX.XX_SchoolName_Position_Date
    match = re.match(r'\d+\.\d+_([^_]+)_', folder_name)
    if match:
        return match.group(1)
    # Fallback: use folder name
    return folder_name


def add_tailor_markers(content: str) -> str:
    """Add %TAILOR markers to key customization points in the CV."""

    # Add tailor instruction block after \begin{document}
    tailor_block = r"""
%% =========================================================================
%% TAILORING GUIDE — Customize for this specific application
%% =========================================================================
%% Search for %TAILOR to find all customization points.
%%
%% Priority 1 (MUST change):
%%   - Profile section: tailor to match job description keywords
%%   - Research Interests: align with department's research themes
%%
%% Priority 2 (CONSIDER changing):
%%   - Teaching bullets: emphasize modules relevant to this school
%%   - Working paper order: put most relevant paper first
%%   - Professional experience: emphasize relevant skills
%%
%% Priority 3 (OPTIONAL):
%%   - Reorder sections to match what the school values most
%%   - Add/remove Chinese publications based on relevance
%% =========================================================================
"""

    content = content.replace(
        r'\pagestyle{empty}',
        r'\pagestyle{empty}' + '\n' + tailor_block,
        1
    )

    # Mark Profile section
    content = content.replace(
        r'\section{Profile}',
        r'\section{Profile}' + '\n' + '%TAILOR: Rewrite profile to match job description keywords and school focus',
        1
    )

    # Mark Research Interests
    content = content.replace(
        r'\section{Research Interests}',
        r'\section{Research Interests}' + '\n' + '%TAILOR: Align with department research themes; reorder or replace areas',
        1
    )

    # Mark Teaching section
    content = content.replace(
        r'\section{Teaching Experience}',
        r'\section{Teaching Experience}' + '\n' + '%TAILOR: Emphasize modules relevant to this school; mention courses you could teach',
        1
    )

    return content


def create_tailored_cv(school_folder: str, short_name: str = None):
    """Create a tailored CV in the target school folder."""

    school_path = Path(school_folder).resolve()

    if not school_path.exists():
        print(f"Error: Folder does not exist: {school_path}")
        print("Create the folder first, then run this script.")
        return False

    if short_name is None:
        short_name = extract_school_name(school_folder)

    # Target file names
    cv_filename = f"CV_Academic_PeiChu_{short_name}.tex"
    bib_filename = "citations.bib"

    cv_target = school_path / cv_filename
    bib_target = school_path / bib_filename

    # Check if files already exist
    if cv_target.exists():
        response = input(f"  {cv_filename} already exists. Overwrite? [y/N]: ")
        if response.lower() != 'y':
            print("  Skipped CV file.")
            return False

    # Read master CV
    with open(MASTER_CV, 'r') as f:
        cv_content = f.read()

    # Add tailor markers
    cv_content = add_tailor_markers(cv_content)

    # Write tailored CV
    with open(cv_target, 'w') as f:
        f.write(cv_content)
    print(f"  Created: {cv_target}")

    # Copy citations.bib
    shutil.copy2(MASTER_BIB, bib_target)
    print(f"  Copied:  {bib_target}")

    # Print instructions
    print(f"""
{'='*60}
  Tailored CV created for: {short_name}
{'='*60}

  Files:
    {cv_target}
    {bib_target}

  Next steps:
    1. Open {cv_filename}
    2. Search for %TAILOR to find customization points
    3. Edit Profile to match job description
    4. Edit Research Interests to match department
    5. Compile:
       cd "{school_path}"
       latexmk -pdf {cv_filename}

  Quick compile command:
    cd "{school_path}" && latexmk -pdf {cv_filename}
{'='*60}
""")
    return True


def sync_master(school_folder: str, short_name: str = None):
    """Show diff between master and tailored version (for updates)."""
    school_path = Path(school_folder).resolve()
    if short_name is None:
        short_name = extract_school_name(school_folder)

    cv_filename = f"CV_Academic_PeiChu_{short_name}.tex"
    cv_target = school_path / cv_filename

    if not cv_target.exists():
        print(f"  No tailored CV found at {cv_target}")
        return

    print(f"  To see differences from master:")
    print(f"    diff {MASTER_CV} {cv_target}")
    print(f"\n  To update citations.bib from master:")
    print(f"    cp {MASTER_BIB} {school_path / 'citations.bib'}")


def list_tailored_cvs():
    """List all tailored CVs across application folders."""
    apps_dir = SCRIPT_DIR.parent / "02_Project" / "Job" / "02_Applications"
    if not apps_dir.exists():
        print(f"  Applications directory not found: {apps_dir}")
        return

    print(f"\n  Tailored CVs found:\n")
    count = 0
    for cv_file in sorted(apps_dir.rglob("CV_Academic_PeiChu_*.tex")):
        rel_path = cv_file.relative_to(SCRIPT_DIR.parent)
        pdf_exists = cv_file.with_suffix('.pdf').exists()
        status = "PDF" if pdf_exists else "TEX only"
        print(f"    [{status:>8}] {rel_path}")
        count += 1

    if count == 0:
        print("    (none found)")
    else:
        print(f"\n  Total: {count} tailored CVs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create tailored CV for school applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create tailored CV for StAndrews
  python create_tailored_cv.py ../02_Project/Job/02_Applications/10_UK/10.23_StAndrews_FinancialManagement_20260305

  # Create with custom short name
  python create_tailored_cv.py /path/to/school/folder --name Oxford

  # List all tailored CVs
  python create_tailored_cv.py --list

  # Show sync status for a school
  python create_tailored_cv.py /path/to/school/folder --sync
        """
    )

    parser.add_argument("school_folder", nargs="?", help="Path to school application folder")
    parser.add_argument("--name", help="Short name for the school (auto-detected if omitted)")
    parser.add_argument("--list", action="store_true", help="List all tailored CVs")
    parser.add_argument("--sync", action="store_true", help="Show sync status with master")

    args = parser.parse_args()

    if args.list:
        list_tailored_cvs()
    elif args.school_folder is None:
        parser.print_help()
    elif args.sync:
        sync_master(args.school_folder, args.name)
    else:
        create_tailored_cv(args.school_folder, args.name)
