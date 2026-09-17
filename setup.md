# Setup Guide

This guide walks through setting up and running the Agromemnon AgentCore project after cloning the repo.

## Prerequisites

Install these before doing anything else:

| Tool | Version | Install |
| --- | --- | --- |
| Node.js | 20.x or later | [nodejs.org](https://nodejs.org/) or a version manager like `nvm` |
| Python | 3.10+ (project targets 3.14) | [python.org](https://www.python.org/downloads/) or `pyenv` |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` ([docs](https://docs.astral.sh/uv/getting-started/installation/)) |
| AWS CLI | v2 | [AWS CLI install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| Docker | latest | Only needed if any agent uses a `Container` build type (this project currently uses `CodeZip`, so this is optional) |

## 1. Install the AgentCore CLI

The AgentCore CLI is distributed as an npm package:

```bash
npm install -g @aws/agentcore
```

Verify the install:

```bash
agentcore --help
```

## 2. Configure AWS credentials

The CLI deploys via CDK/CloudFormation to your AWS account, so credentials must be available in the environment:

```bash
aws configure
```

or export `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_REGION` (and `AWS_SESSION_TOKEN` if using temporary credentials).

## 3. Clone and locate the project

The AgentCore project root is `backend/Agromemnon/` in this repo (it contains `AGENTS.md`, `agentcore/`, and `app/`):

```bash
git clone <repo-url>
cd Agromemnon-AI/backend/Agromemnon
```

All `agentcore` CLI commands below must be run from this directory.

## 4. Install agent dependencies

The generated agent lives at `app/Agromemnon/` and uses `uv` for its virtual environment. From the project root:

```bash
cd app/Agromemnon
uv sync
cd ../..
```

This creates `app/Agromemnon/.venv` with all dependencies from `pyproject.toml`/`uv.lock` (Strands SDK, `bedrock-agentcore`, MCP, etc.).

To work inside that environment directly:

```bash
source app/Agromemnon/.venv/bin/activate   # macOS/Linux
```

## 5. Install CDK dependencies

The infrastructure lives under `agentcore/cdk/` and uses `@aws/agentcore-cdk` L3 constructs:

```bash
cd agentcore/cdk
npm install
cd ../..
```

## 6. Configure secrets / local env

Local secrets (API keys, etc.) go in `agentcore/.env.local` (gitignored, currently empty). The agent's model provider (`app/Agromemnon/model/load.py`) uses Amazon Bedrock via IAM credentials by default, so no API key is required there — but add any provider keys here if you change the model.

Set `LOCAL_DEV=1` in `agentcore/.env.local` to make the agent read from this file instead of AgentCore Identity when running locally.

## 7. Validate the configuration

```bash
agentcore validate
```

This checks `agentcore/agentcore.json` and `agentcore/aws-targets.json` against the schemas in `agentcore/.llm-context/`.

## 8. Run the agent locally

```bash
agentcore dev
```

This starts a local server on `0.0.0.0:8080`. In a separate terminal:

```bash
agentcore invoke --dev "What can you do"
```

## 9. Deploy to AWS

Once credentials and `agentcore/aws-targets.json` are configured (deployment target account/region), deploy with:

```bash
agentcore deploy
```

Then check status or invoke the deployed agent:

```bash
agentcore status
agentcore invoke "What can you do"
```

## Reference

- [AgentCore CLI](https://github.com/aws/agentcore-cli)
- [AgentCore CDK Constructs](https://github.com/aws/agentcore-l3-cdk-constructs)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
- Project-specific config schema and resource model: see [AGENTS.md](AGENTS.md)
