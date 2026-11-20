import os
import sys
import boto3
import botocore.exceptions

def main():
    region = os.environ.get("AWS_REGION", "eu-north-1")
    project = os.environ.get("PROJECT_NAME", "eks-store")
    env = os.environ.get("ENVIRONMENT", "lab")
    state_bucket = os.environ.get("STATE_BUCKET")

    print(f"Checking pre-flight state for {project}-{env} in region {region}...")
    s3 = boto3.client("s3", region_name=region)
    ec2 = boto3.client("ec2", region_name=region)
    rds = boto3.client("rds", region_name=region)

    # 1. Check if network state already exists in remote S3 backend
    state_exists = False
    if state_bucket:
        try:
            s3.head_object(Bucket=state_bucket, Key="stacks/network/terraform.tfstate")
            state_exists = True
            print(f"Network state exists in s3://{state_bucket}/stacks/network/terraform.tfstate. Skipping cleanup.")
            return
        except botocore.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") in ["404", "NoSuchKey"]:
                print(f"No existing network state in s3://{state_bucket}/stacks/network/terraform.tfstate.")
            else:
                print(f"S3 state check note: {e}")

    print("Network remote state does not exist yet. Cleaning up any orphaned untracked remnants from previous failed runs...")

    # A. Delete unattached/orphaned RDS DB Subnet Group
    subnet_group_name = f"{project}-rds-subnet-group-{env}"
    try:
        rds.delete_db_subnet_group(DBSubnetGroupName=subnet_group_name)
        print(f"Cleaned up orphaned DB Subnet Group: {subnet_group_name}")
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ["DBSubnetGroupNotFoundFault", "DBSubnetGroupNotFound"]:
            print(f"DB Subnet Group {subnet_group_name} does not exist (OK).")
        elif "InvalidDBSubnetGroupStateFault" in code:
            print(f"DB Subnet Group {subnet_group_name} is actively used by a DB instance. Keeping it.")
        else:
            print(f"Note on DB Subnet Group {subnet_group_name}: {e}")

    # B. Clean up orphaned VPCs with tag Name = f"{project}-vpc-{env}"
    vpc_tag = f"{project}-vpc-{env}"
    try:
        vpcs_resp = ec2.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": [vpc_tag]}])
        vpcs = vpcs_resp.get("Vpcs", [])
        if not vpcs:
            print(f"No orphaned VPCs found matching {vpc_tag}. Ready for apply.")
            return

        for v in vpcs:
            vpc_id = v["VpcId"]
            print(f"Processing orphaned VPC {vpc_id}...")

            # 1. NAT Gateways
            nats = ec2.describe_nat_gateways(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["NatGateways"]
            active_nats = [n for n in nats if n["State"] not in ["deleted", "deleting"]]
            for n in active_nats:
                nat_id = n["NatGatewayId"]
                print(f"  Deleting NAT Gateway {nat_id}...")
                ec2.delete_nat_gateway(NatGatewayId=nat_id)

            if active_nats:
                print("  Waiting for NAT Gateways to finish deleting...")
                waiter = ec2.get_waiter("nat_gateway_deleted")
                waiter.wait(
                    NatGatewayIds=[n["NatGatewayId"] for n in active_nats],
                    WaiterConfig={"Delay": 15, "MaxAttempts": 30}
                )
                for n in active_nats:
                    for addr in n.get("NatGatewayAddresses", []):
                        alloc_id = addr.get("AllocationId")
                        if alloc_id:
                            try:
                                ec2.release_address(AllocationId=alloc_id)
                                print(f"  Released EIP {alloc_id}")
                            except Exception as err:
                                print(f"  Note releasing EIP {alloc_id}: {err}")

            # 2. VPC Endpoints
            vpces = ec2.describe_vpc_endpoints(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["VpcEndpoints"]
            vpce_ids = [vpce["VpcEndpointId"] for vpce in vpces]
            if vpce_ids:
                print(f"  Deleting VPC endpoints: {vpce_ids}...")
                ec2.delete_vpc_endpoints(VpcEndpointIds=vpce_ids)

            # 3. Internet Gateways
            igws = ec2.describe_internet_gateways(Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}])["InternetGateways"]
            for igw in igws:
                igw_id = igw["InternetGatewayId"]
                print(f"  Detaching and deleting IGW {igw_id}...")
                try:
                    ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
                    ec2.delete_internet_gateway(InternetGatewayId=igw_id)
                except Exception as err:
                    print(f"  Note on IGW {igw_id}: {err}")

            # 4. Route Tables
            rtbs = ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["RouteTables"]
            for rtb in rtbs:
                is_main = any(assoc.get("Main", False) for assoc in rtb.get("Associations", []))
                if not is_main:
                    rtb_id = rtb["RouteTableId"]
                    for assoc in rtb.get("Associations", []):
                        assoc_id = assoc.get("RouteTableAssociationId")
                        if assoc_id and not assoc.get("Main", False):
                            try:
                                ec2.disassociate_route_table(AssociationId=assoc_id)
                            except Exception:
                                pass
                    try:
                        ec2.delete_route_table(RouteTableId=rtb_id)
                        print(f"  Deleted route table {rtb_id}")
                    except Exception as err:
                        print(f"  Note on route table {rtb_id}: {err}")

            # 5. Security Groups
            sgs = ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["SecurityGroups"]
            for sg in sgs:
                if sg["GroupName"] != "default":
                    sg_id = sg["GroupId"]
                    if sg.get("IpPermissions"):
                        try:
                            ec2.revoke_security_group_ingress(GroupId=sg_id, IpPermissions=sg["IpPermissions"])
                        except Exception:
                            pass
                    if sg.get("IpPermissionsEgress"):
                        try:
                            ec2.revoke_security_group_egress(GroupId=sg_id, IpPermissions=sg["IpPermissionsEgress"])
                        except Exception:
                            pass
            for sg in sgs:
                if sg["GroupName"] != "default":
                    sg_id = sg["GroupId"]
                    try:
                        ec2.delete_security_group(GroupId=sg_id)
                        print(f"  Deleted security group {sg_id}")
                    except Exception as err:
                        print(f"  Note on security group {sg_id}: {err}")

            # 6. Subnets
            subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])["Subnets"]
            for sn in subnets:
                sn_id = sn["SubnetId"]
                try:
                    ec2.delete_subnet(SubnetId=sn_id)
                    print(f"  Deleted subnet {sn_id}")
                except Exception as err:
                    print(f"  Note on subnet {sn_id}: {err}")

            # 7. Delete VPC
            try:
                ec2.delete_vpc(VpcId=vpc_id)
                print(f"Successfully removed orphaned VPC: {vpc_id}")
            except Exception as err:
                print(f"Note on VPC {vpc_id}: {err}")

    except Exception as err:
        print(f"Pre-flight cleanup error (ignoring to continue apply): {err}")

if __name__ == "__main__":
    main()
