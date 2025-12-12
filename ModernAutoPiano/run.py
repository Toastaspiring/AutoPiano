import sys
import os

# Add src to path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import main

if __name__ == "__main__":
    main.main()
