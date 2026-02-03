# We strongly recommend using the required_providers block to set the Fabric Provider source and version being used
terraform {
  required_version = ">= 1.8, < 2.0"

  required_providers {
    fabric = {
      source  = "microsoft/fabric"
      version = "1.7.0"
    }

    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.0.0"
    }
  }
}

# Configure the Microsoft Fabric Terraform Provider
provider "fabric" {
  use_cli = true
  preview = true
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}
