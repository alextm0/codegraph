import os
import re
import subprocess
import shutil
import glob

def compile_chapter(chapter_path, preamble, output_dir):
    chapter_rel_path = os.path.relpath(chapter_path, start=os.getcwd()).replace("\\", "/")
    # Remove .tex extension for LaTeX commands
    tex_include_path = chapter_rel_path[:-4] if chapter_rel_path.endswith(".tex") else chapter_rel_path
    
    chapter_basename = os.path.basename(chapter_path).replace(".tex", "")
    temp_tex_name = f"compile_{chapter_basename}.tex"
    
    print(f"\n>>> Compiling {chapter_basename} ...")
    
    # Pre-process preamble to avoid double document environment if it was somehow included
    # (though our regex handles this)
    
    with open(temp_tex_name, "w", encoding="utf-8") as f:
        f.write(preamble)
        f.write("\n\\begin{document}\n")
        # Ensure we have a title if possible, or just the chapter
        f.write(f"\\input{{{tex_include_path}}}\n")
        f.write("\n\\newpage\n")
        f.write("\\bibliography{references}\n")
        f.write("\\end{document}\n")

    try:
        # Run pdflatex
        print(f"    Running pdflatex (1/3)...")
        subprocess.run(["pdflatex", "-interaction=nonstopmode", temp_tex_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Run bibtex
        print(f"    Running bibtex...")
        subprocess.run(["bibtex", temp_tex_name.replace(".tex", "")], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Run pdflatex again to resolve references
        print(f"    Running pdflatex (2/3)...")
        subprocess.run(["pdflatex", "-interaction=nonstopmode", temp_tex_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print(f"    Running pdflatex (3/3)...")
        subprocess.run(["pdflatex", "-interaction=nonstopmode", temp_tex_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        pdf_name = temp_tex_name.replace(".tex", ".pdf")
        if os.path.exists(pdf_name):
            final_pdf_path = os.path.join(output_dir, f"{chapter_basename}.pdf")
            if os.path.exists(final_pdf_path):
                os.remove(final_pdf_path)
            shutil.move(pdf_name, final_pdf_path)
            print(f"    SUCCESS: Generated {final_pdf_path}")
        else:
            print(f"    ERROR: Failed to generate PDF for {chapter_basename}. Check for LaTeX errors.")
    except Exception as e:
        print(f"    ERROR: An exception occurred: {e}")
    finally:
        # Cleanup temporary files
        base_name = temp_tex_name.replace(".tex", "")
        for ext in [".tex", ".aux", ".log", ".bbl", ".blg", ".out", ".toc", ".synctex.gz"]:
            f_to_del = base_name + ext
            if os.path.exists(f_to_del):
                try:
                    os.remove(f_to_del)
                except:
                    pass

def main():
    # Ensure we are in the thesis root
    # (Assuming script is run from thesis root or we reach it)
    thesis_dir = os.getcwd()
    main_tex = os.path.join(thesis_dir, "main.tex")
    
    if not os.path.exists(main_tex):
        print("Error: main.tex not found. Please run this script from the thesis root directory.")
        return

    print("Reading main.tex to extract preamble...")
    with open(main_tex, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract preamble (everything before \begin{document})
    preamble_match = re.search(r"(.*?)(\\begin\{document\})", content, re.DOTALL)
    if not preamble_match:
        print("Error: Could not find \\begin{document} in main.tex")
        return
    preamble = preamble_match.group(1)

    output_dir = os.path.join(thesis_dir, "chapter_pdfs")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Discover chapters
    # 1. Look in chapters/ and chapters/drafts/
    tex_files = glob.glob(os.path.join(thesis_dir, "chapters", "**", "*.tex"), recursive=True)
    
    # Filter for files that contain \chapter{} but aren't just empty headers
    valid_chapters = []
    for f_path in tex_files:
        # Skip files that might be just fragments or temp files
        if os.path.basename(f_path).startswith("compile_"):
            continue
            
        with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
            file_content = f.read()
            if "\\chapter" in file_content:
                # Basic check weight (skip very small files that are just \chapter{Title}\label{...})
                if len(file_content.strip()) > 100 or "draft" in f_path:
                    valid_chapters.append(f_path)

    if not valid_chapters:
        print("No significant chapter files found in chapters/ or chapters/drafts/.")
        return

    print(f"Found {len(valid_chapters)} chapter(s) to compile.")
    
    for chapter_path in sorted(valid_chapters):
        compile_chapter(chapter_path, preamble, output_dir)

    print(f"\nDone! PDFs are available in the '{os.path.basename(output_dir)}' directory.")

if __name__ == "__main__":
    main()
