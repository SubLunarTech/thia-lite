"""
Thia-Lite entry point.
Run with: python -m thia_lite
"""
import sys
import traceback

def _main():
    """Main entry point with error handling for PyInstaller builds."""
    try:
        from thia_lite.cli import main
        main()
    except Exception as e:
        # Keep console open on Windows so user can see the error
        print("\n" + "="*60, file=sys.stderr)
        print("THIA-LITE ERROR", file=sys.stderr)
        print("="*60, file=sys.stderr)
        print(f"\n{type(e).__name__}: {e}", file=sys.stderr)
        print("\nTraceback:", file=sys.stderr)
        traceback.print_exc()
        print("\n" + "="*60, file=sys.stderr)

        if sys.platform == "win32":
            # Keep window open on Windows
            input("\nPress Enter to exit...")

        sys.exit(1)

if __name__ == "__main__":
    _main()
