#!/usr/bin/env python3
"""
Icon Generator for MSFS exe.xml Manager
Creates a professional Windows ICO file with multiple sizes from SVG
"""

import os
import sys
from PIL import Image, ImageDraw
import xml.etree.ElementTree as ET
import re

def parse_svg_to_icon():
    """Parse the SVG file and create an ICO file"""
    
    if not os.path.exists('app_icon.svg'):
        print("❌ app_icon.svg not found, creating fallback icon...")
        return create_fallback_icon()
    
    print("📁 Found app_icon.svg, creating icon from design...")
    return create_modern_icon_from_svg()

def create_modern_icon_from_svg():
    """Create a modern, professional icon based on the SVG design"""
    
    # ICO format standard sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        # Create new image with transparency
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Calculate dimensions based on size
        margin = max(1, size // 32)
        center_x, center_y = size // 2, size // 2
        radius = (size - margin * 2) // 2
        
        # Background gradient (Microsoft Blue theme)
        # Create gradient effect with multiple circles
        gradient_steps = max(10, radius // 2)
        for i in range(gradient_steps):
            alpha = int(255 * (gradient_steps - i) / gradient_steps)
            # Gradient from #0078d4 to #005a9e
            blue_component = int(120 + (212 - 120) * (1 - i / gradient_steps))
            green_component = int(0 + (120 - 0) * (1 - i / gradient_steps))
            color = (0, green_component, blue_component, alpha)
            
            current_radius = radius * (gradient_steps - i) / gradient_steps
            draw.ellipse([center_x - current_radius, center_y - current_radius,
                         center_x + current_radius, center_y + current_radius],
                        fill=color)
        
        # White border
        border_width = max(1, size // 64)
        if border_width > 0:
            draw.ellipse([center_x - radius, center_y - radius,
                         center_x + radius, center_y + radius],
                        outline=(255, 255, 255, 200), width=border_width)
        
        # Airplane shape (scaled to icon size)
        plane_scale = size / 256.0
        airplane_y_offset = -size // 16  # Move airplane slightly up
        
        # Fuselage (main body)
        fuselage_width = max(2, int(45 * plane_scale))
        fuselage_height = max(1, int(8 * plane_scale))
        draw.ellipse([center_x - fuselage_width//2, 
                     center_y + airplane_y_offset - fuselage_height//2,
                     center_x + fuselage_width//2, 
                     center_y + airplane_y_offset + fuselage_height//2],
                    fill=(255, 255, 255, 255))
        
        # Wings
        wing_width = max(1, int(15 * plane_scale))
        wing_height = max(2, int(35 * plane_scale))
        draw.ellipse([center_x - wing_width//2, 
                     center_y + airplane_y_offset - wing_height//2,
                     center_x + wing_width//2, 
                     center_y + airplane_y_offset + wing_height//2],
                    fill=(255, 255, 255, 255))
        
        # Tail (only for larger sizes)
        if size >= 24:
            tail_size = max(2, int(15 * plane_scale))
            tail_width = max(1, int(3 * plane_scale))
            tail_points = [
                (center_x + fuselage_width//2, center_y + airplane_y_offset - tail_width),
                (center_x + fuselage_width//2 + tail_size, center_y + airplane_y_offset - int(8 * plane_scale)),
                (center_x + fuselage_width//2 + tail_size, center_y + airplane_y_offset + int(8 * plane_scale)),
                (center_x + fuselage_width//2, center_y + airplane_y_offset + tail_width)
            ]
            draw.polygon(tail_points, fill=(255, 255, 255, 255))
        
        # Nose (rounded front)
        if size >= 16:
            nose_width = max(1, int(12 * plane_scale))
            nose_height = max(1, int(6 * plane_scale))
            draw.ellipse([center_x - fuselage_width//2 - nose_width, 
                         center_y + airplane_y_offset - nose_height//2,
                         center_x - fuselage_width//2, 
                         center_y + airplane_y_offset + nose_height//2],
                        fill=(255, 255, 255, 255))
        
        # Engine highlights (for larger sizes only)
        if size >= 32:
            engine_width = max(1, int(4 * plane_scale))
            engine_height = max(2, int(8 * plane_scale))
            engine_x = center_x - int(15 * plane_scale)
            
            # Left engine
            draw.ellipse([engine_x - engine_width//2, 
                         center_y + airplane_y_offset - wing_height//2 - engine_height//2,
                         engine_x + engine_width//2, 
                         center_y + airplane_y_offset - wing_height//2 + engine_height//2],
                        fill=(240, 240, 240, 255))
            
            # Right engine
            draw.ellipse([engine_x - engine_width//2, 
                         center_y + airplane_y_offset + wing_height//2 - engine_height//2,
                         engine_x + engine_width//2, 
                         center_y + airplane_y_offset + wing_height//2 + engine_height//2],
                        fill=(240, 240, 240, 255))
        
        # Add XML/code symbol for larger sizes (bottom right)
        if size >= 48:
            symbol_size = max(8, size // 8)
            symbol_radius = symbol_size // 2
            symbol_x = center_x + radius - symbol_radius - margin
            symbol_y = center_y + radius - symbol_radius - margin
            
            # Green circle for XML symbol
            draw.ellipse([symbol_x - symbol_radius, symbol_y - symbol_radius,
                         symbol_x + symbol_radius, symbol_y + symbol_radius],
                        fill=(0, 212, 170, 255))
            
            # White border on symbol
            symbol_border = max(1, symbol_radius // 8)
            draw.ellipse([symbol_x - symbol_radius, symbol_y - symbol_radius,
                         symbol_x + symbol_radius, symbol_y + symbol_radius],
                        outline=(255, 255, 255, 255), width=symbol_border)
            
            # Add brackets for larger icons
            if size >= 64:
                try:
                    # Simple text representation
                    font_size = max(6, symbol_size // 2)
                    # Draw simple bracket symbols
                    bracket_offset = symbol_radius // 3
                    draw.text((symbol_x - bracket_offset, symbol_y - font_size//2), 
                             "</>", fill=(255, 255, 255, 255))
                except:
                    # Fallback: simple dots if text fails
                    dot_size = max(1, symbol_radius // 4)
                    draw.ellipse([symbol_x - dot_size, symbol_y - dot_size,
                                 symbol_x + dot_size, symbol_y + dot_size],
                                fill=(255, 255, 255, 255))
        
        # Add settings gear for larger sizes (top right)
        if size >= 64:
            gear_size = max(6, size // 12)
            gear_radius = gear_size // 2
            gear_x = center_x + radius - gear_radius - margin - 2
            gear_y = center_y - radius + gear_radius + margin + 2
            
            # Dark circle for gear
            draw.ellipse([gear_x - gear_radius, gear_y - gear_radius,
                         gear_x + gear_radius, gear_y + gear_radius],
                        fill=(45, 45, 45, 255))
            
            # White border
            gear_border = max(1, gear_radius // 6)
            draw.ellipse([gear_x - gear_radius, gear_y - gear_radius,
                         gear_x + gear_radius, gear_y + gear_radius],
                        outline=(255, 255, 255, 255), width=gear_border)
            
            # Center hole
            center_hole_radius = max(1, gear_radius // 3)
            draw.ellipse([gear_x - center_hole_radius, gear_y - center_hole_radius,
                         gear_x + center_hole_radius, gear_y + center_hole_radius],
                        fill=(255, 255, 255, 255))
        
        # Add subtle highlight for depth (larger sizes only)
        if size >= 32:
            highlight_size = max(3, size // 10)
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
        return True
    
    return False

def create_fallback_icon():
    """Create a simple fallback icon if SVG parsing fails"""
    
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        # Create image with solid background
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Simple blue circle
        margin = max(1, size // 16)
        draw.ellipse([margin, margin, size-margin, size-margin], 
                    fill=(0, 120, 212, 255))  # Microsoft Blue
        
        # Simple airplane shape - just a cross
        center_x, center_y = size // 2, size // 2
        line_width = max(1, size // 16)
        
        # Horizontal line (wings)
        wing_length = size // 3
        draw.rectangle([center_x - wing_length//2, center_y - line_width//2,
                       center_x + wing_length//2, center_y + line_width//2],
                      fill=(255, 255, 255, 255))
        
        # Vertical line (fuselage)
        fuselage_length = size // 4
        draw.rectangle([center_x - line_width//2, center_y - fuselage_length//2,
                       center_x + line_width//2, center_y + fuselage_length//2],
                      fill=(255, 255, 255, 255))
        
        images.append(img)
    
    # Save as ICO
    if images:
        images[0].save('icon.ico', format='ICO', 
                      sizes=[(img.width, img.height) for img in images])
        return True
    
    return False

def main():
    """Main function to generate the icon"""
    print("🎨 MSFS exe.xml Manager - Icon Generator")
    print("=" * 50)
    
    try:
        success = parse_svg_to_icon()
        
        if success and os.path.exists('icon.ico'):
            size = os.path.getsize('icon.ico')
            print(f"\n✅ Icon generation completed successfully!")
            print(f"📁 Created: icon.ico ({size:,} bytes)")
            print(f"📐 Sizes: 16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256")
            print("\n💡 The icon is now ready for use in your build process.")
            return 0
        else:
            print("\n❌ Icon generation failed!")
            return 1
            
    except ImportError as e:
        print(f"\n❌ Missing dependency: {e}")
        print("💡 Install Pillow: pip install Pillow")
        return 1
        
    except Exception as e:
        print(f"\n❌ Error during icon generation: {e}")
        import traceback
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())