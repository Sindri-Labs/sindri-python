with open("docs/docstrings/sindri.md", "r") as read_file, open("docs/docstrings/sindri.jsx.md", "w") as write_file:
    for line in read_file.readlines():
        line_new = line
        if line.startswith("<a href=") and '<img align="right" style="float:right;" src="https://img.shields.io' in line:
            line_new = line.replace("></a>", "/></a>")
            line_new = line_new.replace('style="float:right;"', 'style={{float:"right"}}')
        write_file.write(line_new)