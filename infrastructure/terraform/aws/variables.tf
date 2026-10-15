variable "aws_region" {
  type        = string
  description = "AWS region for the staging environment."
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC containing the EKS and data subnets."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "At least two private subnets in distinct availability zones."
  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "Provide at least two private subnets."
  }
}

variable "cluster_endpoint_public_access_cidrs" {
  type        = list(string)
  description = "Explicit administrator CIDRs permitted to reach the public EKS endpoint."
  validation {
    condition     = length(var.cluster_endpoint_public_access_cidrs) > 0 && !contains(var.cluster_endpoint_public_access_cidrs, "0.0.0.0/0")
    error_message = "Provide bounded administrator CIDRs; 0.0.0.0/0 is rejected."
  }
}

variable "project_name" {
  type    = string
  default = "verifyops"
}

variable "environment" {
  type    = string
  default = "staging"
}

variable "eks_version" {
  type        = string
  default     = "1.34"
  description = "Version supported by the selected AWS region at apply time."
}

variable "node_instance_types" {
  type    = list(string)
  default = ["m7i.large"]
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 5
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "postgres_engine_version" {
  type    = string
  default = "17.6"
}

variable "postgres_instance_class" {
  type    = string
  default = "db.t4g.small"
}

variable "postgres_multi_az" {
  type    = bool
  default = false
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "monthly_budget_usd" {
  type    = number
  default = 150
}

variable "budget_alert_email" {
  type        = string
  description = "Email receiving an AWS budget alert."
}
