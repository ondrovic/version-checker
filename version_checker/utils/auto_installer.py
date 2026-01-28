"""Auto-installation functionality for updating applications."""

import getpass
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from abc import ABC, abstractmethod
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional, Type

import psutil
import requests
from rich.console import Console
from rich.progress import Progress

console = Console()

# Module-level cached sudo password for the session
_cached_sudo_password: Optional[str] = None


def run_sudo_command(
    cmd: list[str],
    silent: bool = False,
    use_cached_password: bool = True,
) -> subprocess.CompletedProcess[str]:
    """
    Run a command with sudo, prompting for password if needed.

    Uses getpass to securely prompt for password and pipes it to sudo -S.
    Caches the password for subsequent sudo calls in the same session.

    Args:
        cmd: Command to run (without 'sudo' prefix - it will be added)
        silent: If True, suppress output messages
        use_cached_password: If True, reuse password from previous sudo call

    Returns:
        CompletedProcess with the result
    """
    global _cached_sudo_password

    # Check if we already have sudo access (password cached by system)
    check = subprocess.run(
        ["sudo", "-n", "true"],
        capture_output=True,
    )
    if check.returncode == 0:
        # Already have sudo access, run directly
        return subprocess.run(["sudo"] + cmd, text=True)

    # Need to prompt for password
    if use_cached_password and _cached_sudo_password is not None:
        password = _cached_sudo_password
    else:
        if not silent:
            console.print("[cyan]sudo password required[/cyan]")
        try:
            password = getpass.getpass(prompt="[sudo] password: ")
        except (EOFError, KeyboardInterrupt):
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="Password input cancelled"
            )

    # Run with sudo -S (read password from stdin)
    result = subprocess.run(
        ["sudo", "-S"] + cmd,
        input=password + "\n",
        text=True,
        capture_output=True,
    )

    # If successful, cache the password for future use
    if result.returncode == 0:
        _cached_sudo_password = password
    elif "incorrect password" in result.stderr.lower() or "sorry" in result.stderr.lower():
        # Password was wrong, clear cache and let caller handle retry
        _cached_sudo_password = None

    return result


class PackageType(Enum):
    """Supported package types for auto-installation."""

    ZIP = auto()
    DEB = auto()
    PACMAN = auto()
    TAR_XZ = auto()
    TAR_GZ = auto()
    APPIMAGE = auto()
    RPM = auto()
    DMG = auto()
    UNKNOWN = auto()


def detect_package_type(filename: str) -> PackageType:
    """
    Detect package type from filename.

    Compound extensions are checked first to ensure correct detection.

    Args:
        filename: The filename to detect package type from.

    Returns:
        PackageType enum value.
    """
    filename_lower = filename.lower()

    # Check compound extensions first (order matters!)
    if filename_lower.endswith(".pkg.tar.zst"):
        return PackageType.PACMAN
    if filename_lower.endswith(".pkg.tar.xz"):
        return PackageType.PACMAN
    if filename_lower.endswith(".tar.xz"):
        return PackageType.TAR_XZ
    if filename_lower.endswith(".tar.gz") or filename_lower.endswith(".tgz"):
        return PackageType.TAR_GZ

    # Check simple extensions
    if filename_lower.endswith(".zip"):
        return PackageType.ZIP
    if filename_lower.endswith(".deb"):
        return PackageType.DEB
    if filename_lower.endswith(".pacman"):
        return PackageType.PACMAN
    if filename_lower.endswith(".appimage"):
        return PackageType.APPIMAGE
    if filename_lower.endswith(".rpm"):
        return PackageType.RPM
    if filename_lower.endswith(".dmg"):
        return PackageType.DMG

    return PackageType.UNKNOWN


class BasePackageInstaller(ABC):
    """Abstract base class for package installers."""

    def __init__(
        self,
        downloaded_file: Path,
        target_path: Path,
        silent: bool = False,
    ):
        """
        Initialize the package installer.

        Args:
            downloaded_file: Path to the downloaded package file.
            target_path: Path where the executable should be installed.
            silent: If True, suppress console output.
        """
        self.downloaded_file = downloaded_file
        self.target_path = target_path
        self.silent = silent

    @abstractmethod
    def install(self) -> bool:
        """
        Install the package.

        Returns:
            True if installation succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this installer is available on the current system.

        Returns:
            True if the installer can be used, False otherwise.
        """
        pass

    def _print(self, message: str) -> None:
        """Print message if not in silent mode."""
        if not self.silent:
            console.print(message)

    def _ensure_target_directory(self) -> None:
        """Ensure the target directory exists."""
        if not self.target_path.parent.exists():
            self._print(f"  → Creating directory {self.target_path.parent}")
            self.target_path.parent.mkdir(parents=True, exist_ok=True)

    def _backup_existing(self) -> Optional[Path]:
        """Backup existing file if it exists. Returns backup path or None."""
        if self.target_path.exists():
            backup_path = self.target_path.with_suffix(
                self.target_path.suffix + ".bak"
            )
            self._print(f"  → Creating backup at {backup_path.name}")
            shutil.copy2(self.target_path, backup_path)
            return backup_path
        return None


class ZipInstaller(BasePackageInstaller):
    """Installer for ZIP archives."""

    def is_available(self) -> bool:
        """ZIP extraction is always available via Python's zipfile module."""
        return True

    def install(self) -> bool:
        """Extract ZIP and install the executable."""
        temp_dir = None
        try:
            self._ensure_target_directory()

            # Create temporary extraction directory
            temp_dir = Path(tempfile.mkdtemp(prefix="zip_extract_"))

            # Extract zip file
            with zipfile.ZipFile(self.downloaded_file, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find executable in extracted contents
            exe_file = self._find_executable(temp_dir)

            if not exe_file:
                self._print(
                    "[red]Error:[/red] No executable found in downloaded archive"
                )
                return False

            # Backup existing and install new
            self._backup_existing()
            self._print(f"  → Installing to {self.target_path}")
            shutil.copy2(exe_file, self.target_path)

            # Make executable on Unix
            if sys.platform != "win32":
                self.target_path.chmod(
                    self.target_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                )

            return True

        except zipfile.BadZipFile:
            self._print(
                "[red]Error:[/red] Downloaded file is not a valid zip archive"
            )
            return False
        except Exception as e:
            self._print(f"[red]Error during ZIP extraction:[/red] {e}")
            return False
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _find_executable(self, temp_dir: Path) -> Optional[Path]:
        """Find executable file in extracted contents."""
        if sys.platform == "win32":
            # Look for .exe files
            exe_files = list(temp_dir.glob("*.exe"))
            if not exe_files:
                exe_files = list(temp_dir.rglob("*.exe"))
            return exe_files[0] if exe_files else None
        else:
            # On Unix, look for files with execute permission or matching target name
            target_name = self.target_path.name
            # First try exact name match
            for f in temp_dir.rglob("*"):
                if f.is_file() and f.name == target_name:
                    return f
            # Then look for any executable
            for f in temp_dir.rglob("*"):
                if f.is_file() and not f.suffix:
                    return f
            return None


class TarInstaller(BasePackageInstaller):
    """Installer for tar archives (.tar.gz, .tar.xz)."""

    def is_available(self) -> bool:
        """Tar extraction is always available via Python's tarfile module."""
        return True

    def install(self) -> bool:
        """Extract tar archive and install the executable."""
        temp_dir = None
        try:
            self._ensure_target_directory()

            # Create temporary extraction directory
            temp_dir = Path(tempfile.mkdtemp(prefix="tar_extract_"))

            # Determine open mode based on compression
            filename_lower = self.downloaded_file.name.lower()
            if filename_lower.endswith(".tar.xz"):
                mode = "r:xz"
            elif filename_lower.endswith(".tar.gz") or filename_lower.endswith(".tgz"):
                mode = "r:gz"
            else:
                mode = "r:*"  # Auto-detect

            # Extract tar file
            with tarfile.open(self.downloaded_file, mode) as tar_ref:
                tar_ref.extractall(temp_dir)

            # Find executable in extracted contents
            exe_file = self._find_executable(temp_dir)

            if not exe_file:
                self._print(
                    "[red]Error:[/red] No executable found in downloaded archive"
                )
                return False

            # Backup existing and install new
            self._backup_existing()
            self._print(f"  → Installing to {self.target_path}")
            shutil.copy2(exe_file, self.target_path)

            # Preserve or set execute permission
            self.target_path.chmod(
                self.target_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
            )

            return True

        except tarfile.TarError as e:
            self._print(f"[red]Error:[/red] Invalid tar archive: {e}")
            return False
        except Exception as e:
            self._print(f"[red]Error during tar extraction:[/red] {e}")
            return False
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _find_executable(self, temp_dir: Path) -> Optional[Path]:
        """Find executable file in extracted contents."""
        target_name = self.target_path.name
        # First try exact name match
        for f in temp_dir.rglob("*"):
            if f.is_file() and f.name == target_name:
                return f
        # Then look for files with execute permission
        for f in temp_dir.rglob("*"):
            if f.is_file() and os.access(f, os.X_OK):
                return f
        # Then look for files without extension (common for Unix executables)
        for f in temp_dir.rglob("*"):
            if f.is_file() and not f.suffix and f.name not in ("LICENSE", "README"):
                return f
        return None


class DebInstaller(BasePackageInstaller):
    """Installer for Debian packages (.deb)."""

    def is_available(self) -> bool:
        """Check if dpkg is available."""
        return shutil.which("dpkg") is not None

    def install(self) -> bool:
        """Install .deb package using dpkg."""
        try:
            self._print(f"  → Installing {self.downloaded_file.name} with dpkg...")

            result = run_sudo_command(
                ["dpkg", "-i", str(self.downloaded_file)],
                silent=self.silent,
            )

            if result.returncode != 0:
                self._print("[red]Error:[/red] dpkg failed")
                if result.stderr:
                    self._print(f"  {result.stderr.strip()}")
                # Try to fix broken dependencies
                self._print("  → Attempting to fix dependencies...")
                fix_result = run_sudo_command(
                    ["apt-get", "install", "-f", "-y"],
                    silent=self.silent,
                )
                if fix_result.returncode != 0:
                    self._print(
                        "[red]Error:[/red] Failed to fix dependencies"
                    )
                    return False

            self._print("  → Package installed successfully")
            return True

        except Exception as e:
            self._print(f"[red]Error during deb installation:[/red] {e}")
            return False


class PacmanInstaller(BasePackageInstaller):
    """Installer for Arch/Pacman packages (.pkg.tar.zst, .pkg.tar.xz)."""

    def is_available(self) -> bool:
        """Check if pacman is available."""
        return shutil.which("pacman") is not None

    def install(self) -> bool:
        """Install package using pacman."""
        try:
            self._print(f"  → Installing {self.downloaded_file.name} with pacman...")

            result = run_sudo_command(
                ["pacman", "-U", "--noconfirm", str(self.downloaded_file)],
                silent=self.silent,
            )

            if result.returncode != 0:
                self._print("[red]Error:[/red] pacman failed")
                if result.stderr:
                    self._print(f"  {result.stderr.strip()}")
                return False

            self._print("  → Package installed successfully")
            return True

        except Exception as e:
            self._print(f"[red]Error during pacman installation:[/red] {e}")
            return False


class RpmInstaller(BasePackageInstaller):
    """Installer for RPM packages (.rpm)."""

    def is_available(self) -> bool:
        """Check if dnf or rpm is available."""
        return shutil.which("dnf") is not None or shutil.which("rpm") is not None

    def install(self) -> bool:
        """Install .rpm package using dnf or rpm."""
        try:
            self._print(f"  → Installing {self.downloaded_file.name}...")

            # Prefer dnf over rpm
            if shutil.which("dnf"):
                cmd = ["dnf", "install", "-y", str(self.downloaded_file)]
            else:
                cmd = ["rpm", "-i", str(self.downloaded_file)]

            result = run_sudo_command(cmd, silent=self.silent)

            if result.returncode != 0:
                self._print("[red]Error:[/red] Installation failed")
                if result.stderr:
                    self._print(f"  {result.stderr.strip()}")
                return False

            self._print("  → Package installed successfully")
            return True

        except Exception as e:
            self._print(f"[red]Error during RPM installation:[/red] {e}")
            return False


class AppImageInstaller(BasePackageInstaller):
    """Installer for AppImage files."""

    def is_available(self) -> bool:
        """AppImage is available on Linux only."""
        return sys.platform == "linux" or sys.platform.startswith("linux")

    def install(self) -> bool:
        """Install AppImage by copying and making executable."""
        try:
            self._ensure_target_directory()
            self._backup_existing()

            self._print(f"  → Installing AppImage to {self.target_path}")
            shutil.copy2(self.downloaded_file, self.target_path)

            # Make executable
            self.target_path.chmod(
                self.target_path.stat().st_mode
                | stat.S_IXUSR
                | stat.S_IXGRP
                | stat.S_IXOTH
            )

            self._print("  → AppImage installed successfully")
            return True

        except Exception as e:
            self._print(f"[red]Error during AppImage installation:[/red] {e}")
            return False


class DmgInstaller(BasePackageInstaller):
    """Installer for macOS disk images (.dmg)."""

    def is_available(self) -> bool:
        """DMG is available on macOS only."""
        return sys.platform == "darwin"

    def install(self) -> bool:
        """Install from DMG by mounting, copying .app, and unmounting."""
        mount_point = None
        try:
            self._print(f"  → Mounting {self.downloaded_file.name}...")

            # Mount the DMG
            result = subprocess.run(
                ["hdiutil", "attach", str(self.downloaded_file), "-nobrowse"],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                self._print(f"[red]Error:[/red] Failed to mount DMG: {result.stderr}")
                return False

            # Parse mount point from output
            mount_point = self._parse_mount_point(result.stdout)
            if not mount_point:
                self._print("[red]Error:[/red] Could not determine mount point")
                return False

            mount_path = Path(mount_point)

            # Find .app bundle
            app_bundles = list(mount_path.glob("*.app"))
            if not app_bundles:
                self._print("[red]Error:[/red] No .app bundle found in DMG")
                return False

            app_bundle = app_bundles[0]
            self._print(f"  → Found {app_bundle.name}")

            # Install to /Applications or target path
            if self.target_path.suffix == ".app":
                dest = self.target_path
            else:
                dest = Path("/Applications") / app_bundle.name

            self._print(f"  → Copying to {dest}")
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(app_bundle, dest)

            self._print("  → Application installed successfully")
            return True

        except Exception as e:
            self._print(f"[red]Error during DMG installation:[/red] {e}")
            return False
        finally:
            # Always try to unmount
            if mount_point:
                try:
                    subprocess.run(
                        ["hdiutil", "detach", mount_point, "-quiet"],
                        capture_output=True,
                    )
                except Exception:
                    pass

    def _parse_mount_point(self, hdiutil_output: str) -> Optional[str]:
        """Parse mount point from hdiutil attach output."""
        for line in hdiutil_output.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 3:
                mount_point = parts[-1].strip()
                if mount_point.startswith("/Volumes/"):
                    return mount_point
        return None


def get_installer_for_type(
    package_type: PackageType,
    downloaded_file: Path,
    target_path: Path,
    silent: bool = False,
) -> Optional[BasePackageInstaller]:
    """
    Get the appropriate installer for a package type.

    Args:
        package_type: The detected package type.
        downloaded_file: Path to the downloaded package.
        target_path: Path where the executable should be installed.
        silent: If True, suppress console output.

    Returns:
        An installer instance or None if no suitable installer found.
    """
    installer_map: dict[PackageType, Type[BasePackageInstaller]] = {
        PackageType.ZIP: ZipInstaller,
        PackageType.TAR_XZ: TarInstaller,
        PackageType.TAR_GZ: TarInstaller,
        PackageType.DEB: DebInstaller,
        PackageType.PACMAN: PacmanInstaller,
        PackageType.RPM: RpmInstaller,
        PackageType.APPIMAGE: AppImageInstaller,
        PackageType.DMG: DmgInstaller,
    }

    installer_class = installer_map.get(package_type)
    if installer_class:
        installer = installer_class(downloaded_file, target_path, silent)
        if installer.is_available():
            return installer
        if not silent:
            console.print(
                f"[yellow]Warning:[/yellow] Installer for {package_type.name} "
                "is not available on this system"
            )
    return None


class AutoInstaller:
    """Handles automatic installation of application updates."""

    def __init__(
        self,
        file_path: str,
        download_url: str,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
        silent: bool = False,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        fresh_install: bool = False,
        auto_launch: bool = False,
        process_name: Optional[str] = None,
    ):
        """
        Initialize the auto installer.

        Args:
            file_path: Path to the installed executable
            download_url: URL to download the new version
            progress: Optional rich Progress instance for progress tracking
            task_id: Optional task ID for progress tracking
            silent: If True, suppress console output (used when UI is managed externally)
            progress_callback: Optional callback function for progress updates (current, total, speed)
            fresh_install: If True, skip killing processes (executable doesn't exist yet)
            auto_launch: If True, launch the app after installation (default: False)
            process_name: Process name to kill before update (defaults to file_path stem)
        """
        self.file_path = Path(file_path)
        self.download_url = download_url
        self.downloads_dir = Path.home() / "Downloads"
        self.downloaded_file: Optional[Path] = None
        self.progress = progress
        self.task_id = task_id
        self.silent = silent
        self.progress_callback = progress_callback
        self.fresh_install = fresh_install
        self.auto_launch = auto_launch
        # Use provided process_name or derive from file_path
        self.process_name = process_name if process_name else self.file_path.stem

    def _update_status(self, message: str, step: Optional[str] = None) -> None:
        """Update progress status or print to console."""
        if self.silent:
            return
        if self.progress and self.task_id is not None:
            if step:
                self.progress.update(
                    self.task_id, description=f"[cyan]{step}:[/cyan] {message}"
                )
        else:
            console.print(message)

    def install(self) -> bool:
        """
        Execute the full installation process.

        Returns:
            True if installation succeeded, False otherwise
        """
        try:
            # Determine total steps based on auto_launch setting
            total_steps = 5 if self.auto_launch else 4

            # Step 1: Kill running process (skip if fresh install)
            if not self.fresh_install:
                self._update_status("Terminating running processes...", f"Step 1/{total_steps}")
                if not self._kill_process():
                    return False
            else:
                if not self.silent:
                    console.print("  → Skipping process termination (fresh install)")

            # Step 2: Download new version
            self._update_status("Downloading new version...", f"Step 2/{total_steps}")
            if not self._download():
                return False

            # Step 3: Extract and overwrite
            self._update_status("Extracting and installing...", f"Step 3/{total_steps}")
            if not self._extract_and_overwrite():
                return False

            # Step 4: Start new process (only if auto_launch is enabled)
            if self.auto_launch:
                self._update_status("Starting application...", f"Step 4/{total_steps}")
                if not self._start_process():
                    return False
                cleanup_step = 5
            else:
                if not self.silent:
                    console.print("  → Skipping auto-launch (disabled in config)")
                cleanup_step = 4

            # Final step: Cleanup
            self._update_status("Cleaning up...", f"Step {cleanup_step}/{total_steps}")
            self._cleanup()

            return True

        except Exception as e:
            console.print(f"[red]Error during installation:[/red] {e}")
            return False

    def _kill_process(self) -> bool:
        """
        Kill any running instances of the application.

        Uses self.process_name which can be set via config or defaults to file_path stem.

        Returns:
            True if successful or no process running, False on error
        """
        try:
            killed_any = False

            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    # Check if process name matches (case-insensitive)
                    if (
                        proc.info["name"]
                        and self.process_name.lower() in proc.info["name"].lower()
                    ):
                        if not self.silent:
                            console.print(
                                f"  → Terminating {proc.info['name']} (PID: {proc.info['pid']})"
                            )
                        proc.terminate()
                        killed_any = True

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):
                    pass

            # Wait for processes to terminate
            if killed_any:
                time.sleep(2)

                # Force kill if still running
                for proc in psutil.process_iter(["pid", "name"]):
                    try:
                        if (
                            proc.info["name"]
                            and self.process_name.lower() in proc.info["name"].lower()
                        ):
                            if not self.silent:
                                console.print(
                                    f"  → Force killing {proc.info['name']} (PID: {proc.info['pid']})"
                                )
                            proc.kill()
                    except (
                        psutil.NoSuchProcess,
                        psutil.AccessDenied,
                        psutil.ZombieProcess,
                    ):
                        pass

                time.sleep(1)

            return True

        except Exception as e:
            if not self.silent:
                console.print(f"[red]Error killing process:[/red] {e}")
                console.print(f"Please close {self.process_name} manually and try again.")
            return False

    def _download(self) -> bool:
        """
        Download the new version to ~/Downloads.

        Skips download if file already exists with matching size.

        Returns:
            True if download succeeded (or skipped), False otherwise
        """
        try:
            import time

            # Ensure downloads directory exists
            self.downloads_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from URL - preserve original extension
            filename = self.download_url.split("/")[-1]
            # URL decode the filename if needed
            from urllib.parse import unquote
            filename = unquote(filename)

            self.downloaded_file = self.downloads_dir / filename

            # Check if file already exists - do a HEAD request to get expected size
            head_response = requests.head(self.download_url, timeout=10, allow_redirects=True)
            expected_size = int(head_response.headers.get("content-length", 0))

            if self.downloaded_file.exists():
                existing_size = self.downloaded_file.stat().st_size
                if expected_size > 0 and existing_size == expected_size:
                    if not self.silent:
                        console.print(f"  → File already downloaded: {filename}")
                    return True
                else:
                    # Size mismatch, re-download
                    if not self.silent:
                        console.print(f"  → Re-downloading (size mismatch): {filename}")

            # Download with progress indication
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0
            start_time = time.time()

            # Use provided progress or create a new one
            if self.progress and not self.silent:
                download_task: Any = self.progress.add_task(
                    f"Downloading {filename}", total=total_size
                )

                with open(self.downloaded_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            self.progress.update(download_task, advance=len(chunk))

                            # Call progress callback if provided
                            if self.progress_callback:
                                elapsed = time.time() - start_time
                                speed = downloaded_size / elapsed if elapsed > 0 else 0
                                self.progress_callback(
                                    downloaded_size, total_size, speed
                                )
            else:
                # Silent mode or no progress - just download with callback
                with open(self.downloaded_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                            # Call progress callback if provided
                            if self.progress_callback:
                                elapsed = time.time() - start_time
                                speed = downloaded_size / elapsed if elapsed > 0 else 0
                                self.progress_callback(
                                    downloaded_size, total_size, speed
                                )

            return True

        except requests.exceptions.RequestException as e:
            if not self.silent:
                console.print(f"[red]Error downloading file:[/red] {e}")
                console.print("Please check your internet connection and try again.")
            return False
        except Exception as e:
            if not self.silent:
                console.print(f"[red]Unexpected error during download:[/red] {e}")
            return False

    def _extract_and_overwrite(self) -> bool:
        """
        Extract/install the downloaded package and overwrite the executable.

        Uses the strategy pattern to select the appropriate installer based
        on the detected package type.

        Returns:
            True if installation succeeded, False otherwise
        """
        try:
            if not self.downloaded_file or not self.downloaded_file.exists():
                if not self.silent:
                    console.print("[red]Error:[/red] Downloaded file not found")
                return False

            # Detect package type
            package_type = detect_package_type(self.downloaded_file.name)

            if not self.silent:
                console.print(
                    f"  → Detected package type: {package_type.name}"
                )

            # Handle unknown type - fall back to ZIP for backward compatibility
            if package_type == PackageType.UNKNOWN:
                if not self.silent:
                    console.print(
                        "  → Unknown package type, attempting ZIP extraction..."
                    )
                package_type = PackageType.ZIP

            # Get the appropriate installer
            installer = get_installer_for_type(
                package_type,
                self.downloaded_file,
                self.file_path,
                self.silent,
            )

            if not installer:
                if not self.silent:
                    console.print(
                        f"[red]Error:[/red] No installer available for {package_type.name}"
                    )
                return False

            # Run the installation
            return installer.install()

        except Exception as e:
            if not self.silent:
                console.print(f"[red]Unexpected error during installation:[/red] {e}")
            return False

    def _start_process(self) -> bool:
        """
        Start the newly installed application.

        Returns:
            True if process started successfully, False otherwise
        """
        try:
            if not self.file_path.exists():
                if not self.silent:
                    console.print(
                        f"[red]Error:[/red] Executable not found at {self.file_path}"
                    )
                return False

            # Start the process detached from current process
            if sys.platform == "win32":
                # Windows: use CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS
                subprocess.Popen(
                    [str(self.file_path)],
                    cwd=str(self.file_path.parent),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    | subprocess.DETACHED_PROCESS,
                    close_fds=True,
                )
            else:
                # Unix-like systems
                subprocess.Popen(
                    [str(self.file_path)],
                    cwd=str(self.file_path.parent),
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            if not self.silent:
                console.print(f"  → {self.file_path.name} started successfully!")
            return True

        except Exception as e:
            if not self.silent:
                console.print(f"[red]Error starting process:[/red] {e}")
                console.print(f"Please start {self.file_path.name} manually.")
            return False

    def _cleanup(self) -> None:
        """Remove the downloaded zip file."""
        try:
            if self.downloaded_file and self.downloaded_file.exists():
                self.downloaded_file.unlink()
                if not self.silent:
                    console.print(f"  → Removed {self.downloaded_file.name}")
        except Exception as e:
            if not self.silent:
                console.print(
                    f"[yellow]Warning:[/yellow] Could not delete downloaded file: {e}"
                )
                console.print(f"You can manually delete: {self.downloaded_file}")


def auto_install(file_path: str, download_url: str) -> bool:
    """
    Convenience function to perform auto-installation.

    Args:
        file_path: Path to the installed executable
        download_url: URL to download the new version

    Returns:
        True if installation succeeded, False otherwise
    """
    installer = AutoInstaller(file_path, download_url)
    return installer.install()
