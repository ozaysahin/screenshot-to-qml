#!/usr/bin/env python3
"""Compile the Tailwind CSS of design 18 and paste it into the template's <style>.

The template (`designs/18-html-tailwind-billing.html`) is written with Tailwind v4 utility
classes; its <style> holds the compiled CSS so build_case.py needs no Node. After changing the
markup, recompile:

  cd evals/tools/tailwind && npm install && python build.py

Exit codes: 0 ok, 2 error (Node/npm missing, CLI failed).
"""
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "designs" / "18-html-tailwind-billing.html"


def main() -> int:
    if not shutil.which("npx"):
        print("[error] npx not found: install Node.js 18+ and run `npm install` here", file=sys.stderr)
        return 2
    src = TEMPLATE.read_text()
    # scan the markup only: stale CSS or the case JSON must not add classes
    markup = re.sub(r"<script\b.*?</script>", "", src, flags=re.S)
    markup = re.sub(r"<style>.*?</style>", "", markup, flags=re.S)
    (HERE / "markup.html").write_text(markup)
    try:
        subprocess.run(["npx", "@tailwindcss/cli", "-i", "input.css", "-o", "out.css"], cwd=HERE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[error] tailwind CLI failed ({e.returncode}); run `npm install` first", file=sys.stderr)
        return 2
    css = (HERE / "out.css").read_text().strip()
    ver = re.search(r"tailwindcss v([\d.]+)", css).group(1)
    banner_end = css.index("*/") + 2
    note = (f"\n/* Generated with the Tailwind CSS v{ver} CLI (npx @tailwindcss/cli -i input.css -o out.css), not minified.\n"
            '   input.css: @import "tailwindcss"; @source "./index.html";\n'
            '              @theme { --font-sans: "Instrument Sans", sans-serif; --radius-xs..2xl: default scale in px } */')
    css = css[:banner_end] + note + css[banner_end:]
    new, n = re.subn(r"(<!--@fonts-->\s*<style>).*?(</style>)", lambda m: m.group(1) + "\n" + css + "\n" + m.group(2),
                     src, count=1, flags=re.S)
    if n != 1:
        print("[error] template has no `<!--@fonts--><style>` block", file=sys.stderr)
        return 2
    TEMPLATE.write_text(new)
    (HERE / "markup.html").unlink()
    (HERE / "out.css").unlink()
    print(f"{TEMPLATE.name}: {len(css)} bytes of CSS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
