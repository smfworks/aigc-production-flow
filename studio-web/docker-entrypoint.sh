#!/bin/sh
# Inject the configured API token into the SPA at container start.
# The file is not baked into the image. Host ports stay on 127.0.0.1.
set -eu
html=/usr/share/nginx/html
token=$(printf '%s' "${STUDIO_API_TOKEN:-}" | tr -d '\r\n')
escaped=$(printf '%s' "$token" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/</\\u003c/g')
printf 'window.__STUDIO_TOKEN__="%s";\n' "$escaped" > "$html/studio-token.js"
chmod 644 "$html/studio-token.js"
exec /docker-entrypoint.sh nginx -g 'daemon off;'
