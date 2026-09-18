"""
Cleanup: removes partially-created resources from earlier failed/partial
runs of the KB creation script, so you can rerun it clean.

Deletes, in dependency-safe order:
  1. Bedrock Knowledge Base (and its data source) named --kb-name
  2. OpenSearch Serverless collection named --collection-name
  3. OSS security policies (encryption + network) and access policy
     matching --collection-name
  4. IAM roles matching the AgriSchemeKBRole- prefix (inline policies
     detached first)

Safe to run even if some resources don't exist yet — it just skips them.

Usage:
    python 04_cleanup.py --region us-east-1 --collection-name agri-scheme-vectors --kb-name agri-scheme-kb
"""

import argparse

import boto3
from botocore.exceptions import ClientError


def say(msg):
    print(f"[cleanup] {msg}")


def delete_knowledge_base(bedrock_agent, kb_name):
    try:
        paginator = bedrock_agent.get_paginator("list_knowledge_bases")
        for page in paginator.paginate():
            for kb in page["knowledgeBaseSummaries"]:
                if kb["name"] == kb_name:
                    kb_id = kb["knowledgeBaseId"]
                    # delete data sources first
                    ds_resp = bedrock_agent.list_data_sources(knowledgeBaseId=kb_id)
                    for ds in ds_resp.get("dataSourceSummaries", []):
                        say(f"Deleting data source {ds['dataSourceId']}...")
                        bedrock_agent.delete_data_source(
                            knowledgeBaseId=kb_id, dataSourceId=ds["dataSourceId"]
                        )
                    say(f"Deleting knowledge base {kb_id}...")
                    bedrock_agent.delete_knowledge_base(knowledgeBaseId=kb_id)
                    say("  done.")
                    return
        say(f"No knowledge base named '{kb_name}' found — skipping.")
    except ClientError as e:
        say(f"Error deleting knowledge base (may not have bedrock-agent access): {e}")


def delete_oss_collection(aoss, collection_name):
    try:
        resp = aoss.batch_get_collection(names=[collection_name])
        details = resp.get("collectionDetails", [])
        if not details:
            say(f"No collection named '{collection_name}' found — skipping.")
            return
        collection_id = details[0]["id"]
        say(f"Deleting collection {collection_name} ({collection_id})...")
        aoss.delete_collection(id=collection_id)
        say("  done (deletion happens async, may take a minute to fully clear).")
    except ClientError as e:
        say(f"Error deleting collection: {e}")


def delete_oss_policies(aoss, collection_name):
    for policy_type, suffix in [("encryption", "-enc"), ("network", "-net")]:
        name = f"{collection_name}{suffix}"
        try:
            aoss.delete_security_policy(name=name, type=policy_type)
            say(f"Deleted {policy_type} security policy '{name}'")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("ResourceNotFoundException",):
                say(f"No {policy_type} policy named '{name}' — skipping.")
            else:
                say(f"Error deleting {policy_type} policy '{name}': {e}")

    access_name = f"{collection_name}-access"
    try:
        aoss.delete_access_policy(name=access_name, type="data")
        say(f"Deleted data access policy '{access_name}'")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("ResourceNotFoundException",):
            say(f"No data access policy named '{access_name}' — skipping.")
        else:
            say(f"Error deleting access policy '{access_name}': {e}")


def delete_iam_roles(iam, role_prefix="AgriSchemeKBRole"):
    paginator = iam.get_paginator("list_roles")
    matched = []
    for page in paginator.paginate():
        for r in page["Roles"]:
            if r["RoleName"].startswith(role_prefix):
                matched.append(r["RoleName"])

    if not matched:
        say(f"No IAM roles matching prefix '{role_prefix}' found — skipping.")
        return

    for role_name in matched:
        say(f"Deleting IAM role {role_name}...")
        # detach/delete inline policies first
        inline = iam.list_role_policies(RoleName=role_name)["PolicyNames"]
        for pname in inline:
            iam.delete_role_policy(RoleName=role_name, PolicyName=pname)
            say(f"  removed inline policy {pname}")
        # detach managed policies too, just in case
        attached = iam.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]
        for pol in attached:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=pol["PolicyArn"])
            say(f"  detached managed policy {pol['PolicyName']}")
        iam.delete_role(RoleName=role_name)
        say("  role deleted.")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--region", required=True)
    p.add_argument("--collection-name", default="agri-scheme-vectors")
    p.add_argument("--kb-name", default="agri-scheme-kb")
    p.add_argument("--role-prefix", default="AgriSchemeKBRole")
    args = p.parse_args()

    iam = boto3.client("iam")
    aoss = boto3.client("opensearchserverless", region_name=args.region)
    bedrock_agent = boto3.client("bedrock-agent", region_name=args.region)

    say("=== Deleting Knowledge Base ===")
    delete_knowledge_base(bedrock_agent, args.kb_name)

    say("\n=== Deleting OSS collection ===")
    delete_oss_collection(aoss, args.collection_name)

    say("\n=== Deleting OSS policies ===")
    delete_oss_policies(aoss, args.collection_name)

    say("\n=== Deleting IAM roles ===")
    delete_iam_roles(iam, args.role_prefix)

    say("\n=== CLEANUP COMPLETE ===")
    say("Wait ~30s for deletions to propagate before rerunning the create script.")


if __name__ == "__main__":
    main()