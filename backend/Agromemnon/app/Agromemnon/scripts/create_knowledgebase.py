"""
Step 3: Provision the Bedrock Knowledge Base.

This creates, in order:
  1. An IAM role Bedrock can assume to read S3 + write to the vector store
  2. An OpenSearch Serverless "vector search" collection (encryption, network,
     and data access policies included)
  3. A vector index in that collection
  4. The Bedrock Knowledge Base itself (embeddings model = Titan Embed Text v2)
  5. An S3 data source pointed at your bucket
  6. Starts an ingestion job (this is what actually embeds + indexes everything)

NOTE: this is the fiddliest part of the whole pipeline. If you're short on
time, it is often faster to do steps 2-4 via the Bedrock console UI
("Create Knowledge Base" wizard, choose "Quick create a new vector store")
and only script step 5/6 (data source + ingestion) here. The console wizard
handles all the OpenSearch Serverless policy plumbing for you.

If you do run this script, expect it to take a few minutes (OpenSearch
Serverless collections take 1-3 min to become ACTIVE).

Usage:
    python 03_create_knowledge_base.py \\
        --bucket my-hackathon-scheme-docs-bucket \\
        --region ap-south-1 \\
        --account-id 123456789012
"""

import argparse
import json
import time
import uuid

import boto3

EMBED_MODEL_ARN_TEMPLATE = "arn:aws:bedrock:{region}::foundation-model/amazon.titan-embed-text-v2:0"


def create_iam_role(iam, account_id, bucket, region):
    role_name = f"AgriSchemeKBRole-{uuid.uuid4().hex[:8]}"
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock.amazonaws.com"},
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": account_id},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{region}:{account_id}:knowledge-base/*"},
            },
        }],
    }
    role = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
    )
    role_arn = role["Role"]["Arn"]

    inline_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:ListBucket"],
                "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel"],
                "Resource": [EMBED_MODEL_ARN_TEMPLATE.format(region=region)],
            },
            {
                "Effect": "Allow",
                "Action": ["aoss:APIAccessAll"],
                "Resource": "*",
            },
        ],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="AgriSchemeKBPolicy",
        PolicyDocument=json.dumps(inline_policy),
    )
    print(f"Created IAM role {role_arn}")
    print("Waiting 15s for IAM eventual consistency...")
    time.sleep(15)
    return role_arn, role_name


def create_oss_collection(aoss, account_id, role_arn, region, collection_name):
    # Encryption policy
    aoss.create_security_policy(
        name=f"{collection_name}-enc",
        type="encryption",
        policy=json.dumps({
            "Rules": [{"ResourceType": "collection", "Resource": [f"collection/{collection_name}"]}],
            "AWSOwnedKey": True,
        }),
    )
    # Network policy (public for hackathon simplicity)
    aoss.create_security_policy(
        name=f"{collection_name}-net",
        type="network",
        policy=json.dumps([{
            "Rules": [
                {"ResourceType": "collection", "Resource": [f"collection/{collection_name}"]},
                {"ResourceType": "dashboard", "Resource": [f"collection/{collection_name}"]},
            ],
            "AllowFromPublic": True,
        }]),
    )
    # Data access policy — let the KB role and you read/write
    caller_identity_arn = boto3.client("sts").get_caller_identity()["Arn"]
    aoss.create_access_policy(
        name=f"{collection_name}-access",
        type="data",
        policy=json.dumps([{
            "Rules": [
                {
                    "ResourceType": "collection",
                    "Resource": [f"collection/{collection_name}"],
                    "Permission": ["aoss:*"],
                },
                {
                    "ResourceType": "index",
                    "Resource": [f"index/{collection_name}/*"],
                    "Permission": ["aoss:*"],
                },
            ],
            "Principal": [role_arn, caller_identity_arn],
        }]),
    )

    collection = aoss.create_collection(name=collection_name, type="VECTORSEARCH")
    collection_id = collection["createCollectionDetail"]["id"]

    print("Waiting for OpenSearch Serverless collection to become ACTIVE...")
    while True:
        status = aoss.batch_get_collection(ids=[collection_id])["collectionDetails"][0]["status"]
        if status == "ACTIVE":
            break
        time.sleep(10)
    collection_endpoint = aoss.batch_get_collection(ids=[collection_id])["collectionDetails"][0]["collectionEndpoint"]
    print(f"Collection ACTIVE: {collection_endpoint}")
    return collection_id, collection_endpoint


def create_vector_index(collection_endpoint, region, index_name="scheme-index"):
    # Requires opensearch-py: pip install opensearch-py requests-aws4auth
    from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, region, "aoss")
    host = collection_endpoint.replace("https://", "")

    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
    )

    body = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": 1024,  # Titan Embed Text v2 default output dim
                    "method": {"name": "hnsw", "engine": "faiss", "space_type": "l2"},
                },
                "text": {"type": "text"},
                "metadata": {"type": "text"},
            }
        },
    }
    client.indices.create(index=index_name, body=body)
    print(f"Created vector index '{index_name}'")
    return index_name


def create_knowledge_base(bedrock_agent, role_arn, collection_id, index_name, region, name):
    collection_arn = f"arn:aws:aoss:{region}:{boto3.client('sts').get_caller_identity()['Account']}:collection/{collection_id}"

    kb = bedrock_agent.create_knowledge_base(
        name=name,
        roleArn=role_arn,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": EMBED_MODEL_ARN_TEMPLATE.format(region=region),
            },
        },
        storageConfiguration={
            "type": "OPENSEARCH_SERVERLESS",
            "opensearchServerlessConfiguration": {
                "collectionArn": collection_arn,
                "vectorIndexName": index_name,
                "fieldMapping": {
                    "vectorField": "vector",
                    "textField": "text",
                    "metadataField": "metadata",
                },
            },
        },
    )
    kb_id = kb["knowledgeBase"]["knowledgeBaseId"]
    print(f"Knowledge Base created: {kb_id}")
    return kb_id


def create_data_source_and_ingest(bedrock_agent, kb_id, bucket, region):
    ds = bedrock_agent.create_data_source(
        knowledgeBaseId=kb_id,
        name="scheme-docs-s3",
        dataSourceConfiguration={
            "type": "S3",
            "s3Configuration": {
                "bucketArn": f"arn:aws:s3:::{bucket}",
                "inclusionPrefixes": ["schemes/"],
            },
        },
    )
    ds_id = ds["dataSource"]["dataSourceId"]
    print(f"Data source created: {ds_id}")

    job = bedrock_agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
    job_id = job["ingestionJob"]["ingestionJobId"]
    print(f"Ingestion job started: {job_id} — this embeds & indexes every scheme doc.")

    while True:
        status = bedrock_agent.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]["status"]
        print(f"  ingestion status: {status}")
        if status in ("COMPLETE", "FAILED"):
            break
        time.sleep(15)

    return ds_id


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bucket", required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--account-id", required=True)
    p.add_argument("--kb-name", default="agri-scheme-kb")
    args = p.parse_args()

    iam = boto3.client("iam")
    aoss = boto3.client("opensearchserverless", region_name=args.region)
    bedrock_agent = boto3.client("bedrock-agent", region_name=args.region)

    collection_name = "agri-scheme-vectors"

    role_arn, _ = create_iam_role(iam, args.account_id, args.bucket, args.region)
    collection_id, collection_endpoint = create_oss_collection(
        aoss, args.account_id, role_arn, args.region, collection_name
    )
    index_name = create_vector_index(collection_endpoint, args.region)

    print("Waiting 30s for index/permissions propagation before creating the KB...")
    time.sleep(30)

    kb_id = create_knowledge_base(bedrock_agent, role_arn, collection_id, index_name, args.region, args.kb_name)
    create_data_source_and_ingest(bedrock_agent, kb_id, args.bucket, args.region)

    print("\n=== DONE ===")
    print(f"KNOWLEDGE_BASE_ID={kb_id}")
    print("Save this ID — you'll pass it to the Strands `retrieve` tool.")


if __name__ == "__main__":
    main()