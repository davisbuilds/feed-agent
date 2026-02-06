"""Generate launchd plist for macOS scheduling."""

import os
import sys
from pathlib import Path

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.feed</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
        <string>run</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>{project_root}</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>{project_root}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>{log_path}/digest.stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>{log_path}/digest.stderr.log</string>
    
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def main() -> None:
    """Generate and install launchd plist."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Configuration
    python_path = sys.executable
    script_path = script_dir / "run_digest.py"
    log_path = project_root / "logs"
    hour = 7  # 7 AM
    
    # Generate plist content
    plist_content = PLIST_TEMPLATE.format(
        python_path=python_path,
        script_path=script_path,
        project_root=project_root,
        log_path=log_path,
        hour=hour,
    )
    
    # Paths
    plist_name = "com.user.feed.plist"
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    plist_path = launch_agents_dir / plist_name
    
    print("=" * 60)
    print("macOS Launchd Setup")
    print("=" * 60)
    
    # Create logs directory
    log_path.mkdir(exist_ok=True)
    print(f"\n✓ Created logs directory: {log_path}")
    
    # Write plist
    launch_agents_dir.mkdir(exist_ok=True)
    with open(plist_path, "w") as f:
        f.write(plist_content)
    print(f"✓ Created plist: {plist_path}")
    
    print("\n" + "-" * 60)
    print("Next steps:")
    print("-" * 60)
    
    print(f"\n1. Load the agent:")
    print(f"   launchctl load {plist_path}")
    
    print(f"\n2. To run immediately (for testing):")
    print(f"   launchctl start com.user.feed")
    
    print(f"\n3. To check status:")
    print(f"   launchctl list | grep substack")
    
    print(f"\n4. To unload (disable):")
    print(f"   launchctl unload {plist_path}")
    
    print(f"\n5. View logs:")
    print(f"   tail -f {log_path}/digest.stdout.log")
    
    print("\n" + "-" * 60)
    print(f"Scheduled to run daily at {hour}:00 AM")
    print("-" * 60)


if __name__ == "__main__":
    main()
