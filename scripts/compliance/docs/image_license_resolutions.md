<!--
Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
-->

# Digest-bound image package license resolutions

Run `security_image_sca`; its first failure lists every exact package/version whose scanner metadata
is named-only or missing. Add only corroborated rows, retain their source links, then rerun. Tag-only
or package-name-only answers are rejected. Publisher-level container terms remain in
`THIRD_PARTY_LICENSES.md`.

| Scope | Package | Version | SPDX license | Evidence |
|---|---|---|---|---|
| Debian 13 image package | debian-archive-keyring | 2025.1 | GPL-2.0-or-later | [Debian exact-version copyright file](https://sources.debian.org/src/debian-archive-keyring/2025.1/debian/copyright); the OpenPGP keys are not copyrighted and the package support files are GPL-2.0-or-later |
| Debian 13 image package | libcrypt1 | 1:4.4.38-1 | LGPL-2.1-or-later AND BSD-3-Clause AND BSD-2-Clause AND 0BSD AND LicenseRef-Public-Domain | [libxcrypt exact-version licensing inventory](https://sources.debian.org/src/libxcrypt/1%3A4.4.38-1/LICENSING); expression covers the installed library's file-level terms |
| Debian 13 image package | tzdata | 2026b-0+deb13u1 | BSD-3-Clause AND LicenseRef-Public-Domain | [Debian exact-version source](https://sources.debian.org/src/tzdata/2026b-0%2Bdeb13u1/); [upstream license text](https://sources.debian.org/src/tzdata/2026b-1/LICENSE); most files are public domain and the named exceptions are BSD-3-Clause |
