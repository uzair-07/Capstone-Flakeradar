# Deploying FlakeRadar to a server

One small Linux server (2 vCPU, 4 GB RAM is plenty) runs the whole stack with Docker Compose.
Caddy gets an HTTPS certificate automatically. These steps use Hetzner Cloud as an example;
any Ubuntu 24.04 server with a public IP works the same way.

## 1. Create the server

1. Create a project in Hetzner Cloud and add your SSH public key.
2. Create a server: Ubuntu 24.04, type CX22 (or similar), location Falkenstein or Nuremberg.
3. Note its public IPv4 address.
4. Optional: point a domain name at the IP with an `A` record. Without a domain, use
   `<ip>.sslip.io` (for example `203.0.113.7.sslip.io`), which resolves to your IP.

## 2. Install Docker and get the code (on the server)

```bash
ssh root@<ip>
curl -fsSL https://get.docker.com | sh
adduser --disabled-password --gecos "" deploy && usermod -aG docker deploy
su - deploy
git clone https://github.com/uzair-07/Capstone-Flakeradar.git flakeradar
cd flakeradar
```

## 3. Configure

Create `~/flakeradar/.env`:

```bash
SITE_ADDRESS=203.0.113.7.sslip.io          # your domain, without https://
FLAKERADAR_SECRET_KEY=<run: openssl rand -hex 32>
POSTGRES_PASSWORD=<run: openssl rand -hex 16>
FLAKERADAR_ALLOW_REGISTRATION=true         # set to false after creating your account
```

## 4. Start

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Open `https://<SITE_ADDRESS>`, register your account, then set
`FLAKERADAR_ALLOW_REGISTRATION=false` in `.env` and run the same command again.

Only ports 80 and 443 are open to the internet; PostgreSQL and Redis stay on the internal
Docker network.

## 5. Automatic deployment from GitHub

1. On the server, as `deploy`: create a key pair with `ssh-keygen -t ed25519 -f ~/.ssh/gh_deploy -N ""`
   and add the public key: `cat ~/.ssh/gh_deploy.pub >> ~/.ssh/authorized_keys`.
2. In GitHub, **Settings → Secrets and variables → Actions**:
   - variable `DEPLOY_HOST` = the server IP, variable `SITE_URL` = `https://<SITE_ADDRESS>`
   - secret `DEPLOY_USER` = `deploy`, secret `DEPLOY_SSH_KEY` = contents of `~/.ssh/gh_deploy`
3. From then on, every push to `main` that passes CI is deployed by `.github/workflows/deploy.yml`.

## 6. Daily demo data

Create a project `demo` in the web app and a token for it. In GitHub, add variable
`FLAKERADAR_URL` = `https://<SITE_ADDRESS>` and secret `FLAKERADAR_TOKEN` = the token.
`.github/workflows/demo.yml` then uploads the demo suite's results every morning.

## Backups

```bash
docker compose exec -T db pg_dump -U flakeradar flakeradar | gzip > backup-$(date +%F).sql.gz
```
