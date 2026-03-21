#!/usr/bin/env python3
"""
Build a modular CV by assembling section modules.

Usage:
    # Interactive: auto-recommend based on JD
    python build_cv.py --jd <path_to_job_posting.md> --school <ShortName>

    # Manual: specify modules directly
    python build_cv.py --school Leeds --profile research --teaching with_modules --professional compact --awards selected

    # List available modules
    python build_cv.py --list

    # Compile an existing school file
    python build_cv.py --compile schools/leeds.tex
"""

import argparse
import os
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
SECTIONS_DIR = SCRIPT_DIR / "sections"
SCHOOLS_DIR = SCRIPT_DIR / "schools"

# Available module variants
MODULES = {
    "header":       {"variants": ["header"], "required": True},
    "profile":      {"variants": ["profile_research", "profile_teaching", "profile_balanced"], "required": True},
    "education":    {"variants": ["education"], "required": True},
    "research_interests": {"variants": ["research_interests"], "required": False},
    "publications": {"variants": ["publications"], "required": True},
    "conference":   {"variants": ["conference"], "required": False},
    "teaching":     {"variants": ["teaching_full", "teaching_compact", "teaching_with_modules"], "required": True},
    "research_experience": {"variants": ["research_experience"], "required": False},
    "professional": {"variants": ["professional_full", "professional_compact"], "required": True},
    "skills":       {"variants": ["skills"], "required": True},
    "awards":       {"variants": ["awards_full", "awards_selected"], "required": False},
    "service":      {"variants": ["service"], "required": False},
    "certifications": {"variants": ["certifications"], "required": False},
}

# JD keyword → module recommendation mapping
JD_KEYWORDS = {
    "research": {
        "profile": "profile_research",
        "teaching": "teaching_compact",
        "professional": "professional_compact",
        "awards": "awards_selected",
        "section_order": [
            "header", "profile", "education", "research_interests",
            "publications", "conference", "research_experience",
            "teaching", "professional", "skills", "awards", "certifications"
        ]
    },
    "teaching": {
        "profile": "profile_teaching",
        "teaching": "teaching_with_modules",
        "professional": "professional_full",
        "awards": "awards_full",
        "section_order": [
            "header", "profile", "education", "teaching",
            "publications", "conference", "research_interests",
            "research_experience", "professional", "skills",
            "awards", "service", "certifications"
        ]
    },
    "balanced": {
        "profile": "profile_balanced",
        "teaching": "teaching_full",
        "professional": "professional_full",
        "awards": "awards_full",
        "section_order": [
            "header", "profile", "education", "research_interests",
            "publications", "conference", "teaching",
            "research_experience", "professional", "skills",
            "awards", "service", "certifications"
        ]
    }
}


def analyze_jd(jd_path: str) -> dict:
    """Analyze a job description to recommend module configuration."""
    with open(jd_path, 'r') as f:
        content = f.read().lower()

    # Score each focus type
    scores = {"research": 0, "teaching": 0, "balanced": 0}

    research_words = ["research", "publication", "REF", "journal", "academic output",
                      "research-active", "scholarly", "PhD supervision", "grant",
                      "funding", "research excellence", "research strategy"]
    teaching_words = ["teaching", "module", "curriculum", "student", "tutorial",
                      "lecture", "assessment", "pedagogy", "learning", "programme",
                      "course design", "teaching excellence", "education"]

    for word in research_words:
        scores["research"] += content.count(word.lower())
    for word in teaching_words:
        scores["teaching"] += content.count(word.lower())

    # Determine focus
    r, t = scores["research"], scores["teaching"]
    if r > t * 1.5:
        focus = "research"
    elif t > r * 1.5:
        focus = "teaching"
    else:
        focus = "balanced"

    return {
        "focus": focus,
        "scores": scores,
        "config": JD_KEYWORDS[focus]
    }


def generate_school_tex(school_name: str, config: dict, output_path: Path = None):
    """Generate a school-specific .tex file from module configuration."""
    if output_path is None:
        output_path = SCHOOLS_DIR / f"{school_name.lower()}.tex"

    section_order = config.get("section_order", JD_KEYWORDS["balanced"]["section_order"])

    lines = [
        f"% schools/{school_name.lower()}.tex — Auto-generated for {school_name}",
        f"% Focus: {config.get('focus', 'balanced')}",
        f"% Usage: cd academic-cv && latexmk -pdf schools/{school_name.lower()}.tex",
        r"\input{cv_base}",
        r"\begin{document}",
        r"\pagestyle{empty}",
        ""
    ]

    for section in section_order:
        # Determine which variant to use
        if section in config:
            variant = config[section]
        elif section in MODULES and len(MODULES[section]["variants"]) == 1:
            variant = MODULES[section]["variants"][0]
        else:
            variant = section  # Default: use section name as variant

        # Check file exists
        tex_file = SECTIONS_DIR / f"{variant}.tex"
        if tex_file.exists():
            lines.append(f"\\input{{sections/{variant}}}")
        else:
            lines.append(f"% WARNING: sections/{variant}.tex not found")

    lines.extend([
        "",
        r"\vfill",
        r"\center{\footnotesize Last updated: \today}",
        r"\end{document}",
    ])

    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    return output_path


def compile_tex(tex_path: Path):
    """Compile a .tex file using latexmk."""
    print(f"  Compiling: {tex_path}")
    result = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", str(tex_path)],
        cwd=str(SCRIPT_DIR),
        capture_output=True, text=True
    )
    pdf_path = tex_path.with_suffix('.pdf')
    if pdf_path.exists():
        print(f"  PDF created: {pdf_path}")
        return True
    else:
        print(f"  Compilation failed. Check log: {tex_path.with_suffix('.log')}")
        return False


def list_modules():
    """List all available section modules."""
    print("\n  Available Section Modules:\n")
    print(f"  {'Module':<22} {'Variants':<55} {'Required'}")
    print(f"  {'─'*22} {'─'*55} {'─'*8}")
    for name, info in MODULES.items():
        variants = ", ".join(info["variants"])
        req = "Yes" if info["required"] else "No"
        print(f"  {name:<22} {variants:<55} {req}")

    print(f"\n  Focus Presets:\n")
    for focus, config in JD_KEYWORDS.items():
        sections = " → ".join(config["section_order"][:6]) + " → ..."
        print(f"  {focus:<12} {sections}")
    print()


def copy_to_school_folder(school_tex: Path, target_folder: str, school_name: str):
    """Copy compiled CV to school application folder."""
    import shutil
    target = Path(target_folder)
    if not target.exists():
        print(f"  Target folder does not exist: {target}")
        return

    # Copy .tex and .pdf
    cv_name = f"CV_Academic_PeiChu_{school_name}"
    for ext in ['.tex', '.pdf']:
        src = school_tex.with_suffix(ext)
        if src.exists():
            dst = target / f"{cv_name}{ext}"
            shutil.copy2(src, dst)
            print(f"  Copied: {dst}")

    # Copy citations.bib
    bib_src = SCRIPT_DIR / "citations.bib"
    bib_dst = target / "citations.bib"
    shutil.copy2(bib_src, bib_dst)
    print(f"  Copied: {bib_dst}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build modular academic CV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-recommend from JD
  python build_cv.py --jd ../02_Project/Job/02_Applications/10_UK/10.25_Leeds/01_job_posting.md --school Leeds

  # Manual configuration
  python build_cv.py --school Bath --profile teaching --teaching with_modules --professional full

  # List available modules
  python build_cv.py --list

  # Compile existing school file
  python build_cv.py --compile schools/leeds.tex

  # Copy to school application folder
  python build_cv.py --school Leeds --deploy ../02_Project/Job/02_Applications/10_UK/10.25_Leeds/
        """
    )

    parser.add_argument("--school", help="Short name for the school")
    parser.add_argument("--jd", help="Path to job description file for auto-recommendation")
    parser.add_argument("--profile", choices=["research", "teaching", "balanced"], help="Profile variant")
    parser.add_argument("--teaching", choices=["full", "compact", "with_modules"], help="Teaching variant")
    parser.add_argument("--professional", choices=["full", "compact"], help="Professional experience variant")
    parser.add_argument("--awards", choices=["full", "selected"], help="Awards variant")
    parser.add_argument("--list", action="store_true", help="List available modules")
    parser.add_argument("--compile", help="Compile an existing .tex file")
    parser.add_argument("--deploy", help="Copy compiled CV to school application folder")
    parser.add_argument("--no-compile", action="store_true", help="Skip compilation")

    args = parser.parse_args()

    if args.list:
        list_modules()

    elif args.compile:
        compile_tex(Path(args.compile))

    elif args.jd and args.school:
        # Auto-recommend from JD
        print(f"\n  Analyzing JD: {args.jd}")
        analysis = analyze_jd(args.jd)
        focus = analysis["focus"]
        scores = analysis["scores"]
        config = analysis["config"]
        config["focus"] = focus

        print(f"  Focus detected: {focus.upper()}")
        print(f"  Keyword scores: research={scores['research']}, teaching={scores['teaching']}")
        print(f"\n  Recommended configuration:")
        print(f"    Profile:      {config.get('profile', 'balanced')}")
        print(f"    Teaching:     {config.get('teaching', 'full')}")
        print(f"    Professional: {config.get('professional', 'full')}")
        print(f"    Awards:       {config.get('awards', 'full')}")
        print(f"    Section order: {' → '.join(config['section_order'][:6])}...")

        # Apply manual overrides
        if args.profile:
            config["profile"] = f"profile_{args.profile}"
        if args.teaching:
            config["teaching"] = f"teaching_{args.teaching}"
        if args.professional:
            config["professional"] = f"professional_{args.professional}"
        if args.awards:
            config["awards"] = f"awards_{args.awards}"

        # Generate and compile
        tex_path = generate_school_tex(args.school, config)
        print(f"\n  Generated: {tex_path}")

        if not args.no_compile:
            compile_tex(tex_path)

        if args.deploy:
            copy_to_school_folder(tex_path, args.deploy, args.school)

    elif args.school:
        # Manual configuration
        config = dict(JD_KEYWORDS["balanced"])  # Start from balanced
        config["focus"] = args.profile or "balanced"
        if args.profile:
            config["profile"] = f"profile_{args.profile}"
        if args.teaching:
            config["teaching"] = f"teaching_{args.teaching}"
        if args.professional:
            config["professional"] = f"professional_{args.professional}"
        if args.awards:
            config["awards"] = f"awards_{args.awards}"

        tex_path = generate_school_tex(args.school, config)
        print(f"\n  Generated: {tex_path}")

        if not args.no_compile:
            compile_tex(tex_path)

        if args.deploy:
            copy_to_school_folder(tex_path, args.deploy, args.school)

    else:
        parser.print_help()
