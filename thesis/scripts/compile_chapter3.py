import os
import re
import subprocess
import shutil

"""
DEDICATED SCRIPT TO COMPILE CHAPTER 3: DESIGN AND METHODOLOGY
This script extracts the styling from main.tex and generates a standalone PDF for Chapter 3.
"""

def main():
    # Configuration
    main_tex_path = "main.tex"
    chapter_include = "chapters/chapter3_design_methodology"
    output_filename = "chapter3_design_methodology.pdf"
    output_dir = "chapter_pdfs"
    temp_tex = "temp_compile_ch3.tex"
    
    # ensure we are in the right directory
    if not os.path.exists(main_tex_path):
        print(f"Error: {main_tex_path} not found. Run this from the thesis root.")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"--- Extracting preamble from {main_tex_path} ---")
    with open(main_tex_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract everything before \begin{document}
    preamble_match = re.search(r"(.*?)(\\begin\{document\})", content, re.DOTALL)
    if not preamble_match:
        print("Error: Could not find preamble in main.tex")
        return
    preamble = preamble_match.group(1)

    print(f"--- Creating temporary wrapper for Chapter 3 ---")
    with open(temp_tex, "w", encoding="utf-8") as f:
        f.write(preamble)
        f.write("\n\\begin{document}\n")
        f.write(f"\\input{{{chapter_include}}}\n")
        f.write("\n\\newpage\n")
        f.write("\\bibliography{references}\n")
        f.write("\\end{document}\n")

    base_name = temp_tex.replace(".tex", "")
    
    # Compilation pipeline
    steps = [
        (["pdflatex", "-interaction=nonstopmode", temp_tex], "First pass (pdflatex)"),
        (["bibtex", base_name], "Reference resolution (bibtex)"),
        (["pdflatex", "-interaction=nonstopmode", temp_tex], "Second pass (pdflatex)"),
        (["pdflatex", "-interaction=nonstopmode", temp_tex], "Final pass (pdflatex)")
    ]

    print(f"--- Starting Compilation ---")
    for cmd, desc in steps:
        print(f"Running: {desc}...")
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode != 0:
            print(f"  Note: {desc} completed with status {result.returncode}")

    # Move resulting PDF
    pdf_source = f"{base_name}.pdf"
    pdf_dest = os.path.join(output_dir, output_filename)
    
    if os.path.exists(pdf_source):
        if os.path.exists(pdf_dest):
            os.remove(pdf_dest)
        shutil.move(pdf_source, pdf_dest)
        print(f"\nSUCCESS! Generated: {pdf_dest}")
    else:
        print(f"\nERROR: PDF generation failed. Check {base_name}.log for details.")

    # Cleanup
    print("Cleaning up temporary files...")
    for ext in [".tex", ".aux", ".log", ".out", ".bbl", ".blg", ".toc", ".synctex.gz"]:
        target = base_name + ext
        if os.path.exists(target):
            try:
                os.remove(target)
            except:
                pass

if __name__ == "__main__":
    main()
