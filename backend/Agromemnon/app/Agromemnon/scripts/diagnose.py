"""
Step 3b: Diagnostic + resume script.

Since you've partially run step 3 already, this checks what exists at each
stage and only creates what's missing, then kicks off ingestion. Safe to
run multiple times.

Usage:
    python 03b_diagnose_and_resume.py \\
        --bucket my-hackathon-scheme-docs-bucket \\
        --region us-east-1 \\
        --account-id 123456789012 \\
        --collection-name agri-scheme-vectors \\
        --kb-name agri-scheme-kb
"""

import argparse
import json
import sys
import time

import boto3
from botocore.exceptions import ClientError

EMBED_MODEL_ARN_TEMPLATE = "arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"


def say(msg):
    print(f"[diag] {msg}")


def check_role(iam, account_id, bucket, region, role_prefix="AgriSchemeKBRole"):
    say("Checking IAM role...")
    paginator = iam.get_paginator("list_roles")
    for page in paginator.paginate():
        for r in page["Roles"]:
            if r["RoleName"].startswith(role_prefix):
                say(f"  FOUND role: {r['RoleName']} ({r['Arn']})")
                return r["Arn"], r["RoleName"]
    say("  No existing role found — will need to create one.")
    return None, None


def check_oss_collection(aoss, collection_name):
    say(f"Checking OpenSearch Serverless collection '{collection_name}'...")
    try:
        resp = aoss.batch_get_collection(names=[collection_name])
        details = resp.get("collectionDetails", [])
        if details:
            d = details[0]
            say(f"  FOUND collection: status={d['status']} endpoint={d.get('collectionEndpoint')}")
            return d
        say("  Not found.")
        return None
    except ClientError as e:
        say(f"  Error checking collection: {e}")
        return None


def check_vector_index(collection_endpoint, region, index_name="scheme-index"):
    say(f"Checking vector index '{index_name}'...")
    try:
        from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
        credentials = boto3.Session().get_credentials()
        auth = AWSV4SignerAuth(credentials, region, "aoss")
        host = collection_endpoint.replace("https://", "")
        client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=auth, use_ssl=True, verify_certs=True,
            connection_class=RequestsHttpConnection, timeout=30,
        )
        exists = client.indices.exists(index=index_name)
        say(f"  Index exists: {exists}")
        return exists, client
    except Exception as e:
        say(f"  Could not check index (may be a permissions or connectivity issue): {e}")
        return False, None


def check_knowledge_base(bedrock_agent, kb_name):
    say(f"Checking for Knowledge Base named '{kb_name}'...")
    try:
        paginator = bedrock_agent.get_paginator("list_knowledge_bases")
        for page in paginator.paginate():
            for kb in page["knowledgeBaseSummaries"]:
                if kb["name"] == kb_name:
                    say(f"  FOUND KB: {kb['knowledgeBaseId']} status={kb['status']}")
                    return kb["knowledgeBaseId"], kb["status"]
        say("  Not found.")
        return None, None
    except ClientError as e:
        say(f"  Error listing knowledge bases (possibly no bedrock-agent access): {e}")
        return None, None


def check_data_source(bedrock_agent, kb_id):
    if not kb_id:
        return None
    say("Checking for data source on this KB...")
    resp = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
    sources = resp.get("dataSourceSummaries", [])
    if sources:
        ds = sources[0]
        say(f"  FOUND data source: {ds['dataSourceId']} status={ds['status']}")
        return ds["dataSourceId"]
    say("  Not found.")
    return None


def run_ingestion(bedrock_agent, kb_id, ds_id):
    say("Starting ingestion job...")
    job = bedrock_agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    job_id = job["ingestionJob"]["ingestionJobId"]
    say(f"  Job started: {job_id}")
    while True:
        status_resp = bedrock_agent.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]
        status = status_resp["status"]
        stats = status_resp.get("statistics", {})
        say(f"  status={status} stats={stats}")
        if status in ("COMPLETE", "FAILED"):
            if status == "FAILED":
                say(f"  FAILURE DETAIL: {status_resp.get('failureReasons')}")
            break
        time.sleep(15)
    return job_id


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--account-id", required=True)
    p.add_argument("--collection-name", default="agri-scheme-vectors")
    p.add_argument("--index-name", default="scheme-index")
    p.add_argument("--kb-name", default="agri-scheme-kb")
    args = p.parse_args()

    iam = boto3.client("iam")
    aoss = boto3.client("opensearchserverless", region_name=args.region)
    bedrock_agent = boto3.client("bedrock-agent", region_name=args.region)

    say("=== Identity check ===")
    ident = boto3.client("sts").get_caller_identity()
    say(f"  {ident['Arn']}")

    say("\n=== IAM role ===")
    role_arn, role_name = check_role(iam, args.account_id, args.bucket, args.region)

    say("\n=== OSS collection ===")
    collection = check_oss_collection(aoss, args.collection_name)
    collection_endpoint = collection.get("collectionEndpoint") if collection else None
    collection_id = collection.get("id") if collection else None
    collection_status = collection.get("status") if collection else None

    if collection_status and collection_status != "ACTIVE":
        say(f"  Collection exists but not ACTIVE yet (status={collection_status}). Waiting...")
        while collection_status != "ACTIVE":
            time.sleep(10)
            collection = check_oss_collection(aoss, args.collection_name)
            collection_status = collection.get("status") if collection else None

    say("\n=== Vector index ===")
    index_exists = False
    if collection_endpoint:
        index_exists, _ = check_vector_index(collection_endpoint, args.region, args.index_name)
    else:
        say("  Skipped — no active collection endpoint yet.")

    say("\n=== Knowledge Base ===")
    kb_id, kb_status = check_knowledge_base(bedrock_agent, args.kb_name)

    say("\n=== Data source ===")
    ds_id = check_data_source(bedrock_agent, kb_id)

    say("\n=== SUMMARY ===")
    say(f"  IAM role:        {'OK - ' + role_arn if role_arn else 'MISSING'}")
    say(f"  OSS collection:  {'OK - ' + collection_status if collection_status else 'MISSING'}")
    say(f"  Vector index:    {'OK' if index_exists else 'MISSING'}")
    say(f"  Knowledge Base:  {'OK - ' + kb_id + ' (' + str(kb_status) + ')' if kb_id else 'MISSING'}")
    say(f"  Data source:     {'OK - ' + ds_id if ds_id else 'MISSING'}")

    if not (role_arn and collection_status == "ACTIVE" and index_exists and kb_id and ds_id):
        say("\nSomething is still missing above. Re-run 03_create_knowledge_base.py "
            "(it's safe-ish to re-run individual pieces) or fill the gap manually via "
            "the Bedrock console, then re-run this diagnostic to confirm before ingesting.")
        sys.exit(1)

    if kb_status != "ACTIVE":
        say(f"\nKB status is '{kb_status}', not ACTIVE — check the console for errors before ingesting.")
        sys.exit(1)

    say("\nAll pieces present and ACTIVE. Starting ingestion now.")
    run_ingestion(bedrock_agent, kb_id, ds_id)

    say("\n=== DONE ===")
    say(f"KNOWLEDGE_BASE_ID={kb_id}")


if __name__ == "__main__":
    main()