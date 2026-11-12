import sys
from pathlib import Path
value = int(Path(sys.argv[1]).read_text().strip())
Path(sys.argv[2]).write_text(f"#pragma once\n#define DEMO_VALUE {value}\n")
