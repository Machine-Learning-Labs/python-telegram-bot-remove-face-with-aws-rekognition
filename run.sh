#!/bin/bash

export AWS_DEFAULT_REGION=eu-west-1

log_folder="../bot_logs"
mkdir -p $log_folder

current_date=$(date +%Y-%m-%d)
log_file_bot="$log_folder/bot_$current_date.log"
log_file_scheduler="$log_folder/scheduler_$current_date.log"

# Run scripts
nohup python3 src/bot.py > "$log_file_bot" 2>&1 &
nohup python3 src/scheduler.py > "$log_file_scheduler" 2>&1 &

echo "Scripts bot.py and scheduler.py started. Logs are being saved in $log_folder"

