#!/bin/sh
# Add Authorization on the /api proxy. The value is not written under the
# document root, so it is not a script any site can load.
set -eu
token=$(printf '%s' "${STUDIO_API_TOKEN:-}" | tr -d '\r\n')
if printf '%s' "$token" | grep -q '[$"\\ #;{}`]'; then
  echo "studio-web: STUDIO_API_TOKEN contains a character nginx cannot embed. Choose another secret." >&2
  exit 1
fi
mkdir -p /etc/nginx/snippets
if [ -n "$token" ]; then
  printf 'proxy_set_header Authorization "Bearer %s";\n' "$token" > /etc/nginx/snippets/studio-auth.conf
else
  printf 'proxy_set_header Authorization $http_authorization;\n' > /etc/nginx/snippets/studio-auth.conf
fi
if chown root:nginx /etc/nginx/snippets/studio-auth.conf 2>/dev/null; then
  chmod 640 /etc/nginx/snippets/studio-auth.conf
else
  chmod 644 /etc/nginx/snippets/studio-auth.conf
fi
exec /docker-entrypoint.sh nginx -g 'daemon off;'
