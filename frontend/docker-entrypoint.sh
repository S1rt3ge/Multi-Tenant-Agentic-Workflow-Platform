#!/bin/sh
set -eu

sanitize_url() {
  printf '%s' "$1" | tr -d '\r\n'
}

json_escape() {
  sanitize_url "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

origin_from_url() {
  value=$(sanitize_url "$1")
  case "$value" in
    http://*|https://*|ws://*|wss://*) ;;
    *) return 0 ;;
  esac

  origin=$(printf '%s' "$value" | sed -E 's#^([A-Za-z][A-Za-z0-9+.-]*://[^/?#]+).*$#\1#')
  case "$origin" in
    *"'"*|*";"*|*" "*) return 0 ;;
  esac
  printf ' %s' "$origin"
}

websocket_origin_from_http_url() {
  value=$(sanitize_url "$1")
  case "$value" in
    https://*) scheme="wss://" ;;
    http://*) scheme="ws://" ;;
    *) return 0 ;;
  esac

  host=$(printf '%s' "$value" | sed -E 's#^[A-Za-z][A-Za-z0-9+.-]*://([^/?#]+).*$#\1#')
  case "$host" in
    *"'"*|*";"*|*" "*) return 0 ;;
  esac
  printf ' %s%s' "$scheme" "$host"
}

API_URL=$(sanitize_url "${VITE_API_URL:-}")
WS_URL=$(sanitize_url "${VITE_WS_URL:-}")
CSP_CONNECT_SRC="'self' http://localhost:* ws://localhost:*$(origin_from_url "$API_URL")$(websocket_origin_from_http_url "$API_URL")$(origin_from_url "$WS_URL")"

sed "s#__CSP_CONNECT_SRC__#$CSP_CONNECT_SRC#g" /etc/nginx/conf.d/default.conf > /tmp/default.conf
cat /tmp/default.conf > /etc/nginx/conf.d/default.conf

cat > /usr/share/nginx/html/env.js <<EOF
window.__GRAPHPILOT_CONFIG__ = {
  VITE_API_URL: "$(json_escape "$API_URL")",
  VITE_WS_URL: "$(json_escape "$WS_URL")"
};
EOF

exec nginx -g 'daemon off;'
