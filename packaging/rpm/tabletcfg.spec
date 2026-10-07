Name:           tabletcfg
Version:        0.1.0
Release:        1%{?dist}
Summary:        Graphics tablet configurator for X11 (libinput)

License:        GPL-3.0-or-later
URL:            https://github.com/viniciusorig/tabletcfg
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  desktop-file-utils

Requires:       python3-gobject
Requires:       gtk3
Requires:       python3-pyudev
Requires:       xinput
Requires:       xrandr
Requires:       xorg-x11-drv-libinput
Requires:       sudo
Requires:       systemd

%description
GTK window and command line to configure a graphics tablet under X11 with the
libinput driver: map the tablet to a monitor or screen area, crop the tablet
area, rotate, keep aspect ratio, adjust the pen pressure curve and remap tablet
and pen buttons (shortcut, mouse click, scroll, command). Settings are kept in
profiles and reapplied automatically when the tablet is plugged in.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l tabletcfg
install -Dm644 data/tabletcfg.desktop %{buildroot}%{_datadir}/applications/tabletcfg.desktop
install -Dm644 data/70-tabletcfg-uinput.rules %{buildroot}%{_udevrulesdir}/70-tabletcfg-uinput.rules
install -Dm644 data/tabletcfg.1 %{buildroot}%{_mandir}/man1/tabletcfg.1

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/tabletcfg.desktop
%{py3_test_envvars} %{python3} -m unittest discover -s tests -t .

%files -f %{pyproject_files}
%doc README.md
%{_bindir}/tabletcfg
%{_datadir}/applications/tabletcfg.desktop
%{_udevrulesdir}/70-tabletcfg-uinput.rules
%{_mandir}/man1/tabletcfg.1*

%changelog
* Wed Oct 07 2026 viniciusorig <vinicius100loucototal@gmail.com> - 0.1.0-1
- Primeira versão
