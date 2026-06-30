# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.4.0] - 2026-06-30
### Added
- Introduce custom themes to switch between light / dark mode
- Add support to fetch project artwork data either from hash ID or full ArtStation project URL
- Add help dialog explaining available patterns for file name customisation

## [2.3.0] - 2026-03-15
### Added
- Added context menu (right-click) option to:
  - copy file name (without file extension) from selected URL directly to clipboard
  - select all artwork URLs
  - deselect all artwork URLs
- The starting counter for the custom file name can now be set using the pattern `$#{d+}`, where `d+` represents one or more digits
- For single file downloads, a counter can be included in custom file names through the use of `$#` or `$#{d+}`

### Changed
- Files that are to be downloaded **must now be selected**, while unselected images are ignored

## [2.2.1] - 2026-03-09
### Fixed
- Fixed issue where using `$N` pattern in custom name with either a single file or multiple files without the `$#` pattern resulted in custom name with unedited $N being used

## [2.2.0] - 2026-03-25 *(Internal build only - no GitHub release)*
### Added
- Added button to clear the download log

## [2.1.2] - 2026-02-24 *(Internal build only - no GitHub release)*
### Fixed
- Fixed issue where using `$N` pattern in custom name resulted in only using the name of the very first file in the list, not the original name of the file being downloaded

## [2.1.1] - 2026-02-12
### Added
- Added prompt to download image at it's original dimension when available
- Insertion of selected image dimension into URL is now more dynamic, no longer requiring the pattern `/large/` to be present in the URL

### Changed
- Addressed the special case of GIF's, which must be downloaded at their given dimension

## [2.1.0] - 2026-02-03
### Added
- Added context menu (right-click) to _Download Status_ so a selected file can be viewed on disk with the OS-specific default file explorer after download (only Windows/Linux)
- The original file name can be included anywhere in the custom file name by using the pattern `$N`
- The location of a digit/number in the custom file name can be specified by using the pattern `$#` (if omitted, numbers will be appended at the end)

### Changed
- A number is no longer appended to the user-defined file name when only one file is to be downloaded

## [2.0.0] - 2026-01-14
### Added
- _File Exists_ window:
  - Added notification for file size differences between the file that is to be downloaded and an already existing file of the same name
  - Added button to allow overwriting the existing file of the same name
  - Added button to show the existing file on disk via the operating system's default file explorer
- _Download Status_ will now also include width and height of downloaded images, not just file size
- Added button to open download directory via the operating system's default file explorer

## [1.2.0] - 2026-01-11
### Added
- Added buttons to either append the URL of a single artwork to or remove selected artworks from the artworks list

### Changed
- Moved _Fallback Method_ to menubar at the top for preservation

## [1.1.0] - 2026-01-03
### Added
- Added button to the file renaming pop-up to skip not only the current file, but all other already existing files as well
- The number of successfully saved files is now displayed in the download status window

## [1.0.0] - 2026-01-03
### Added
- Initial release of feature complete artwork downloader with the following features:
  - Choose the image dimensions from the predefined list provided by ArtStation
  - Get a list of artworks featured on a project page
  - Exclude images from download by clicking on them
  - Specify a custom file name (it will be numbered sequentially)
  - Option to skip or rename a file if one with the same name already exists in the specified download directory
  - Alternatively, skip the download of all files that already exist
  - Download results will be displayed for each file

[2.4.0]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v2.4.0
[2.3.0]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v2.3.0
[2.2.1]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v2.2.1
[2.2.0]: https://github.com/jrotzetter/artstation-artwork-downloader/commit/c6311771a2a9ac2565d6e3e3369cdb6ad2c93d82
[2.1.2]: https://github.com/jrotzetter/artstation-artwork-downloader/commit/5b7c177bd8096b8b2ce7e7a72bcbf55eb669b805
[2.1.1]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v2.1.1
[2.1.0]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v2.1.0
[2.0.0]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v2.0.0
[1.2.0]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v1.2.0
[1.1.0]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v1.1.0
[1.0.0]: https://github.com/jrotzetter/artstation-artwork-downloader/releases/tag/v1.0.0
