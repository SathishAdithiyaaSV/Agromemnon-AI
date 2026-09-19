# Leaf disease classifier — training and deployment

The tomato leaf disease model behind the `plant_doctor` agent. Everything here is
run **once, by hand, offline**; the deployed agent only calls the finished endpoint.

## What gets built

A MobileNetV3-Small fine-tuned on the ten PlantVillage tomato classes, served from a
SageMaker **serverless** inference endpoint named `agromemnon-leaf-disease`.

Scope is deliberately one crop. PlantVillage's other 28 classes need a longer job and
a bigger instance, and tomato covers the diseases smallholders photograph most. The
classifier cannot say "this is not a tomato" — it forces every image into one of its
ten classes — so `plant_doctor` pairs it with Claude's own reading of the photo,
which is what catches an out-of-scope crop. See `agents/plant_doctor.py`.

## Prerequisites

```bash
pip install -r requirements-dev.txt        # SageMaker SDK, not an agent dependency
aws configure                               # credentials for account 222758971755
```

You also need a SageMaker execution role with S3 access. Pass it as `--role`, or run
from an environment where `sagemaker.get_execution_role()` resolves.

> **Note:** `~/.aws/config` currently has `region = use-east-1`, which is a typo and
> makes every AWS call fail to resolve an endpoint. Fix it to `us-east-1`, or pass
> `--region us-east-1` to each script below.

## Steps

### 1. Prepare the dataset

```bash
python prepare_data.py --download --bucket <your-bucket>
```

Clones PlantVillage (~2 GB, shallow), keeps up to 400 images per tomato class, splits
80/20 per class, and uploads to `s3://<bucket>/plantvillage/tomato/{train,val}/`.
Writes `dataset-manifest.json`.

Already have the dataset locally? Skip the clone:

```bash
python prepare_data.py --source ~/PlantVillage-Dataset/raw/color --bucket <your-bucket>
```

Raise `--per-class` for a better model and a longer job; 400 is tuned for a demo.

### 2. Train

```bash
python launch_training.py          # reads dataset-manifest.json
```

Roughly 5 minutes on the default `ml.g4dn.xlarge`. No GPU quota? Use
`--instance-type ml.c5.2xlarge` — about 20 minutes, same accuracy.

Expect validation accuracy in the mid-to-high 90s. PlantVillage is clean studio
imagery, so **treat that number as an upper bound, not field accuracy** — a phone
photo taken at dusk against a mixed background is a harder problem than the
validation split. The per-class table printed at the end matters more than the
headline: a class sitting far below the rest is the one that will embarrass you.

Writes `training-output.json` with the model artefact URI.

### 3. Deploy

```bash
python deploy_endpoint.py          # reads training-output.json
```

Creates the serverless endpoint (3 GB, max concurrency 5). Serverless because leaf
photos arrive in bursts: a provisioned `ml.m5.large` bills ~$60/month to sit idle,
where serverless bills per request. The tradeoff is a few seconds of cold start on
the first photo after a quiet period.

### 4. Point the agent at it

`agentcore/agentcore.json` already sets `LEAF_DISEASE_ENDPOINT=agromemnon-leaf-disease`
and `LEAF_DISEASE_REGION=us-east-1`. Change them only if you deployed under another
name, then:

```bash
agentcore deploy
```

## Verifying the endpoint

```bash
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name agromemnon-leaf-disease \
  --content-type image/jpeg \
  --body fileb://some-leaf.jpg \
  --region us-east-1 \
  /dev/stdout
```

Returns `{"predictions": [{"label": "...", "confidence": 0.93}, ...]}`.

## Retraining or widening the crop set

`TOMATO_CLASSES` in `prepare_data.py` is the scope. Add classes there, then add a
matching entry to `TREATMENTS` in `tools/leaf_disease_treatments.py` — the keys must
match the PlantVillage directory names **exactly**, because the endpoint emits those
strings verbatim and the tool looks the treatment up by them. A class with no
treatment record still classifies, but the agent will only identify it and send the
farmer to their KVK for the cure.

## Cost

| Item | Rough cost |
|---|---|
| Training job (`ml.g4dn.xlarge`, ~5 min) | under $0.10 per run |
| S3 storage for the subset (~500 MB) | cents per month |
| Serverless endpoint, idle | $0 |
| Serverless endpoint, per inference | fractions of a cent |

Delete the endpoint when you are done demoing:

```bash
aws sagemaker delete-endpoint --endpoint-name agromemnon-leaf-disease --region us-east-1
```
