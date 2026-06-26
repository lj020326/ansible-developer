#!/usr/bin/env bash

## ref: https://github.com/lidarr/Lidarr/issues/515
## ref: https://bbs.archlinux.org/viewtopic.php?pid=1855695#p1855695
# frontend for:            cuetools, shntool, mp3splt
# optional dependencies:    flac, mac, wavpack, ttaenc
# v1.5 Updated with dependency checks and help

SDIR=`pwd`

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

tracknums()
{
    trackno=$(($1 + 1))
    boolval=1
    for (( i=1; i<$1; i++ ))
      do
        lz=""
        if [ $i -lt 10 ]; then
            lz="0"
        fi
        if [[ -f "./split/$lz$i. *.flac" ]] || [[ -f "./split/$lz$i *.flac" ]]; then
            boolval=$boolval
        else
            boolval=0
        fi
    done
    return $boolval
}

checker()
{
    retval=1
    ft="$1"
    cf="$2.cue"
    adjfactor="0.88"
    # Fixed: used grep -E and wc -l for line counts
    tracksincue=$(grep -Ec "TRACK [0-9]{1,3} AUDIO" "./$cf")
    indexincue=$(grep -Ec "INDEX [0-9]{1,3}" "./$cf")
    trackssplitted=$(find ./split -type f -name "*.flac" | wc -l)

    if [ "$tracksincue" -gt "$trackssplitted" ] && [ "$indexincue" -gt "$trackssplitted" ]; then
        retval=0
        printf "\n\nERROR: Track count mismatch!\n"
        printf "Cue Tracks: $tracksincue | Split Files: $trackssplitted\n"
    fi

    if [ "$ft" == "wav" ]; then
        adjfactor="0.6"
    fi
    origsize=$(find ./ -type f -maxdepth 1 -name "*.$ft" -print -exec sh -c "stat -c%s \"{}\"" \; | awk '{ SUM += $1} END { print SUM }')
    origsizeadj=$(echo "$origsize*$adjfactor" | bc)
    sourcefile=$((${origsizeadj%.*} - 1488))

    if [[ "$ft" == "mp3" ]] || [[ "$ft" == "ogg" ]]; then
        totsize=$(find ./split -type f -name "*.$ft" -print -exec sh -c "stat -c%s \"{}\"" \; | awk '{ SUM += $1} END { print SUM }')
    else
        totsize=$(find ./split -type f -name "*.flac" -print -exec sh -c "stat -c%s \"{}\"" \; | awk '{ SUM += $1} END { print SUM }')
    fi

    if [ "$totsize" -gt "$sourcefile" ]; then
        return $retval
    else
        return 0
    fi
}

splitter()
{
    cfn="$2"
    DIR="$1"

    if [ -z "$DIR" ]; then DIR="$SDIR"; fi

    echo "Processing Directory: $DIR"
    cd "$DIR" || return

    # Fixed: wc -l to count files properly
    cuefiles=$(find ./ -maxdepth 1 -type f -name "*.cue" | wc -l)

    # Determine type from the first relevant file found
    TYPE=$(ls -t1 *.flac *.ape *.wav *.wv *.mp3 2>/dev/null | head -n 1)

    case $TYPE in
        *.flac*)
            mkdir -p split
            if [ "$cuefiles" -gt 1 ] && [[ -f "$cfn.flac" ]]; then
                shnsplit -d split -f "$cfn.cue" -o "flac flac -V --best -o %f -" "$cfn.flac" -t "%n. %p - %t"
            else
                shnsplit -d split -f *.cue -o "flac flac -V --best -o %f -" *.flac -t "%n. %p - %t"
            fi
            rm -f split/00.*pregap*
            cuetag "$cfn.cue" split/*.flac

            if [ -z "$(ls -A ./split)" ]; then
                echo "Failure: No files in split directory"
                rmdir split
            elif [[ "$(checker 'flac' "$cfn")" -eq 0 ]]; then
                echo "Failure: Checker validation failed"
            else
                # Clean up and move
                [[ -f "$cfn.flac" ]] && rm "$cfn.flac" || rm *.flac
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
