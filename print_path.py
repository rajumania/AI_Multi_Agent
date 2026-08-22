import sys
import os

with open(r"c:\Users\rajub\Downloads\genai\genai\path.txt", "w") as f:
    f.write(f"EXE: {sys.executable}\n")
    f.write(f"CWD: {os.getcwd()}\n")
    f.write(f"PATH: {sys.path}\n")
