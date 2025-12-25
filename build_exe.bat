@echo off
echo Building FieldMapper executable...
echo This may take a few minutes, please wait...
echo.

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build the executable
pyinstaller FieldMapper.spec --clean --noconfirm

echo.
if exist dist\FieldMapper.exe (
    echo.
    echo ========================================
    echo Build completed successfully!
    echo Executable location: dist\FieldMapper.exe
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Build failed. Please check the output above.
    echo ========================================
)

pause

