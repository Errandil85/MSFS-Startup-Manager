@echo off
echo =====================================================
echo    MSFS exe.xml Manager - Build Script
echo =====================================================

REM Create venv if not exists
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Install Pillow for icon conversion
echo Installing Pillow for icon generation...
pip install Pillow

REM Generate icon from SVG (if we have a Python script for it)
echo Generating application icon...
python -c "
try:
    from PIL import Image, ImageDraw
    import os
    
    # Create a simple icon if SVG conversion fails
    def create_icon():
        # Create multiple sizes for ICO format
        sizes = [16, 24, 32, 48, 64, 128, 256]
        images = []
        
        for size in sizes:
            # Create image with gradient background
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Background circle
            margin = size // 16
            draw.ellipse([margin, margin, size-margin, size-margin], 
                        fill=(0, 120, 212, 255))  # Microsoft Blue
            
            # Simple airplane shape
            center_x, center_y = size // 2, size // 2
            plane_size = size // 3
            
            # Fuselage
            draw.ellipse([center_x - plane_size//2, center_y - plane_size//8,
                         center_x + plane_size//2, center_y + plane_size//8],
                        fill=(255, 255, 255, 255))
            
            # Wings
            draw.ellipse([center_x - plane_size//4, center_y - plane_size//2,
                         center_x + plane_size//4, center_y + plane_size//2],
                        fill=(255, 255, 255, 255))
            
            images.append(img)
        
        # Save as ICO
        images[0].save('icon.ico', format='ICO', sizes=[(img.width, img.height) for img in images])
        print('Icon created successfully: icon.ico')
        return True
    
    create_icon()
    
except ImportError:
    print('Pillow not available, skipping icon generation')
except Exception as e:
    print(f'Icon generation failed: {e}')
"

REM Check if icon was created, if not create a fallback
if not exist icon.ico (
    echo Creating fallback icon...
    echo. > icon.ico
)

REM Create version info file
echo Creating version info...
echo VSVersionInfo( > version_info.txt
echo   ffi=FixedFileInfo( >> version_info.txt
echo     filevers=(2,0,0,0), >> version_info.txt
echo     prodvers=(2,0,0,0), >> version_info.txt
echo     mask=0x3f, >> version_info.txt
echo     flags=0x0, >> version_info.txt
echo     OS=0x4, >> version_info.txt
echo     fileType=0x1, >> version_info.txt
echo     subtype=0x0, >> version_info.txt
echo     date=(0, 0) >> version_info.txt
echo   ), >> version_info.txt
echo   kids=[ >> version_info.txt
echo     StringFileInfo( >> version_info.txt
echo       [ >> version_info.txt
echo         StringTable( >> version_info.txt
echo           '040904B0', >> version_info.txt
echo           [StringStruct('CompanyName', 'Flight Sim Tools'), >> version_info.txt
echo            StringStruct('FileDescription', 'MSFS exe.xml Manager'), >> version_info.txt
echo            StringStruct('FileVersion', '2.0.0.0'), >> version_info.txt
echo            StringStruct('InternalName', 'MSFSExeXmlManager'), >> version_info.txt
echo            StringStruct('LegalCopyright', 'Copyright 2024'), >> version_info.txt
echo            StringStruct('OriginalFilename', 'MSFSExeXmlManager.exe'), >> version_info.txt
echo            StringStruct('ProductName', 'MSFS exe.xml Manager'), >> version_info.txt
echo            StringStruct('ProductVersion', '2.0.0.0')]) >> version_info.txt
echo       ]), >> version_info.txt
echo     VarFileInfo([VarStruct('Translation', [1033, 1200])]) >> version_info.txt
echo   ] >> version_info.txt
echo ) >> version_info.txt

REM Clean previous build
echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build executable
echo Building executable...
pyinstaller main.spec

REM Check build result
if exist "dist\MSFSExeXmlManager.exe" (
    echo.
    echo =====================================================
    echo    BUILD SUCCESSFUL!
    echo =====================================================
    echo.
    echo Your executable is ready:
    echo   Location: dist\MSFSExeXmlManager.exe
    echo   Size: 
    for %%F in ("dist\MSFSExeXmlManager.exe") do echo     %%~zF bytes
    echo.
    echo You can now distribute this single executable file.
    echo It contains all dependencies and doesn't require Python installation.
    echo.
) else (
    echo.
    echo =====================================================
    echo    BUILD FAILED!
    echo =====================================================
    echo.
    echo Please check the error messages above.
)

REM Cleanup temporary files
if exist version_info.txt del version_info.txt

echo Press any key to exit...
pause > nul