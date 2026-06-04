import os
import re
def clean_latex(text):
    # Headings
    text = re.sub(r"\\chapter\*?\{(.+?)\}", r"# \1", text)
    text = re.sub(r"\\section\{(.+?)\}", r"## \1", text)
    text = re.sub(r"\\subsection\{(.+?)\}", r"### \1", text)
    text = re.sub(r"\\paragraph\{(.+?)\}", r"**\1**", text)

    # Styles
    text = re.sub(r"\\textit\{(.+?)\}", r"*\1*", text)
    text = re.sub(r"\\textbf\{(.+?)\}", r"**\1**", text)
    text = re.sub(r"\\texttt\{(.+?)\}", r"`\1`", text)

    # Citations & References
    text = re.sub(r"\\cite\{(.+?)\}", r"[Cite: \1]", text)
    text = re.sub(r"\\(?:cref|Cref|ref|autoref)\{(.+?)\}", r"[Ref: \1]", text)

    # Remove Labels
    text = re.sub(r"\\label\{.+?\}", "", text)

    # Remove Bibliography tags
    text = re.sub(r"\\bibliographystyle\{.+?\}", "", text)
    text = re.sub(r"\\bibliography\{.+?\}", "", text)
    # Lists
    text = re.sub(r"\\begin\{itemize\}", "", text)
    text = re.sub(r"\\end\{itemize\}", "", text)
    text = re.sub(r"\\begin\{enumerate\}", "", text)
    text = re.sub(r"\\end\{enumerate\}", "", text)
    text = re.sub(r"\\item", "- ", text)

    # Environments (Figures, Tables, Algorithms)
    def handle_env(match):
        caption_match = re.search(r"\\caption\{(.+?)\}", match.group(0))
        if caption_match:
            return f"\n> **Caption:** {caption_match.group(1)}\n"
        return ""

    text = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", handle_env, text, flags=re.DOTALL)
    text = re.sub(r"\\begin\{table\}.*?\\end\{table\}", handle_env, text, flags=re.DOTALL)
    text = re.sub(r"\\begin\{algorithm\}.*?\\end\{algorithm\}", handle_env, text, flags=re.DOTALL)
    text = re.sub(r"\\begin\{lstlisting\}.*?\\end\{lstlisting\}", "[Code Listing Block]", text, flags=re.DOTALL)

    # Clean up math (basic)
    text = re.sub(r"\$(.+?)\$", r"$\1$", text) 

    # Common LaTeX escapes and symbols
    text = text.replace(r"\%", "%")
    text = text.replace(r"\_", "_")
    text = text.replace(r"\&", "&")
    text = text.replace(r"\#", "#")
    text = text.replace(r"---", "—")
    text = text.replace(r"--", "–")
    text = text.replace(r"~", " ")

    # Remove formatting artifacts
    text = re.sub(r"\\vspace\{.+?\}", "", text)
    text = re.sub(r"\\hrule", "", text)
    text = re.sub(r"\\newpage", "", text)
    text = re.sub(r"\\cleardoublepage", "", text)
    text = re.sub(r"\\noindent", "", text)

    # Remove remaining LaTeX comments
    text = re.sub(r"^%.*$", "", text, flags=re.MULTILINE)

    # Clean up multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def combine_thesis():
    thesis_dir = "thesis"
    chapters_dir = os.path.join(thesis_dir, "chapters")
    output_file = os.path.join(thesis_dir, "thesis_combined.md")
    
    chapter_files = [
        "chapter1_introduction.tex",
        "chapter2_background_related_work.tex",
        "chapter3_design_methodology.tex",
        "chapter4_implementation.tex",
        "chapter5_evaluation_results.tex",
        "chapter6_discussion_limitations.tex",
        "chapter7_conclusion_future_work.tex"
    ]
    
    combined_content = []
    
    # 1. Extract Abstract from main.tex
    main_path = os.path.join(thesis_dir, "main.tex")
    with open(main_path, "r") as f:
        main_content = f.read()
        
    abstract_match = re.search(r"\\chapter\*\{Abstract\}(.*?)\\tableofcontents", main_content, re.DOTALL)
    if abstract_match:
        abstract_text = abstract_match.group(1).strip()
        cleaned_abstract = clean_latex(abstract_text)
        combined_content.append("# Abstract\n\n")
        combined_content.append(cleaned_abstract + "\n\n")
        print("Abstract extracted.")
    else:
        print("Abstract not found in main.tex")
    
    # 2. Process Chapters
    for filename in chapter_files:
        path = os.path.join(chapters_dir, filename)
        if os.path.exists(path):
            with open(path, "r") as f:
                content = f.read()
                cleaned = clean_latex(content)
                combined_content.append(cleaned + "\n\n")
                print(f"Processed {filename}")
        else:
            print(f"Warning: {filename} not found.")
            
    # 3. Write Output
    with open(output_file, "w") as f:
        f.writelines(combined_content)
    print(f"Final file created at {output_file}")

if __name__ == "__main__":
    combine_thesis()
