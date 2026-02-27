from datetime import timezone
content=open("Alii_master_unified.py").read()
content=content.replace("if \\"description\\" in \\n", "if \\"description\\" in \\n")
content=content.replace("if \\"capabilities\\" in \\n", "if \\"capabilities\\" in \\n")
content=content.replace("if \\"methods\\" in \\n", "if \\"methods\\" in \\n")
content=content.replace("if \\"status\\" in \\n", "if \\"status\\" in \\n")
open("Alii_master_unified.py","w").write(content)
print("DONE")
