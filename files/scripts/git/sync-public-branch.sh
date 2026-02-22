#!/usr/bin/env bash

VERSION="2026.2.4"

GIT_DEFAULT_BRANCH=main
GIT_PUBLIC_BRANCH=public
GIT_REMOVE_CACHED_FILES=0

## ref: https://intoli.com/blog/exit-on-errors-in-bash-scripts/
# exit when any command fails
set -e

#SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#SCRIPT_DIR="$(dirname "$0")"
SCRIPT_NAME="$(basename "$0")"

CONFIRM=0

## PURPOSE RELATED VARS
#REPO_DIR=$( git rev-parse --show-toplevel )
#REPO_DIR="$(cd "${SCRIPT_DIR}" && git rev-parse --show-toplevel)"
REPO_DIR="$(git rev-parse --show-toplevel)"

PUBLIC_GITIGNORE=.gitignore.pub
PUBLIC_GITMODULES=.gitmodules.pub

## ref: https://stackoverflow.com/questions/53839253/how-can-i-convert-an-array-into-a-comma-separated-string
declare -a EXCLUDES_ARRAY
EXCLUDES_ARRAY+=('.git')
EXCLUDES_ARRAY+=('.gitmodule')

declare -a IGNORE_ARRAY
IGNORE_ARRAY+=('.git')

printf -v IGNORE_LIST '%s,' "${IGNORE_ARRAY[@]}"
IGNORE_LIST="${IGNORE_LIST%,}"

EXCLUDES_ARRAY+=("${IGNORE_ARRAY[@]}")

printf -v EXCLUDES_LIST '%s,' "${EXCLUDES_ARRAY[@]}"
EXCLUDES_LIST="${EXCLUDES_LIST%,}"

#TEMP_DIR=$(mktemp -d -p ~)
TEMP_DIR=$(mktemp -d /tmp/sync-repo.XXXXXXXXXX)


#### LOGGING RELATED
LOG_ERROR=0
LOG_WARN=1
LOG_FAILED=2
LOG_SUCCESS=3
LOG_INFO=4
LOG_TRACE=5
LOG_DEBUG=6

declare -A LOGLEVEL_TO_STR
LOGLEVEL_TO_STR["${LOG_ERROR}"]="ERROR"
LOGLEVEL_TO_STR["${LOG_WARN}"]="WARN"
LOGLEVEL_TO_STR["${LOG_FAILED}"]="FAILED"
LOGLEVEL_TO_STR["${LOG_SUCCESS}"]="SUCCESS"
LOGLEVEL_TO_STR["${LOG_INFO}"]="INFO"
LOGLEVEL_TO_STR["${LOG_TRACE}"]="TRACE"
LOGLEVEL_TO_STR["${LOG_DEBUG}"]="DEBUG"

# string formatters
# Force color if FORCE_COLOR is set, otherwise auto-detect TTY
if [[ -n "${FORCE_COLOR:-}" ]] || [[ -t 1 ]]; then
  tty_escape() { printf "\033[%sm" "$1"; }
else
  tty_escape() { :; }
fi
tty_mkbold() { tty_escape "1;$1"; }
tty_underline="$(tty_escape "4;39")"
tty_dim_grey="$(tty_escape "2;39")"
tty_red="$(tty_mkbold 31)"
tty_green="$(tty_mkbold 32)"
tty_yellow="$(tty_mkbold 33)"
tty_blue="$(tty_mkbold 34)"
tty_magenta="$(tty_mkbold 35)"
tty_cyan="$(tty_mkbold 36)"
tty_bold="$(tty_mkbold 39)"
tty_reset="$(tty_escape 0)"

function shell_join() {
  local arg
  printf "%s" "$1"
  shift
  for arg in "$@"
  do
    printf " "
    printf "%s" "${arg// /\ }"
  done
}

function chomp() {
  printf "%s" "${1/"$'\n'"/}"
}

function reverse_array() {
  local -n array_source_ref=$1
  local -n reversed_array_ref=$2
  # iterate over the keys of the loglevel_to_str array
  for key in "${!array_source_ref[@]}"; do
    # get the value associated with the current key
    value="${array_source_ref[$key]}"
    # add the reversed key-value pair to the reversed_array_ref array
    reversed_array_ref["$value"]="$key"
  done
}

declare -A LOGLEVELSTR_TO_LEVEL
reverse_array LOGLEVEL_TO_STR LOGLEVELSTR_TO_LEVEL

#LOG_LEVEL_IDX=${LOG_DEBUG}
LOG_LEVEL_IDX=${LOG_INFO}
LOG_LEVEL_PADDING_LENGTH=7
#LOG_INCLUDE_INVOKER=true
LOG_PAD_LEVEL=true

# --- Logging Functions ---

function _log_message() {
    local log_message_level="${1}"
    local log_message="${2}"
    local log_prefix="${3:-}"

    if (( log_message_level > LOG_LEVEL_IDX )); then
        return 0
    fi

    local log_level_str="${LOGLEVEL_TO_STR[$log_message_level]}"
    [[ -z "$log_level_str" ]] && { echo "Unknown level: $log_message_level" >&2; return 1; }

    local log_level_display="${log_level_str}"
    if [[ "${LOG_PAD_LEVEL:-false}" = "true" ]] || [[ "${LOG_PAD_LEVEL:-0}" = "1" ]]; then
        printf -v log_level_display "%-${LOG_LEVEL_PADDING_LENGTH}s" "${log_level_str}"
    fi

    local log_context=""
    local _log_tty_color="${tty_reset}"

    if [ -n "${BASH_VERSION:-}" ]; then
        local script_path="${BASH_SOURCE[2]##*/}"

        # Build Call Stack: skip _log_message (0) and wrapper (1)
        local stack_parts=("${FUNCNAME[@]:2}")
        local call_stack=""

        for (( i=${#stack_parts[@]}-1; i>=0; i-- )); do
            local func="${stack_parts[i]}"

            # Normalize 'source' to 'main' or keep existing 'main'
            if [[ "$func" == "main" || "$func" == "source" ]]; then
                # Only add 'main' if it's the first thing in our built stack
                if [[ -z "$call_stack" ]]; then
                    call_stack="main"
                fi
            else
                # Add real function names, separated by colons
                [[ -n "$call_stack" ]] && call_stack+=":"
                call_stack+="$func"
            fi
        done

        # If call_stack is empty (called from top-level), just use the script name
        # Otherwise, append the stack with parentheses
        local func_context=""
        if [[ -n "$call_stack" ]]; then
            func_context="${call_stack%:}()"
        fi

        local line_no="${BASH_LINENO[1]}"

        case "${log_message_level}" in
            "$LOG_DEBUG") _log_tty_color="${tty_dim_grey}"; log_context="${func_context}[${line_no}]" ;;
            "$LOG_TRACE") _log_tty_color="${tty_blue}";     log_context="${func_context}[${line_no}]" ;;
            "$LOG_SUCCESS") _log_tty_color="${tty_green}"; log_context="${func_context}" ;;
            "$LOG_FAILED")  _log_tty_color="${tty_red}";   log_context="${func_context}" ;;
            "$LOG_WARN")  _log_tty_color="${tty_yellow}";  log_context="${func_context}" ;;
            "$LOG_ERROR") _log_tty_color="${tty_red}";     log_context="${func_context}[${line_no}]" ;;
            *)            _log_tty_color="${tty_reset}";   log_context="${func_context}" ;;
        esac
    else
        log_context="$(basename "$0")"
    fi

    [[ "${LOG_INCLUDE_INVOKER:-false}" = "true" ]] || [[ "${LOG_INCLUDE_INVOKER:-0}" = "1" ]] && log_context="${script_path}=>${log_context}"
    [[ -n "${log_prefix}" ]] && log_context="${log_prefix}::${log_context}"

    # Standardized Output
#    printf "${_log_tty_color}%s [%s] %s:${tty_reset} %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$log_message_level" "$log_context" "$log_message"
    printf "[%s] ${_log_tty_color}%s %s${tty_reset}\n" "$log_level_display" "$log_context" "$log_message"
}

# Wrapper Functions with Prefix Support
log()                { _log_message "${LOG_INFO}"           "$1" "${2:-}"; }
log_debug()          { _log_message "${LOG_DEBUG}"          "$1" "${2:-}"; }
log_trace()          { _log_message "${LOG_TRACE}"          "$1" "${2:-}"; }
log_info()           { _log_message "${LOG_INFO}"           "$1" "${2:-}"; }
log_success()        { _log_message "${LOG_SUCCESS}"        "$1" "${2:-}"; }
log_failed()         { _log_message "${LOG_FAILED}"         "$1" "${2:-}"; }
log_warn()        { _log_message "${LOG_WARN}"           "$1" "${2:-}"; }
log_error()          { _log_message "${LOG_ERROR}"          "$1" "${2:-}"; }

function ohai()  { printf "${tty_blue}==>${tty_bold} %s${tty_reset}\n" "$*"; }
function abort() { log_error "$1"; exit 1; }
function warn()  { log_warn "$1"; }
function error() { log_error "$1"; }
function fail()  { error "$1"; exit 1; }

function set_log_level() {
  local level_idx="${LOGLEVELSTR_TO_LEVEL[${1^^}]}" # ^^ makes it case-insensitive
  if [[ -n "$level_idx" ]]; then
    LOG_LEVEL_IDX="$level_idx"
  else
    abort "Unknown log level: [$1]"
  fi
}

# --- Helper Functions ---

function execute() {
  log_info "${*}"
  if ! "$@"
  then
    abort "$(printf "Failed during: %s" "$(shell_join "$@")")"
  fi
}

function execute_eval_command() {
  local RUN_COMMAND="${*}"

  log_debug "${RUN_COMMAND}"
  COMMAND_RESULT=$(eval "${RUN_COMMAND}")
#  COMMAND_RESULT=$(eval "${RUN_COMMAND} > /dev/null 2>&1")
  local RETURN_STATUS=$?

  if [[ $RETURN_STATUS -eq 0 ]]; then
    if [[ $COMMAND_RESULT != "" ]]; then
      log_debug $'\n'"${COMMAND_RESULT}"
    fi
    log_debug "SUCCESS!"
  else
    log_error "ERROR (${RETURN_STATUS})"
#    echo "${COMMAND_RESULT}"
    abort "$(printf "Failed during: %s" "${RUN_COMMAND}")"
  fi

}

function is_installed() {
  command -v "${1}" >/dev/null 2>&1 || return 1
}

function check_required_commands() {
  MISSING_COMMANDS=""
  for CURRENT_COMMAND in "$@"
  do
    is_installed "${CURRENT_COMMAND}" || MISSING_COMMANDS="${MISSING_COMMANDS} ${CURRENT_COMMAND}"
  done

  if [[ -n "${MISSING_COMMANDS}" ]]; then
    fail "Please install the following commands required by this script: ${MISSING_COMMANDS}"
  fi
}

function git_commit_push() {
  local LOCAL_BRANCH
  local REMOTE_AND_BRANCH
  LOCAL_BRANCH="$(git symbolic-ref --short HEAD)" && \
  REMOTE_AND_BRANCH=$(git rev-parse --abbrev-ref "${LOCAL_BRANCH}@{upstream}") && \
  IFS=/ read -r REMOTE_NAME REMOTE_BRANCH <<< "${REMOTE_AND_BRANCH}" && \
  echo "Staging changes:" && \
  (git add -A || true) && \
  echo "Committing changes:" && \
  (git commit -am "Sync: Automated sync from main to public branch." || true) && \
  echo "Pushing branch '${LOCAL_BRANCH}' to remote '${REMOTE_NAME}' branch '${REMOTE_BRANCH}':" && \
  (git push -f -u "${REMOTE_NAME}" "${LOCAL_BRANCH}:${REMOTE_BRANCH}" || true)
}

function search_repo_keywords () {

  #export -p | sed 's/declare -x //' | sed 's/export //'
  if [ -z ${REPO_EXCLUDE_KEYWORDS+x} ]; then
    abort "REPO_EXCLUDE_KEYWORDS not set/defined"
  fi

  log_debug "REPO_EXCLUDE_KEYWORDS=${REPO_EXCLUDE_KEYWORDS}"

  IFS=',' read -ra REPO_EXCLUDE_KEYWORDS_ARRAY <<< "$REPO_EXCLUDE_KEYWORDS"

  log_debug "REPO_EXCLUDE_KEYWORDS_ARRAY=${REPO_EXCLUDE_KEYWORDS_ARRAY[*]}"

  # ref: https://superuser.com/questions/1371834/escaping-hyphens-with-printf-in-bash
  #'-e' ==> '\055e'
  local GREP_DELIM=' \055e '
  printf -v GREP_PATTERN_SEARCH "${GREP_DELIM}%s" "${REPO_EXCLUDE_KEYWORDS_ARRAY[@]}"

  ## strip prefix
  local GREP_PATTERN_SEARCH=${GREP_PATTERN_SEARCH#"$GREP_DELIM"}
  ## strip suffix
  #local GREP_PATTERN_SEARCH=${GREP_PATTERN_SEARCH%"$GREP_DELIM"}

  log_debug "GREP_PATTERN_SEARCH=${GREP_PATTERN_SEARCH}"

  local GREP_COMMAND="grep ${GREP_PATTERN_SEARCH}"
  log_debug "GREP_COMMAND=${GREP_COMMAND}"

  local FIND_DELIM=' -o '
#  printf -v FIND_EXCLUDE_DIRS "\055path '*/%s/*' -prune${FIND_DELIM}" "${EXCLUDES_ARRAY[@]}"
  printf -v FIND_EXCLUDE_DIRS "! -path '*/%s/*'${FIND_DELIM}" "${EXCLUDES_ARRAY[@]}"
  local FIND_EXCLUDE_DIRS=${FIND_EXCLUDE_DIRS%"$FIND_DELIM"}

  log_debug "FIND_EXCLUDE_DIRS=${FIND_EXCLUDE_DIRS}"

  ## this works:
  ## find . \( -path '*/.git/*' \) -prune -name '.*' -o -exec grep -i example {} 2>/dev/null +
  ## find . \( -path '*/save/*' -prune -o -path '*/.git/*' -prune \) -o -exec grep -i example {} 2>/dev/null +
  ## find . \( ! -path '*/save/*' -o ! -path '*/.git/*' \) -o -exec grep -i example {} 2>/dev/null +
  ## ref: https://stackoverflow.com/questions/6565471/how-can-i-exclude-directories-from-grep-r#8692318
  ## ref: https://unix.stackexchange.com/questions/342008/find-and-echo-file-names-only-with-pattern-found
  ## ref: https://www.baeldung.com/linux/find-exclude-paths
  local FIND_CMD="find ${REPO_DIR}/ \( ${FIND_EXCLUDE_DIRS} \) -o -exec ${GREP_COMMAND} {} 2>/dev/null +"
  log_info "${FIND_CMD}"

  local EXCEPTION_COUNT
  EXCEPTION_COUNT=$(eval "${FIND_CMD} | wc -l")
  if [[ $EXCEPTION_COUNT -eq 0 ]]; then
    log_info "SUCCESS => No exclusion keyword matches found!!"
  else
    log_error "There are [${EXCEPTION_COUNT}] exclusion keyword matches found:"
    eval "${FIND_CMD}"
    exit 1
  fi
  return "${EXCEPTION_COUNT}"
}

# --- Core Functions ---

# Function to clean up the temporary directory
cleanup() {
    if [[ -d "${TEMP_DIR}" ]]; then
        log_info "Cleaning up temporary directory: ${TEMP_DIR}"
        rm -rf "${TEMP_DIR}"
    fi
}

# Function to handle errors
on_error() {
    local exit_code="$?"
    if [[ "$exit_code" -ne 0 ]]; then
        log_error "Script failed with error code $exit_code."
        cleanup
    fi
}

# Function to copy the project to a temporary directory
copy_project_to_temp_dir() {
    local REPO_DIR="$1"
    log_info "Copying project to temporary directory: ${TEMP_DIR}"

    local RSYNC_CMD="rsync -dar --links --exclude={${EXCLUDES_LIST}} '${REPO_DIR}/' '${TEMP_DIR}/'"
    #local RSYNC_CMD="rsync -av --exclude={'${EXCLUDES_LIST}'} --exclude='.git/' '${REPO_DIR}/' '${TEMP_DIR}/'"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "Dry run: Would have executed: ${RSYNC_CMD}"
        # Since it's a dry run, we don't actually execute the rsync
    else
        log_debug "Executing: ${RSYNC_CMD}"
        execute_eval_command "${RSYNC_CMD}"
    fi
}

# Function to update the public branch
sync_public_branch() {
    local REPO_DIR="$1"
    local PUBLIC_BRANCH="$2"

    if [ -e "${REPO_DIR}/.gitignore" ]; then
        log_info "Read .gitignore and populate excludes array"
        while read -r line; do
            line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [[ -z "$line" || "$line" =~ ^#.* ]] && continue
            EXCLUDES_ARRAY+=("$line")
        done < "${REPO_DIR}/.gitignore"
    fi

    if [ -e "${REPO_DIR}/.rsync-ignore" ]; then
        log_info "Read .rsync-ignore and populate IGNORE_ARRAY array"
        while read -r line; do
            line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [[ -z "$line" || "$line" =~ ^#.* ]] && continue
            IGNORE_ARRAY+=("$line")
        done < "${REPO_DIR}/.rsync-ignore"
    fi

    log_info "Stashing any local changes on the current branch."
    if ! git -C "${REPO_DIR}" stash push -u -m "Stash before sync to ${PUBLIC_BRANCH}"; then
        log_error "Failed to stash local changes."
    fi

#    git fetch --all
    git fetch github

    log_info "Checking out public branch: ${PUBLIC_BRANCH}"
    if ! git -C "${REPO_DIR}" checkout "${PUBLIC_BRANCH}"; then
        log_error "Failed to checkout branch: ${PUBLIC_BRANCH}"
    fi

    log_info "Pulling latest changes from the public branch."
    local REMOTE_AND_BRANCH
    REMOTE_AND_BRANCH=$(git rev-parse --abbrev-ref "${PUBLIC_BRANCH}@{upstream}") && \
    IFS=/ read -r REMOTE_NAME REMOTE_BRANCH <<< "${REMOTE_AND_BRANCH}" && \

    if [[ -z "${REMOTE_BRANCH}" ]]; then
        log_warn "No upstream branch found for ${PUBLIC_BRANCH}. Skipping pull."
    else
        log_info "Pulling from REMOTE_BRANCH remote: ${REMOTE_NAME}"
        if ! git -C "${REPO_DIR}" pull "${REMOTE_NAME}" "${REMOTE_BRANCH}:${PUBLIC_BRANCH}"; then
            log_warn "Failed to pull from ${REMOTE_NAME}/${REMOTE_BRANCH}:${PUBLIC_BRANCH}. Continuing anyway."
        fi
    fi

    log_info "Syncing temporary directory to public branch."

    if [ "${GIT_REMOVE_CACHED_FILES}" -eq 1 ]; then
      log_info "Removing files cached in git"
      git rm -r --cached .
    fi

    log_info "Copy ${TEMP_DIR} to project dir ${REPO_DIR}"
    # Added --delete and --exclude '.git/'
    local RSYNC_CMD="rsync -dar --links --delete --exclude '.git/' --exclude={${IGNORE_LIST}} '${TEMP_DIR}/' '${REPO_DIR}/'"
#    local RSYNC_CMD="rsync -dar --links --delete --exclude '.git/' '${TEMP_DIR}/' '${REPO_DIR}/'"
#    local RSYNC_CMD="rsync -av --delete --exclude '.git/' '${TEMP_DIR}/' '${REPO_DIR}/'"
#    local RSYNC_CMD="rsync ${RSYNC_UPDATE_OPTS} ${TEMP_DIR}/ ${REPO_DIR}/"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "Dry run: Would have executed: ${RSYNC_CMD}"
    else
        log_debug "Executing: ${RSYNC_CMD}"
        if ! eval "${RSYNC_CMD}"; then
            log_error "rsync failed during sync to public branch."
        fi
    fi

    if [ -n "${PUBLIC_GITIGNORE}" ]; then
      if [ -e "${PUBLIC_GITIGNORE}" ]; then
        log_info "Update public files:"
        cp -p "${PUBLIC_GITIGNORE}" .gitignore
      fi
    fi

    if [ -n "${PUBLIC_GITMODULES}" ]; then
      if [ -e "${PUBLIC_GITMODULES}" ]; then
        echo "Update public submodules:"
        cp -p $PUBLIC_GITMODULES .gitmodules
        git submodule deinit -f . && \
        git submodule update --init --recursive --remote
      fi
    fi

    log_info "Show changes before push:"
    git status

    ## https://stackoverflow.com/questions/5989592/git-cannot-checkout-branch-error-pathspec-did-not-match-any-files-kn
    ## git diff --name-only ${GIT_PUBLIC_BRANCH} ${GIT_DEFAULT_BRANCH} --

    if [ $CONFIRM -eq 0 ]; then
      ## https://www.shellhacks.com/yes-no-bash-script-prompt-confirmation/
      read -p "Are you sure you want to merge the changes above to public branch ${TARGET_BRANCH}? " -n 1 -r
      echo    # (optional) move to a new line
      if [[ ! $REPLY =~ ^[Yy]$ ]]
      then
          exit 1
      fi
    fi

    ## https://stackoverflow.com/questions/5738797/how-can-i-push-a-local-git-branch-to-a-remote-with-a-different-name-easily
    log_info "Add all the files:"
    git_commit_push

#    log_info "Checkout ${GIT_DEFAULT_BRANCH} branch:" && \
#    git checkout ${GIT_DEFAULT_BRANCH}

    log_info "Returning to the original branch and applying stashed changes."
    if ! git -C "${REPO_DIR}" checkout -; then
        log_error "Failed to checkout original branch."
    fi

    if [ -e .gitmodules ]; then
      echo "Resetting ansible submodule for private"
      git submodule deinit -f . && \
      git submodule update --init --recursive --remote && \
      git_commit_push
    fi

    log_info "Returning to the original branch and applying stashed changes."
    if git -C "${REPO_DIR}" stash list | grep -q 'stash'; then
        if ! git -C "${REPO_DIR}" stash pop; then
            log_warn "Failed to apply stashed changes. You may have uncommitted changes. Please handle manually."
        fi
    else
        log_info "No stashed changes to apply."
    fi

    if [ -e "${REPO_DIR}/.rsync-post-sync" ]; then
        log_info "Sourcing .rsync-post-sync"

        # Use the source command (shorthand '.')
        . "${REPO_DIR}/.rsync-post-sync"

        # Check the exit code of the sourced commands
        EXIT_CODE=$?

        if [ $EXIT_CODE -ne 0 ]; then
            # Use stderr for warnings/errors
            log_warn "Warning: Sourced script failed with exit code $EXIT_CODE" >&2
        fi
    fi
}


function usage() {
  echo "Usage: ${SCRIPT_NAME} [options]"
  echo ""
  echo "  Options:"
  echo "       -L [ERROR|WARN|INFO|TRACE|DEBUG] : run with specified log level (default: '${LOGLEVEL_TO_STR[${LOG_LEVEL_IDX}]}')"
  echo "       -v : show script version"
  echo "       -h : help"
  echo "     [TEST_CASES]"
  echo ""
  echo "  Examples:"
	echo "       ${SCRIPT_NAME} "
	echo "       ${SCRIPT_NAME} -L DEBUG"
  echo "       ${SCRIPT_NAME} -v"
	[ -z "$1" ] || exit "$1"
}


function main() {

  trap on_error ERR
  check_required_commands rsync

  while getopts "L:vh" opt; do
      case "${opt}" in
          L) set_log_level "${OPTARG}" ;;
          v) echo "${VERSION}" && exit ;;
          h) usage 1 ;;
          \?) usage 2 ;;
          *) usage ;;
      esac
  done
  shift $((OPTIND-1))

  log_debug "REPO_DIR=${REPO_DIR}"
  log_debug "TEMP_DIR=${TEMP_DIR}"

  search_repo_keywords
  local RETURN_STATUS=$?
  if [[ $RETURN_STATUS -ne 0 ]]; then
    log_error "search_repo_keywords: FAILED"
    exit ${RETURN_STATUS}
  fi

  copy_project_to_temp_dir "${REPO_DIR}"
  sync_public_branch "${REPO_DIR}" "${GIT_PUBLIC_BRANCH}"

  log_info "Sync completed successfully."
  cleanup

  trap - ERR

}

main "$@"
