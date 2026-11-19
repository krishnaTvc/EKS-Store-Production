terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Stack       = "network"
    }
  }
}

# 1. VPC Definition
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc-${var.environment}"
  }
}

# 2. Subnets (2 AZs for High Availability)
# Public Subnets: for ALB and NAT Gateway
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name                                        = "${var.project_name}-public-${var.availability_zones[count.index]}"
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

# Private Application Subnets: for EKS Managed Nodes & Pods
resource "aws_subnet" "private_app" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 2)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name                                        = "${var.project_name}-private-app-${var.availability_zones[count.index]}"
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

# Isolated Database Subnets: for RDS PostgreSQL (No Internet Access)
resource "aws_subnet" "isolated_db" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.project_name}-isolated-db-${var.availability_zones[count.index]}"
  }
}

# 3. Internet Gateway
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw-${var.environment}"
  }
}

# 4. NAT Gateway & Elastic IP (Optional toggle for cost pauses)
resource "aws_eip" "nat" {
  count  = var.enable_nat_gateway ? 1 : 0
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-nat-eip-${var.environment}"
  }
}

resource "aws_nat_gateway" "nat" {
  count         = var.enable_nat_gateway ? 1 : 0
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "${var.project_name}-nat-${var.environment}"
  }

  depends_on = [aws_internet_gateway.igw]
}

# 5. Routing Tables
# Public Route Table -> IGW
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = {
    Name = "${var.project_name}-rt-public-${var.environment}"
  }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private App Route Table -> NAT Gateway (when enabled)
resource "aws_route_table" "private_app" {
  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.nat[0].id
    }
  }

  tags = {
    Name = "${var.project_name}-rt-private-app-${var.environment}"
  }
}

resource "aws_route_table_association" "private_app" {
  count          = length(aws_subnet.private_app)
  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private_app.id
}

# Isolated DB Route Table: strictly local routing only (no default route!)
resource "aws_route_table" "isolated_db" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-rt-isolated-db-${var.environment}"
  }
}

resource "aws_route_table_association" "isolated_db" {
  count          = length(aws_subnet.isolated_db)
  subnet_id      = aws_subnet.isolated_db[count.index].id
  route_table_id = aws_route_table.isolated_db.id
}

# 6. S3 VPC Gateway Endpoint (Zero Cost Private Access for EKS Pods & Importer)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private_app.id]

  tags = {
    Name = "${var.project_name}-vpce-s3-${var.environment}"
  }
}

# 7. Core Security Group Boundaries
# Public Application Load Balancer (ALB) Security Group
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg-${var.environment}"
  description = "Allows inbound HTTPS and HTTP traffic to public ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from Internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from Internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound to VPC and services"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg-${var.environment}"
  }
}

# EKS Worker Nodes Security Group
resource "aws_security_group" "eks_nodes" {
  name        = "${var.project_name}-eks-nodes-sg-${var.environment}"
  description = "Security group for EKS worker nodes and pods"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Traffic from ALB to NodePort and Pod ports"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "Inter-node cluster communication"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    description = "Allow all outbound from nodes"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name                                        = "${var.project_name}-eks-nodes-sg-${var.environment}"
    "kubernetes.io/cluster/${var.cluster_name}" = "owned"
  }
}

# RDS PostgreSQL Security Group: Strictly port 5432 from EKS Nodes
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg-${var.environment}"
  description = "Controls database access; allows port 5432 exclusively from EKS nodes"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL port 5432 from EKS nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    description = "No arbitrary outbound from isolated database"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  tags = {
    Name = "${var.project_name}-rds-sg-${var.environment}"
  }
}

# 8. RDS Subnet Group (for private DB placement)
resource "aws_db_subnet_group" "rds" {
  name        = "${var.project_name}-rds-subnet-group-${var.environment}"
  description = "Subnet group for private RDS PostgreSQL instance"
  subnet_ids  = aws_subnet.isolated_db[*].id

  tags = {
    Name = "${var.project_name}-rds-subnet-group-${var.environment}"
  }
}
