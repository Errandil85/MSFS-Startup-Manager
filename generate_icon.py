#!/usr/bin/env python3
"""
Icon Generator for MSFS exe.xml Manager
Creates a professional Windows ICO file with multiple sizes
"""

from PIL import Image, ImageDraw
import os


def create_modern_icon():
    """Create a modern, professional icon for the MSFS exe.xml Manager"""
    
    # ICO format standard sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        # Create new image with transparency
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Calculate dimensions based on size
        margin = max(2, size // 20)
        center_x, center_y = size // 2, size // 2
        radius = (size - margin * 2) // 2
        
        # Background gradient (simulated with concentric circles)
        for i in range(radius, 0, -1):
            # Create gradient effect from blue to darker blue
            alpha = int(255 * (i / radius))
            blue_intensity = int(120 + 92 * (1 - i / radius))  # From 120 to 212
            color = (0, blue_intensity, 212, alpha)
            
            draw.ellipse([center_x - i, center_y - i, center_x + i, center_y + i], 
                        fill=color)
        
        # Airplane shape (scaled to icon size)
        plane_scale = size / 256.0  # Scale factor based on 256px reference
        
        # Fuselage (main body)
        fuselage_width = int(45 * plane_scale)
        fuselage_height = int(8 * plane_scale)
        draw.ellipse([center_x - fuselage_width//2, center_y - fuselage_height//2,
                     center_x + fuselage_width//2, center_y + fuselage_height//2],
                    fill=(255, 255, 255, 255))
        
        # Wings
        wing_width = int(15 * plane_scale)
        wing_height = int(35 * plane_scale)
        draw.ellipse([center_x - wing_width//2, center_y - wing_height//2,
                     center_x + wing_width//2, center_y + wing_height//2],
                    fill=(255, 255, 255, 255))
        
        # Tail (simple triangle)
        tail_size = int(15 * plane_scale)
        if tail_size > 2:  # Only draw tail for larger sizes
            tail_points = [
                (center_x + fuselage_width//2, center_y - int(3 * plane_scale)),
                (center_x + fuselage_width//2 + tail_size, center_y - int(8 * plane_scale)),
                (center_x + fuselage_width//2 + tail_size, center_y + int(8 * plane_scale)),
                (center_x + fuselage_width//2, center_y + int(3 * plane_scale))
            ]
            draw.polygon(tail_points, fill=(255, 255, 255, 255))
        
        # Nose (rounded front)
        nose_width = int(12 * plane_scale)
        nose_height = int(6 * plane_scale)
        if nose_width > 1 and nose_height > 1:
            draw.ellipse([center_x - fuselage_width//2 - nose_width, center_y - nose_height//2,
                         center_x - fuselage_width//2, center_y + nose_height//2],
                        fill=(255, 255, 255, 255))
        
        # Engine highlights (for larger sizes only)
        if size >= 32:
            engine_width = int(4 * plane_scale)
            engine_height = int(8 * plane_scale)
            engine_x = center_x - int(15 * plane_scale)
            
            # Left engine
            draw.ellipse([engine_x - engine_width//2, center_y - wing_height//2 - engine_height//2,
                         engine_x + engine_width//2, center_y - wing_height//2 + engine_height//2],
                        fill=(240, 240, 240, 255))
            
            # Right engine
            draw.ellipse([engine_x - engine_width//2, center_y + wing_height//2 - engine_height//2,
                         engine_x + engine_width//2, center_y + wing_height//2 + engine_height//2],
                        fill=(240, 240, 240, 255))
        
        # Add XML/code symbol for larger sizes
        if size >= 64:
            symbol_size = size // 6
            symbol_x = center_x + radius//2
            symbol_y = center_y + radius//2
            symbol_radius = symbol_size // 2
            
            # Green circle for XML symbol
            draw.ellipse([symbol_x - symbol_radius, symbol_y - symbol_radius,
                         symbol_x + symbol_radius, symbol_y + symbol_radius],
                        fill=(0, 212, 170, 255))
            
            # Simple brackets (scaled font size)
            if size >= 128:
                # For larger sizes, we can add more detail
                bracket_size = symbol_size // 3
                draw.text((symbol_x - bracket_size//2, symbol_y - bracket_size//2), 
                         "</", fill=(255, 255, 255, 255))
        
        # Add subtle highlight for depth (larger sizes only)
        if size >= 48:
            highlight_size = size // 8
            highlight_x = center_x - radius//3
            highlight_y = center_y - radius//3
            draw.ellipse([highlight_x - highlight_size//2, highlight_y - highlight_size//2,
                         highlight_x + highlight_size//2, highlight_y + highlight_size//2],
                        fill=(255, 255, 255, 38))  # 15% opacity white
        
        images.append(img)
    
    # Save as ICO file with all sizes
    if images:
        images[0].save('icon.ico', format='ICO', 
                      sizes=[(img.width, img.height) for img in images])
        print(f"✓ Icon created successfully: icon.ico")
        print(f"  Sizes included: {[img.width for img in images]}")
        return True
    
    return False


def main():
    """Main function to generate the icon"""
    print("🎨 MSFS exe.xml Manager - Icon Generator")
    print("=" * 45)
    
    try:
        if create_modern_icon():
            print("\n✅ Icon generation completed successfully!")
            print("\n📁 Files created:")
            if os.path.exists('icon.ico'):
                size = os.path.getsize('icon.ico')
                print(f"   icon.ico ({size:,} bytes)")
            
            print("\n💡 The icon is now ready for use in your build process.")
        else:
            print("\n❌ Icon generation failed!")
            return 1
            
    except ImportError as e:
        print(f"\n❌ Missing dependency: {e}")
        print("💡 Install Pillow: pip install Pillow")
        return 1
        
    except Exception as e:
        print(f"\n❌ Error during icon generation: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())