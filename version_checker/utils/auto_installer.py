"""Auto-installation functionality for updating applications."""

import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Optional

import psutil
import requests
from rich.console import Console
from rich.progress import Progress

console = Console()


class AutoInstaller:
    """Handles automatic installation of application updates."""

    def __init__(
        self,
        file_path: str,
        download_url: str,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
        silent: bool = False,
        progress_callback: Optional[Callable] = None,
        fresh_install: bool = False,
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
            # Step 1: Kill running process (skip if fresh install)
            if not self.fresh_install:
                self._update_status("Terminating running processes...", "Step 1/5")
                if not self._kill_process():
                    return False
            else:
                if not self.silent:
                    console.print("  → Skipping process termination (fresh install)")

            # Step 2: Download new version
            self._update_status("Downloading new version...", "Step 2/5")
            if not self._download():
                return False

            # Step 3: Extract and overwrite
            self._update_status("Extracting and installing...", "Step 3/5")
            if not self._extract_and_overwrite():
                return False

            # Step 4: Start new process
            self._update_status("Starting application...", "Step 4/5")
            if not self._start_process():
                return False

            # Step 5: Cleanup
            self._update_status("Cleaning up...", "Step 5/5")
            self._cleanup()

            return True

        except Exception as e:
            console.print(f"[red]Error during installation:[/red] {e}")
            return False

    def _kill_process(self) -> bool:
        """
        Kill any running instances of OlivedPro.

        Returns:
            True if successful or no process running, False on error
        """
        try:
            killed_any = False
            process_name = "OlivedPro"

            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    # Check if process name matches (case-insensitive)
                    if (
                        proc.info["name"]
                        and process_name.lower() in proc.info["name"].lower()
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
                            and process_name.lower() in proc.info["name"].lower()
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
                console.print("Please close OlivedPro manually and try again.")
            return False

    def _download(self) -> bool:
        """
        Download the new version to ~/Downloads.

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            import time

            # Ensure downloads directory exists
            self.downloads_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename from URL
            filename = self.download_url.split("/")[-1]
            if not filename.endswith(".zip"):
                filename += ".zip"

            self.downloaded_file = self.downloads_dir / filename

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
        Extract the downloaded zip and overwrite the executable.

        Returns:
            True if extraction succeeded, False otherwise
        """
        try:
            if not self.downloaded_file or not self.downloaded_file.exists():
                if not self.silent:
                    console.print("[red]Error:[/red] Downloaded file not found")
                return False

            # Create temporary extraction directory
            temp_dir = self.downloads_dir / "temp_extract"
            temp_dir.mkdir(exist_ok=True)

            try:
                # Extract zip file
                with zipfile.ZipFile(self.downloaded_file, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)

                # Find the .exe file in extracted contents
                exe_files = list(temp_dir.glob("*.exe"))

                if not exe_files:
                    # Check subdirectories
                    exe_files = list(temp_dir.rglob("*.exe"))

                if not exe_files:
                    if not self.silent:
                        console.print(
                            "[red]Error:[/red] No .exe file found in downloaded archive"
                        )
                    return False

                # Use the first .exe found (should be OlivedPro.exe)
                new_exe = exe_files[0]

                # Ensure target directory exists (for fresh installs)
                if not self.file_path.parent.exists():
                    if not self.silent:
                        console.print(f"  → Creating directory {self.file_path.parent}")
                    self.file_path.parent.mkdir(parents=True, exist_ok=True)

                # Backup old executable (if exists)
                backup_path = self.file_path.with_suffix(".exe.bak")
                if self.file_path.exists():
                    if not self.silent:
                        console.print(f"  → Creating backup at {backup_path.name}")
                    shutil.copy2(self.file_path, backup_path)

                # Install new version
                if not self.silent:
                    action = "Installing" if self.fresh_install else "Updating"
                    console.print(f"  → {action} to {self.file_path}")
                shutil.copy2(new_exe, self.file_path)

                # Clean up temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)

                return True

            except zipfile.BadZipFile:
                if not self.silent:
                    console.print(
                        "[red]Error:[/red] Downloaded file is not a valid zip archive"
                    )
                return False
            except Exception as e:
                if not self.silent:
                    console.print(f"[red]Error during extraction:[/red] {e}")
                # Clean up temp directory on error
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                return False

        except Exception as e:
            if not self.silent:
                console.print(f"[red]Unexpected error during extraction:[/red] {e}")
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
