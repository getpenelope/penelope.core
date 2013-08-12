#!/bin/sh

DOMAIN='penelope'

../../../../bin/i18ndude rebuild-pot --pot locale/${DOMAIN}.pot --create ${DOMAIN} .

../../../../bin/i18ndude sync --pot locale/${DOMAIN}.pot locale/*/LC_MESSAGES/${DOMAIN}.po

# Compile po files
for lang in $(find locale -mindepth 1 -maxdepth 1 -type d); do
    if test -d $lang/LC_MESSAGES; then
        msgfmt -o $lang/LC_MESSAGES/${DOMAIN}.mo $lang/LC_MESSAGES/${DOMAIN}.po
    fi
done
