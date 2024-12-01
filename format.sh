#!/usr/bin/sh

autoflake \
    --remove-all-unused-imports \
    --remove-unused-variables \
    --ignore-init-module-imports \
    --in-place \
    --recursive \
    model_resolver
black model_resolver
