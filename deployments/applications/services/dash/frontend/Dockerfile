# Small, dependency-free static-file server (Decision 1: the frontend
# task serves files only -- no Python, no cli, no Vault/Nomad credential,
# no proxy logic). nginx:alpine has no repo precedent to match; it is the
# smallest widely-used static server, chosen for that reason alone.
FROM nginx:alpine

COPY index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8000
