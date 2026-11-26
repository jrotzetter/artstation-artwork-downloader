"""
PyInstaller entry point — not part of the package, exists solely
to bootstrap the absolute import for the frozen build.
"""

from artstation_artwork_downloader.main import main

if __name__ == "__main__":
    main()
