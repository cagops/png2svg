# PNG to SVG

![GitHub License](https://img.shields.io/github/license/cagops/png2svg)
![GitHub Forks](https://img.shields.io/github/forks/cagops/png2svg)
![GitHub Stars](https://img.shields.io/github/stars/cagops/png2svg)
![GitHub Last Commit](https://img.shields.io/github/last-commit/cagops/png2svg)

A Python tool that converts PNG images to whiteboard animation software ready SVG files with optimized drawing paths. 

> [!NOTE]
> The script and generated PNG images were tested with the VideoScribe software.

## What it does

This tool converts PNG images into SVG files specifically designed for whiteboard animation software like VideoScribe. It creates drawing guides that follow a natural drawing order:

1. **Dark contours first** - Traces all nearly-black pixels to create outlines
2. **Color fills by hue** - Fills colored areas with multiple strokes, progressing from dark to light hues

The original PNG image is embedded unchanged in the SVG, while invisible drawing guides control the animation sequence.

## Features

- Automatic contour detection for dark pixels
- Hue-based color sorting for natural drawing progression
- Configurable stroke parameters (width, jitter, line count)
- Preserves original image quality
- Batch processing support

## Installation

1. Install Python 3.6 or higher
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install potrace (required for path tracing):
   - macOS: `brew install potrace`
   - Ubuntu/Debian: `sudo apt-get install potrace`
   - Windows: Download from http://potrace.sourceforge.net/

## Usage

### Basic Usage

```bash
python png2svg.py -i input_images -o output_images
```

### Advanced Options

```bash
python png2svg.py -i input_images -o output_images \
  --luma-th 60 \
  --outline-w 6 \
  --fill-factor 0.6 \
  --fill-lines 3 \
  --palette-k 20
```

### Parameters

- `--luma-th`: Luminance threshold for dark pixels (default: 60)
- `--alpha-th`: Alpha transparency threshold (default: 5)
- `--outline-w`: Outline stroke width in pixels (default: 6)
- `--fill-factor`: Fill stroke width factor (0-1, default: 0.6)
- `--fill-lines`: Number of strokes per color blob (default: 3)
- `--fill-jitter`: Stroke position randomness (0-1, default: 0.3)
- `--palette-k`: Number of hue buckets for color ordering (default: 20)

## Example

The repository includes `input_images/database-1.png` as a sample image. Run the converter to see the output:

```bash
python png2svg.py -i input_images -o output_images
```

This will create `output_images/database-1.svg` ready for use in whiteboard animation softwares.

## How it works

1. **Dark phase**: Detects pixels below the luminance threshold and traces their contours using potrace
2. **Color phase**: Groups remaining pixels by hue, creates bounding boxes for each color blob
3. **Stroke generation**: Fills each blob with parallel strokes oriented to match the blob's shape
4. **SVG assembly**: Combines all paths with the embedded original PNG

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for guidelines on how to contribute to this project.

## Code of Conduct

This project follows our [Code of Conduct](.github/CODE_OF_CONDUCT.md) to ensure a welcoming environment for all contributors.
