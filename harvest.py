#!/usr/bin/env python3
"""Direct runner for Window Website Harvester.

Usage examples:
    python harvest.py run --preset free-max --export
    python harvest.py run --sources overture,osm,crtsh,commoncrawl_domains --export
    python harvest.py run --sources serper --countries GB,US,CA,AU,IE --export
    python harvest.py verify --concurrency 150
    python harvest.py export --format all --output output/
    python harvest.py stats
"""

from window_harvester.cli import main

if __name__ == "__main__":
    main()
