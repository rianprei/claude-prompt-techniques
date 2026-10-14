#!/usr/bin/env python3
"""Make this skill available to the agent CLIs on this machine, or print the text for a CLI that reads a file.

    python3 scripts/install.py status                  where the skill is, per target, and any conflict
    python3 scripts/install.py install [--target T]    add a link in each target's skill folder
    python3 scripts/install.py remove  [--target T]    remove only the links this script points at this repository
    python3 scripts/install.py snippet                 text for a CLI that reads an instructions file

A CLI that loads skills looks in a folder for one that holds SKILL.md. `install` puts a link named prompt-techniques in
that folder, pointing at this repository, so `git pull` updates every CLI at once. It never replaces a real folder, never
removes anything it did not link, and refuses to add the skill next to another skill whose name says "prompt" unless
--force is given (the README's rule: one prompt skill at a time; the name is a heuristic, so --force exists). Stdlib only;
nothing here calls a network.
"""

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "prompt-techniques"
TARGETS = {"claude": ".claude/skills", "codex": ".codex/skills", "agents": ".agents/skills"}
LINK = re.compile(r"\]\(((?:references|scripts|evals)/[^)#]+)\)")
PROMPT_NAME = re.compile(r"prompt", re.IGNORECASE)


def source_problems(root=ROOT):
    """Why this folder cannot be installed as the skill, as text. An empty list means it can."""
    skill = root / "SKILL.md"
    if not skill.is_file():
        return [f"{skill} is missing"]
    text = skill.read_text(encoding="utf-8")
    problems = []
    head = re.match(r"---\n(.*?)\n---", text, re.S)
    name = re.search(r"^name:\s*(\S+)", head.group(1), re.M) if head else None
    if not name or name.group(1) != SKILL_NAME:
        problems.append(f"SKILL.md must declare 'name: {SKILL_NAME}' in its frontmatter")
    for target in LINK.findall(text):
        if not (root / target).exists():
            problems.append(f"SKILL.md links to {target}, which does not exist")
    return problems


def link_state(link, root=ROOT):
    """'here' (a link to this repository, or this repository itself), 'elsewhere' (a link to another folder),
    'real-folder' or 'absent'."""
    if link.is_symlink():
        return "here" if Path(os.path.realpath(link)) == root.resolve() else "elsewhere"
    if link.exists():
        return "here" if link.resolve() == root.resolve() else "real-folder"
    return "absent"


def other_prompt_skills(folder):
    """Other skills in this folder whose name says 'prompt': the one-at-a-time rule applies to them."""
    if not folder.is_dir():
        return []
    return sorted(entry.name for entry in folder.iterdir() if entry.name != SKILL_NAME and PROMPT_NAME.search(entry.name))


def plan(home, names, force=False, root=ROOT):
    rows = []
    for name in names:
        folder = Path(home) / TARGETS[name]
        link = folder / SKILL_NAME
        state = link_state(link, root)
        others = other_prompt_skills(folder)
        if state == "here":
            action = "keep"
            reason = "already a link to this repository" if link.is_symlink() else "this repository itself is in this folder"
            if others:
                reason += "; but other prompt-engineering skills are here too: " + ", ".join(others)
        elif state == "real-folder":
            action, reason = "refuse", "a real folder with this name is in the way; it was not touched"
        elif state == "elsewhere":
            action, reason = "refuse", f"a link to another folder is in the way ({os.path.realpath(link)}); not touched"
        elif others and not force:
            action, reason = "refuse", ("other prompt-engineering skills are here: " + ", ".join(others) +
                                        "; one at a time, use --force to add anyway")
        else:
            action, reason = "create", ("with --force beside: " + ", ".join(others)) if others else ""
        rows.append({"target": name, "folder": folder, "link": link, "state": state, "action": action, "reason": reason})
    return rows


def apply_plan(rows, dry_run, root=ROOT):
    for row in rows:
        if dry_run:
            continue
        if row["action"] == "create":
            try:
                row["folder"].mkdir(parents=True, exist_ok=True)
                os.symlink(root.resolve(), row["link"], target_is_directory=True)
            except OSError as exc:  # Windows needs symlink rights; report it instead of a traceback
                row.update(action="refuse", reason=f"could not create the link ({exc.strerror or exc}); nothing was changed")
        elif row["action"] == "remove" and row["link"].is_symlink():
            os.unlink(row["link"])
    return rows


def snippet(root=ROOT):
    return (f"Skill: {SKILL_NAME}. Prompt engineering, and image prompts for a named model.\n"
            f"Read {root / 'SKILL.md'} when a request asks for a prompt, a prompt technique, or an image prompt for a "
            "named model.\n"
            f"The files it links (references/..., scripts/...) are relative to {root}; read them on demand, not all at once.\n"
            f"Run its scripts from {root}, for example: cd {root} && python3 scripts/image_prompt.py render "
            "--target midjourney --brief brief.json\n")


def _report(rows):
    for row in rows:
        shown = str(row["folder"] / SKILL_NAME).replace(str(Path.home()), "~", 1)
        print(f"{row['target']:<7} {row['action']:<7} {shown}" + (f"  — {row['reason']}" if row["reason"] else ""))


def main(argv=None, home=None):
    parser = argparse.ArgumentParser(description="Install this skill for agent CLIs, or print its snippet.")
    parser.add_argument("--home", default=None, help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("snippet", help="text for a CLI that reads an instructions file")
    for name, help_text in (("status", "where the skill is, per target"),
                            ("install", "add a link in each target's skill folder"),
                            ("remove", "remove only the links this script made")):
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--target", action="append", choices=sorted(TARGETS), help="default: all targets")
        if name in ("install", "remove"):
            sub.add_argument("--dry-run", action="store_true", help="show the plan and change nothing")
        if name == "install":
            sub.add_argument("--force", action="store_true", help="add beside other prompt-engineering skills")
    args = parser.parse_args(argv)
    home = Path(args.home) if args.home else (home or Path.home())

    if args.command == "snippet":
        print(snippet(), end="")
        return 0
    problems = source_problems()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    names = args.target or sorted(TARGETS)
    if args.command == "status":
        _report(plan(home, names))
        return 0
    if args.command == "install":
        rows = apply_plan(plan(home, names, force=args.force), args.dry_run)
        _report(rows)
        return 1 if any(row["action"] == "refuse" for row in rows) else 0
    rows = []
    for row in plan(home, names):
        if row["state"] == "here" and row["link"].is_symlink():
            row.update(action="remove", reason="this repository's link")
        elif row["state"] == "here":
            row.update(action="skip", reason="this repository itself is in this folder; not removed")
        else:
            row.update(action="skip", reason="not a link to this repository; left alone")
        rows.append(row)
    _report(apply_plan(rows, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
