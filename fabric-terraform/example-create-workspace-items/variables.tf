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
  default     = ""
}

variable "warehouse_name" {
  type        = string
}

variable "lakehouse_name" {
  type        = string
}

variable "notebook_folder_name" {
  type        = string
}

variable "notebook_1_name" {
  type        = string
}

