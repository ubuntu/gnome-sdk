#!/bin/bash

LC_ALL=C

DEBUG_ROOT=$1
OBJECT=$2

if [ ! -f "${OBJECT}" ]; then
  echo "File ${OBJECT} does not exists"
  exit 1
fi

if [ ! -d "${DEBUG_ROOT}" ]; then
  echo "Directory ${DEBUG_ROOT} does not exists"
  exit 1
fi

FILE=$(file "${OBJECT}")

echo "${FILE}" | grep -Eq "LSB pie executable|LSB executable"
IS_EXECUTABLE=$?

echo "${FILE}" | grep "LSB shared object" | grep -q "dynamically linked"
IS_SHARED_LIB=$?

echo "${FILE}" | grep "LSB shared object" | grep -q "static-pie linked"
IS_STATIC_LIB=$?

if [ ${IS_EXECUTABLE} -ne 0 -a ${IS_SHARED_LIB} -ne 0 -a ${IS_STATIC_LIB} -ne 0 ]; then
  echo "File ${OBJECT} is not some ELF we can analyze. file returned: ${FILE}"
  exit 0
fi

echo "${FILE}" | grep -q "not stripped"
STRIPPED_EXIT=$?
if [ ${STRIPPED_EXIT} -ne 0 ]; then
  echo "File ${OBJECT} was stripped, no debug info"
  exit 0
fi

echo "${FILE}" | grep -q "BuildID"
HAS_BUILDID=$?
if [ ${HAS_BUILDID} -ne 0 ]; then
  echo "File ${OBJECT} does not have BuildID"
  exit 1
fi

## Usage of BuildID, debug file path and parameters of objcopy/strip are all
## taken from what dh_strip's make_debug() does for packaging debug symbols

BUILDID=$(echo "${FILE}" | cut -d'=' -f2 | cut -d',' -f1)
DEBUG_FIRST=${BUILDID:0:2}
DEBUG_FILE=${BUILDID:2}
DEBUG_PATH="${DEBUG_ROOT}/${DEBUG_FIRST}/${DEBUG_FILE}.debug"

mkdir -p $(dirname "${DEBUG_PATH}")

echo "Extracting debug symbols from ${OBJECT} into ${DEBUG_PATH}"
objcopy --only-keep-debug --compress-debug-sections "${OBJECT}" "${DEBUG_PATH}"


if [ ${IS_SHARED_LIB} -eq 0 ]; then
  STRIP_UNNEEDED="--strip-unneeded"
fi
echo "Stripping ${OBJECT}"
strip --remove-section=.comment --remove-section=.note ${STRIP_UNNEEDED} "${OBJECT}"
