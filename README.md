# ArtStation Artwork Project Downloader

[![GitHub Release](https://img.shields.io/github/release/jrotzetter/artstation-artwork-downloader?include_prereleases=&sort=semver&color=blue)](https://github.com/jrotzetter/artstation-artwork-downloader/releases/ "View releases")
[![License](https://img.shields.io/badge/License-MIT-blue)](#license "View license summary")
[![Issues - artstation-artwork-downloader](https://img.shields.io/github/issues/jrotzetter/artstation-artwork-downloader)](https://github.com/jrotzetter/artstation-artwork-downloader/issues "View open issues")
[![Made with Python](https://img.shields.io/badge/Python-3.14.0-blue?logo=python&logoColor=white)](https://www.python.org/ "Go to Python homepage")

## Overview
This is a simple Tkinter GUI application for downloading artwork projects from [ArtStation](https://www.artstation.com/). It was initially written as an exercise in webscraping and creating GUI applications with Tkinter.

## Features
While there exist other more sophisticated tools with support for many more image hosting sites (e.g. [gallery-dl](https://github.com/mikf/gallery-dl)), at the time of writing none allowed for the **selection of output image size** in an easy to use GUI application.

> [!WARNING]
> Repeated downloads of a large number of files in too short amount of time might cause you to be IP banned from ArtStation. Be careful to not overdo it!

![GUI preview](preview.png)

### How to use:
1. Select target directory to download images to
2. Select image dimensions (small, medium, large, 4k, 8k)
3. Paste hash ID (found after artstation.com/artwork/*hashid*)
4. Visit resulting URL with your browser, then copy it's JSON content and load it with the corresponding button into the app
5. (Optional) Select images that are to be excluded from download
6. (Optional) Enter a custom file name (files will be numbered sequentually)
7. Download images

> [!TIP]
> If `8k` is selected (the default setting), images will always be downloaded at the best possible quality and size, even if the actual image is not available at 8k.

## Installation
1. Clone the repository or download the zip file
2. Ensure that you have at least **Python 3.7** installed on your system
3. Navigate to the project directory in your command line interface (CLI) of choice
4. (Optional): create a virtual environment for the dependencies
5. Run `pip install -r /path/to/requirements.txt` to install required dependencies
6. Execute the main script using `python main.py`

## Future plans
- Find a way around the 403 response (Cloudflare) to directly load the JSON content
- Instead of skipping files with same name, add dialog to allow renaming

## Disclaimer
This program is intended for personal, non-profit use only and is not optimized for large-scale, high-volume scraping of files. Please source your data for training AI models ethically. Publicly available datasets for educational experimentation with machine learning and deep learning can be found on [Kaggle](https://www.kaggle.com/datasets).

## License
Released under [MIT](https://choosealicense.com/licenses/mit/) by
[@jrotzetter](https://github.com/jrotzetter)

This license means:

- You can freely copy, modify, distribute and reuse this software.
- The _original license_ and copyright notice must be included with copies of this software.
- Please _link back_ to this repo if you use a significant portion of the source code.
- The software is provided “as is”, without warranty of any kind.
