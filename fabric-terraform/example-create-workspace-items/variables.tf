variable "workspace_name" {
    description = "The name of the Fabric workspace where items will be created."
    type        = string
  
}

variable "capacity_name" {  
    description = "The name of the Fabric capacity associated with the workspace."
    type        = string
  
}

variable "subscription_id" {
  type        = string
  description = "Subscription ID used for Deployment"
  default     = "Subscription ID here"
}

variable "warehouse_name" {
  type        = string
}

variable "lakehouse_name_bronze" {
  type        = string
}

variable "lakehouse_name_silver" {
    type        = string
}

variable "lakehouse_name_gold" {
  type        = string
}


variable "notebook_folder_name" {
  type        = string
}

variable "notebook_1_name" {
  type        = string
}

variable "pipelines_folder_name" {
  type        = string
}


variable "variables_folder_name" {
  type        = string
}

variable "user_data_functions_folder_name" {
  type        = string
}

variable "power_bi_reports_folder_name" {
  type        = string
}