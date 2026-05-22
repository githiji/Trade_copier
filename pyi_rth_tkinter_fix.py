import os
import sys


base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
tcl_path = os.path.join(base_path, "_tcl_data")
tk_path = os.path.join(base_path, "_tk_data")

if os.path.isdir(tcl_path):
    os.environ["TCL_LIBRARY"] = tcl_path

if os.path.isdir(tk_path):
    os.environ["TK_LIBRARY"] = tk_path
