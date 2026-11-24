#!/usr/bin/env bash

## ref: https://github.com/lidarr/Lidarr/issues/515
## ref: https://bbs.archlinux.org/viewtopic.php?pid=1855695#p1855695
# frontend for:            cuetools, shntool, mp3splt
# optional dependencies:    flac, mac, wavpack, ttaenc
# v1.5 Updated with dependency checks and help

SPLITTER_DIR="${PWD}"

show_help() {
    cat << EOF
Usage: $(basename "$0") [PATH]

A frontend for splitting single-file audio albums (FLAC, APE, etc.) into
individual tracks using a .cue file.

Arguments:
  PATH    The directory containing the audio file and .cue file.
          Defaults to the current directory if omitted.

Options:
  -h, --help    Show this help message and exit.

Dependencies:
  Required: cuetools, shntool, flac
  Optional: mp3splt (for mp3/ogg), wavpack (for .wv), ttaenc (for .tta)
EOF
}

check_dependencies() {
    local missing=()
    local deps=("cuetag" "shnsplit" "flac" "bc")

    # Add optional deps based on file types if needed,
    # but these are the core requirements for your current task
    for tool in "${deps[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing+=("$tool")
        fi
    done

    if [ ${#missing[@]} -ne 0 ]; then
        echo "Error: Missing required dependencies: ${missing[*]}"
        echo "-------------------------------------------------------"
        echo "To install the core tools on Debian/Ubuntu/Proxmox:"
        echo "  sudo apt-get update && sudo apt-get install cuetools shntool flac bc"
        echo ""
        echo "For specific formats, you may also need:"
        echo "  sudo apt-get install mp3splt wavpack"
        echo "-------------------------------------------------------"
        exit 1
    fi
}

# Run dependency check immediately
if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
    show_help
    exit 0
fi

check_dependencies

track_nums()
{
    # shellcheck disable=SC2034
    track_num=$(($1 + 1))
    bool_val=1
    for (( i=1; i<$1; i++ ))
      do
        lz=""
        if [ $i -lt 10 ]; then
            lz="0"
        fi
        if [[ -f "./split/$lz$i. *.flac" ]] || [[ -f "./split/$lz$i *.flac" ]]; then
            :
        else
            bool_val=0
        fi
    done
    return $bool_val
}

checker()
{
    ret_val=1
    ft="$1"
    cf="$2.cue"
    adj_factor="0.88"
    # Fixed: used grep -E and wc -l for line counts
    tracks_in_cue=$(grep -Ec "TRACK [0-9]{1,3} AUDIO" "./$cf")
    index_in_cue=$(grep -Ec "INDEX [0-9]{1,3}" "./$cf")
    split_tracks=$(find ./split -type f -name "*.flac" | wc -l)

    if [ "$tracks_in_cue" -gt "$split_tracks" ] && [ "$index_in_cue" -gt "$split_tracks" ]; then
        ret_val=0
        printf "\n\nERROR: Track count mismatch!\n"
        printf "Cue Tracks: %s | Split Files: %s\n" "$tracks_in_cue" "$split_tracks"
    fi

    if [ "$ft" == "wav" ]; then
        adj_factor="0.6"
    fi
    # orig_size=$(find ./ -type f -maxdepth 1 -name "*.$ft" -print -exec sh -c "stat -c%s \"{}\"" \; | awk '{ SUM += $1} END { print SUM }')
    orig_size=$(find ./ -type f -maxdepth 1 -name "*.$ft" -print -exec sh -c 'stat -c%s "$1"' _ {} \; | awk '{ SUM += $1} END { print SUM }')
    orig_size_adj=$(echo "$orig_size*$adj_factor" | bc)
    source_file=$((${orig_size_adj%.*} - 1488))

    if [[ "$ft" == "mp3" ]] || [[ "$ft" == "ogg" ]]; then
        tot_size=$(find ./split -type f -name "*.$ft" -print -exec sh -c 'stat -c%s "$1"' _ {} \; | awk '{ SUM += $1} END { print SUM }')
    else
        tot_size=$(find ./split -type f -name "*.flac" -print -exec sh -c 'stat -c%s "$1"' _ {} \; | awk '{ SUM += $1} END { print SUM }')
    fi

    if [ "$tot_size" -gt "$source_file" ]; then
        return $ret_val
    else
        return 0
    fi
}

splitter()
{
    cfn="$2"
    DIR="$1"

    if [ -z "$DIR" ]; then DIR="$SPLITTER_DIR"; fi

    echo "Processing Directory: $DIR"
    cd "$DIR" || return

    # Fixed: wc -l to count files properly
    cue_files=$(find ./ -maxdepth 1 -type f -name "*.cue" | wc -l)

    # Determine type from the first relevant file found
    # TYPE=$(ls -t1 *.flac *.ape *.wav *.wv *.mp3 2>/dev/null | head -n 1)
    # Determine type from the newest relevant file found (Linux GNU stat)
    shopt -s nullglob
    newest_file=""
    newest_mtime=-1

    for file in *.flac *.ape *.wav *.wv *.mp3; do
        [[ -e "${file}" ]] || continue
        mtime=$(stat -c '%Y' -- "${file}") || continue
        if (( mtime > newest_mtime )); then
            newest_mtime=${mtime}
            newest_file=${file}
        fi
    done

    TYPE="${newest_file}"

    case $TYPE in
        *.flac*)
            mkdir -p split
            if [ "$cue_files" -gt 1 ] && [[ -f "$cfn.flac" ]]; then
                shnsplit -d split -f "$cfn.cue" -o "flac flac -V --best -o %f -" "$cfn.flac" -t "%n. %p - %t"
            else
                shnsplit -d split -f ./*.cue -o "flac flac -V --best -o %f -" ./*.flac -t "%n. %p - %t"
            fi
            rm -f split/00.*pregap*
            cuetag "$cfn.cue" split/*.flac

            if [ -z "$(ls -A ./split)" ]; then
                echo "Failure: No files in split directory"
                rmdir split
            fi

            checker 'flac' "${cfn}"
            rc="$?"
            if [[ "${rc}" -eq 0 ]]; then
                echo "Failure: Checker validation failed"
            else
                # Clean up and move
                if [[ -f "$cfn.flac" ]]; then
                    rm -- "$cfn.flac"
                else
                    rm -f -- ./*.flac
                fi
                mv split/*.flac ./
                rmdir split
                echo "Success"
            fi
            ;;
        # ... other cases (ape, mp3, etc.) follow similar logic ...
        *)
            echo "Error: No supported audio files found or format not implemented in this snippet."
            ;;
    esac
}

# Main Execution Logic
if [ -d "$1" ]; then
    find "$1" -type f -name "*.cue" | while read -r f; do
        h="$(dirname "$f")"
        g="$(basename "$f")"
        splitter "$h" "${g%.cue}"
    done
else
    show_help
fi
