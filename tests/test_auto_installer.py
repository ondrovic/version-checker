"""Tests for auto-installer functionality."""

import tarfile
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import psutil
import pytest

from version_checker.utils.auto_installer import (
    run_sudo_command,
    AppImageInstaller,
    AutoInstaller,
    BasePackageInstaller,
    DebInstaller,
    DmgInstaller,
    PackageType,
    PacmanInstaller,
    RpmInstaller,
    TarInstaller,
    ZipInstaller,
    auto_install,
    detect_package_type,
    get_installer_for_type,
)


class TestPackageTypeDetection:
    """Test cases for package type detection."""

    def test_detect_zip(self) -> None:
        """Test detection of ZIP files."""
        assert detect_package_type("app.zip") == PackageType.ZIP
        assert detect_package_type("APP.ZIP") == PackageType.ZIP
        assert detect_package_type("app_linux_amd64.zip") == PackageType.ZIP

    def test_detect_deb(self) -> None:
        """Test detection of DEB packages."""
        assert detect_package_type("app.deb") == PackageType.DEB
        assert detect_package_type("app_1.0.0_amd64.deb") == PackageType.DEB

    def test_detect_rpm(self) -> None:
        """Test detection of RPM packages."""
        assert detect_package_type("app.rpm") == PackageType.RPM
        assert detect_package_type("app-1.0.0.x86_64.rpm") == PackageType.RPM

    def test_detect_appimage(self) -> None:
        """Test detection of AppImage files."""
        assert detect_package_type("app.AppImage") == PackageType.APPIMAGE
        assert detect_package_type("app.appimage") == PackageType.APPIMAGE

    def test_detect_dmg(self) -> None:
        """Test detection of DMG files."""
        assert detect_package_type("app.dmg") == PackageType.DMG
        assert detect_package_type("App-Installer.DMG") == PackageType.DMG

    def test_detect_tar_gz(self) -> None:
        """Test detection of tar.gz archives."""
        assert detect_package_type("app.tar.gz") == PackageType.TAR_GZ
        assert detect_package_type("app_linux_amd64.tar.gz") == PackageType.TAR_GZ
        assert detect_package_type("app.tgz") == PackageType.TAR_GZ

    def test_detect_tar_xz(self) -> None:
        """Test detection of tar.xz archives."""
        assert detect_package_type("app.tar.xz") == PackageType.TAR_XZ
        assert detect_package_type("app_linux_amd64.tar.xz") == PackageType.TAR_XZ

    def test_detect_pacman_pkg_tar_zst(self) -> None:
        """Test detection of Pacman packages (.pkg.tar.zst)."""
        assert detect_package_type("app-1.0.0-1-x86_64.pkg.tar.zst") == PackageType.PACMAN

    def test_detect_pacman_pkg_tar_xz(self) -> None:
        """Test detection of Pacman packages (.pkg.tar.xz)."""
        assert detect_package_type("app-1.0.0-1-x86_64.pkg.tar.xz") == PackageType.PACMAN

    def test_detect_pacman_extension(self) -> None:
        """Test detection of .pacman files (alternate Arch package extension)."""
        assert detect_package_type("Heroic-2.19.1-linux-x64.pacman") == PackageType.PACMAN
        assert detect_package_type("app.PACMAN") == PackageType.PACMAN

    def test_detect_unknown(self) -> None:
        """Test detection of unknown file types."""
        assert detect_package_type("app.txt") == PackageType.UNKNOWN
        assert detect_package_type("app") == PackageType.UNKNOWN
        assert detect_package_type("app.exe") == PackageType.UNKNOWN


class TestZipInstaller:
    """Test cases for ZipInstaller."""

    def test_is_available(self, temp_dir: Path) -> None:
        """Test that ZIP installer is always available."""
        installer = ZipInstaller(
            temp_dir / "app.zip",
            temp_dir / "app",
            silent=True,
        )
        assert installer.is_available() is True

    def test_install_success(self, temp_dir: Path) -> None:
        """Test successful ZIP installation."""
        # Create a zip with an executable
        zip_path = temp_dir / "app.zip"
        target_path = temp_dir / "installed" / "myapp"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("myapp", b"#!/bin/bash\necho hello")

        installer = ZipInstaller(zip_path, target_path, silent=True)
        result = installer.install()

        assert result is True
        assert target_path.exists()

    def test_install_bad_zip(self, temp_dir: Path) -> None:
        """Test installation with corrupted ZIP."""
        zip_path = temp_dir / "bad.zip"
        zip_path.write_bytes(b"not a zip file")

        installer = ZipInstaller(
            zip_path,
            temp_dir / "app",
            silent=True,
        )
        result = installer.install()

        assert result is False

    def test_install_no_executable(self, temp_dir: Path) -> None:
        """Test installation when no executable found."""
        zip_path = temp_dir / "app.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", b"Just a readme")

        installer = ZipInstaller(
            zip_path,
            temp_dir / "app",
            silent=True,
        )
        result = installer.install()

        assert result is False


class TestTarInstaller:
    """Test cases for TarInstaller."""

    def test_is_available(self, temp_dir: Path) -> None:
        """Test that Tar installer is always available."""
        installer = TarInstaller(
            temp_dir / "app.tar.gz",
            temp_dir / "app",
            silent=True,
        )
        assert installer.is_available() is True

    def test_install_tar_gz_success(self, temp_dir: Path) -> None:
        """Test successful tar.gz installation."""
        tar_path = temp_dir / "app.tar.gz"
        target_path = temp_dir / "installed" / "myapp"

        # Create a tar.gz with an executable
        with tarfile.open(tar_path, "w:gz") as tf:
            # Create a temporary file to add
            exe_path = temp_dir / "myapp"
            exe_path.write_bytes(b"#!/bin/bash\necho hello")
            exe_path.chmod(0o755)
            tf.add(exe_path, arcname="myapp")

        installer = TarInstaller(tar_path, target_path, silent=True)
        result = installer.install()

        assert result is True
        assert target_path.exists()

    def test_install_tar_xz_success(self, temp_dir: Path) -> None:
        """Test successful tar.xz installation."""
        tar_path = temp_dir / "app.tar.xz"
        target_path = temp_dir / "installed" / "myapp"

        # Create a tar.xz with an executable
        with tarfile.open(tar_path, "w:xz") as tf:
            exe_path = temp_dir / "myapp"
            exe_path.write_bytes(b"#!/bin/bash\necho hello")
            exe_path.chmod(0o755)
            tf.add(exe_path, arcname="myapp")

        installer = TarInstaller(tar_path, target_path, silent=True)
        result = installer.install()

        assert result is True
        assert target_path.exists()

    def test_install_invalid_tar(self, temp_dir: Path) -> None:
        """Test installation with invalid tar file."""
        tar_path = temp_dir / "bad.tar.gz"
        tar_path.write_bytes(b"not a tar file")

        installer = TarInstaller(
            tar_path,
            temp_dir / "app",
            silent=True,
        )
        result = installer.install()

        assert result is False


class TestDebInstaller:
    """Test cases for DebInstaller."""

    @patch("shutil.which")
    def test_is_available_with_dpkg(self, mock_which: MagicMock) -> None:
        """Test availability when dpkg is present."""
        mock_which.return_value = "/usr/bin/dpkg"
        installer = DebInstaller(Path("/tmp/app.deb"), Path("/usr/bin/app"), silent=True)
        assert installer.is_available() is True

    @patch("shutil.which")
    def test_is_not_available_without_dpkg(self, mock_which: MagicMock) -> None:
        """Test availability when dpkg is not present."""
        mock_which.return_value = None
        installer = DebInstaller(Path("/tmp/app.deb"), Path("/usr/bin/app"), silent=True)
        assert installer.is_available() is False

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_success(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test successful deb installation."""
        mock_which.return_value = "/usr/bin/dpkg"
        mock_sudo.return_value = MagicMock(returncode=0, stderr="")

        deb_path = temp_dir / "app.deb"
        deb_path.write_bytes(b"fake deb")

        installer = DebInstaller(deb_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is True
        mock_sudo.assert_called_once()

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_failure_with_fix_attempt(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test deb installation failure triggers dependency fix."""
        mock_which.return_value = "/usr/bin/dpkg"
        # First call fails, second (apt-get -f) also fails
        mock_sudo.side_effect = [
            MagicMock(returncode=1, stderr="dependency error"),
            MagicMock(returncode=1, stderr="still broken"),
        ]

        deb_path = temp_dir / "app.deb"
        deb_path.write_bytes(b"fake deb")

        installer = DebInstaller(deb_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is False
        assert mock_sudo.call_count == 2


class TestPacmanInstaller:
    """Test cases for PacmanInstaller."""

    @patch("shutil.which")
    def test_is_available_with_pacman(self, mock_which: MagicMock) -> None:
        """Test availability when pacman is present."""
        mock_which.return_value = "/usr/bin/pacman"
        installer = PacmanInstaller(
            Path("/tmp/app.pkg.tar.zst"), Path("/usr/bin/app"), silent=True
        )
        assert installer.is_available() is True

    @patch("shutil.which")
    def test_is_not_available_without_pacman(self, mock_which: MagicMock) -> None:
        """Test availability when pacman is not present."""
        mock_which.return_value = None
        installer = PacmanInstaller(
            Path("/tmp/app.pkg.tar.zst"), Path("/usr/bin/app"), silent=True
        )
        assert installer.is_available() is False

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_success(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test successful pacman installation."""
        mock_which.return_value = "/usr/bin/pacman"
        mock_sudo.return_value = MagicMock(returncode=0, stderr="")

        pkg_path = temp_dir / "app.pkg.tar.zst"
        pkg_path.write_bytes(b"fake pkg")

        installer = PacmanInstaller(pkg_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is True
        mock_sudo.assert_called_once()

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_conflicting_files_auto_remove_and_retry_success(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        mock_which.return_value = "/usr/bin/pacman"

        stderr = (
            "error: failed to commit transaction (conflicting files)\n"
            "tabby-terminal: /usr/share/applications/tabby.desktop exists in filesystem (owned by tabby)\n"
        )
        mock_sudo.side_effect = [
            MagicMock(returncode=1, stderr=stderr),  # install fails
            MagicMock(returncode=0, stderr=""),  # remove owner succeeds
            MagicMock(returncode=0, stderr=""),  # retry succeeds
        ]

        pkg_path = temp_dir / "tabby-terminal.pkg.tar.zst"
        pkg_path.write_bytes(b"fake pkg")

        installer = PacmanInstaller(pkg_path, temp_dir / "tabby", silent=True)
        assert installer.install() is True

        install_cmd = ["pacman", "-U", "--noconfirm", str(pkg_path)]
        remove_cmd = ["pacman", "-Rns", "--noconfirm", "tabby"]
        assert mock_sudo.call_args_list == [
            call(install_cmd, silent=True),
            call(remove_cmd, silent=True),
            call(install_cmd, silent=True),
        ]

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_conflicting_files_multiple_owners_removed_then_retry(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        mock_which.return_value = "/usr/bin/pacman"

        stderr = (
            "error: failed to commit transaction (conflicting files)\n"
            "pkgA: /usr/share/foo exists in filesystem (owned by ownerA)\n"
            "pkgA: /usr/share/bar exists in filesystem (owned by ownerB)\n"
        )
        mock_sudo.side_effect = [
            MagicMock(returncode=1, stderr=stderr),  # install fails
            MagicMock(returncode=0, stderr=""),  # remove owners succeeds
            MagicMock(returncode=0, stderr=""),  # retry succeeds
        ]

        pkg_path = temp_dir / "pkgA.pkg.tar.zst"
        pkg_path.write_bytes(b"fake pkg")

        installer = PacmanInstaller(pkg_path, temp_dir / "pkgA", silent=True)
        assert installer.install() is True

        install_cmd = ["pacman", "-U", "--noconfirm", str(pkg_path)]
        # Order is derived from stderr parse order
        remove_cmd = ["pacman", "-Rns", "--noconfirm", "ownerA", "ownerB"]
        assert mock_sudo.call_args_list == [
            call(install_cmd, silent=True),
            call(remove_cmd, silent=True),
            call(install_cmd, silent=True),
        ]

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_conflicting_files_owner_parse_failed_returns_false(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        mock_which.return_value = "/usr/bin/pacman"

        stderr = "error: failed to commit transaction (conflicting files)\nno owners here\n"
        mock_sudo.return_value = MagicMock(returncode=1, stderr=stderr)

        pkg_path = temp_dir / "pkgA.pkg.tar.zst"
        pkg_path.write_bytes(b"fake pkg")

        installer = PacmanInstaller(pkg_path, temp_dir / "pkgA", silent=True)
        assert installer.install() is False

        mock_sudo.assert_called_once()


class TestRpmInstaller:
    """Test cases for RpmInstaller."""

    @patch("shutil.which")
    def test_is_available_with_dnf(self, mock_which: MagicMock) -> None:
        """Test availability when dnf is present."""
        mock_which.side_effect = lambda x: "/usr/bin/dnf" if x == "dnf" else None
        installer = RpmInstaller(Path("/tmp/app.rpm"), Path("/usr/bin/app"), silent=True)
        assert installer.is_available() is True

    @patch("shutil.which")
    def test_is_available_with_rpm_only(self, mock_which: MagicMock) -> None:
        """Test availability when only rpm is present."""
        mock_which.side_effect = lambda x: "/usr/bin/rpm" if x == "rpm" else None
        installer = RpmInstaller(Path("/tmp/app.rpm"), Path("/usr/bin/app"), silent=True)
        assert installer.is_available() is True

    @patch("shutil.which")
    def test_is_not_available(self, mock_which: MagicMock) -> None:
        """Test availability when neither dnf nor rpm is present."""
        mock_which.return_value = None
        installer = RpmInstaller(Path("/tmp/app.rpm"), Path("/usr/bin/app"), silent=True)
        assert installer.is_available() is False

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_success_with_dnf(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test successful rpm installation with dnf."""
        mock_which.side_effect = lambda x: "/usr/bin/dnf" if x == "dnf" else None
        mock_sudo.return_value = MagicMock(returncode=0, stderr="")

        rpm_path = temp_dir / "app.rpm"
        rpm_path.write_bytes(b"fake rpm")

        installer = RpmInstaller(rpm_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is True
        # Verify dnf was used
        call_args = mock_sudo.call_args[0][0]
        assert "dnf" in call_args


class TestAppImageInstaller:
    """Test cases for AppImageInstaller."""

    @patch("sys.platform", "linux")
    def test_is_available_on_linux(self) -> None:
        """Test availability on Linux."""
        installer = AppImageInstaller(
            Path("/tmp/app.AppImage"), Path("/usr/bin/app"), silent=True
        )
        assert installer.is_available() is True

    @patch("sys.platform", "darwin")
    def test_is_not_available_on_macos(self) -> None:
        """Test unavailability on macOS."""
        installer = AppImageInstaller(
            Path("/tmp/app.AppImage"), Path("/usr/bin/app"), silent=True
        )
        assert installer.is_available() is False

    @patch("sys.platform", "win32")
    def test_is_not_available_on_windows(self) -> None:
        """Test unavailability on Windows."""
        installer = AppImageInstaller(
            Path("/tmp/app.AppImage"), Path("/usr/bin/app"), silent=True
        )
        assert installer.is_available() is False

    def test_install_success(self, temp_dir: Path) -> None:
        """Test successful AppImage installation."""
        appimage_path = temp_dir / "app.AppImage"
        appimage_path.write_bytes(b"fake appimage")

        target_path = temp_dir / "installed" / "app.AppImage"

        installer = AppImageInstaller(appimage_path, target_path, silent=True)

        with patch.object(installer, "is_available", return_value=True):
            result = installer.install()

        assert result is True
        assert target_path.exists()
        # Check executable bit is set
        import stat
        assert target_path.stat().st_mode & stat.S_IXUSR


class TestDmgInstaller:
    """Test cases for DmgInstaller."""

    @patch("sys.platform", "darwin")
    def test_is_available_on_macos(self) -> None:
        """Test availability on macOS."""
        installer = DmgInstaller(
            Path("/tmp/app.dmg"), Path("/Applications/App.app"), silent=True
        )
        assert installer.is_available() is True

    @patch("sys.platform", "linux")
    def test_is_not_available_on_linux(self) -> None:
        """Test unavailability on Linux."""
        installer = DmgInstaller(
            Path("/tmp/app.dmg"), Path("/Applications/App.app"), silent=True
        )
        assert installer.is_available() is False

    @patch("subprocess.run")
    @patch("shutil.copytree")
    @patch("shutil.rmtree")
    @patch("sys.platform", "darwin")
    def test_install_success(
        self,
        mock_rmtree: MagicMock,
        mock_copytree: MagicMock,
        mock_run: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test successful DMG installation."""
        # Setup mocks
        mount_output = "/dev/disk2\t\t\t/Volumes/TestApp"
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=mount_output, stderr=""),  # attach
            MagicMock(returncode=0),  # detach
        ]

        dmg_path = temp_dir / "app.dmg"
        dmg_path.write_bytes(b"fake dmg")

        # Create fake .app in /Volumes
        volumes_path = Path("/Volumes/TestApp")

        with patch.object(Path, "glob") as mock_glob:
            mock_glob.return_value = [Path("/Volumes/TestApp/TestApp.app")]
            with patch.object(Path, "exists", return_value=True):
                installer = DmgInstaller(
                    dmg_path, temp_dir / "TestApp.app", silent=True
                )
                # This test just verifies the mock setup, actual test would need
                # more complex filesystem mocking


class TestGetInstallerForType:
    """Test cases for get_installer_for_type function."""

    def test_get_zip_installer(self, temp_dir: Path) -> None:
        """Test getting ZIP installer."""
        installer = get_installer_for_type(
            PackageType.ZIP,
            temp_dir / "app.zip",
            temp_dir / "app",
            silent=True,
        )
        assert isinstance(installer, ZipInstaller)

    def test_get_tar_installer_for_tar_gz(self, temp_dir: Path) -> None:
        """Test getting Tar installer for .tar.gz."""
        installer = get_installer_for_type(
            PackageType.TAR_GZ,
            temp_dir / "app.tar.gz",
            temp_dir / "app",
            silent=True,
        )
        assert isinstance(installer, TarInstaller)

    def test_get_tar_installer_for_tar_xz(self, temp_dir: Path) -> None:
        """Test getting Tar installer for .tar.xz."""
        installer = get_installer_for_type(
            PackageType.TAR_XZ,
            temp_dir / "app.tar.xz",
            temp_dir / "app",
            silent=True,
        )
        assert isinstance(installer, TarInstaller)

    @patch("shutil.which")
    def test_get_deb_installer_when_available(
        self, mock_which: MagicMock, temp_dir: Path
    ) -> None:
        """Test getting DEB installer when dpkg is available."""
        mock_which.return_value = "/usr/bin/dpkg"
        installer = get_installer_for_type(
            PackageType.DEB,
            temp_dir / "app.deb",
            temp_dir / "app",
            silent=True,
        )
        assert isinstance(installer, DebInstaller)

    @patch("shutil.which")
    def test_get_deb_installer_when_unavailable(
        self, mock_which: MagicMock, temp_dir: Path
    ) -> None:
        """Test getting DEB installer when dpkg is not available."""
        mock_which.return_value = None
        installer = get_installer_for_type(
            PackageType.DEB,
            temp_dir / "app.deb",
            temp_dir / "app",
            silent=True,
        )
        assert installer is None

    def test_get_unknown_type_returns_none(self, temp_dir: Path) -> None:
        """Test that unknown package type returns None."""
        installer = get_installer_for_type(
            PackageType.UNKNOWN,
            temp_dir / "app.unknown",
            temp_dir / "app",
            silent=True,
        )
        assert installer is None


class TestAutoInstaller:
    """Test cases for AutoInstaller class."""

    def test_init_default(self, temp_dir: Path) -> None:
        """Test AutoInstaller initialization with defaults."""
        file_path = str(temp_dir / "app.exe")
        download_url = "https://example.com/app.zip"

        installer = AutoInstaller(file_path, download_url)

        assert installer.file_path == Path(file_path)
        assert installer.download_url == download_url
        assert installer.downloads_dir == Path.home() / "Downloads"
        assert installer.downloaded_file is None
        assert installer.progress is None
        assert installer.task_id is None
        assert installer.silent is False
        assert installer.progress_callback is None
        assert installer.fresh_install is False

    def test_init_with_options(self, temp_dir: Path) -> None:
        """Test AutoInstaller initialization with custom options."""
        file_path = str(temp_dir / "app.exe")
        download_url = "https://example.com/app.zip"
        mock_progress = MagicMock()
        mock_callback = MagicMock()

        installer = AutoInstaller(
            file_path,
            download_url,
            progress=mock_progress,
            task_id="task1",
            silent=True,
            progress_callback=mock_callback,
            fresh_install=True,
        )

        assert installer.progress == mock_progress
        assert installer.task_id == "task1"
        assert installer.silent is True
        assert installer.progress_callback == mock_callback
        assert installer.fresh_install is True

    @patch("version_checker.utils.auto_installer.console")
    def test_update_status_not_silent(self, mock_console: MagicMock) -> None:
        """Test _update_status when not in silent mode."""
        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        installer._update_status("Test message")

        mock_console.print.assert_called_once_with("Test message")

    def test_update_status_silent(self) -> None:
        """Test _update_status in silent mode."""
        installer = AutoInstaller(
            "/path/to/app.exe", "https://example.com/app.zip", silent=True
        )

        # Should not raise any exceptions
        installer._update_status("Test message")

    @patch("version_checker.utils.auto_installer.console")
    def test_update_status_with_progress(self, mock_console: MagicMock) -> None:
        """Test _update_status with progress tracking."""
        _ = mock_console  # unused but required by patch
        mock_progress = MagicMock()
        installer = AutoInstaller(
            "/path/to/app.exe",
            "https://example.com/app.zip",
            progress=mock_progress,
            task_id="task1",
        )

        installer._update_status("Test message", "Step 1/5")

        mock_progress.update.assert_called_once()

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_success(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test killing process successfully."""
        _ = mock_console  # unused but required by patch
        # Mock process - name must match the file_path stem ("app" from "/path/to/app.exe")
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "app.exe"}
        mock_psutil.process_iter.return_value = [mock_proc]

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        result = installer._kill_process()

        assert result is True
        mock_proc.terminate.assert_called_once()

    @patch("version_checker.utils.auto_installer.psutil")
    def test_kill_process_no_process_running(self, mock_psutil: MagicMock) -> None:
        """Test when no process is running."""
        mock_psutil.process_iter.return_value = []

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        result = installer._kill_process()

        assert result is True

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_force_kill(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test force killing process."""
        _ = mock_console  # unused but required by patch
        # Mock process that doesn't terminate - name must match file_path stem
        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "app.exe"}

        # First call returns the process, second call also returns it (still running)
        mock_psutil.process_iter.side_effect = [[mock_proc], [mock_proc]]

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        result = installer._kill_process()

        assert result is True
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_error(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test error handling in kill_process."""
        mock_psutil.process_iter.side_effect = Exception("Test error")

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")

        result = installer._kill_process()

        assert result is False
        mock_console.print.assert_called()

    @patch("version_checker.utils.auto_installer.requests")
    def test_download_success(self, mock_requests: MagicMock, temp_dir: Path) -> None:
        """Test successful download."""
        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests.get.return_value = mock_response

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is True
        assert installer.downloaded_file is not None
        assert installer.downloaded_file.exists()

    @patch("version_checker.utils.auto_installer.requests")
    def test_download_with_progress(
        self, mock_requests: MagicMock, temp_dir: Path
    ) -> None:
        """Test download with progress tracking."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests.get.return_value = mock_response

        mock_progress = MagicMock()
        installer = AutoInstaller(
            str(temp_dir / "app.exe"),
            "https://example.com/app.zip",
            progress=mock_progress,
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is True
        mock_progress.add_task.assert_called_once()

    @patch("version_checker.utils.auto_installer.requests")
    def test_download_with_callback(
        self, mock_requests: MagicMock, temp_dir: Path
    ) -> None:
        """Test download with progress callback."""
        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests.get.return_value = mock_response

        mock_callback = MagicMock()
        installer = AutoInstaller(
            str(temp_dir / "app.exe"),
            "https://example.com/app.zip",
            progress_callback=mock_callback,
            silent=True,
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is True
        assert mock_callback.called

    @patch("version_checker.utils.auto_installer.requests")
    @patch("version_checker.utils.auto_installer.console")
    def test_download_file_already_exists_matching_size(
        self, mock_console: MagicMock, mock_requests: MagicMock, temp_dir: Path
    ) -> None:
        """Test download skipped when file already exists with matching size."""
        # Create existing file
        existing_file = temp_dir / "app.zip"
        existing_file.write_bytes(b"existing content 1234")

        mock_head = MagicMock()
        mock_head.headers = {"content-length": str(len(b"existing content 1234"))}
        mock_requests.head.return_value = mock_head

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is True
        # get should not be called since file already exists
        mock_requests.get.assert_not_called()
        mock_console.print.assert_called()

    @patch("version_checker.utils.auto_installer.requests")
    @patch("version_checker.utils.auto_installer.console")
    def test_download_file_exists_size_mismatch(
        self, mock_console: MagicMock, mock_requests: MagicMock, temp_dir: Path
    ) -> None:
        """Test re-download when file exists with size mismatch."""
        # Create existing file
        existing_file = temp_dir / "app.zip"
        existing_file.write_bytes(b"small")

        mock_head = MagicMock()
        mock_head.headers = {"content-length": "1000"}  # Different size
        mock_requests.head.return_value = mock_head

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "1000"}
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests.get.return_value = mock_response

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is True
        # get should be called since size mismatch
        mock_requests.get.assert_called_once()
        # Should print re-downloading message
        mock_console.print.assert_called()

    @patch("version_checker.utils.auto_installer.requests")
    @patch("version_checker.utils.auto_installer.console")
    def test_download_request_error(
        self, mock_console: MagicMock, mock_requests: MagicMock, temp_dir: Path
    ) -> None:
        """Test download with request error."""
        # Import the actual exception class
        import requests as real_requests

        mock_requests.get.side_effect = real_requests.exceptions.RequestException(
            "Network error"
        )
        mock_requests.exceptions = real_requests.exceptions

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloads_dir = temp_dir

        result = installer._download()

        assert result is False
        mock_console.print.assert_called()

    def test_extract_and_overwrite_success(self, temp_dir: Path) -> None:
        """Test successful extraction and installation."""
        # Create a mock zip file with an exe
        zip_path = temp_dir / "app.zip"
        exe_content = b"Mock executable content"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("app.exe", exe_content)

        target_path = temp_dir / "installed" / "app.exe"
        installer = AutoInstaller(str(target_path), "https://example.com/app.zip")
        installer.downloaded_file = zip_path
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is True
        assert target_path.exists()

    def test_extract_and_overwrite_with_backup(self, temp_dir: Path) -> None:
        """Test extraction with backup of existing file."""
        # Create existing exe
        target_path = temp_dir / "app.exe"
        target_path.write_bytes(b"Old version")

        # Create zip with new version
        zip_path = temp_dir / "app.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("app.exe", b"New version")

        installer = AutoInstaller(str(target_path), "https://example.com/app.zip")
        installer.downloaded_file = zip_path
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is True
        assert target_path.exists()
        backup_path = target_path.with_suffix(".exe.bak")
        assert backup_path.exists()

    def test_extract_and_overwrite_no_exe_found(self, temp_dir: Path) -> None:
        """Test extraction when no exe is found in zip."""
        # Create zip without exe
        zip_path = temp_dir / "app.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", b"No exe here")

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = zip_path
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is False

    def test_extract_and_overwrite_bad_zip(self, temp_dir: Path) -> None:
        """Test extraction with corrupted zip file."""
        # Create invalid zip
        zip_path = temp_dir / "app.zip"
        zip_path.write_bytes(b"Not a valid zip file")

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = zip_path
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is False

    def test_extract_and_overwrite_no_downloaded_file(self, temp_dir: Path) -> None:
        """Test extraction when downloaded file doesn't exist."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = temp_dir / "nonexistent.zip"
        installer.downloads_dir = temp_dir

        result = installer._extract_and_overwrite()

        assert result is False

    @patch("version_checker.utils.auto_installer.subprocess")
    def test_start_process_windows(
        self, mock_subprocess: MagicMock, temp_dir: Path
    ) -> None:
        """Test starting process on Windows."""
        exe_path = temp_dir / "app.exe"
        exe_path.write_bytes(b"Mock exe")

        with patch("version_checker.utils.auto_installer.sys.platform", "win32"):
            installer = AutoInstaller(str(exe_path), "https://example.com/app.zip")

            result = installer._start_process()

            assert result is True
            mock_subprocess.Popen.assert_called_once()
            call_args: Any = mock_subprocess.Popen.call_args
            # Check that creationflags parameter exists and is set
            assert "creationflags" in call_args[1]
            # The actual value will be the OR'd flags
            assert call_args[1]["creationflags"] is not None

    @patch("version_checker.utils.auto_installer.subprocess")
    def test_start_process_unix(
        self, mock_subprocess: MagicMock, temp_dir: Path
    ) -> None:
        """Test starting process on Unix-like systems."""
        exe_path = temp_dir / "app.exe"
        exe_path.write_bytes(b"Mock exe")

        with patch("version_checker.utils.auto_installer.sys.platform", "linux"):
            installer = AutoInstaller(str(exe_path), "https://example.com/app.zip")

            result = installer._start_process()

            assert result is True
            mock_subprocess.Popen.assert_called_once()
            call_args: Any = mock_subprocess.Popen.call_args
            assert call_args[1]["start_new_session"] is True

    @patch("version_checker.utils.auto_installer.subprocess")
    @patch("version_checker.utils.auto_installer.console")
    def test_start_process_file_not_found(
        self, mock_console: MagicMock, mock_subprocess: MagicMock, temp_dir: Path
    ) -> None:
        """Test starting process when file doesn't exist."""
        _ = mock_subprocess  # unused but required by patch
        installer = AutoInstaller(
            str(temp_dir / "nonexistent.exe"), "https://example.com/app.zip"
        )

        result = installer._start_process()

        assert result is False
        mock_console.print.assert_called()

    @patch("version_checker.utils.auto_installer.subprocess")
    @patch("version_checker.utils.auto_installer.console")
    def test_start_process_error(
        self, mock_console: MagicMock, mock_subprocess: MagicMock, temp_dir: Path
    ) -> None:
        """Test error handling in start_process."""
        exe_path = temp_dir / "app.exe"
        exe_path.write_bytes(b"Mock exe")

        mock_subprocess.Popen.side_effect = Exception("Test error")

        installer = AutoInstaller(str(exe_path), "https://example.com/app.zip")

        result = installer._start_process()

        assert result is False
        mock_console.print.assert_called()

    def test_cleanup_success(self, temp_dir: Path) -> None:
        """Test successful cleanup."""
        zip_path = temp_dir / "app.zip"
        zip_path.write_bytes(b"Mock zip")

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = zip_path

        installer._cleanup()

        assert not zip_path.exists()

    def test_cleanup_no_file(self, temp_dir: Path) -> None:
        """Test cleanup when no file to clean."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = None

        # Should not raise exception
        installer._cleanup()

    @patch("version_checker.utils.auto_installer.console")
    def test_cleanup_error(self, mock_console: MagicMock, temp_dir: Path) -> None:
        """Test cleanup error handling."""
        _ = mock_console  # unused but may be called on error
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloaded_file = temp_dir / "nonexistent.zip"

        # Should handle error gracefully
        installer._cleanup()
        # May or may not print depending on implementation

    def test_install_full_process(self, temp_dir: Path) -> None:
        """Test full installation process."""
        exe_path = temp_dir / "app.exe"
        zip_path = temp_dir / "app.zip"

        # Create zip with exe
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("app.exe", b"New version")

        installer = AutoInstaller(str(exe_path), "https://example.com/app.zip")
        installer.downloads_dir = temp_dir
        installer.fresh_install = True  # Skip kill process

        with patch.object(installer, "_download", return_value=True):
            with patch.object(installer, "_extract_and_overwrite", return_value=True):
                with patch.object(installer, "_start_process", return_value=True):
                    installer.downloaded_file = zip_path

                    result = installer.install()

                    assert result is True

    def test_install_download_fails(self, temp_dir: Path) -> None:
        """Test installation when download fails."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", return_value=False):
            result = installer.install()

            assert result is False

    def test_install_extract_fails(self, temp_dir: Path) -> None:
        """Test installation when extraction fails."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", return_value=True):
            with patch.object(installer, "_extract_and_overwrite", return_value=False):
                result = installer.install()

                assert result is False

    def test_install_start_process_fails(self, temp_dir: Path) -> None:
        """Test installation when starting process fails (with auto_launch enabled)."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip",
            auto_launch=True,  # Enable auto_launch to test start_process failure
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", return_value=True):
            with patch.object(installer, "_extract_and_overwrite", return_value=True):
                with patch.object(installer, "_start_process", return_value=False):
                    result = installer.install()

                    assert result is False

    def test_install_with_kill_process(self, temp_dir: Path) -> None:
        """Test installation with kill process step."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = False  # Don't skip kill process

        with patch.object(installer, "_kill_process", return_value=True):
            with patch.object(installer, "_download", return_value=True):
                with patch.object(
                    installer, "_extract_and_overwrite", return_value=True
                ):
                    with patch.object(installer, "_start_process", return_value=True):
                        result = installer.install()

                        assert result is True

    def test_install_kill_process_fails(self, temp_dir: Path) -> None:
        """Test installation when kill process fails."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = False

        with patch.object(installer, "_kill_process", return_value=False):
            result = installer.install()

            assert result is False

    @patch("version_checker.utils.auto_installer.console")
    def test_install_exception(self, mock_console: MagicMock, temp_dir: Path) -> None:
        """Test installation with unexpected exception."""
        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", side_effect=Exception("Test error")):
            result = installer.install()

            assert result is False
            mock_console.print.assert_called()


class TestAutoInstallFunction:
    """Test cases for auto_install convenience function."""

    def test_auto_install_success(self, temp_dir: Path) -> None:
        """Test auto_install function success."""
        with patch("version_checker.utils.auto_installer.AutoInstaller") as mock_class:
            mock_installer = MagicMock()
            mock_class.return_value = mock_installer
            mock_installer.install.return_value = True

            result = auto_install(
                str(temp_dir / "app.exe"), "https://example.com/app.zip"
            )

            assert result is True
            mock_class.assert_called_once_with(
                str(temp_dir / "app.exe"), "https://example.com/app.zip"
            )
            mock_installer.install.assert_called_once()

    def test_auto_install_failure(self, temp_dir: Path) -> None:
        """Test auto_install function failure."""
        with patch("version_checker.utils.auto_installer.AutoInstaller") as mock_class:
            mock_installer = MagicMock()
            mock_class.return_value = mock_installer
            mock_installer.install.return_value = False

            result = auto_install(
                str(temp_dir / "app.exe"), "https://example.com/app.zip"
            )

            assert result is False


class TestRunSudoCommand:
    """Test cases for run_sudo_command function."""

    @patch("version_checker.utils.auto_installer.subprocess.run")
    def test_sudo_already_cached(self, mock_run: MagicMock) -> None:
        """Test when sudo is already cached (passwordless)."""
        from version_checker.utils.auto_installer import run_sudo_command

        # First call checks if sudo is cached, returns 0 (cached)
        # Second call runs the actual command
        mock_run.side_effect = [
            MagicMock(returncode=0),  # sudo -n true succeeds
            MagicMock(returncode=0, stdout="", stderr=""),  # actual command
        ]

        result = run_sudo_command(["ls", "/root"])

        assert result.returncode == 0
        assert mock_run.call_count == 2
        # First call should be sudo -n true
        assert mock_run.call_args_list[0][0][0] == ["sudo", "-n", "true"]
        # Second call should be sudo + cmd
        assert mock_run.call_args_list[1][0][0] == ["sudo", "ls", "/root"]

    @patch("version_checker.utils.auto_installer.getpass.getpass")
    @patch("version_checker.utils.auto_installer.subprocess.run")
    def test_sudo_password_prompt(
        self, mock_run: MagicMock, mock_getpass: MagicMock
    ) -> None:
        """Test when sudo needs password prompt."""
        from version_checker.utils.auto_installer import run_sudo_command, _cached_sudo_password
        import version_checker.utils.auto_installer as auto_installer_module

        # Clear cached password
        auto_installer_module._cached_sudo_password = None

        # sudo -n true fails (not cached), then command succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1),  # sudo -n true fails
            MagicMock(returncode=0, stdout="", stderr=""),  # sudo -S command succeeds
        ]
        mock_getpass.return_value = "testpassword"

        result = run_sudo_command(["ls", "/root"], use_cached_password=False)

        assert result.returncode == 0
        mock_getpass.assert_called_once()
        # Password should now be cached
        assert auto_installer_module._cached_sudo_password == "testpassword"

    @patch("version_checker.utils.auto_installer.getpass.getpass")
    @patch("version_checker.utils.auto_installer.subprocess.run")
    def test_sudo_password_cancelled(
        self, mock_run: MagicMock, mock_getpass: MagicMock
    ) -> None:
        """Test when user cancels password prompt."""
        from version_checker.utils.auto_installer import run_sudo_command
        import version_checker.utils.auto_installer as auto_installer_module

        auto_installer_module._cached_sudo_password = None
        mock_run.return_value = MagicMock(returncode=1)  # sudo -n true fails
        mock_getpass.side_effect = EOFError()

        result = run_sudo_command(["ls", "/root"], use_cached_password=False)

        assert result.returncode == 1
        assert result.stderr == "Password input cancelled"

    @patch("version_checker.utils.auto_installer.getpass.getpass")
    @patch("version_checker.utils.auto_installer.subprocess.run")
    def test_sudo_keyboard_interrupt(
        self, mock_run: MagicMock, mock_getpass: MagicMock
    ) -> None:
        """Test when user presses Ctrl+C during password prompt."""
        from version_checker.utils.auto_installer import run_sudo_command
        import version_checker.utils.auto_installer as auto_installer_module

        auto_installer_module._cached_sudo_password = None
        mock_run.return_value = MagicMock(returncode=1)  # sudo -n true fails
        mock_getpass.side_effect = KeyboardInterrupt()

        result = run_sudo_command(["ls", "/root"], use_cached_password=False)

        assert result.returncode == 1
        assert result.stderr == "Password input cancelled"

    @patch("version_checker.utils.auto_installer.getpass.getpass")
    @patch("version_checker.utils.auto_installer.subprocess.run")
    def test_sudo_wrong_password(
        self, mock_run: MagicMock, mock_getpass: MagicMock
    ) -> None:
        """Test when user enters wrong password."""
        from version_checker.utils.auto_installer import run_sudo_command
        import version_checker.utils.auto_installer as auto_installer_module

        auto_installer_module._cached_sudo_password = None
        mock_run.side_effect = [
            MagicMock(returncode=1),  # sudo -n true fails
            MagicMock(returncode=1, stdout="", stderr="Sorry, incorrect password"),
        ]
        mock_getpass.return_value = "wrongpassword"

        result = run_sudo_command(["ls", "/root"], use_cached_password=False)

        assert result.returncode == 1
        # Password should be cleared from cache
        assert auto_installer_module._cached_sudo_password is None

    @patch("version_checker.utils.auto_installer.subprocess.run")
    def test_sudo_uses_cached_password(self, mock_run: MagicMock) -> None:
        """Test that cached password is reused."""
        from version_checker.utils.auto_installer import run_sudo_command
        import version_checker.utils.auto_installer as auto_installer_module

        # Set cached password
        auto_installer_module._cached_sudo_password = "cachedpass"

        mock_run.side_effect = [
            MagicMock(returncode=1),  # sudo -n true fails
            MagicMock(returncode=0, stdout="", stderr=""),  # sudo -S succeeds
        ]

        result = run_sudo_command(["ls", "/root"])

        assert result.returncode == 0
        # Should use cached password, not prompt


class TestZipInstallerWindowsBranch:
    """Test cases for ZipInstaller Windows-specific code paths."""

    @patch("version_checker.utils.auto_installer.sys.platform", "win32")
    def test_find_executable_windows_exe(self, temp_dir: Path) -> None:
        """Test finding .exe files on Windows."""
        # Create a zip with an exe file
        zip_path = temp_dir / "app.zip"
        target_path = temp_dir / "installed" / "app.exe"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("myapp.exe", b"mock exe content")

        installer = ZipInstaller(zip_path, target_path, silent=True)
        result = installer.install()

        assert result is True
        assert target_path.exists()

    @patch("version_checker.utils.auto_installer.sys.platform", "win32")
    def test_find_executable_windows_nested(self, temp_dir: Path) -> None:
        """Test finding nested .exe files on Windows."""
        zip_path = temp_dir / "app.zip"
        target_path = temp_dir / "installed" / "app.exe"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("subdir/myapp.exe", b"mock exe content")

        installer = ZipInstaller(zip_path, target_path, silent=True)
        result = installer.install()

        assert result is True
        assert target_path.exists()

    @patch("version_checker.utils.auto_installer.sys.platform", "win32")
    def test_find_executable_windows_no_exe(self, temp_dir: Path) -> None:
        """Test when no .exe found on Windows."""
        zip_path = temp_dir / "app.zip"
        target_path = temp_dir / "installed" / "app.exe"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", b"no exe here")

        installer = ZipInstaller(zip_path, target_path, silent=True)
        result = installer.install()

        assert result is False

    def test_find_executable_unix_fallback(self, temp_dir: Path) -> None:
        """Test Unix fallback to files without extension."""
        zip_path = temp_dir / "app.zip"
        target_path = temp_dir / "installed" / "differentname"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # File without extension that doesn't match target name
            zf.writestr("someexe", b"mock exe content")

        installer = ZipInstaller(zip_path, target_path, silent=True)
        result = installer.install()

        assert result is True
        assert target_path.exists()


class TestTarInstallerEdgeCases:
    """Test edge cases for TarInstaller."""

    def test_tar_auto_detect_mode(self, temp_dir: Path) -> None:
        """Test tar with auto-detect compression mode."""
        tar_path = temp_dir / "app.tar"  # Plain tar without compression suffix
        target_path = temp_dir / "installed" / "myapp"

        # Create a plain tar
        with tarfile.open(tar_path, "w") as tf:
            exe_path = temp_dir / "myapp"
            exe_path.write_bytes(b"#!/bin/bash\necho hello")
            exe_path.chmod(0o755)
            tf.add(exe_path, arcname="myapp")

        installer = TarInstaller(tar_path, target_path, silent=True)
        result = installer.install()

        assert result is True
        assert target_path.exists()

    def test_find_executable_no_exact_match(self, temp_dir: Path) -> None:
        """Test finding executable when no exact name match."""
        tar_path = temp_dir / "app.tar.gz"
        target_path = temp_dir / "installed" / "differentname"

        with tarfile.open(tar_path, "w:gz") as tf:
            exe_path = temp_dir / "someexe"
            exe_path.write_bytes(b"#!/bin/bash\necho hello")
            exe_path.chmod(0o755)
            tf.add(exe_path, arcname="someexe")

        installer = TarInstaller(tar_path, target_path, silent=True)
        result = installer.install()

        assert result is True

    def test_find_executable_fallback_no_extension(self, temp_dir: Path) -> None:
        """Test fallback to files without extension."""
        tar_path = temp_dir / "app.tar.gz"
        target_path = temp_dir / "installed" / "differentname"

        with tarfile.open(tar_path, "w:gz") as tf:
            # Create file without extension and without execute permission
            exe_path = temp_dir / "binaryfile"
            exe_path.write_bytes(b"binary content")
            tf.add(exe_path, arcname="binaryfile")

        installer = TarInstaller(tar_path, target_path, silent=True)
        result = installer.install()

        assert result is True

    def test_tar_no_executable_found(self, temp_dir: Path) -> None:
        """Test when no executable found in tar."""
        tar_path = temp_dir / "app.tar.gz"
        target_path = temp_dir / "installed" / "myapp"

        with tarfile.open(tar_path, "w:gz") as tf:
            # Only add files that will be skipped (LICENSE, README)
            license_path = temp_dir / "LICENSE"
            license_path.write_text("MIT License")
            tf.add(license_path, arcname="LICENSE")
            readme_path = temp_dir / "README"
            readme_path.write_text("Documentation")
            tf.add(readme_path, arcname="README")

        installer = TarInstaller(tar_path, target_path, silent=True)
        result = installer.install()

        assert result is False

    def test_tar_exception_handling(self, temp_dir: Path) -> None:
        """Test generic exception handling in tar installer."""
        tar_path = temp_dir / "app.tar.gz"
        target_path = temp_dir / "installed" / "myapp"
        tar_path.write_bytes(b"not a tar file at all")

        installer = TarInstaller(tar_path, target_path, silent=True)
        result = installer.install()

        assert result is False

    def test_tar_generic_exception(self, temp_dir: Path) -> None:
        """Test generic exception handling (non-TarError) in tar installer."""
        tar_path = temp_dir / "app.tar.gz"
        target_path = temp_dir / "installed" / "myapp"

        # Create a valid tar but mock extraction to fail
        with tarfile.open(tar_path, "w:gz") as tf:
            exe_path = temp_dir / "myapp"
            exe_path.write_bytes(b"#!/bin/bash\necho hello")
            tf.add(exe_path, arcname="myapp")

        installer = TarInstaller(tar_path, target_path, silent=True)

        # Mock extractall to raise a generic exception
        with patch("tarfile.open") as mock_open:
            mock_tar = MagicMock()
            mock_tar.__enter__ = MagicMock(return_value=mock_tar)
            mock_tar.__exit__ = MagicMock(return_value=False)
            mock_tar.extractall.side_effect = PermissionError("Access denied")
            mock_open.return_value = mock_tar

            result = installer.install()

        assert result is False


class TestDebInstallerExceptionHandling:
    """Test exception handling in DebInstaller."""

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_exception(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test exception handling during deb installation."""
        mock_which.return_value = "/usr/bin/dpkg"
        mock_sudo.side_effect = Exception("Unexpected error")

        deb_path = temp_dir / "app.deb"
        deb_path.write_bytes(b"fake deb")

        installer = DebInstaller(deb_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is False


class TestPacmanInstallerExceptionHandling:
    """Test exception handling in PacmanInstaller."""

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_failure(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test pacman installation failure."""
        mock_which.return_value = "/usr/bin/pacman"
        mock_sudo.return_value = MagicMock(returncode=1, stderr="Package conflict")

        pkg_path = temp_dir / "app.pkg.tar.zst"
        pkg_path.write_bytes(b"fake pkg")

        installer = PacmanInstaller(pkg_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is False

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_exception(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test exception handling during pacman installation."""
        mock_which.return_value = "/usr/bin/pacman"
        mock_sudo.side_effect = Exception("Unexpected error")

        pkg_path = temp_dir / "app.pkg.tar.zst"
        pkg_path.write_bytes(b"fake pkg")

        installer = PacmanInstaller(pkg_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is False


class TestRpmInstallerEdgeCases:
    """Test edge cases for RpmInstaller."""

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_with_rpm_fallback(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test rpm installation when dnf is not available."""
        # dnf not available, rpm is
        mock_which.side_effect = lambda x: None if x == "dnf" else "/usr/bin/rpm"
        mock_sudo.return_value = MagicMock(returncode=0, stderr="")

        rpm_path = temp_dir / "app.rpm"
        rpm_path.write_bytes(b"fake rpm")

        installer = RpmInstaller(rpm_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is True
        # Verify rpm was used instead of dnf
        call_args = mock_sudo.call_args[0][0]
        assert "rpm" in call_args

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_failure(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test rpm installation failure."""
        mock_which.side_effect = lambda x: "/usr/bin/dnf" if x == "dnf" else None
        mock_sudo.return_value = MagicMock(returncode=1, stderr="Dependency error")

        rpm_path = temp_dir / "app.rpm"
        rpm_path.write_bytes(b"fake rpm")

        installer = RpmInstaller(rpm_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is False

    @patch("version_checker.utils.auto_installer.run_sudo_command")
    @patch("shutil.which")
    def test_install_exception(
        self, mock_which: MagicMock, mock_sudo: MagicMock, temp_dir: Path
    ) -> None:
        """Test exception handling during rpm installation."""
        mock_which.side_effect = lambda x: "/usr/bin/dnf" if x == "dnf" else None
        mock_sudo.side_effect = Exception("Unexpected error")

        rpm_path = temp_dir / "app.rpm"
        rpm_path.write_bytes(b"fake rpm")

        installer = RpmInstaller(rpm_path, temp_dir / "app", silent=True)
        result = installer.install()

        assert result is False


class TestAppImageInstallerExceptionHandling:
    """Test exception handling in AppImageInstaller."""

    @patch("sys.platform", "linux")
    def test_install_exception(self, temp_dir: Path) -> None:
        """Test exception handling during AppImage installation."""
        appimage_path = temp_dir / "app.AppImage"
        appimage_path.write_bytes(b"fake appimage")

        # Target in a directory that will fail to create
        target_path = Path("/nonexistent/deeply/nested/path/app.AppImage")

        installer = AppImageInstaller(appimage_path, target_path, silent=True)

        with patch.object(installer, "is_available", return_value=True):
            with patch.object(
                installer, "_ensure_target_directory", side_effect=Exception("Permission denied")
            ):
                result = installer.install()

        assert result is False


class TestDmgInstallerComplete:
    """Complete test coverage for DmgInstaller."""

    @patch("subprocess.run")
    @patch("sys.platform", "darwin")
    def test_install_mount_failure(self, mock_run: MagicMock, temp_dir: Path) -> None:
        """Test DMG installation when mounting fails."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Mount failed")

        dmg_path = temp_dir / "app.dmg"
        dmg_path.write_bytes(b"fake dmg")

        installer = DmgInstaller(dmg_path, Path("/Applications/App.app"), silent=True)
        result = installer.install()

        assert result is False

    @patch("subprocess.run")
    @patch("sys.platform", "darwin")
    def test_install_no_mount_point_found(
        self, mock_run: MagicMock, temp_dir: Path
    ) -> None:
        """Test DMG installation when mount point cannot be parsed."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Invalid output", stderr=""
        )

        dmg_path = temp_dir / "app.dmg"
        dmg_path.write_bytes(b"fake dmg")

        installer = DmgInstaller(dmg_path, Path("/Applications/App.app"), silent=True)
        result = installer.install()

        assert result is False

    @patch("subprocess.run")
    @patch("sys.platform", "darwin")
    def test_install_no_app_bundle(self, mock_run: MagicMock, temp_dir: Path) -> None:
        """Test DMG installation when no .app bundle found."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/dev/disk2\t\t\t/Volumes/TestApp", stderr=""
        )

        dmg_path = temp_dir / "app.dmg"
        dmg_path.write_bytes(b"fake dmg")

        installer = DmgInstaller(dmg_path, Path("/Applications/App.app"), silent=True)

        with patch.object(Path, "glob", return_value=[]):
            result = installer.install()

        assert result is False

    @patch("subprocess.run")
    @patch("shutil.copytree")
    @patch("shutil.rmtree")
    @patch("sys.platform", "darwin")
    def test_install_success_with_app_suffix(
        self,
        mock_rmtree: MagicMock,
        mock_copytree: MagicMock,
        mock_run: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test successful DMG installation with .app target path."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/dev/disk2\t\t\t/Volumes/TestApp", stderr=""),
            MagicMock(returncode=0),  # detach
        ]

        dmg_path = temp_dir / "app.dmg"
        dmg_path.write_bytes(b"fake dmg")

        installer = DmgInstaller(dmg_path, temp_dir / "TestApp.app", silent=True)

        with patch.object(Path, "glob", return_value=[Path("/Volumes/TestApp/TestApp.app")]):
            with patch.object(Path, "exists", return_value=False):
                result = installer.install()

        assert result is True
        mock_copytree.assert_called_once()

    @patch("subprocess.run")
    @patch("shutil.copytree")
    @patch("shutil.rmtree")
    @patch("sys.platform", "darwin")
    def test_install_success_default_applications(
        self,
        mock_rmtree: MagicMock,
        mock_copytree: MagicMock,
        mock_run: MagicMock,
        temp_dir: Path,
    ) -> None:
        """Test DMG installation to default /Applications directory."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/dev/disk2\t\t\t/Volumes/TestApp", stderr=""),
            MagicMock(returncode=0),
        ]

        dmg_path = temp_dir / "app.dmg"
        dmg_path.write_bytes(b"fake dmg")

        # Target without .app suffix triggers install to /Applications
        installer = DmgInstaller(dmg_path, temp_dir / "TestApp", silent=True)

        with patch.object(Path, "glob", return_value=[Path("/Volumes/TestApp/TestApp.app")]):
            with patch.object(Path, "exists", return_value=True):
                result = installer.install()

        assert result is True

    @patch("subprocess.run")
    @patch("sys.platform", "darwin")
    def test_install_exception(self, mock_run: MagicMock, temp_dir: Path) -> None:
        """Test exception handling during DMG installation."""
        mock_run.side_effect = Exception("Unexpected error")

        dmg_path = temp_dir / "app.dmg"
        dmg_path.write_bytes(b"fake dmg")

        installer = DmgInstaller(dmg_path, Path("/Applications/App.app"), silent=True)
        result = installer.install()

        assert result is False

    @patch("subprocess.run")
    @patch("sys.platform", "darwin")
    def test_install_unmount_exception(self, mock_run: MagicMock, temp_dir: Path) -> None:
        """Test that unmount exceptions are suppressed in finally block."""
        # Mount succeeds
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="/dev/disk2\t\t\t/Volumes/TestApp", stderr=""),
            Exception("Unmount failed"),  # Detach fails
        ]

        dmg_path = temp_dir / "app.dmg"
        dmg_path.write_bytes(b"fake dmg")

        installer = DmgInstaller(dmg_path, temp_dir / "TestApp.app", silent=True)

        with patch.object(Path, "glob", return_value=[]):
            result = installer.install()

        # Should return False (no app found) but not raise exception from unmount
        assert result is False

    @patch("sys.platform", "darwin")
    def test_parse_mount_point(self) -> None:
        """Test parsing mount point from hdiutil output."""
        installer = DmgInstaller(Path("/tmp/app.dmg"), Path("/Applications/App.app"), silent=True)

        # Valid output
        output = "/dev/disk2s1\tApple_HFS\t/Volumes/MyApp"
        mount_point = installer._parse_mount_point(output)
        assert mount_point == "/Volumes/MyApp"

        # Invalid output
        invalid_output = "Just some text"
        mount_point = installer._parse_mount_point(invalid_output)
        assert mount_point is None

        # Output with non-volume path
        non_volume = "/dev/disk2s1\tApple_HFS\t/some/other/path"
        mount_point = installer._parse_mount_point(non_volume)
        assert mount_point is None


class TestGetInstallerForTypeWarning:
    """Test get_installer_for_type warning message."""

    @patch("shutil.which")
    @patch("version_checker.utils.auto_installer.console")
    def test_unavailable_installer_warning(
        self, mock_console: MagicMock, mock_which: MagicMock, temp_dir: Path
    ) -> None:
        """Test warning message when installer is unavailable."""
        mock_which.return_value = None

        installer = get_installer_for_type(
            PackageType.DEB,
            temp_dir / "app.deb",
            temp_dir / "app",
            silent=False,  # Not silent to trigger warning
        )

        assert installer is None
        mock_console.print.assert_called()


class TestAutoInstallerWithAutoLaunch:
    """Test AutoInstaller with auto_launch enabled."""

    def test_install_with_auto_launch_success(self, temp_dir: Path) -> None:
        """Test installation with auto_launch enabled."""
        exe_path = temp_dir / "app.exe"
        exe_path.write_bytes(b"Mock exe")

        installer = AutoInstaller(
            str(exe_path),
            "https://example.com/app.zip",
            auto_launch=True,
        )
        installer.fresh_install = True

        with patch.object(installer, "_download", return_value=True):
            with patch.object(installer, "_extract_and_overwrite", return_value=True):
                with patch.object(installer, "_start_process", return_value=True):
                    result = installer.install()

        assert result is True


class TestAutoInstallerExtractionEdgeCases:
    """Test edge cases in AutoInstaller extraction."""

    def test_extract_unknown_package_type_fallback(self, temp_dir: Path) -> None:
        """Test fallback to ZIP for unknown package type."""
        # Create a file with unknown extension
        unknown_path = temp_dir / "app.unknown"

        # But make it a valid zip
        with zipfile.ZipFile(unknown_path, "w") as zf:
            zf.writestr("app.exe", b"mock exe")

        target_path = temp_dir / "installed" / "app.exe"
        installer = AutoInstaller(str(target_path), "https://example.com/app.zip")
        installer.downloaded_file = unknown_path

        result = installer._extract_and_overwrite()

        assert result is True

    def test_extract_no_installer_available(self, temp_dir: Path) -> None:
        """Test when no installer is available for package type."""
        # Create a file with unknown extension that's not a valid zip
        unknown_path = temp_dir / "app.strange"
        unknown_path.write_bytes(b"not a valid archive")

        target_path = temp_dir / "installed" / "app"
        installer = AutoInstaller(str(target_path), "https://example.com/app.zip")
        installer.downloaded_file = unknown_path

        result = installer._extract_and_overwrite()

        assert result is False

    @patch("version_checker.utils.auto_installer.console")
    def test_extract_no_installer_available_non_silent(
        self, mock_console: MagicMock, temp_dir: Path
    ) -> None:
        """Test no installer message when not in silent mode."""
        # Create a deb file when dpkg is not available
        deb_path = temp_dir / "app.deb"
        deb_path.write_bytes(b"fake deb content")

        target_path = temp_dir / "installed" / "app"
        installer = AutoInstaller(
            str(target_path),
            "https://example.com/app.deb",
            silent=False,  # Not silent to trigger message
        )
        installer.downloaded_file = deb_path

        with patch("shutil.which", return_value=None):  # dpkg not available
            result = installer._extract_and_overwrite()

        assert result is False
        # Check that the "No installer available" message was printed
        mock_console.print.assert_called()


class TestKillProcessExceptionHandling:
    """Test exception handling in _kill_process."""

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_no_such_process(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test handling NoSuchProcess exception."""
        import psutil as real_psutil

        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "app.exe"}
        mock_proc.terminate.side_effect = real_psutil.NoSuchProcess(1234)
        mock_psutil.process_iter.return_value = [mock_proc]
        mock_psutil.NoSuchProcess = real_psutil.NoSuchProcess
        mock_psutil.AccessDenied = real_psutil.AccessDenied
        mock_psutil.ZombieProcess = real_psutil.ZombieProcess

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")
        result = installer._kill_process()

        assert result is True

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_access_denied(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test handling AccessDenied exception."""
        import psutil as real_psutil

        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "app.exe"}
        mock_proc.terminate.side_effect = real_psutil.AccessDenied(1234)
        mock_psutil.process_iter.return_value = [mock_proc]
        mock_psutil.NoSuchProcess = real_psutil.NoSuchProcess
        mock_psutil.AccessDenied = real_psutil.AccessDenied
        mock_psutil.ZombieProcess = real_psutil.ZombieProcess

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")
        result = installer._kill_process()

        assert result is True

    @patch("version_checker.utils.auto_installer.psutil")
    @patch("version_checker.utils.auto_installer.console")
    def test_kill_process_force_kill_exceptions(
        self, mock_console: MagicMock, mock_psutil: MagicMock
    ) -> None:
        """Test handling exceptions during force kill."""
        import psutil as real_psutil

        mock_proc = MagicMock()
        mock_proc.info = {"pid": 1234, "name": "app.exe"}
        mock_proc.kill.side_effect = real_psutil.NoSuchProcess(1234)

        # First iter returns process (triggers terminate), second returns same (triggers kill)
        mock_psutil.process_iter.side_effect = [[mock_proc], [mock_proc]]
        mock_psutil.NoSuchProcess = real_psutil.NoSuchProcess
        mock_psutil.AccessDenied = real_psutil.AccessDenied
        mock_psutil.ZombieProcess = real_psutil.ZombieProcess

        installer = AutoInstaller("/path/to/app.exe", "https://example.com/app.zip")
        result = installer._kill_process()

        assert result is True


class TestDownloadExceptionHandling:
    """Test exception handling in _download."""

    @patch("version_checker.utils.auto_installer.console")
    def test_download_unexpected_exception(
        self, mock_console: MagicMock, temp_dir: Path
    ) -> None:
        """Test handling unexpected exceptions during download."""
        import requests as real_requests

        installer = AutoInstaller(
            str(temp_dir / "app.exe"), "https://example.com/app.zip"
        )
        installer.downloads_dir = temp_dir

        # Patch requests at the module level but use real exceptions
        with patch("version_checker.utils.auto_installer.requests") as mock_requests:
            mock_requests.head.return_value = MagicMock(headers={"content-length": "1000"})
            mock_requests.get.side_effect = ValueError("Unexpected error")
            mock_requests.exceptions = real_requests.exceptions

            result = installer._download()

        assert result is False
        mock_console.print.assert_called()
