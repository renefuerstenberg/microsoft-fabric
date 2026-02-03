terraform {
  backend "azurerm" {
    resource_group_name   = "RG-NAME"
    storage_account_name  = "storageaccountname"
    container_name        = "fabricstate"
    key                   = "terraform.fabricstate"
  }
}
