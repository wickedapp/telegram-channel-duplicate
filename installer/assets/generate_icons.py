#!/usr/bin/env python3
"""
Generate system tray icons for the Telegram Channel Duplicator.

Creates ICO files with multiple sizes (16, 24, 32, 48, 64, 128, 256) for Windows system tray.
Each icon is a simple colored circle on a transparent background with a darker border
and subtle 3D highlight effect.

Icons generated:
- icon.ico - Base app icon (blue)
- icon_green.ico - Running state
- icon_red.ico - Stopped state
- icon_yellow.ico - Connecting state

Usage:
    python generate_icons.py

The script will regenerate all icons in the same directory where it is located.
"""

from PIL import Image, ImageDraw
import os


def create_circle_icon(color: str, size: int) -> Image.Image:
    """
    Create a single size icon with a colored circle.

    Args:
        color: Fill color for the circle (e.g., 'green', '#FF0000', (255, 0, 0))
        size: Icon size in pixels (creates size x size image)

    Returns:
        PIL Image with colored circle on transparent background
    """
    # Create transparent RGBA image
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Calculate circle bounds with small padding
    padding = max(1, size // 8)
    bounds = (padding, padding, size - padding - 1, size - padding - 1)

    # Draw filled circle with slight border for visibility
    # Add a darker border of the same hue for definition
    border_colors = {
        'blue': '#1565C0',
        '#2196F3': '#1565C0',
        'green': '#2E7D32',
        '#4CAF50': '#2E7D32',
        'red': '#C62828',
        '#F44336': '#C62828',
        'yellow': '#F9A825',
        '#FFEB3B': '#F9A825',
        '#FFC107': '#FF8F00',
    }

    # Get border color
    border_color = border_colors.get(color, '#333333')

    # Draw border circle (slightly larger)
    border_bounds = (
        bounds[0] - 1,
        bounds[1] - 1,
        bounds[2] + 1,
        bounds[3] + 1
    )
    draw.ellipse(border_bounds, fill=border_color)

    # Draw main circle
    draw.ellipse(bounds, fill=color)

    # Add highlight for 3D effect on larger sizes
    if size >= 32:
        highlight_size = size // 4
        highlight_pos = (padding + size // 6, padding + size // 6)
        highlight_bounds = (
            highlight_pos[0],
            highlight_pos[1],
            highlight_pos[0] + highlight_size,
            highlight_pos[1] + highlight_size
        )
        # Semi-transparent white highlight
        highlight_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight_img)
        highlight_draw.ellipse(highlight_bounds, fill=(255, 255, 255, 80))
        img = Image.alpha_composite(img, highlight_img)

    return img


def create_ico_file(color: str, filename: str, output_dir: str) -> str:
    """
    Create an ICO file with multiple sizes.

    Args:
        color: Color for the icon circle
        filename: Output filename (without path)
        output_dir: Directory to save the ICO file

    Returns:
        Full path to created ICO file
    """
    # Standard sizes for Windows system tray icons
    # Include 256 for better high-DPI support
    sizes = [16, 24, 32, 48, 64, 128, 256]

    # Create the largest image first
    largest_img = create_circle_icon(color, sizes[-1])

    # Save as ICO - Pillow will create the smaller sizes automatically
    output_path = os.path.join(output_dir, filename)

    # Save with explicit sizes - Pillow handles resizing
    largest_img.save(
        output_path,
        format='ICO',
        sizes=[(s, s) for s in sizes]
    )

    return output_path


def main():
    """Generate all tray icons."""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Icon definitions: (filename, color, description)
    icons = [
        ('icon.ico', '#2196F3', 'Base app icon (blue)'),
        ('icon_green.ico', '#4CAF50', 'Running state'),
        ('icon_red.ico', '#F44336', 'Stopped state'),
        ('icon_yellow.ico', '#FFC107', 'Connecting state'),
    ]

    print("Generating system tray icons...")
    print(f"Output directory: {script_dir}")
    print()

    for filename, color, description in icons:
        output_path = create_ico_file(color, filename, script_dir)
        print(f"  Created: {filename} - {description}")

    print()
    print("Done! All icons generated successfully.")


if __name__ == '__main__':
    main()
