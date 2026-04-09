#!/bin/bash

# Default values
API_URL="http://127.0.0.1:5000/batch/api/run-by-name"
BATCH_NAME=""
AS_OF_DATE=""

usage() {
    echo "Usage: $0 -n \"<batch_name>\" [-d <YYYY-MM-DD>] [-u <url>]"
    echo "Example: $0 -n 'EOM Processing' -d '2026-03-31'"
    exit 1
}

while getopts "n:d:u:h" opt; do
    case $opt in
        n) BATCH_NAME="$OPTARG" ;;
        d) AS_OF_DATE="$OPTARG" ;;
        u) API_URL="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

if [ -z "$BATCH_NAME" ]; then
    echo "Error: Batch name is required."
    usage
fi

# Build JSON payload
PAYLOAD=$(cat <<EOF
{
  "name": "$BATCH_NAME",
  "as_of_date": "$AS_OF_DATE",
  "run_by": "api_shell_script"
}
EOF
)

# Call REST API
echo "Calling REST API to run batch: $BATCH_NAME"
curl -s -X POST -H "Content-Type: application/json" -d "$PAYLOAD" "$API_URL"
echo ""
