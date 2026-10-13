"""Local studio for Nano Banana image generation: frozen briefs and one approval per paid run.

Run it from the repository root:  python3 -m studio serve --fake-provider
"""

import os
import sys

# The studio imports the shared modules in scripts/ by plain name (contracts, validate_prompt).
# Setting the path here, in the package, means no module depends on another one having run first.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
