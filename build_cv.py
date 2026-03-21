#!/usr/bin/env python3
"""
Build a precision one-page CV by matching content atoms to JD criteria.
Atoms contain actual LaTeX — the generator renders them directly, no \input.

Usage:
    python build_cv.py --jd <job_posting.md> --school Leeds
    python build_cv.py --school Bath --preset teaching
    python build_cv.py --list
"""

import argparse
import subprocess
import yaml
from pathlib import Path
from collections import defaultdict, OrderedDict

SCRIPT_DIR = Path(__file__).parent.resolve()
INVENTORY_PATH = SCRIPT_DIR / "content_inventory.yaml"
SCHOOLS_DIR = SCRIPT_DIR / "schools"

SECTION_ORDER = [
    "header", "profile", "education", "research_interests",
    "publications", "conference", "teaching", "research_experience",
    "professional", "skills", "awards", "service", "certifications"
]

SECTION_TITLES = {
    "education": "Education",
    "research_interests": "Research Interests",
    "publications": "Publications",
    "conference": "Conference Presentations",
    "teaching": "Teaching Experience",
    "research_experience": "Research Experience",
    "professional": "Professional Experience",
    "skills": "Research Skills",
    "awards": "Awards",
    "service": "Leadership \\& Service",
    "certifications": "Professional Certifications",
}

SECTION_HEADER_COST = 2  # lines per \section{}
PAGE_BUDGET = 43  # calibrated: 10pt scale=0.92, tested on StAndrews JD

# ─────────────────────────────────────────────────────────────────────────────
# LOADING
# ─────────────────────────────────────────────────────────────────────────────

def load_inventory() -> dict:
    with open(INVENTORY_PATH, 'r') as f:
        data = yaml.safe_load(f)
    return {k: v for k, v in data.items()
            if not k.startswith('_') and isinstance(v, dict) and 'latex' in v}


# ─────────────────────────────────────────────────────────────────────────────
# JD ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

CRITERIA_KEYWORDS = {
    'phd': ['phd', 'doctoral', 'doctorate'],
    'accounting_finance': ['accounting', 'finance', 'financial'],
    'publication_record': ['publication', 'published', 'peer-reviewed', 'journal', 'ref'],
    'research_quality': ['research excellence', 'high-quality', 'abs', 'ssci', 'impact'],
    'research_pipeline': ['working paper', 'research pipeline', 'research agenda'],
    'funded_research': ['grant', 'funding', 'esrc', 'leverhulme', 'external funding'],
    'quantitative_methods': ['quantitative', 'econometric', 'statistical', 'empirical'],
    'ML_skills': ['machine learning', 'artificial intelligence', 'data science', 'predictive'],
    'teaching_experience_UG': ['teaching', 'undergraduate', 'tutorial', 'lecture', 'module'],
    'supervision_PG': ['supervision', 'postgraduate', 'dissertation', 'thesis supervision'],
    'teaching_qualification': ['pgcert', 'hea', 'fellow', 'teaching qualification', 'fhea'],
    'curriculum_design': ['curriculum', 'module design', 'course development', 'programme'],
    'assessment_experience': ['assessment', 'marking', 'feedback', 'grading'],
    'industry_experience': ['industry', 'professional experience', 'practitioner'],
    'central_banking': ['banking', 'central bank', 'financial regulation', 'monetary'],
    'leadership': ['leadership', 'management', 'director', 'team lead'],
    'university_service': ['service', 'committee', 'administration', 'citizenship'],
    'student_support': ['pastoral', 'student support', 'wellbeing'],
    'international': ['international', 'global', 'cross-cultural', 'diversity'],
    'software_skills': ['stata', 'python', 'r ', 'programming', 'software'],
    'data_literacy': ['data', 'database', 'wrds', 'bloomberg'],
    'corporate_governance': ['corporate governance', 'board', 'executive'],
    'sustainable_finance': ['sustainable', 'esg', 'climate', 'responsible'],
    'technology_management': ['technology', 'digital', 'innovation', 'it governance'],
}

PRESETS = {
    'research': {
        'phd': 10, 'publication_record': 10, 'research_quality': 9,
        'quantitative_methods': 8, 'research_pipeline': 7,
        'teaching_experience_UG': 5, 'industry_experience': 4,
    },
    'teaching': {
        'phd': 10, 'teaching_experience_UG': 10, 'teaching_qualification': 9,
        'supervision_PG': 8, 'curriculum_design': 7, 'assessment_experience': 7,
        'publication_record': 6, 'industry_experience': 5,
    },
    'balanced': {
        'phd': 10, 'publication_record': 9, 'teaching_experience_UG': 9,
        'quantitative_methods': 7, 'supervision_PG': 7, 'industry_experience': 5,
    }
}


def extract_criteria_from_jd(jd_path: str) -> dict:
    with open(jd_path, 'r') as f:
        content = f.read().lower()
    criteria = {}
    for crit, keywords in CRITERIA_KEYWORDS.items():
        score = sum(content.count(kw) for kw in keywords)
        if score > 0:
            criteria[crit] = min(10, score + 3)
    return criteria


# ─────────────────────────────────────────────────────────────────────────────
# MATCHING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def score_atoms(inventory: dict, criteria: dict) -> list:
    scored = []
    for atom_id, atom in inventory.items():
        proves = set(atom.get('proves', []))
        base_pri = atom.get('priority', 5)

        # Apply boosts
        for crit in criteria:
            boosts = atom.get('priority_boost', {})
            if crit in boosts:
                base_pri += boosts[crit]

        if atom.get('fixed'):
            matched = [c for c in criteria if c in proves]
            scored.append({
                'id': atom_id, 'atom': atom, 'score': 100,
                'matched_criteria': matched or ['FIXED'],
                'lines': atom.get('lines', 1)
            })
        else:
            matched = [c for c in criteria if c in proves]
            crit_score = sum(criteria[c] for c in matched)
            scored.append({
                'id': atom_id, 'atom': atom,
                'score': base_pri + crit_score,
                'matched_criteria': matched,
                'lines': atom.get('lines', 1)
            })
    return scored


def select_atoms(scored: list, budget: int = PAGE_BUDGET) -> tuple:
    fixed = [a for a in scored if a['score'] >= 100]
    optional = [a for a in scored if a['score'] < 100]

    # Profile: pick best variant
    profiles = [a for a in optional if a['atom'].get('variant_of') == 'profile']
    others = [a for a in optional if a['atom'].get('variant_of') != 'profile']
    others.sort(key=lambda a: a['score'] / max(a['lines'], 0.5), reverse=True)

    selected = list(fixed)
    used_lines = sum(a['lines'] for a in selected)

    if profiles:
        best = max(profiles, key=lambda a: a['score'])
        selected.append(best)
        used_lines += best['lines']

    # Count section headers we'll need
    sections_used = set(a['atom']['section'] for a in selected)

    for atom in others:
        section = atom['atom'].get('section', 'other')
        new_section = section not in sections_used
        header_cost = SECTION_HEADER_COST if new_section else 0
        total_cost = atom['lines'] + header_cost

        if used_lines + total_cost > budget:
            continue
        if atom['score'] <= 3:
            continue

        selected.append(atom)
        used_lines += total_cost
        sections_used.add(section)

    covered = set()
    for a in selected:
        covered.update(a['matched_criteria'])

    return selected, used_lines, covered


# ─────────────────────────────────────────────────────────────────────────────
# LATEX GENERATION — INLINE, NO \input
# ─────────────────────────────────────────────────────────────────────────────

def generate_onepage_tex(school: str, selected: list) -> Path:
    """Generate a standalone .tex with inline content from selected atoms."""
    out_path = SCHOOLS_DIR / f"{school.lower()}.tex"

    # Group by section, preserving order
    by_section = OrderedDict()
    for sec in SECTION_ORDER:
        atoms = [a for a in selected if a['atom'].get('section') == sec]
        if atoms:
            by_section[sec] = atoms

    lines = [
        f"% schools/{school.lower()}.tex — Auto-generated one-page CV for {school}",
        f"% Built by build_cv.py criteria matching engine",
        r"\input{cv_base}",
        r"\begin{document}",
        r"\pagestyle{empty}",
        "",
    ]

    for section, atoms in by_section.items():
        # Header and profile have their own \section inside their latex
        if section in ('header', 'profile'):
            for a in atoms:
                latex = a['atom']['latex'].strip()
                lines.append(latex)
                lines.append("")
            continue

        # Add section header
        title = SECTION_TITLES.get(section, section.replace('_', ' ').title())
        lines.append(f"\\section{{{title}}}")
        lines.append("")

        # Separate parent (header) atoms and child (bullet) atoms
        parents = [a for a in atoms if not a['atom'].get('is_bullet')]
        children = [a for a in atoms if a['atom'].get('is_bullet')]

        # Build parent → children map
        children_map = defaultdict(list)
        orphan_bullets = []
        for c in children:
            p = c['atom'].get('parent')
            if p:
                children_map[p].append(c)
            else:
                orphan_bullets.append(c)

        # Render each parent followed by its children
        for p in parents:
            latex = p['atom']['latex'].strip()
            lines.append(latex)
            kids = children_map.get(p['id'], [])
            if kids:
                lines.append(r"\begin{itemize}[nosep, leftmargin=1em, itemsep=1pt, label=--]")
                for k in kids:
                    lines.append(f"    \\item {k['atom']['latex'].strip()}")
                lines.append(r"\end{itemize}")
            lines.append("")

        # Render orphan bullets (no parent)
        if orphan_bullets:
            lines.append(r"\begin{itemize}[nosep, leftmargin=1em, itemsep=1pt, label=--]")
            for b in orphan_bullets:
                lines.append(f"    \\item {b['atom']['latex'].strip()}")
            lines.append(r"\end{itemize}")
            lines.append("")

    lines.extend([
        r"\vfill",
        r"\center{\footnotesize Last updated: \today}",
        r"\end{document}",
    ])

    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# COMPILE & VERIFY
# ─────────────────────────────────────────────────────────────────────────────

def compile_and_check(tex_path: Path) -> int:
    print(f"\n  Compiling: {tex_path.name}")
    subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode",
         f"-outdir={SCHOOLS_DIR}", str(tex_path)],
        cwd=str(SCRIPT_DIR), capture_output=True, text=True
    )
    pdf_path = SCHOOLS_DIR / tex_path.with_suffix('.pdf').name
    if not pdf_path.exists():
        print(f"  ❌ Compilation failed")
        return -1

    try:
        r = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True)
        for line in r.stdout.split('\n'):
            if 'Pages:' in line:
                pages = int(line.split(':')[1].strip())
                if pages == 1:
                    print(f"  ✅ ONE PAGE — {pdf_path}")
                else:
                    print(f"  ⚠️  {pages} PAGES — needs trimming. {pdf_path}")
                return pages
    except:
        pass
    print(f"  PDF: {pdf_path}")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────────────────────────────────────

def print_report(criteria: dict, selected: list, covered: set, used_lines: int):
    print("=" * 70)
    print("  CRITERIA MATCHING REPORT")
    print("=" * 70)

    print(f"\n  {'Criterion':<30} {'Wt':>3} {'Status':>8} {'Covered by'}")
    print(f"  {'─'*30} {'─'*3} {'─'*8} {'─'*30}")

    uncovered = []
    for crit, weight in sorted(criteria.items(), key=lambda x: -x[1]):
        hit = crit in covered
        icon = " ✅ " if hit else " ❌ "
        by = ""
        if hit:
            for a in selected:
                if crit in a.get('matched_criteria', []):
                    by = a['id']
                    break
        print(f"  {crit:<30} {weight:>3} {icon:>8} {by}")
        if not hit:
            uncovered.append((crit, weight))

    total = len(criteria)
    matched = total - len(uncovered)
    print(f"\n  Coverage: {matched}/{total} criteria")
    print(f"  Content lines: {used_lines}/{PAGE_BUDGET}")

    if uncovered:
        print(f"\n  ⚠️  UNCOVERED:")
        for c, w in uncovered:
            print(f"     - {c} (weight: {w})")

    # Show selected atoms by section
    print(f"\n  {'─'*70}")
    print(f"  SELECTED ({len(selected)} atoms):")
    for sec in SECTION_ORDER:
        atoms = [a for a in selected if a['atom'].get('section') == sec]
        if atoms:
            print(f"\n  [{sec.upper()}]")
            for a in atoms:
                tag = "FIXED" if a['score'] >= 100 else f"{a['score']}"
                print(f"    {a['id']:<35} {a['lines']}L  score={tag}")
    print("=" * 70)


# ─────────────────────────────────────────────────────────────────────────────
# LIST
# ─────────────────────────────────────────────────────────────────────────────

def list_atoms():
    inv = load_inventory()
    print(f"\n  Content Inventory: {len(inv)} atoms\n")
    print(f"  {'ID':<35} {'Section':<18} {'L':>2} {'P':>3} {'Bullet':>6}  Proves")
    print(f"  {'─'*35} {'─'*18} {'─'*2} {'─'*3} {'─'*6}  {'─'*35}")
    for k, v in sorted(inv.items(), key=lambda x: (x[1].get('section',''), -x[1].get('priority',0))):
        sec = v.get('section','?')
        lines = v.get('lines',1)
        pri = v.get('priority',0)
        bullet = "  •" if v.get('is_bullet') else ""
        fixed = " [F]" if v.get('fixed') else ""
        proves = ', '.join(v.get('proves',[])[:3])
        print(f"  {k:<35} {sec:<18} {lines:>2} {pri:>3} {bullet:>6}  {proves}{fixed}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build precision one-page CV")
    parser.add_argument("--school", help="School short name")
    parser.add_argument("--jd", help="Path to job description")
    parser.add_argument("--preset", choices=["research", "teaching", "balanced"])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--deploy", help="Copy to school folder")
    args = parser.parse_args()

    if args.list:
        list_atoms()
    elif args.school and (args.jd or args.preset):
        inv = load_inventory()
        print(f"\n  Loaded {len(inv)} atoms")

        if args.jd:
            print(f"  JD: {args.jd}")
            criteria = extract_criteria_from_jd(args.jd)
        else:
            print(f"  Preset: {args.preset.upper()}")
            criteria = PRESETS[args.preset]

        print(f"  Criteria: {len(criteria)}")

        scored = score_atoms(inv, criteria)
        selected, used, covered = select_atoms(scored)
        print_report(criteria, selected, covered, used)

        if not args.report_only:
            tex = generate_onepage_tex(args.school, selected)
            print(f"\n  Generated: {tex}")
            pages = compile_and_check(tex)

            if args.deploy:
                import shutil
                target = Path(args.deploy)
                pdf = SCHOOLS_DIR / f"{args.school.lower()}.pdf"
                for src in [tex, pdf]:
                    if src.exists():
                        dst = target / f"CV_Academic_PeiChu_{args.school}{src.suffix}"
                        shutil.copy2(src, dst)
                        print(f"  Deployed: {dst}")
                shutil.copy2(SCRIPT_DIR / "citations.bib", target / "citations.bib")
    else:
        parser.print_help()
