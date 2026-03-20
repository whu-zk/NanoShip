# 🚀 NanoShip

> **Talk to your server, not the YAML files.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**NanoShip** is an AI-powered deployment agent designed for indie developers and small teams. It eliminates the complexity of DevOps by automatically generating Docker configurations, deploying to your servers, and monitoring your applications—all through a simple, intuitive CLI.

![NanoShip Demo](https://via.placeholder.com/800x400/0d1117/00d4aa?text=NanoShip+Demo+GIF)

## ✨ Features

### 🎯 Semantic Deployment (Zero-Config)
```bash
nanoship deploy . to my-vps --domain myapp.com
```
- **Auto-detects** your project's language and framework
- **Generates** optimized Dockerfile and docker-compose.yml
- **Deploys** via SSH with a single command
- **Configures** reverse proxy (Caddy/Nginx) and SSL automatically

### 🔍 Smart Log Analysis & Self-Healing
- Monitors application health automatically
- Uses AI to analyze crash logs
- Sends actionable fix suggestions via webhook

### 🛡️ Server Security Audit
```bash
nanoship audit my-vps
```
- Scans for security vulnerabilities
- Identifies performance bottlenecks
- Provides hardening recommendations

## 🚀 Quick Start

### Installation

```bash
# Using pip
pip install nanoship

# Or install from source
git clone https://github.com/nanoship/nanoship.git
cd nanoship
pip install -e ".[dev]"
```

### Configuration

Set your LLM API key (for AI-powered features):

```bash
# For DeepSeek (recommended)
export NANOSHIP_LLM_API_KEY="your-deepseek-api-key"
export NANOSHIP_LLM_MODEL="deepseek-chat"

# Or for OpenAI
export NANOSHIP_LLM_API_KEY="your-openai-api-key"
export NANOSHIP_LLM_MODEL="gpt-4"
```

### First Deployment

```bash
# 1. Add your server
nanoship server add my-vps 192.168.1.100 --user root --key ~/.ssh/id_rsa

# 2. Deploy your project
nanoship deploy . to my-vps --domain myapp.com

# 3. Check the logs
nanoship deploy logs my-vps myapp
```

## 📖 Usage Guide

### Server Management

```bash
# Add a server with SSH key authentication
nanoship server add production 203.0.113.1 --key ~/.ssh/id_rsa

# Add a server with password (not recommended)
nanoship server add staging 203.0.113.2 --user ubuntu --password "secret"

# List all servers
nanoship server list

# Test connection
nanoship server test production

# Remove a server
nanoship server remove staging
```

### Deployment

```bash
# Basic deployment
nanoship deploy up . my-vps

# With custom domain and SSL
nanoship deploy up . my-vps --domain api.example.com

# Without SSL (for local testing)
nanoship deploy up . my-vps --no-ssl

# View logs
nanoship deploy logs my-vps my-project

# Follow logs in real-time
nanoship deploy logs my-vps my-project --follow

# Check deployment history
nanoship deploy status
```

### Project Analysis

```bash
# Analyze current project
nanoship analyze

# Generate Docker files
nanoship analyze --generate
```

### Server Audit

```bash
# Run security audit
nanoship audit my-vps
```

### System Check

```bash
# Verify your setup
nanoship doctor
```

## 🏗️ Supported Technologies

### Languages & Frameworks

| Language | Frameworks | Auto-Detection |
|----------|-----------|----------------|
| **Python** | FastAPI, Flask, Django, generic | ✅ |
| **Node.js** | Express, Next.js, React, Vue, NestJS | ✅ |
| **Go** | Any | ✅ |
| **Rust** | Any | ✅ |
| **Static** | HTML/CSS/JS | ✅ |

### Reverse Proxy & SSL

- **Caddy** (preferred) - Automatic HTTPS with Let's Encrypt
- **Nginx** - Traditional reverse proxy with Certbot SSL

## 🏛️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    NanoShip CLI                         │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   Server    │  │   Deploy    │  │     Audit       │ │
│  │   Manager   │  │   Engine    │  │     Engine      │ │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────┘ │
│         │                │                              │
│  ┌──────▼────────────────▼──────┐  ┌─────────────────┐ │
│  │      SSH Manager (Paramiko)  │  │   AI Engine     │ │
│  │                              │  │   (LiteLLM)     │ │
│  └──────────────┬───────────────┘  └─────────────────┘ │
│                 │                                       │
│  ┌──────────────▼───────────────┐  ┌─────────────────┐ │
│  │   Project Analyzer           │  │   Database      │ │
│  │   - Language detection       │  │   (SQLite)      │ │
│  │   - Dockerfile generation    │  └─────────────────┘ │
│  └──────────────────────────────┘                       │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Remote Server  │
                    │  - Docker       │
                    │  - Caddy/Nginx  │
                    └─────────────────┘
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NANOSHIP_LLM_PROVIDER` | LLM provider | `deepseek` |
| `NANOSHIP_LLM_API_KEY` | API key for LLM | - |
| `NANOSHIP_LLM_MODEL` | Model name | `deepseek-chat` |
| `NANOSHIP_SSH_KEY_PATH` | Default SSH key path | `~/.ssh/id_rsa` |
| `NANOSHIP_DB_PATH` | SQLite database path | `~/.nanoship/nanoship.db` |
| `NANOSHIP_WEBHOOK_URL` | Notification webhook URL | - |

### Configuration File

Create `~/.nanoship/config.yaml`:

```yaml
llm:
  provider: deepseek
  api_key: sk-...
  model: deepseek-chat

ssh:
  timeout: 30
  key_path: ~/.ssh/id_rsa

deployment:
  default_path: /opt/nanoship
  auto_ssl: true

notifications:
  webhook_url: https://hooks.slack.com/...
  webhook_type: slack
```

## 🤖 AI-Powered Features

NanoShip uses LLMs (via LiteLLM) to provide intelligent assistance:

### Log Analysis
When your app crashes, NanoShip automatically:
1. Collects the last 50 lines of logs
2. Sends them to the LLM for analysis
3. Identifies the root cause
4. Suggests specific fixes

### Security Auditing
The `audit` command uses AI to:
- Analyze server configuration
- Identify security vulnerabilities
- Provide hardening recommendations
- Generate fix commands

### Dockerfile Optimization
AI suggestions for:
- Multi-stage builds
- Security best practices
- Performance optimizations
- Dependency management

## 📝 Example Workflows

### Deploy a FastAPI App

```bash
# Your project structure:
# my-api/
# ├── main.py
# ├── requirements.txt
# └── .env

# 1. Add your VPS
cd my-api
nanoship server add my-vps 203.0.113.1 --key ~/.ssh/id_rsa

# 2. Deploy
nanoship deploy . to my-vps --domain api.myapp.com

# 3. Done! Your API is live with SSL
```

### Deploy a Next.js App

```bash
cd my-nextjs-app

# NanoShip auto-detects Next.js and generates proper Dockerfile
nanoship deploy . to my-vps --domain www.myapp.com
```

### Monitor and Self-Heal

```bash
# Setup monitoring (add to crontab)
*/5 * * * * nanoship monitor my-vps myapp --notify

# When issues are detected, you'll get:
# - Root cause analysis
# - Suggested fix command
# - One-click rollback option
```

## 🧪 Development

```bash
# Clone the repository
git clone https://github.com/nanoship/nanoship.git
cd nanoship

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black nanoship/
ruff check nanoship/

# Type checking
mypy nanoship/
```

## 🗺️ Roadmap

- [ ] **TUI Dashboard** - Terminal UI with real-time metrics (Textual)
- [ ] **Multi-Server Deployments** - Deploy to multiple servers simultaneously
- [ ] **Database Migrations** - Automated database migration handling
- [ ] **Blue-Green Deployments** - Zero-downtime deployments
- [ ] **Webhook Notifications** - Slack, Discord, DingTalk, Feishu integration
- [ ] **Health Checks** - Automated health monitoring with alerting
- [ ] **Backup & Restore** - Automated backup strategies

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [Nanobot](https://github.com/sjdonado/nanobot) for the cron-based approach
- Built with [Typer](https://typer.tiangolo.com/) for the CLI
- Uses [LiteLLM](https://litellm.ai/) for unified LLM access
- SSH operations powered by [Paramiko](https://www.paramiko.org/)

## 💬 Community

- [GitHub Discussions]()
- [Discord Server]()
- [Twitter/X: @nanoship]()

---

<p align="center">
  Made with ❤️ for indie developers
</p>
