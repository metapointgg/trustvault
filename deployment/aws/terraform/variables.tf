variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "name_prefix" {
  type    = string
  default = "trustvault"
}

variable "source_imports_bucket" {
  type = string
}

variable "fits_containers_bucket" {
  type = string
}

variable "derived_reports_bucket" {
  type = string
}
