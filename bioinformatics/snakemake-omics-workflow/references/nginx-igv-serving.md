# Nginx Serving for IGV Track HTML / Result Files

## Context

The Omics workflow generates `igv_track.html` files that reference local paths (FASTA, GTF, BigWig, etc.). These HTML files must be served via HTTP for browser access — they load `igv.min.js` via `<script src>` and fetch reference/data files via relative/absolute URLs mapped through nginx.

## Nginx Config Template

Server: `10.135.4.3` (internal IP). Source-installed at `/usr/local/nginx/`.

Config file: `~/.nginx.conf` (user-owned, no sudo needed).

```
error_log /home/luosg/nginx_logs/error.log;
pid /home/luosg/nginx_logs/nginx.pid;

events {
    worker_connections 1024;
}

http {
    sendfile        on;
    tcp_nopush      on;
    chunked_transfer_encoding on;

    server {
        listen 8080;
        access_log /home/luosg/nginx_logs/access.log;
        server_name _;

        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        allow 127.0.0.1;
        deny all;

        location /data/ {
            alias /rna_seq_1/luoshg/;
            autoindex off;
            expires 7d;
        }

        location /ref/ {
            alias /disk5/luosg/Reference/;
            autoindex off;
            expires 7d;
        }

        location / { return 403; }
    }
}
```

## URL Mapping

The `igv_config.publicPathMap` in raw.json defines the same mappings:

| nginx location | Filesystem path | Purpose |
|---|---|---|
| `/data/` | `/rna_seq_1/luoshg/` | Workflow outputs (BigWig, peaks, tracks) |
| `/ref/` | `/disk5/luosg/Reference/` | Reference files (FASTA, GTF, igv.min.js) |

**Example URL for igv_track.html:**
```
http://10.135.4.3:8080/data/Chipseq_20260709/output/PeakCalling/tracks/igv_track.html
```

## Startup / Shutdown

```bash
# Start
mkdir -p /home/luosg/nginx_logs
/usr/local/nginx/sbin/nginx -c /home/luosg/.nginx.conf -p /home/luosg/nginx_logs/

# Stop
/usr/local/nginx/sbin/nginx -c /home/luosg/.nginx.conf -p /home/luosg/nginx_logs/ -s stop

# Reload config
/usr/local/nginx/sbin/nginx -c /home/luosg/.nginx.conf -p /home/luosg/nginx_logs/ -s reload
```

## Pitfalls

1. **Port 80 requires root** — use 8080 (or other high port) since user has no sudo.
2. **Default log/pid paths are unwritable** — `/usr/local/nginx/logs/` requires root. Must set `error_log`, `pid`, `access_log` to user-writable paths.
3. **`-p` prefix flag needed** — nginx opens its compiled-in pid path before reading the config. The `-p` flag redirects this to a writable directory.
4. **Nginx not running by default** — must start manually or add to cron. Check with `ps aux | grep nginx`.
