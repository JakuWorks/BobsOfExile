#!/bin/bash

echo "This program may exit with an error message. It will NOT correct its mistakes. If that happens, then you must manually delete any (temporary) files created by it before running it again."

exit_if_file_exists() {
	if [ -f $1 ]; then
		echo "The file '$1' already exists! Remove it before running the program. Comment: '$2'"
		exit 1
	fi
}

exit_if_dir_exists() {
	if [ -d $1 ]; then
		echo "The dir '$1' already exists! Remove it before running the program. Comment: '$2'"
		exit 1
	fi
}
exit_if_file_not_exists() {
	if [ ! -f $1 ]; then
		echo "The file '$1' doesn't exist! The program cannot continue. Comment: '$2'"
		exit 1
	fi
}

exit_if_dir_not_exists() {
	if [ ! -d $1 ]; then
		echo "The dir '$1' doesn't exist! The program cannot continue. Comment: '$2'"
		exit 1
	fi
}

exit_commented() {
	echo "ERROR! Comment: '$1'"
	exit 1
}


# ---

ARG_MODE="$1"
MODE_CLIENT='client'
MODE_SERVER='server'
MODE_BOTH='both'
ENV_PORTABLE='./.env'
exit_if_file_exists "$ENV_PORTABLE"

if [[ $ARG_MODE == $MODE_CLIENT ]]; then
	ENV_PATH='./.env-client'
	MODE_NAME="$MODE_CLIENT"'mode'
elif [[ $ARG_MODE == $MODE_SERVER ]]; then
	ENV_PATH='./.env-server'
	MODE_NAME="$MODE_SERVER"'mode'
elif [[ $ARG_MODE == $MODE_BOTH ]]; then
	echo "SELECTED $MODE_BOTH"
    /bin/bash "$0" "$MODE_CLIENT" || exit_commented "Making client mode portable failed"
    /bin/bash "$0" "$MODE_SERVER" || exit_commented "Making server mode portable failed"
    exit 0
else
	echo "Missing arg1 (mode), can be '$MODE_CLIENT' or '$MODE_SERVER' or '$MODE_BOTH'"
	exit 1
fi

exit_if_file_not_exists "$ENV_PATH"


# ---

BIN='./bin/'
exit_if_dir_not_exists "$BIN"

PORTABLE_BIN='./bin-portable/'
PORTABLE_PYTHON="$PORTABLE_BIN"'pypy3.11-v7.3.21-linux64/' # FREQUENT EDIT
PORTABLE_PYTHON_BIN="$PORTABLE_PYTHON"'bin/'
PORTABLE_PYTHON_PYTHON="$PORTABLE_PYTHON_BIN"'python3'
PORTABLE_PYTHON_PIP="$PORTABLE_PYTHON_BIN"'pip3'

PORTABLE_PYTHON_LIB="$PORTABLE_PYTHON"'lib/'
PORTABLE_PYTHON_LIB_PYTHON="$PORTABLE_PYTHON_LIB"'pypy3.11/'
PORTABLE_PYTHON_LIB_PYTHON_ENSUREPIP="$PORTABLE_PYTHON_LIB_PYTHON"'ensurepip/'
exit_if_dir_exists "$PORTABLE_BIN"

# UNUSED IN THIS SCRIPT
# DEV_REQUIREMENTS_FILE='./dev-requirements.txt'
# exit_if_file_not_exists "$DEV_REQUIREMENTS_FILE"

RESULT_ZIP_PATH='.BobsOfExile-portable-'"$MODE_NAME"'.zip'
exit_if_file_exists "$RESULT_ZIP_PATH"


# ---

echo "SELECTED $MODE_NAME"

cp -r "$BIN" "$PORTABLE_BIN" || exit_commented "Making portable bin"

# Checking for each in this order to increase error msg helpfulness
exit_if_dir_not_exists "$PORTABLE_BIN"
exit_if_dir_not_exists "$PORTABLE_PYTHON"
exit_if_dir_not_exists "$PORTABLE_PYTHON_BIN"
exit_if_file_not_exists "$PORTABLE_PYTHON_PYTHON"

exit_if_dir_not_exists "$PORTABLE_PYTHON_LIB"
exit_if_dir_not_exists "$PORTABLE_PYTHON_LIB_PYTHON"
exit_if_dir_not_exists "$PORTABLE_PYTHON_LIB_PYTHON_ENSUREPIP"

"$PORTABLE_PYTHON_PYTHON" -m ensurepip || exit_commented "Ensuring pip"
rm -r "$PORTABLE_PYTHON_LIB_PYTHON_ENSUREPIP" || exit_commented "Removing ensurepip lib"
exit_if_file_not_exists "$PORTABLE_PYTHON_PIP"
"$PORTABLE_PYTHON_PIP" install . || exit_commented "Installing project"

cp "$ENV_PATH" "$ENV_PORTABLE" || exit_commented "Copying selected env"
(find . -type d -name '__pycache__' | xargs rm -r) || exit_commented 'Removing all __pycache__'

# Depending on shell expansion here
zip -9 "$RESULT_ZIP_PATH" ./* -x ./*/ ./.* ./*.log || exit_commented "Adding results zip shallow"
zip -9 "$RESULT_ZIP_PATH" "$ENV_PORTABLE" || exit_commented "Adding results zip portable env"
zip -r -9 "$RESULT_ZIP_PATH" "$PORTABLE_BIN" || exit_commented "Adding results zip portable bin"

rm -r "$PORTABLE_BIN" || exit_commented "Removing portable bin"
rm "$ENV_PORTABLE" || exit_commented "Removing portable env"

echo "FINISHED WITHOUT ANY EXPECTED ERRORS ($MODE_NAME)"
