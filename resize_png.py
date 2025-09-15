from PIL import Image
import sys
import os

def resize_png(png_path, output_path=None, size=(256, 256)):
    if not os.path.exists(png_path):
        print(f"❌ File not found: {png_path}")
        return
    
    if output_path is None:
        output_path = os.path.splitext(png_path)[0] + f"_{size[0]}x{size[1]}.png"

    img = Image.open(png_path).convert("RGBA")
    img = img.resize(size, Image.LANCZOS)  # High-quality resize
    img.save(output_path, format="PNG")
    print(f"✅ Saved resized PNG as {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python resize_png.py <input.png> [output.png]")
    else:
        png_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        resize_png(png_file, output_file)
