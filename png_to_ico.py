from PIL import Image
import sys
import os

def png_to_ico(png_path, ico_path=None, sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)]):
    if not os.path.exists(png_path):
        print(f"❌ File not found: {png_path}")
        return
    
    if ico_path is None:
        ico_path = os.path.splitext(png_path)[0] + ".ico"

    img = Image.open(png_path).convert("RGBA")
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"✅ Saved icon as {ico_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python png_to_ico.py <input.png> [output.ico]")
    else:
        png_file = sys.argv[1]
        ico_file = sys.argv[2] if len(sys.argv) > 2 else None
        png_to_ico(png_file, ico_file)
