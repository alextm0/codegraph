# Build PDF into ../out (matches Cursor/VS Code -output-directory=out).
$out_dir = '../out';
$pdf_mode = 1;
$pdflatex = 'pdflatex -file-line-error -interaction=nonstopmode -synctex=1 %O %S';
