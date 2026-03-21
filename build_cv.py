#!/usr/bin/env python3
"""
Build a precision one-page CV by matching content atoms to JD criteria.

Usage:
    # Auto-match from JD (RECOMMENDED)
    python build_cv.py --jd <job_posting.md> --school Leeds

    # Manual preset
    python build_cv.py --school Bath --preset teaching

    # List available atoms
    python build_cv.py --list

    # Show matching report only (no compile)
    python build_cv.py --jd <job_posting.md> --school Leeds --report-only
"""

import argparse
import os
import re
import subprocess
import yaml
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).parent.resolve()
SECTIONS_DIR = SCRIPT_DIR / "sections"
SCHOOLS_DIR = SCRIPT_DIR / "schools"
INVENTORY_PATH = SCRIPT_DIR / "content_inventory.yaml"

# Page budget
PAGE_BUDGET = 36  # available content lines (after header + section overhead + footer)


def load_inventory() -> dict:
    """Load content inventory from YAML."""
    with open(INVENTORY_PATH, 'r') as f:
        data = yaml.safe_load(f)
    # Filter out metadata keys
    return {k: v for k, v in data.items() if not k.startswith('_') and isinstance(v, dict) and 'text' in v}


def extract_criteria_from_jd(jd_path: str) -> dict:
    """Extract criteria and keywords from a job description file."""
    with open(jd_path, 'r') as f:
        content = f.read().lower()

    # Common criteria patterns in academic JDs
    criteria_keywords = {
        # Qualifications
        'phd': ['phd', 'doctoral', 'doctorate'],
        'accounting_finance': ['accounting', 'finance', 'financial'],
        'masters_degree': ['master', 'msc', 'mba'],

        # Research
        'publication_record': ['publication', 'published', 'peer-reviewed', 'journal', 'ref'],
        'research_quality': ['research excellence', 'high-quality', 'abs', 'ssci', 'impact factor'],
        'research_pipeline': ['working paper', 'research pipeline', 'active research', 'research agenda'],
        'research_vision': ['research plan', 'research strategy', 'future research', '5-year'],
        'funded_research': ['grant', 'funding', 'esrc', 'leverhulme', 'external funding'],
        'quantitative_methods': ['quantitative', 'econometric', 'statistical', 'empirical'],
        'ML_skills': ['machine learning', 'artificial intelligence', 'data science', 'predictive'],

        # Teaching
        'teaching_experience_UG': ['teaching', 'undergraduate', 'tutorial', 'lecture', 'module delivery'],
        'supervision_PG': ['supervision', 'postgraduate', 'dissertation', 'thesis supervision'],
        'teaching_qualification': ['pgcert', 'hea', 'fellow', 'teaching qualification', 'sfhea', 'fhea'],
        'curriculum_design': ['curriculum', 'module design', 'course development', 'programme'],
        'assessment_experience': ['assessment', 'marking', 'feedback', 'grading'],

        # Professional
        'industry_experience': ['industry', 'professional experience', 'practitioner', 'sector experience'],
        'central_banking': ['banking', 'central bank', 'financial regulation', 'monetary policy'],
        'leadership': ['leadership', 'management', 'director', 'team lead'],

        # Institutional
        'university_service': ['service', 'committee', 'administration', 'citizenship'],
        'student_support': ['pastoral', 'student support', 'wellbeing', 'student experience'],
        'international': ['international', 'global', 'cross-cultural', 'diversity'],

        # Methods/Skills
        'software_skills': ['stata', 'python', 'r ', 'matlab', 'programming', 'software'],
        'data_literacy': ['data', 'database', 'wrds', 'bloomberg', 'compustat'],

        # Specific
        'corporate_governance': ['corporate governance', 'board', 'executive', 'ceo', 'cto'],
        'sustainable_finance': ['sustainable', 'esg', 'climate', 'responsible', 'green finance'],
        'banking': ['banking', 'bank', 'fintech', 'financial services'],
        'technology_management': ['technology', 'digital', 'innovation', 'it governance'],
    }

    found_criteria = {}
    for criterion, keywords in criteria_keywords.items():
        score = sum(content.count(kw) for kw in keywords)
        if score > 0:
            # Weight: essential criteria mentioned more often get higher weight
            weight = min(10, score + 3)  # base 3 + frequency, capped at 10
            found_criteria[criterion] = {
                'weight': weight,
                'frequency': score,
                'keywords_found': [kw for kw in keywords if kw in content]
            }

    return found_criteria


def match_atoms_to_criteria(inventory: dict, criteria: dict) -> list:
    """Score each atom based on how many/how well it matches JD criteria."""
    scored_atoms = []

    for atom_id, atom in inventory.items():
        if atom.get('fixed'):
            # Fixed atoms always included, but still track their criteria coverage
            proves = set(atom.get('proves', []))
            matched = [c for c in criteria if c in proves]
            scored_atoms.append({
                'id': atom_id,
                'atom': atom,
                'score': 100,  # always include
                'matched_criteria': matched if matched else ['FIXED'],
                'lines': atom.get('lines', 1)
            })
            continue

        # Calculate match score
        proves = set(atom.get('proves', []))
        base_priority = atom.get('priority', 5)
        matched = []
        criteria_score = 0

        for criterion, info in criteria.items():
            if criterion in proves:
                criteria_score += info['weight']
                matched.append(criterion)

            # Check priority boosts
            boosts = atom.get('priority_boost', {})
            if criterion in boosts:
                base_priority += boosts[criterion]

        total_score = base_priority + criteria_score

        scored_atoms.append({
            'id': atom_id,
            'atom': atom,
            'score': total_score,
            'matched_criteria': matched,
            'lines': atom.get('lines', 1)
        })

    return scored_atoms


def select_atoms_for_one_page(scored_atoms: list, budget: int = PAGE_BUDGET) -> tuple:
    """Select optimal subset of atoms that fits in one page (greedy knapsack)."""
    # Separate fixed and optional
    fixed = [a for a in scored_atoms if a['score'] >= 100]
    optional = [a for a in scored_atoms if a['score'] < 100]

    # Sort optional by score density (score / lines)
    optional.sort(key=lambda a: a['score'] / max(a['lines'], 0.5), reverse=True)

    # Start with fixed atoms
    selected = list(fixed)
    used_lines = sum(a['lines'] for a in selected)

    # Handle profile variants: pick the best one
    profile_atoms = [a for a in optional if a['atom'].get('variant_of') == 'profile']
    other_atoms = [a for a in optional if a['atom'].get('variant_of') != 'profile']

    if profile_atoms:
        best_profile = max(profile_atoms, key=lambda a: a['score'])
        if used_lines + best_profile['lines'] <= budget:
            selected.append(best_profile)
            used_lines += best_profile['lines']

    # Greedy fill with remaining atoms
    used_sections = set()
    for atom in other_atoms:
        if used_lines + atom['lines'] > budget:
            continue
        if atom['score'] <= 3:  # skip very low value atoms
            continue
        selected.append(atom)
        used_lines += atom['lines']
        used_sections.add(atom['atom'].get('section', 'unknown'))

    # Collect all covered criteria
    all_covered = set()
    for a in selected:
        all_covered.update(a['matched_criteria'])

    return selected, used_lines, all_covered


def generate_matching_report(criteria: dict, selected: list, all_covered: set, used_lines: int) -> str:
    """Generate a human-readable matching report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  CRITERIA MATCHING REPORT")
    lines.append("=" * 70)

    # Coverage table
    lines.append(f"\n  {'Criterion':<30} {'Weight':>6} {'Covered':>8} {'By Atom'}")
    lines.append(f"  {'─'*30} {'─'*6} {'─'*8} {'─'*30}")

    uncovered = []
    for criterion, info in sorted(criteria.items(), key=lambda x: -x[1]['weight']):
        covered = criterion in all_covered
        status = "  ✅  " if covered else "  ❌  "
        # Find which atom covers it
        covering_atom = ""
        if covered:
            for a in selected:
                if criterion in a.get('matched_criteria', []):
                    covering_atom = a['id']
                    break
        lines.append(f"  {criterion:<30} {info['weight']:>6} {status:>8} {covering_atom}")
        if not covered:
            uncovered.append(criterion)

    # Summary
    total_criteria = len(criteria)
    covered_count = total_criteria - len(uncovered)
    lines.append(f"\n  Coverage: {covered_count}/{total_criteria} criteria matched")
    lines.append(f"  Lines used: {used_lines}/{PAGE_BUDGET}")

    if uncovered:
        lines.append(f"\n  ⚠️  UNCOVERED CRITERIA:")
        for c in uncovered:
            lines.append(f"     - {c} (weight: {criteria[c]['weight']})")

    # Selected atoms by section
    lines.append(f"\n  {'─'*70}")
    lines.append(f"  SELECTED CONTENT ({len(selected)} atoms, {used_lines} lines):")
    lines.append(f"  {'─'*70}")

    sections_order = ['header', 'profile', 'education', 'research_interests',
                      'publications', 'conference', 'teaching', 'research_experience',
                      'professional', 'skills', 'awards', 'service', 'certifications']

    for section in sections_order:
        section_atoms = [a for a in selected if a['atom'].get('section') == section]
        if section_atoms:
            lines.append(f"\n  [{section.upper()}]")
            for a in section_atoms:
                score_str = "FIXED" if a['score'] >= 100 else f"score={a['score']}"
                lines.append(f"    {a['id']:<35} ({a['lines']}L, {score_str})")

    lines.append(f"\n{'='*70}")
    return '\n'.join(lines)


def generate_onepage_tex(school_name: str, selected: list, output_path: Path = None) -> Path:
    """Generate a one-page .tex file from selected atoms."""
    if output_path is None:
        output_path = SCHOOLS_DIR / f"{school_name.lower()}.tex"

    # Group selected atoms by section
    sections = defaultdict(list)
    for atom in selected:
        section = atom['atom'].get('section', 'other')
        sections[section].append(atom)

    # Section order
    section_order = ['header', 'profile', 'education', 'research_interests',
                     'publications', 'conference', 'teaching', 'research_experience',
                     'professional', 'skills', 'awards', 'service', 'certifications']

    # Map section to .tex file
    section_to_file = {
        'header': 'header',
        'education': 'education',
        'publications': 'publications',
        'conference': 'conference',
        'research_interests': 'research_interests',
        'skills': 'skills',
        'service': 'service',
        'certifications': 'certifications',
        'research_experience': 'research_experience',
    }

    # For sections with variants, determine which variant
    profile_atoms = sections.get('profile', [])
    if profile_atoms:
        best = max(profile_atoms, key=lambda a: a['score'])
        variant = best['atom'].get('variant_of', '')
        if 'research' in best['id']:
            section_to_file['profile'] = 'profile_research'
        elif 'teaching' in best['id']:
            section_to_file['profile'] = 'profile_teaching'
        else:
            section_to_file['profile'] = 'profile_balanced'

    # Determine teaching variant based on whether modules atom is selected
    teaching_atoms = sections.get('teaching', [])
    has_modules = any('modules' in a['id'] for a in teaching_atoms)
    teaching_count = len(teaching_atoms)
    if has_modules:
        section_to_file['teaching'] = 'teaching_with_modules'
    elif teaching_count <= 3:
        section_to_file['teaching'] = 'teaching_compact'
    else:
        section_to_file['teaching'] = 'teaching_full'

    # Professional variant
    prof_atoms = sections.get('professional', [])
    if len(prof_atoms) <= 2:
        section_to_file['professional'] = 'professional_compact'
    else:
        section_to_file['professional'] = 'professional_full'

    # Awards variant
    award_atoms = sections.get('awards', [])
    if len(award_atoms) <= 4:
        section_to_file['awards'] = 'awards_selected'
    else:
        section_to_file['awards'] = 'awards_full'

    # Build .tex content
    tex_lines = [
        f"% schools/{school_name.lower()}.tex — Auto-generated for {school_name}",
        f"% Generated by build_cv.py criteria matching engine",
        f"% Usage: cd academic-cv && latexmk -pdf schools/{school_name.lower()}.tex",
        r"\input{cv_base}",
        r"\begin{document}",
        r"\pagestyle{empty}",
        ""
    ]

    for section in section_order:
        if section not in sections:
            continue
        variant = section_to_file.get(section, section)
        tex_file = SECTIONS_DIR / f"{variant}.tex"
        if tex_file.exists():
            tex_lines.append(f"\\input{{sections/{variant}}}")

    tex_lines.extend([
        "",
        r"\vfill",
        r"\center{\footnotesize Last updated: \today}",
        r"\end{document}",
    ])

    with open(output_path, 'w') as f:
        f.write('\n'.join(tex_lines))

    return output_path


def compile_tex(tex_path: Path) -> bool:
    """Compile a .tex file using latexmk."""
    print(f"\n  Compiling: {tex_path}")
    result = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", str(tex_path)],
        cwd=str(SCRIPT_DIR),
        capture_output=True, text=True
    )

    # Check page count
    pdf_path = tex_path.with_suffix('.pdf')
    if pdf_path.exists():
        # Try to get page count
        try:
            count_result = subprocess.run(
                ["pdfinfo", str(pdf_path)],
                capture_output=True, text=True
            )
            for line in count_result.stdout.split('\n'):
                if 'Pages:' in line:
                    pages = int(line.split(':')[1].strip())
                    status = "✅ ONE PAGE" if pages == 1 else f"⚠️ {pages} PAGES — needs trimming"
                    print(f"  PDF: {pdf_path} ({status})")
                    return pages == 1
        except:
            pass
        print(f"  PDF created: {pdf_path}")
        return True
    else:
        print(f"  ❌ Compilation failed")
        return False


def list_atoms():
    """List all content atoms with their tags."""
    inventory = load_inventory()
    print(f"\n  Content Inventory: {len(inventory)} atoms\n")
    print(f"  {'ID':<35} {'Section':<20} {'Lines':>5} {'Pri':>4}  Proves")
    print(f"  {'─'*35} {'─'*20} {'─'*5} {'─'*4}  {'─'*40}")

    for atom_id, atom in sorted(inventory.items(), key=lambda x: (x[1].get('section', ''), -x[1].get('priority', 0))):
        section = atom.get('section', '?')
        lines = atom.get('lines', 1)
        pri = atom.get('priority', 0)
        proves = ', '.join(atom.get('proves', [])[:3])
        fixed = " [FIXED]" if atom.get('fixed') else ""
        print(f"  {atom_id:<35} {section:<20} {lines:>5} {pri:>4}  {proves}{fixed}")


def run_preset(school_name: str, preset: str):
    """Run with a preset configuration (research/teaching/balanced)."""
    print(f"\n  Preset: {preset.upper()} for {school_name}")

    # Create synthetic criteria based on preset
    presets = {
        'research': {
            'phd': {'weight': 10, 'frequency': 5, 'keywords_found': []},
            'publication_record': {'weight': 10, 'frequency': 5, 'keywords_found': []},
            'research_quality': {'weight': 9, 'frequency': 3, 'keywords_found': []},
            'quantitative_methods': {'weight': 8, 'frequency': 3, 'keywords_found': []},
            'research_pipeline': {'weight': 7, 'frequency': 2, 'keywords_found': []},
            'teaching_experience_UG': {'weight': 5, 'frequency': 1, 'keywords_found': []},
            'industry_experience': {'weight': 4, 'frequency': 1, 'keywords_found': []},
        },
        'teaching': {
            'phd': {'weight': 10, 'frequency': 5, 'keywords_found': []},
            'teaching_experience_UG': {'weight': 10, 'frequency': 5, 'keywords_found': []},
            'teaching_qualification': {'weight': 9, 'frequency': 3, 'keywords_found': []},
            'supervision_PG': {'weight': 8, 'frequency': 3, 'keywords_found': []},
            'curriculum_design': {'weight': 7, 'frequency': 2, 'keywords_found': []},
            'assessment_experience': {'weight': 7, 'frequency': 2, 'keywords_found': []},
            'publication_record': {'weight': 6, 'frequency': 1, 'keywords_found': []},
            'industry_experience': {'weight': 5, 'frequency': 1, 'keywords_found': []},
        },
        'balanced': {
            'phd': {'weight': 10, 'frequency': 5, 'keywords_found': []},
            'publication_record': {'weight': 9, 'frequency': 3, 'keywords_found': []},
            'teaching_experience_UG': {'weight': 9, 'frequency': 3, 'keywords_found': []},
            'quantitative_methods': {'weight': 7, 'frequency': 2, 'keywords_found': []},
            'supervision_PG': {'weight': 7, 'frequency': 2, 'keywords_found': []},
            'industry_experience': {'weight': 5, 'frequency': 1, 'keywords_found': []},
        }
    }

    return presets.get(preset, presets['balanced'])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build precision one-page CV by matching content atoms to JD criteria",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--school", help="Short name for the school")
    parser.add_argument("--jd", help="Path to job description file")
    parser.add_argument("--preset", choices=["research", "teaching", "balanced"], help="Use a preset instead of JD")
    parser.add_argument("--list", action="store_true", help="List all content atoms")
    parser.add_argument("--report-only", action="store_true", help="Show matching report without compiling")
    parser.add_argument("--compile", help="Compile an existing .tex file")
    parser.add_argument("--deploy", help="Copy to school application folder")

    args = parser.parse_args()

    if args.list:
        list_atoms()

    elif args.compile:
        compile_tex(Path(args.compile))

    elif args.school and (args.jd or args.preset):
        # Load inventory
        inventory = load_inventory()
        print(f"\n  Loaded {len(inventory)} content atoms")

        # Extract criteria
        if args.jd:
            print(f"  Analyzing JD: {args.jd}")
            criteria = extract_criteria_from_jd(args.jd)
        else:
            criteria = run_preset(args.school, args.preset)

        print(f"  Found {len(criteria)} matching criteria")

        # Match atoms to criteria
        scored = match_atoms_to_criteria(inventory, criteria)

        # Select optimal subset
        selected, used_lines, covered = select_atoms_for_one_page(scored)

        # Generate report
        report = generate_matching_report(criteria, selected, covered, used_lines)
        print(report)

        if not args.report_only:
            # Generate .tex
            tex_path = generate_onepage_tex(args.school, selected)
            print(f"\n  Generated: {tex_path}")

            # Compile
            compile_tex(tex_path)

            # Deploy if requested
            if args.deploy:
                import shutil
                target = Path(args.deploy)
                for ext in ['.tex', '.pdf']:
                    src = tex_path.with_suffix(ext)
                    if src.exists():
                        dst = target / f"CV_Academic_PeiChu_{args.school}{ext}"
                        shutil.copy2(src, dst)
                        print(f"  Deployed: {dst}")
                bib_dst = target / "citations.bib"
                shutil.copy2(SCRIPT_DIR / "citations.bib", bib_dst)

    else:
        parser.print_help()
