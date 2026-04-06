#!/bin/sh
#
# Copyright (c) 2026 Enji Cooper <ngie@FreeBSD.org>
#
# SPDX-License-Identifier: BSD-2-Clause

set -e

SRCDIR="$(realpath "$(dirname "$0")/../src")"

: "${PYTHON=python3}"
export PYTHONPATH="${SRCDIR}"

version="$("${PYTHON}" -c 'from ghpr import __version__; print(__version__)')"
ghpr_init_file="$("${PYTHON}" -c 'import ghpr; print(ghpr.__file__)')"
new_version="$(( version + 1 ))"

tag="v${new_version}"

sed -i '' -e '/__version__ = /s/"'"${version}"'"/"'"${new_version}"'"/' "${ghpr_init_file}"
git commit -m "Bump to ${tag}." -s .

git tag "${tag}"
git push --follow --tags
gh release create --generate-notes --prerelease "v${new_version}"
