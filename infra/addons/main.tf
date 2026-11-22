terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Stack       = "addons"
    }
  }
}

data "aws_caller_identity" "current" {}

data "aws_eks_cluster" "cluster" {
  count = (var.cluster_endpoint == "" || var.cluster_certificate_authority_data == "" || var.oidc_provider_url == "") ? 1 : 0
  name  = var.cluster_name
}

data "aws_vpc" "main" {
  count = var.vpc_id == "" ? 1 : 0
  tags = {
    Name = "${var.project_name}-vpc-${var.environment}"
  }
}

locals {
  resolved_cluster_endpoint = var.cluster_endpoint != "" ? var.cluster_endpoint : (length(data.aws_eks_cluster.cluster) > 0 ? data.aws_eks_cluster.cluster[0].endpoint : "https://dummy.eks.amazonaws.com")
  resolved_cluster_ca       = var.cluster_certificate_authority_data != "" ? var.cluster_certificate_authority_data : (length(data.aws_eks_cluster.cluster) > 0 ? data.aws_eks_cluster.cluster[0].certificate_authority[0].data : "ZHVtbXk=")
  resolved_oidc_url         = var.oidc_provider_url != "" ? var.oidc_provider_url : (length(data.aws_eks_cluster.cluster) > 0 ? data.aws_eks_cluster.cluster[0].identity[0].oidc[0].issuer : "https://oidc.eks.eu-north-1.amazonaws.com/id/DUMMY")
  resolved_oidc_arn         = var.oidc_provider_arn != "" ? var.oidc_provider_arn : "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/${replace(local.resolved_oidc_url, "https://", "")}"
  resolved_vpc_id           = var.vpc_id != "" ? var.vpc_id : (length(data.aws_vpc.main) > 0 ? data.aws_vpc.main[0].id : "")
}

provider "kubernetes" {
  host                   = local.resolved_cluster_endpoint
  cluster_ca_certificate = base64decode(local.resolved_cluster_ca)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", var.cluster_name, "--region", var.aws_region]
    command     = "aws"
  }
}

provider "helm" {
  kubernetes {
    host                   = local.resolved_cluster_endpoint
    cluster_ca_certificate = base64decode(local.resolved_cluster_ca)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", var.cluster_name, "--region", var.aws_region]
      command     = "aws"
    }
  }
}

# 1. AWS Managed Core EKS Addons
resource "aws_eks_addon" "vpc_cni" {
  cluster_name = var.cluster_name
  addon_name   = "vpc-cni"
}

resource "aws_eks_addon" "coredns" {
  cluster_name = var.cluster_name
  addon_name   = "coredns"
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name = var.cluster_name
  addon_name   = "kube-proxy"
}

# 2. AWS Load Balancer Controller IAM Role (IRSA)
resource "aws_iam_role" "aws_load_balancer_controller" {
  name = "${var.project_name}-alb-controller-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = local.resolved_oidc_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(local.resolved_oidc_url, "https://", "")}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "aws_load_balancer_controller" {
  name        = "${var.project_name}-alb-controller-policy-${var.environment}"
  description = "Permissions for AWS Load Balancer Controller to manage ALBs and Target Groups"

  policy = file("${path.module}/iam_alb_policy.json")
}

resource "aws_iam_role_policy_attachment" "aws_load_balancer_controller" {
  role       = aws_iam_role.aws_load_balancer_controller.name
  policy_arn = aws_iam_policy.aws_load_balancer_controller.arn
}

# 3. AWS Load Balancer Controller Helm Release
resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = "1.8.2"

  set {
    name  = "clusterName"
    value = var.cluster_name
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = aws_iam_role.aws_load_balancer_controller.arn
  }

  set {
    name  = "region"
    value = var.aws_region
  }

  set {
    name  = "vpcId"
    value = local.resolved_vpc_id
  }

  depends_on = [
    aws_iam_role_policy_attachment.aws_load_balancer_controller
  ]
}

# 4. Kubernetes Metrics Server Helm Release (Enables HPA & kubectl top)
resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  namespace  = "kube-system"
  version    = "3.12.2"

  set {
    name  = "args[0]"
    value = "--kubelet-preferred-address-types=InternalIP"
  }
}

# 5. Secrets Store CSI Driver & AWS Secrets Manager Provider (ASCP)
resource "helm_release" "secrets_store_csi_driver" {
  name       = "secrets-store-csi-driver"
  repository = "https://kubernetes-sigs.github.io/secrets-store-csi-driver/charts"
  chart      = "secrets-store-csi-driver"
  namespace  = "kube-system"
  version    = "1.4.6"

  set {
    name  = "syncSecret.enabled"
    value = "true"
  }

  set {
    name  = "enableSecretRotation"
    value = "true"
  }

  set {
    name  = "tokenRequests[0].audience"
    value = "sts.amazonaws.com"
  }
}

resource "helm_release" "aws_secrets_manager_provider" {
  name       = "aws-secrets-manager-provider"
  repository = "https://aws.github.io/secrets-store-csi-driver-provider-aws"
  chart      = "secrets-store-csi-driver-provider-aws"
  namespace  = "kube-system"

  set {
    name  = "secrets-store-csi-driver.install"
    value = "false"
  }

  depends_on = [helm_release.secrets_store_csi_driver]
}
